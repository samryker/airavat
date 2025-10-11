from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import json

from firebase_admin import firestore

try:  # LLM integration - Use both Gemini and HF models
    import requests
    import os
    from typing import Dict, Any
    
    class _HybridLLM:
        def __init__(self):
            self.base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            
        async def ainvoke(self, prompt: str) -> "AIMessage":
            try:
                # Use the optimized Gemini endpoint for primary analysis
                gemini_response = requests.post(
                    f"{self.base_url}/gemini/suggest",
                    json={
                        "patient_id": "digital_twin_service",
                        "query_text": prompt,
                        "symptoms": [],
                        "medical_history": [],
                        "current_medications": []
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                gemini_text = ""
                if gemini_response.status_code == 200:
                    gemini_data = gemini_response.json()
                    gemini_text = gemini_data.get("text", "")
                
                # Use HF model for genetic/biomarker analysis if relevant
                hf_analysis = ""
                if any(keyword in prompt.lower() for keyword in ['genetic', 'biomarker', 'dna', 'gene', 'mutation', 'variant']):
                    try:
                        hf_response = requests.post(
                            f"{self.base_url}/genetic/analyze",
                            json={"text": prompt},
                            headers={"Content-Type": "application/json"},
                            timeout=20
                        )
                        
                        if hf_response.status_code == 200:
                            hf_data = hf_response.json()
                            if "analysis" in hf_data:
                                hf_analysis = f"\n\nGenetic Analysis: {str(hf_data['analysis'])[:200]}..."
                    except Exception as e:
                        print(f"HF analysis failed: {e}")
                
                # Combine both analyses
                combined_response = gemini_text
                if hf_analysis:
                    combined_response += hf_analysis
                
                return AIMessage(combined_response if combined_response else "Analysis temporarily unavailable")
                    
            except Exception as e:
                print(f"Error calling hybrid LLM service: {e}")
                return AIMessage("LLM service temporarily unavailable")
    
    class AIMessage:
        def __init__(self, content: str):
            self.content = content
    
    _llm = _HybridLLM()
    
except Exception:  # Fallback dummy model when LLM not available
    class AIMessage:  # minimal stand-in
        def __init__(self, content: str):
            self.content = content

    class _DummyLLM:
        async def ainvoke(self, prompt: str) -> AIMessage:
            return AIMessage("LLM service unavailable")

    _llm = _DummyLLM()


# =============================================================================
# AUTONOMOUS DIGITAL TWIN AGENT
# =============================================================================

class AutonomousDigitalTwinAgent:
    """
    Autonomous agent for Digital Twin analysis
    Flow: File Upload → HF Model → Context Tokenizer → Gemini Analysis
    """
    
    def __init__(self):
        self.base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self.hf_model = "OpenMed/OpenMed-NER-GenomeDetect-SuperClinical-434M"
    
    async def analyze_lab_report(
        self, 
        patient_id: str, 
        file_content: bytes, 
        filename: str
    ) -> Dict[str, Any]:
        """
        Autonomous agent workflow:
        1. Upload to HF model for initial analysis
        2. Apply context tokenization to reduce size
        3. Feed to Gemini for comprehensive medical analysis
        4. Return structured response with confidence, inferences, and recommendations
        """
        
        try:
            # Step 1: HF Model Analysis
            print(f"🔬 Step 1: Analyzing file with HF model...")
            hf_analysis = await self._analyze_with_hf(file_content, filename)
            
            # Step 2: Context Tokenization
            print(f"📊 Step 2: Tokenizing and compressing context...")
            tokenized_context = await self._tokenize_context(hf_analysis)
            
            # Step 3: Gemini Comprehensive Analysis
            print(f"🤖 Step 3: Performing Gemini analysis...")
            gemini_response = await self._analyze_with_gemini(
                patient_id, 
                tokenized_context, 
                filename
            )
            
            # Step 4: Structure response
            structured_response = {
                "success": True,
                "patient_id": patient_id,
                "filename": filename,
                "hf_analysis": hf_analysis,
                "tokenized_context": tokenized_context,
                "gemini_analysis": gemini_response,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "processing_steps": {
                    "hf_completed": True,
                    "tokenization_completed": True,
                    "gemini_completed": True
                }
            }
            
            return structured_response
            
        except Exception as e:
            print(f"❌ Error in autonomous agent workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "patient_id": patient_id,
                "filename": filename
            }
    
    async def _analyze_with_hf(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Step 1: Analyze file with HF model"""
        try:
            # Convert bytes to text
            text_content = file_content.decode('utf-8', errors='ignore')
            
            # Call HF genetic analysis endpoint
            response = requests.post(
                f"{self.base_url}/genetic/analyze",
                json={"text": text_content[:2000]},  # Limit input size
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                hf_data = response.json()
                return {
                    "status": "success",
                    "analysis": hf_data.get("analysis", {}),
                    "entities_found": len(hf_data.get("analysis", {}).get("genetic_markers", [])),
                    "raw_text_length": len(text_content)
                }
            else:
                return {
                    "status": "partial",
                    "error": f"HF API returned {response.status_code}",
                    "raw_text": text_content[:500]  # Fallback: use raw text
                }
                
        except Exception as e:
            print(f"HF analysis error: {e}")
            # Fallback: return raw text for Gemini
            try:
                text_content = file_content.decode('utf-8', errors='ignore')
                return {
                    "status": "fallback",
                    "error": str(e),
                    "raw_text": text_content[:1000]
                }
            except:
                return {
                    "status": "failed",
                    "error": str(e)
                }
    
    async def _tokenize_context(self, hf_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Step 2: Tokenize and compress context for efficient Gemini processing"""
        
        def count_tokens(text: str) -> int:
            """Estimate token count"""
            return max(1, len(text) // 3.5)
        
        def compress_text(text: str, max_tokens: int = 500) -> str:
            """Compress text to fit within token budget"""
            current_tokens = count_tokens(text)
            if current_tokens <= max_tokens:
                return text
            
            # Calculate compression ratio
            target_length = int(len(text) * (max_tokens / current_tokens))
            return text[:target_length] + "..."
        
        try:
            # Extract key information from HF analysis
            if hf_analysis.get("status") == "success":
                analysis = hf_analysis.get("analysis", {})
                
                # Compress each section
                compressed = {
                    "genetic_markers": analysis.get("genetic_markers", [])[:10],  # Top 10
                    "genes_analyzed": analysis.get("genes_analyzed", [])[:10],
                    "clinical_significance": analysis.get("clinical_significance", [])[:5],
                    "summary": compress_text(str(analysis), max_tokens=300)
                }
                
                compressed_str = json.dumps(compressed, separators=(',', ':'))
                
            else:
                # Fallback: compress raw text
                raw_text = hf_analysis.get("raw_text", "")
                compressed_str = compress_text(raw_text, max_tokens=500)
            
            token_count = count_tokens(compressed_str)
            
            return {
                "compressed_data": compressed_str,
                "token_count": token_count,
                "original_size": hf_analysis.get("raw_text_length", 0),
                "compression_ratio": f"{(token_count / max(hf_analysis.get('raw_text_length', 1000), 1)) * 100:.1f}%"
            }
            
        except Exception as e:
            print(f"Tokenization error: {e}")
            return {
                "compressed_data": str(hf_analysis)[:500],
                "token_count": 150,
                "error": str(e)
            }
    
    async def _analyze_with_gemini(
        self, 
        patient_id: str, 
        tokenized_context: Dict[str, Any],
        filename: str
    ) -> Dict[str, Any]:
        """Step 3: Comprehensive Gemini analysis with structured output"""
        
        try:
            # Create comprehensive medical analysis prompt
            prompt = f"""
You are an advanced medical AI analyzing a patient's lab report. Provide a comprehensive, structured analysis.

Patient ID: {patient_id}
Report File: {filename}

Lab Report Data (Pre-analyzed and compressed):
{tokenized_context.get('compressed_data', '')}

Please provide a detailed medical analysis with the following structure:

1. PRIMARY ANALYSIS:
   - Key findings from the lab report
   - Notable biomarkers or genetic markers identified
   - Any abnormal values or concerning patterns

2. CONFIDENCE ASSESSMENT:
   - Overall confidence score (0-100%)
   - Reliability of the data
   - Areas requiring further investigation

3. MEDICAL INFERENCES:
   - What the data suggests about the patient's health
   - Potential health risks or conditions indicated
   - Positive health indicators
   - Correlations between different markers

4. PROACTIVE RECOMMENDATIONS:
   - Immediate actions the patient should take
   - Lifestyle modifications suggested
   - Additional tests recommended
   - Follow-up timeline
   - Preventive measures

5. SEVERITY ASSESSMENT:
   - Overall health status: [Critical/Concerning/Moderate/Good/Excellent]
   - Priority level for medical attention: [Urgent/High/Medium/Low]

Provide your response in a clear, structured format that a patient can understand while maintaining medical accuracy.
"""
            
            # Call Gemini suggest endpoint
            response = requests.post(
                f"{self.base_url}/gemini/suggest",
                json={
                    "patient_id": patient_id,
                    "query_text": prompt,
                    "symptoms": [],
                    "medical_history": [],
                    "current_medications": []
                },
                headers={"Content-Type": "application/json"},
                timeout=45
            )
            
            if response.status_code == 200:
                gemini_data = response.json()
                text_response = gemini_data.get("text", "")
                
                # Parse the response to extract structured information
                parsed_response = self._parse_gemini_response(text_response)
                
                return {
                    "status": "success",
                    "raw_response": text_response,
                    "parsed_analysis": parsed_response,
                    "confidence_score": parsed_response.get("confidence_score", 75),
                    "severity": parsed_response.get("severity", "Moderate"),
                    "priority": parsed_response.get("priority", "Medium")
                }
            else:
                return {
                    "status": "failed",
                    "error": f"Gemini API returned {response.status_code}",
                    "fallback_message": "Unable to complete analysis at this time"
                }
                
        except Exception as e:
            print(f"Gemini analysis error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "fallback_message": "Analysis service temporarily unavailable"
            }
    
    def _parse_gemini_response(self, text: str) -> Dict[str, Any]:
        """Parse Gemini response to extract structured information"""
        
        # Extract confidence score
        confidence_score = 75  # Default
        if "confidence" in text.lower():
            import re
            confidence_match = re.search(r'(\d+)%', text)
            if confidence_match:
                confidence_score = int(confidence_match.group(1))
        
        # Extract severity
        severity = "Moderate"
        severity_keywords = {
            "Critical": ["critical", "severe", "urgent", "emergency"],
            "Concerning": ["concerning", "worrying", "elevated risk"],
            "Moderate": ["moderate", "attention needed"],
            "Good": ["good", "normal", "healthy"],
            "Excellent": ["excellent", "optimal", "exceptional"]
        }
        
        text_lower = text.lower()
        for sev, keywords in severity_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                severity = sev
                break
        
        # Extract priority
        priority = "Medium"
        if any(word in text_lower for word in ["urgent", "immediate", "critical"]):
            priority = "Urgent"
        elif any(word in text_lower for word in ["high priority", "soon", "promptly"]):
            priority = "High"
        elif any(word in text_lower for word in ["low priority", "routine", "when convenient"]):
            priority = "Low"
        
        return {
            "confidence_score": confidence_score,
            "severity": severity,
            "priority": priority,
            "full_analysis": text,
            "sections": {
                "primary_analysis": self._extract_section(text, "PRIMARY ANALYSIS", "CONFIDENCE"),
                "confidence_assessment": self._extract_section(text, "CONFIDENCE", "MEDICAL INFERENCES"),
                "medical_inferences": self._extract_section(text, "MEDICAL INFERENCES", "PROACTIVE"),
                "proactive_recommendations": self._extract_section(text, "PROACTIVE", "SEVERITY"),
                "severity_assessment": self._extract_section(text, "SEVERITY", None)
            }
        }
    
    def _extract_section(self, text: str, start_marker: str, end_marker: Optional[str]) -> str:
        """Extract a section from the text between markers"""
        try:
            start_idx = text.find(start_marker)
            if start_idx == -1:
                return ""
            
            if end_marker:
                end_idx = text.find(end_marker, start_idx)
                if end_idx == -1:
                    return text[start_idx:].strip()
                return text[start_idx:end_idx].strip()
            else:
                return text[start_idx:].strip()
        except:
            return ""


# Initialize autonomous agent
_autonomous_agent = AutonomousDigitalTwinAgent()


_db_client: Optional[firestore.Client] = None


def _get_db() -> Optional[firestore.Client]:
    """Lazily acquire Firestore client after firebase_admin initialization."""
    global _db_client
    if _db_client is None:
        try:
            _db_client = firestore.client()
        except Exception:
            _db_client = None
    return _db_client

router = APIRouter(prefix="/digital_twin", tags=["Digital Twin"])


class DigitalTwinPayload(BaseModel):
    """Incoming payload for updating a digital twin."""
    height_cm: float
    weight_kg: float
    biomarkers: Optional[Dict[str, float]] = None


class DigitalTwinRecord(DigitalTwinPayload):
    """Stored representation of a digital twin."""
    patient_id: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)


_twin_store: Dict[str, DigitalTwinRecord] = {}


class TreatmentUpdatePayload(DigitalTwinPayload):
    """Payload containing real-time data and a report from chat assistant."""
    report: str


class TreatmentUpdateResponse(BaseModel):
    twin: DigitalTwinRecord
    inference: str
    stored: bool


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Simple health check for the digital twin service."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.put("/{patient_id}", response_model=DigitalTwinRecord)
async def upsert_twin(patient_id: str, payload: DigitalTwinPayload) -> DigitalTwinRecord:
    """Create or update a digital twin for the specified patient."""
    record = DigitalTwinRecord(patient_id=patient_id, **payload.model_dump())
    _twin_store[patient_id] = record
    # Persist for cross-instance availability
    try:
        db = _get_db()
        if db:
            db.collection("twin_customizations").document(patient_id).set({
                "userId": patient_id,
                "height_cm": record.height_cm,
                "weight_kg": record.weight_kg,
                "biomarkers": record.biomarkers or {},
                "lastUpdated": datetime.utcnow(),
            }, merge=True)
    except Exception:
        pass
    return record


@router.get("/{patient_id}", response_model=DigitalTwinRecord)
async def get_twin(patient_id: str) -> DigitalTwinRecord:
    """Retrieve the digital twin for a patient.
    Fallback order: in-memory -> Firestore twin_customizations -> default stub.
    """
    # 1) In-memory
    record = _twin_store.get(patient_id)
    if record:
        return record

    # 2) Firestore persistence
    db = _get_db()
    if db:
        try:
            doc = db.collection("twin_customizations").document(patient_id).get()
            if doc.exists:
                data = doc.to_dict() or {}
                height_cm = float(data.get("height_cm") or 170.0)
                weight_kg = float(data.get("weight_kg") or 70.0)
                biomarkers = data.get("biomarkers") or {}
                record = DigitalTwinRecord(
                    patient_id=patient_id,
                    height_cm=height_cm,
                    weight_kg=weight_kg,
                    biomarkers=biomarkers,
                )
                _twin_store[patient_id] = record
                return record
        except Exception:
            pass

    # 3) Default stub (avoid 404 to keep UI functional)
    record = DigitalTwinRecord(
        patient_id=patient_id,
        height_cm=170.0,
        weight_kg=70.0,
        biomarkers={},
    )
    _twin_store[patient_id] = record
    return record


@router.post("/{patient_id}/treatment", response_model=TreatmentUpdateResponse)
async def process_treatment(patient_id: str, payload: TreatmentUpdatePayload) -> TreatmentUpdateResponse:
    """Update twin, infer treatment via hybrid LLM (Gemini + HF), and store in Firestore."""
    record = DigitalTwinRecord(patient_id=patient_id, **payload.model_dump(exclude={"report"}))
    _twin_store[patient_id] = record

    # Create comprehensive prompt for hybrid analysis
    prompt = f"""
    Analyze this patient's digital twin data and provide comprehensive treatment insights:
    
    Patient Data:
    - Height: {payload.height_cm}cm
    - Weight: {payload.weight_kg}kg
    - BMI: {round(payload.weight_kg / ((payload.height_cm / 100) ** 2), 1)}
    - Biomarkers: {payload.biomarkers or {}}
    
    Report: {payload.report}
    
    Provide:
    1. Medical analysis and recommendations
    2. Lifestyle suggestions based on BMI and biomarkers
    3. Suggested tests if biomarkers indicate concerns
    4. Proactive health monitoring recommendations
    """
    
    result = await _llm.ainvoke(prompt)
    inference = getattr(result, "content", str(result))

    stored = False
    db = _get_db()
    if db:
        try:
            db.collection("updated_treatment").document(patient_id).set(
                {
                    "patient_id": patient_id,
                    "twin": record.model_dump(),
                    "report": payload.report,
                    "inference": inference,
                    "updated_at": datetime.utcnow(),
                    "analysis_type": "hybrid_gemini_hf"
                }
            )
            stored = True
        except Exception:
            stored = False

    return TreatmentUpdateResponse(twin=record, inference=inference, stored=stored)


@router.get("/{patient_id}/live", response_model=Dict[str, Any])
async def get_live_twin_data(patient_id: str) -> Dict[str, Any]:
    """Get complete live twin data combining SMPL model + biomarkers + AI insights."""
    try:
        # Get SMPL model data
        smpl_data = {}
        twin_record = _twin_store.get(patient_id)
        if twin_record:
            smpl_data = {
                "height_cm": twin_record.height_cm,
                "weight_kg": twin_record.weight_kg,
                "bmi": round(twin_record.weight_kg / ((twin_record.height_cm / 100) ** 2), 1),
                "biomarkers": twin_record.biomarkers or {}
            }
        
        # Get biomarkers from Firestore
        biomarkers = {}
        db = _get_db()
        if db:
            try:
                # Get from twin_customizations collection
                twin_doc = db.collection("twin_customizations").document(patient_id).get()
                if twin_doc.exists:
                    twin_data = twin_doc.to_dict()
                    biomarkers = twin_data.get("biomarkers", {})
                
                # Also check biomarkers collection
                biomarker_docs = db.collection("biomarkers").document(patient_id).collection("reports").order_by("timestamp", direction="desc").limit(1).get()
                for doc in biomarker_docs:
                    latest_biomarkers = doc.to_dict().get("biomarkers", {})
                    biomarkers.update(latest_biomarkers)
                    
            except Exception as e:
                print(f"Error fetching biomarkers: {e}")
        
        # Generate AI insights using hybrid model
        ai_insights = ""
        if biomarkers and smpl_data:
            prompt = f"""
            Analyze this patient's live digital twin data and provide comprehensive health insights:
            
            Physical Data:
            - Height: {smpl_data.get('height_cm', 'unknown')}cm
            - Weight: {smpl_data.get('weight_kg', 'unknown')}kg  
            - BMI: {smpl_data.get('bmi', 'unknown')}
            
            Biomarkers: {biomarkers}
            
            Provide:
            1. Key health insights based on physical and biomarker data
            2. Proactive recommendations for health monitoring
            3. Lifestyle suggestions based on BMI and biomarker patterns
            4. Any genetic or biomarker concerns that need attention
            """
            try:
                result = await _llm.ainvoke(prompt)
                ai_insights = getattr(result, "content", "AI insights temporarily unavailable")
            except Exception:
                ai_insights = "AI insights temporarily unavailable"
        
        return {
            "patient_id": patient_id,
            "smpl_data": smpl_data,
            "biomarkers": biomarkers,
            "ai_insights": ai_insights,
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "data_sources": {
                "smpl": bool(twin_record),
                "biomarkers": bool(biomarkers),
                "ai_insights": bool(ai_insights)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting live twin data: {str(e)}")


@router.post("/{patient_id}/biomarkers")
async def update_biomarkers(patient_id: str, biomarkers: Dict[str, Any]) -> Dict[str, Any]:
    """Update patient biomarkers for live twin visualization."""
    try:
        db = _get_db()
        if not db:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Store in biomarkers collection
        biomarker_data = {
            "biomarkers": biomarkers,
            "timestamp": datetime.utcnow(),
            "reportType": "live_update"
        }
        
        db.collection("biomarkers").document(patient_id).collection("reports").add(biomarker_data)
        
        # Also update twin_customizations for quick access
        db.collection("twin_customizations").document(patient_id).set({
            "userId": patient_id,
            "biomarkers": biomarkers,
            "lastUpdated": datetime.utcnow()
        }, merge=True)
        
        return {
            "status": "success",
            "message": "Biomarkers updated successfully",
            "patient_id": patient_id,
            "biomarker_count": len(biomarkers)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating biomarkers: {str(e)}")

@router.post("/{patient_id}/genetic-analysis")
async def analyze_genetic_data(patient_id: str, genetic_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze genetic data using both Gemini and HF models for digital twin."""
    try:
        # Create comprehensive genetic analysis prompt
        genetic_text = genetic_data.get("genetic_report", "")
        if not genetic_text:
            genetic_text = str(genetic_data)
        
        # Use hybrid LLM for genetic analysis
        prompt = f"""
        Perform comprehensive genetic analysis for this patient's digital twin:
        
        Patient ID: {patient_id}
        Genetic Data: {genetic_text}
        
        Provide:
        1. Genetic risk assessment
        2. Biomarker correlations with genetic variants
        3. Personalized health recommendations based on genetics
        4. Proactive monitoring suggestions for genetic predispositions
        """
        
        result = await _llm.ainvoke(prompt)
        analysis = getattr(result, "content", "Genetic analysis temporarily unavailable")
        
        # Store analysis in Firestore
        db = _get_db()
        if db:
            try:
                db.collection("genetic_analysis").document(patient_id).set({
                    "patient_id": patient_id,
                    "genetic_data": genetic_data,
                    "analysis": analysis,
                    "timestamp": datetime.utcnow(),
                    "analysis_type": "hybrid_gemini_hf"
                })
            except Exception as e:
                print(f"Error storing genetic analysis: {e}")
        
        return {
            "status": "success",
            "patient_id": patient_id,
            "genetic_analysis": analysis,
            "analysis_type": "hybrid_gemini_hf",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing genetic data: {str(e)}")


# =============================================================================
# AUTONOMOUS AGENT ENDPOINTS
# =============================================================================

class LabReportAnalysisResponse(BaseModel):
    """Response model for autonomous lab report analysis"""
    success: bool
    patient_id: str
    filename: str
    confidence_score: int
    severity: str
    priority: str
    primary_analysis: str
    medical_inferences: str
    proactive_recommendations: str
    full_analysis: str
    timestamp: str
    processing_steps: Dict[str, bool]
    saved_to_firestore: bool = False


@router.post("/{patient_id}/analyze-lab-report", response_model=LabReportAnalysisResponse)
async def analyze_lab_report_autonomous(
    patient_id: str,
    file: UploadFile = File(...)
) -> LabReportAnalysisResponse:
    """
    🤖 Autonomous Agent Endpoint for Lab Report Analysis
    
    Workflow:
    1. File Upload → HF Model Analysis
    2. Context Tokenization (compression)
    3. Gemini Comprehensive Medical Analysis
    4. Structured Response with Confidence, Inferences, Recommendations
    5. Save to Firestore
    
    Returns detailed medical analysis with confidence scores and actionable recommendations.
    """
    try:
        # Read file content
        file_content = await file.read()
        filename = file.filename or "lab_report.txt"
        
        # Run autonomous agent workflow
        analysis_result = await _autonomous_agent.analyze_lab_report(
            patient_id=patient_id,
            file_content=file_content,
            filename=filename
        )
        
        if not analysis_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {analysis_result.get('error', 'Unknown error')}"
            )
        
        # Extract structured data
        gemini_analysis = analysis_result.get("gemini_analysis", {})
        parsed_analysis = gemini_analysis.get("parsed_analysis", {})
        sections = parsed_analysis.get("sections", {})
        
        # Save to Firestore
        saved = False
        db = _get_db()
        if db:
            try:
                # Save to digital_twin_analyses collection
                analysis_doc = {
                    "patient_id": patient_id,
                    "filename": filename,
                    "confidence_score": parsed_analysis.get("confidence_score", 75),
                    "severity": parsed_analysis.get("severity", "Moderate"),
                    "priority": parsed_analysis.get("priority", "Medium"),
                    "primary_analysis": sections.get("primary_analysis", ""),
                    "confidence_assessment": sections.get("confidence_assessment", ""),
                    "medical_inferences": sections.get("medical_inferences", ""),
                    "proactive_recommendations": sections.get("proactive_recommendations", ""),
                    "severity_assessment": sections.get("severity_assessment", ""),
                    "full_analysis": parsed_analysis.get("full_analysis", ""),
                    "hf_analysis": analysis_result.get("hf_analysis", {}),
                    "tokenization_info": analysis_result.get("tokenized_context", {}),
                    "timestamp": datetime.utcnow(),
                    "analysis_type": "autonomous_agent",
                    "processing_completed": True
                }
                
                # Save with auto-generated ID
                doc_ref = db.collection("digital_twin_analyses").document(patient_id).collection("reports").add(analysis_doc)
                
                # Also update patient's digital twin record
                db.collection("twin_customizations").document(patient_id).set({
                    "userId": patient_id,
                    "last_analysis_timestamp": datetime.utcnow(),
                    "last_analysis_confidence": parsed_analysis.get("confidence_score", 75),
                    "last_analysis_severity": parsed_analysis.get("severity", "Moderate"),
                    "lastUpdated": datetime.utcnow()
                }, merge=True)
                
                saved = True
                print(f"✅ Analysis saved to Firestore for patient {patient_id}")
                
            except Exception as e:
                print(f"⚠️ Error saving to Firestore: {e}")
                saved = False
        
        # Return structured response
        return LabReportAnalysisResponse(
            success=True,
            patient_id=patient_id,
            filename=filename,
            confidence_score=parsed_analysis.get("confidence_score", 75),
            severity=parsed_analysis.get("severity", "Moderate"),
            priority=parsed_analysis.get("priority", "Medium"),
            primary_analysis=sections.get("primary_analysis", "Analysis not available"),
            medical_inferences=sections.get("medical_inferences", "Inferences not available"),
            proactive_recommendations=sections.get("proactive_recommendations", "Recommendations not available"),
            full_analysis=parsed_analysis.get("full_analysis", ""),
            timestamp=analysis_result.get("timestamp", datetime.utcnow().isoformat() + "Z"),
            processing_steps=analysis_result.get("processing_steps", {}),
            saved_to_firestore=saved
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in autonomous lab report analysis: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze lab report: {str(e)}"
        )


@router.get("/{patient_id}/analysis-history")
async def get_analysis_history(patient_id: str, limit: int = 10) -> Dict[str, Any]:
    """Get patient's analysis history from Firestore"""
    try:
        db = _get_db()
        if not db:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Fetch analysis history
        analyses = []
        docs = db.collection("digital_twin_analyses").document(patient_id).collection("reports").order_by("timestamp", direction="desc").limit(limit).stream()
        
        for doc in docs:
            data = doc.to_dict()
            analyses.append({
                "id": doc.id,
                "filename": data.get("filename", ""),
                "confidence_score": data.get("confidence_score", 0),
                "severity": data.get("severity", ""),
                "priority": data.get("priority", ""),
                "timestamp": data.get("timestamp", datetime.utcnow()).isoformat() if isinstance(data.get("timestamp"), datetime) else str(data.get("timestamp", "")),
                "analysis_summary": data.get("primary_analysis", "")[:200] + "..."
            })
        
        return {
            "patient_id": patient_id,
            "total_analyses": len(analyses),
            "analyses": analyses
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching analysis history: {str(e)}")


@router.post("/{patient_id}/save-analysis")
async def save_analysis_to_digital_twin(patient_id: str, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save a specific analysis to the patient's digital twin persistent memory
    This endpoint allows the Flutter UI to explicitly save selected analyses
    """
    try:
        db = _get_db()
        if not db:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Validate required fields
        required_fields = ["filename", "confidence_score", "severity", "full_analysis"]
        for field in required_fields:
            if field not in analysis_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Save to digital twin persistent memory
        save_doc = {
            "patient_id": patient_id,
            "saved_at": datetime.utcnow(),
            "analysis_data": analysis_data,
            "pinned": analysis_data.get("pinned", False),
            "notes": analysis_data.get("user_notes", "")
        }
        
        # Save with auto-generated ID
        doc_ref = db.collection("digital_twin_analyses").document(patient_id).collection("saved_analyses").add(save_doc)
        
        # Update patient's twin record
        db.collection("twin_customizations").document(patient_id).set({
            "userId": patient_id,
            "has_saved_analyses": True,
            "lastUpdated": datetime.utcnow()
        }, merge=True)
        
        return {
            "status": "success",
            "message": "Analysis saved to digital twin memory",
            "patient_id": patient_id,
            "saved_analysis_id": doc_ref[1].id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving analysis: {str(e)}")
