from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

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
