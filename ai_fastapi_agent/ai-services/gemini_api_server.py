#!/usr/bin/env python3
"""
Production-ready Gemini API Server
Consolidated FastAPI server with Gemini 2.5 Flash-Lite integration
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Environment variables loaded from .env file")
except ImportError:
    print("⚠️ python-dotenv not available, using system environment variables")

# FastAPI and related imports
from fastapi import FastAPI, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Gemini imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False

# Hugging Face imports
try:
    from huggingface_hub import InferenceClient
    HF_AVAILABLE = True
except ImportError:
    InferenceClient = None
    HF_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gemini_api_server")

# Import optimized context retriever
try:
    from optimized_context_retriever import OptimizedContextRetriever
    CONTEXT_RETRIEVER_AVAILABLE = True
except ImportError:
    OptimizedContextRetriever = None
    CONTEXT_RETRIEVER_AVAILABLE = False

# Optional Firebase Admin (for Digital Twin persistence)
FIREBASE_AVAILABLE = False
db = None
try:
    import firebase_admin  # type: ignore
    from firebase_admin import credentials, firestore  # type: ignore

    if not firebase_admin._apps:
        try:
            # Prefer ADC in Cloud Run
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized with Application Default Credentials")
        except Exception as _adc_err:
            # Fallback to JSON in env variable
            try:
                key_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
                if key_json:
                    import json as _json
                    cred = credentials.Certificate(_json.loads(key_json))
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase initialized from FIREBASE_SERVICE_ACCOUNT_JSON")
            except Exception as _json_err:  # pragma: no cover
                logger.warning(f"Firebase init fallback failed: {_json_err}")

    try:
        db = firestore.client()  # type: ignore
        FIREBASE_AVAILABLE = True
    except Exception as _db_err:  # pragma: no cover
        logger.warning(f"Firestore client unavailable: {_db_err}")
        db = None
except Exception as _fb_err:  # pragma: no cover
    logger.info(f"Firebase Admin not available: {_fb_err}")

# =============================================================================
# DATA MODELS
# =============================================================================

class PatientQuery(BaseModel):
    patient_id: str
    query_text: str
    symptoms: Optional[List[str]] = []
    medical_history: Optional[List[str]] = []
    current_medications: Optional[List[str]] = []
    additional_data: Optional[Dict[str, Any]] = {}
    request_id: Optional[str] = None
    uploaded_files: Optional[List[Dict[str, Any]]] = None

class GeminiResponseFeatures(BaseModel):
    category: str
    urgency: str
    keywords: List[str]
    actionable_steps_present: bool

class StructuredGeminiOutput(BaseModel):
    text: str
    features: GeminiResponseFeatures

class AgentResponse(BaseModel):
    request_id: str
    response_text: str
    suggestions: Optional[List[Dict[str, Any]]] = []

# =============================================================================
# DIGITAL TWIN MODELS
# =============================================================================

class DigitalTwinPayload(BaseModel):
    height_cm: float
    weight_kg: float
    biomarkers: Optional[Dict[str, float]] = None

class DigitalTwinRecord(DigitalTwinPayload):
    patient_id: str
    updated_at: str

# =============================================================================
# GEMINI SERVICE
# =============================================================================

class GeminiService:
    def __init__(self, firestore_service=None):
        self.model = None
        self.api_key = None
        self.initialized = False
        self.firestore_service = firestore_service
        self.context_retriever = None
        self._initialize()
        
        # Initialize optimized context retriever if available
        if CONTEXT_RETRIEVER_AVAILABLE and firestore_service:
            self.context_retriever = OptimizedContextRetriever(firestore_service, max_tokens=2000)
            logger.info("✅ Optimized context retriever initialized for token efficiency")
    
    def _initialize(self):
        """Initialize Gemini service with proper error handling"""
        try:
            # Check for GitHub secrets first, then fallback to local env
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            
            if not self.api_key:
                logger.warning("No Gemini API key found in environment variables")
                logger.info("Available env vars: GEMINI_API_KEY={}, GOOGLE_API_KEY={}".format(
                    bool(os.getenv("GEMINI_API_KEY")), bool(os.getenv("GOOGLE_API_KEY"))
                ))
                return
            
            # Log key source for debugging
            if os.getenv("GEMINI_API_KEY"):
                logger.info("✅ Gemini API key loaded from GEMINI_API_KEY")
            elif os.getenv("GOOGLE_API_KEY"):
                logger.info("✅ Gemini API key loaded from GOOGLE_API_KEY")
            
            logger.info(f"✅ Gemini API key found: {self.api_key[:10]}...")
            
            if not GEMINI_AVAILABLE:
                logger.error("Google Generative AI library not available")
                return
            
            # Configure Gemini
            genai.configure(api_key=self.api_key, transport='rest')
            logger.info(f"Gemini configured with API key: {self.api_key[:10]}...")
            
            # Try to initialize model with fallback options (using correct model names)
            model_names = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-flash-latest"]
            
            for model_name in model_names:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    logger.info(f"Gemini model initialized successfully: {model_name}")
                    self.initialized = True
                    return
                except Exception as e:
                    logger.warning(f"Gemini model init failed for {model_name}: {e}")
            
            logger.error("All Gemini model initialization attempts failed")
            
        except Exception as e:
            logger.error(f"Gemini configuration failed: {e}")
    
    async def generate_text(self, prompt: str) -> str:
        """Generate text using Gemini with comprehensive error handling"""
        if not self.initialized or not self.model:
            logger.warning("Gemini model not available, returning fallback response")
            return ""
        
        try:
            logger.info(f"Generating text with Gemini (prompt length: {len(prompt)})")
            
            # Generate content (run synchronous method in thread pool)
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            
            text = getattr(response, "text", "") or ""
            logger.info(f"Gemini response generated (length: {len(text)})")
            return text
            
        except Exception as e:
            logger.error(f"Error generating text with Gemini: {e}")
            return ""
    
    async def get_treatment_suggestion(self, patient_query: PatientQuery, patient_context: Optional[Dict[str, Any]] = None) -> StructuredGeminiOutput:
        """Get treatment suggestion from Gemini with optimized context and cost management"""
        try:
            # Use optimized context retriever if available
            optimized_context = None
            if self.context_retriever:
                try:
                    context_result = await self.context_retriever.retrieve(
                        patient_query.patient_id, 
                        patient_query.query_text,
                        uploaded_files=patient_query.uploaded_files
                    )
                    optimized_context = context_result.get('trimmed_context_text', '')
                    
                    # Log token usage for cost tracking
                    token_usage = self.context_retriever.get_token_usage_estimate(optimized_context)
                    logger.info(f"Token usage: {token_usage['input_tokens']} tokens, "
                              f"Estimated cost: {token_usage['total_estimated_cost']}, "
                              f"Budget utilization: {token_usage['budget_utilization']}")
                    
                except Exception as e:
                    logger.warning(f"Optimized context retrieval failed: {e}")
                    optimized_context = None
            
            # Create comprehensive medical prompt with optimized context
            prompt = self._create_medical_prompt(patient_query, optimized_context or patient_context)
            
            # Log prompt length for cost tracking
            prompt_tokens = len(prompt) // 3.5  # Rough token estimate
            logger.info(f"Prompt length: {len(prompt)} chars, ~{prompt_tokens:.0f} tokens")
            
            # Generate text using Gemini
            text = await self.generate_text(prompt)
            
            if not text:
                # Fallback response when Gemini is not available
                fallback_text = f"Thank you for your query: '{patient_query.query_text}'. I understand you're experiencing {', '.join(patient_query.symptoms) if patient_query.symptoms else 'concerns'}. Please consult with a healthcare professional for personalized medical advice."
                return StructuredGeminiOutput(
                    text=fallback_text,
                    features=GeminiResponseFeatures(
                        category="medical_query",
                        urgency="medium",
                        keywords=patient_query.symptoms if patient_query.symptoms else [],
                        actionable_steps_present=False
                    )
                )
            
            return StructuredGeminiOutput(
                text=text,
                features=GeminiResponseFeatures(
                    category="medical_query",
                    urgency="medium",
                    keywords=patient_query.symptoms if patient_query.symptoms else [],
                    actionable_steps_present=True
                )
            )
            
        except Exception as e:
            logger.error(f"Error getting treatment suggestion: {e}")
            return StructuredGeminiOutput(
                text="I'm currently unable to process your medical query. Please consult with a healthcare professional for personalized medical advice.",
                features=GeminiResponseFeatures(
                    category="medical_query",
                    urgency="medium",
                    keywords=patient_query.symptoms if patient_query.symptoms else [],
                    actionable_steps_present=False
                )
            )
    
    def _create_medical_prompt(self, patient_query: PatientQuery, patient_context: Optional[Dict[str, Any]] = None) -> str:
        """Create comprehensive medical prompt for Gemini"""
        prompt_parts = [
            "You are Airavat, an advanced medical AI assistant. Provide comprehensive, personalized medical guidance.",
            "",
            f"Patient ID: {patient_query.patient_id}",
            f"Query: {patient_query.query_text}",
        ]
        
        # Add symptoms if provided
        if patient_query.symptoms:
            prompt_parts.append(f"Symptoms: {', '.join(patient_query.symptoms)}")
        
        # Add medical history if provided
        if patient_query.medical_history:
            prompt_parts.append(f"Medical History: {', '.join(patient_query.medical_history)}")
        
        # Add current medications if provided
        if patient_query.current_medications:
            prompt_parts.append(f"Current Medications: {', '.join(patient_query.current_medications)}")
        
        # Add patient context if available
        if patient_context:
            prompt_parts.append(f"Additional Context: {str(patient_context)}")
        
        prompt_parts.extend([
            "",
            "Please provide:",
            "1. A detailed, personalized response addressing the patient's specific situation",
            "2. Multiple actionable suggestions with confidence scores (0.0-1.0)",
            "3. Consider the patient's medical history, current medications, and symptoms",
            "4. Always emphasize consulting healthcare providers for serious concerns",
            "",
            "Format your response as natural conversation with clear, actionable next steps."
        ])
        
        return "\n".join(prompt_parts)

# =============================================================================
# HUGGING FACE SERVICE
# =============================================================================

class HuggingFaceService:
    def __init__(self):
        self.client = None
        self.initialized = False
        self._initialize()
    
    def _initialize(self):
        """Initialize Hugging Face service"""
        try:
            hf_token = os.getenv("HF_TOKEN")
            
            if not hf_token:
                logger.warning("No Hugging Face token found in environment variables")
                logger.info("Available env vars: HF_TOKEN={}".format(bool(os.getenv("HF_TOKEN"))))
                return
            
            # Log token source for debugging
            logger.info("✅ Hugging Face token loaded from HF_TOKEN")
            logger.info(f"✅ Hugging Face token found: {hf_token[:10]}...")
            
            if not HF_AVAILABLE:
                logger.error("Hugging Face library not available")
                return
            
            self.client = InferenceClient(token=hf_token)
            logger.info("Hugging Face InferenceClient initialized successfully")
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Hugging Face service initialization failed: {e}")
    
    async def analyze_genetic_text(self, text: str) -> Dict[str, Any]:
        """Analyze genetic text using Hugging Face models"""
        if not self.initialized or not self.client:
            return {"error": "Hugging Face service not available"}
        
        try:
            logger.info(f"Analyzing genetic text (length: {len(text)})")
            
            # Use token classification for genetic analysis
            result = await asyncio.to_thread(
                self.client.token_classification,
                text,
                model="OpenMed/OpenMed-NER-GenomeDetect-SuperClinical-434M"
            )
            
            return {
                "status": "success",
                "analysis": result,
                "entities_found": len(result),
                "text_length": len(text)
            }
            
        except Exception as e:
            logger.error(f"Error in genetic analysis: {e}")
            return {"error": f"Genetic analysis failed: {str(e)}"}

# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

# Initialize services
gemini_service = GeminiService()
hf_service = HuggingFaceService()

# Create FastAPI app
app = FastAPI(
    title="Airavat Gemini API Server",
    description="Production-ready Gemini API server with medical AI capabilities",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mira-d303d.web.app",
        "https://mira-d303d.firebaseapp.com",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "*"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# ENDPOINTS
# =============================================================================

try:
    from smpl_service.router import router as smpl_router
    app.include_router(smpl_router)
except Exception:
    logger.warning("SMPL router unavailable; /smpl endpoints will return 404")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "gemini_initialized": gemini_service.initialized,
            "huggingface_initialized": hf_service.initialized
        }
    }

@app.get("/debug/config")
async def debug_config():
    """Debug configuration endpoint"""
    return {
        "environment": {
            "GEMINI_API_KEY_PRESENT": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
            "HF_TOKEN_PRESENT": bool(os.getenv("HF_TOKEN")),
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "production"),
            "GITHUB_SECRETS_LOADED": bool(os.getenv("GEMINI_API_KEY") and os.getenv("HF_TOKEN")),
            "GEMINI_KEY_SOURCE": "GEMINI_API_KEY" if os.getenv("GEMINI_API_KEY") else ("GOOGLE_API_KEY" if os.getenv("GOOGLE_API_KEY") else "None"),
            "HF_TOKEN_SOURCE": "HF_TOKEN" if os.getenv("HF_TOKEN") else "None"
        },
        "services": {
            "gemini_initialized": gemini_service.initialized,
            "huggingface_initialized": hf_service.initialized,
            "gemini_available": GEMINI_AVAILABLE,
            "huggingface_available": HF_AVAILABLE,
            "context_retriever_available": CONTEXT_RETRIEVER_AVAILABLE
        }
    }

# =============================================================================
# DIGITAL TWIN MINIMAL ENDPOINTS
# =============================================================================

@app.put("/digital_twin/{patient_id}")
async def upsert_digital_twin(patient_id: str, payload: DigitalTwinPayload):
    """Upsert the latest twin document for a patient. Uses Firestore if available."""
    try:
        record = DigitalTwinRecord(
            patient_id=patient_id,
            height_cm=payload.height_cm,
            weight_kg=payload.weight_kg,
            biomarkers=payload.biomarkers or {},
            updated_at=datetime.utcnow().isoformat() + "Z",
        )

        if FIREBASE_AVAILABLE and db is not None:
            try:
                db.collection("twin_customizations").document(patient_id).set({
                    "userId": patient_id,
                    "height_cm": record.height_cm,
                    "weight_kg": record.weight_kg,
                    "biomarkers": record.biomarkers or {},
                    "lastUpdated": datetime.utcnow(),
                }, merge=True)
            except Exception as e:  # pragma: no cover
                logger.warning(f"Firestore upsert failed: {e}")

        return {"status": "success", "twin": record.model_dump()}
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Twin upsert failed: {str(e)}")


@app.get("/digital_twin/{patient_id}")
async def get_digital_twin(patient_id: str):
    """Return the latest twin document if present, otherwise a sensible default."""
    try:
        if FIREBASE_AVAILABLE and db is not None:
            try:
                doc = db.collection("twin_customizations").document(patient_id).get()
                if doc.exists:
                    data = doc.to_dict() or {}
                    return {
                        "status": "success",
                        "twin": {
                            "patient_id": patient_id,
                            "height_cm": float(data.get("height_cm") or 170.0),
                            "weight_kg": float(data.get("weight_kg") or 70.0),
                            "biomarkers": data.get("biomarkers") or {},
                            "updated_at": (data.get("lastUpdated") or datetime.utcnow()).isoformat() + "Z",
                        },
                    }
            except Exception as e:  # pragma: no cover
                logger.warning(f"Firestore read failed: {e}")

        # Default stub if none stored
        return {
            "status": "success",
            "twin": {
                "patient_id": patient_id,
                "height_cm": 170.0,
                "weight_kg": 70.0,
                "biomarkers": {},
                "updated_at": datetime.utcnow().isoformat() + "Z",
            },
        }
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Twin fetch failed: {str(e)}")

@app.post("/gemini/suggest", response_model=StructuredGeminiOutput)
async def gemini_suggest(patient_query: PatientQuery):
    """Main Gemini suggestion endpoint"""
    logger.info(f"Processing Gemini suggestion for patient: {patient_query.patient_id}")
    logger.info(f"Query: {patient_query.query_text[:100]}...")
    
    try:
        # Extract optional patient context sent by frontend (from Firebase)
        patient_context = None
        try:
            if patient_query.additional_data and isinstance(patient_query.additional_data, dict):
                patient_context = patient_query.additional_data.get("patient_context")
        except Exception:
            patient_context = None

        response = await gemini_service.get_treatment_suggestion(patient_query, patient_context)
        logger.info(f"Gemini suggestion generated (length: {len(response.text)})")
        return response
    except Exception as e:
        logger.exception(f"Error processing Gemini suggestion for patient {patient_query.patient_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.post("/agent/query", response_model=AgentResponse)
async def agent_query(patient_query: PatientQuery):
    """Legacy agent query endpoint for compatibility"""
    logger.info(f"Processing agent query for patient: {patient_query.patient_id}")
    
    try:
        # Use Gemini service for response (forward patient_context if provided)
        patient_context = None
        try:
            if patient_query.additional_data and isinstance(patient_query.additional_data, dict):
                patient_context = patient_query.additional_data.get("patient_context")
        except Exception:
            patient_context = None

        gemini_response = await gemini_service.get_treatment_suggestion(patient_query, patient_context)
        
        # Convert to AgentResponse format
        suggestions = []
        if gemini_response.features.actionable_steps_present:
            suggestions = [
                {"suggestion_text": "Consult with a healthcare professional", "confidence_score": 0.9},
                {"suggestion_text": "Monitor your symptoms closely", "confidence_score": 0.8}
            ]
        
        return AgentResponse(
            request_id=patient_query.request_id or f"req_{datetime.utcnow().timestamp()}",
            response_text=gemini_response.text,
            suggestions=suggestions
        )
    except Exception as e:
        logger.exception(f"Error processing agent query for patient {patient_query.patient_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.post("/genetic/analyze")
async def analyze_genetic_text(request: Dict[str, str]):
    """Genetic text analysis endpoint"""
    try:
        text = request.get("text", "")
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text field is required"
            )
        
        logger.info(f"Analyzing genetic text (length: {len(text)})")
        
        result = await hf_service.analyze_genetic_text(text)
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in genetic analysis endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing genetic analysis: {str(e)}"
        )

@app.post("/upload/analyze")
async def analyze_uploaded_file(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    file_type: str = Form("unknown")
):
    """Analyze uploaded file with Gemini and HF models"""
    try:
        # Read file content
        content = await file.read()
        
        # Check file size (5MB limit)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large. Maximum size is 5MB"
            )
        
        # Process file based on type
        file_info = {
            "name": file.filename,
            "type": file_type,
            "size": len(content),
            "content": content.decode('utf-8', errors='ignore') if file_type in ['text', 'genetic', 'lab_report'] else None
        }
        
        # Create patient query with file context
        patient_query = PatientQuery(
            patient_id=patient_id,
            query_text=f"Please analyze this {file_type} file: {file.filename}",
            uploaded_files=[file_info]
        )
        
        # Get analysis from Gemini
        response = await gemini_service.get_treatment_suggestion(patient_query)
        
        # If it's a genetic file, also run HF analysis
        hf_analysis = None
        if file_type == "genetic" and file_info["content"]:
            hf_analysis = await hf_service.analyze_genetic_text(file_info["content"])
        
        return {
            "status": "success",
            "file_analysis": {
                "filename": file.filename,
                "type": file_type,
                "size": len(content),
                "gemini_response": response.text,
                "hf_analysis": hf_analysis if hf_analysis else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )

@app.get("/cost/estimate")
async def get_cost_estimate(patient_id: str, query_text: str):
    """Get cost estimate for a query without processing"""
    try:
        if not gemini_service.context_retriever:
            return {"error": "Context retriever not available"}
        
        # Get context without processing
        context_result = await gemini_service.context_retriever.retrieve(patient_id, query_text)
        token_usage = gemini_service.context_retriever.get_token_usage_estimate(
            context_result.get('trimmed_context_text', '')
        )
        
        return {
            "status": "success",
            "cost_estimate": token_usage,
            "context_preview": context_result.get('trimmed_context_text', '')[:200] + "..."
        }
        
    except Exception as e:
        logger.error(f"Error getting cost estimate: {e}")
        return {"error": str(e)}

# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main function to run the server"""
    logger.info("Starting Airavat Gemini API Server")
    logger.info(f"Gemini service initialized: {gemini_service.initialized}")
    logger.info(f"Hugging Face service initialized: {hf_service.initialized}")
    
    # Cloud Run configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))  # Cloud Run uses port 8080
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Reload mode: {reload}")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'production')}")
    
    # For Cloud Run, disable reload in production
    if os.getenv("ENVIRONMENT") == "production":
        reload = False
        logger.info("Production mode: reload disabled")
    
    uvicorn.run(
        "gemini_api_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
 