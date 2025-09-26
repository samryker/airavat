from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from .data_models import PatientQuery, AgentResponse, FeedbackDataModel, TreatmentPlanUpdate
from .agent_core import MedicalAgent
from .mcp_medical_agent import MCPMedicalAgent
from .firestore_service import FirestoreService
from mcp_config import mcp_config
import uvicorn # For running the app directly if needed
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
import logging # Added logging
from typing import Dict, Any, List
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from google import generativeai as genai
from .gemini_service import is_gemini_available as _gemini_available, model as _gemini_model

# Optional imports for new services
try:
    from .genetic_analysis_service import GeneticAnalysisService
    GENETIC_AVAILABLE = True
except ImportError:
    GeneticAnalysisService = None
    GENETIC_AVAILABLE = False

try:
    from .notification_service import NotificationService
    NOTIFICATION_AVAILABLE = True
except ImportError:
    NotificationService = None
    NOTIFICATION_AVAILABLE = False

try:
    from .user_data_service import UserDataService
    USER_DATA_AVAILABLE = True
except ImportError:
    UserDataService = None
    USER_DATA_AVAILABLE = False

# Try both import styles for SMPL router (top-level and relative)
SMPL_AVAILABLE = False
smpl_router = None
try:
    from smpl_service.router import router as smpl_router
    SMPL_AVAILABLE = True
except Exception as e1:
    try:
        from ..smpl_service.router import router as smpl_router
        SMPL_AVAILABLE = True
    except Exception as e2:
        smpl_router = None
        SMPL_AVAILABLE = False
        # Set up basic logger early to record why SMPL failed
        logging.getLogger("api").warning(f"SMPL router import failed: top-level={e1}; relative={e2}")

# Try both import styles for Digital Twin router (top-level and relative)
DIGITAL_TWIN_AVAILABLE = False
digital_twin_router = None
try:
    from digital_twin_service.router import router as digital_twin_router
    DIGITAL_TWIN_AVAILABLE = True
except Exception as e1:
    try:
        from ..digital_twin_service.router import router as digital_twin_router
        DIGITAL_TWIN_AVAILABLE = True
    except Exception as e2:
        digital_twin_router = None
        DIGITAL_TWIN_AVAILABLE = False
        logging.getLogger("api").warning(
            f"Digital Twin router import failed: top-level={e1}; relative={e2}"
        )

load_dotenv() # Load local env for dev only; CI/CD secrets already in env

# Setup logging for the main application
logger = logging.getLogger("api") # Can use a specific name
logging.basicConfig(level=logging.INFO) # Basic config, can be more sophisticated

app = FastAPI(
    title="Airavat Medical Agent API",
    description="API for interacting with the AI Medical Agent, including dynamic planning, RL-based feedback, genetic analysis, notifications, and SMPL.",
    version="0.4.0", # Incremented version for new features
)

# Add CORS middleware
# ALLOWED_ORIGINS can be provided as a comma-separated list via environment variable
default_allowed_origins = [
    "https://mira-d303d.web.app",
    "https://mira-d303d.firebaseapp.com",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env.strip():
    if allowed_origins_env.strip() == "*":
        allowed_origins = ["*"]
    else:
        allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = default_allowed_origins
logger.info(f"CORS config: ALLOWED_ORIGINS env='{allowed_origins_env}', using list={allowed_origins}")

use_wildcard = allowed_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # Enhanced regex to cover Firebase Hosting and localhost during migrations
    allow_origin_regex=None if use_wildcard else r"^(https:\/\/[a-zA-Z0-9-]+\.web\.app|https:\/\/[a-zA-Z0-9-]+\.firebaseapp\.com|http:\/\/localhost(?::\d+)?|http:\/\/127\.0\.0\.1(?::\d+)?|https:\/\/storage\.googleapis\.com)$",
    allow_credentials=False if use_wildcard else True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=[
        "Content-Type", 
        "Authorization", 
        "X-Requested-With", 
        "Accept", 
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
        "Cache-Control",
        "Pragma",
        "Expires",
        "Range"
    ],
    expose_headers=[
        "Content-Type", 
        "Authorization",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Headers",
        "Content-Range",
        "Accept-Ranges"
    ],
    max_age=86400,
)

if DIGITAL_TWIN_AVAILABLE and digital_twin_router:
    app.include_router(digital_twin_router)
else:
    logger.warning("Digital Twin router not available; /digital_twin endpoints will not be served")

if SMPL_AVAILABLE and smpl_router:
    app.include_router(smpl_router)
else:
    logger.warning("SMPL router not available; /smpl endpoints will not be served")

# Fallback inline SMPL endpoints (ensure availability in Cloud Run)
_SMPL_ASSETS_BASE_URL = os.getenv("SMPL_ASSETS_BASE_URL", "https://storage.googleapis.com/mira-smpl-assets/models")

@app.get("/smpl/health")
async def smpl_health_inline():
    return {
        "status": "ok",
        "assets_base_url": _SMPL_ASSETS_BASE_URL or None,
    }

@app.get("/smpl/generate")
async def smpl_generate_inline(
    patient_id: str | None = None,
    height: float | None = 170.0,
    weight: float | None = 70.0,
    gender: str | None = "neutral",
    model: str | None = None,
    beta1: float | None = None,
):
    # Choose model
    selected = model if model in {"male", "female", "neutral"} else (
        gender if gender in {"male", "female"} else "neutral"
    )
    asset_file = f"{selected}.glb"
    
    # Generate signed URL for private bucket access
    asset_url = None
    if _SMPL_ASSETS_BASE_URL:
        try:
            from google.cloud import storage
            from datetime import timedelta
            
            # Extract bucket and object path from SMPL_ASSETS_BASE_URL
            # e.g., https://storage.googleapis.com/bucket-name/models -> bucket-name, models/file.glb
            if "storage.googleapis.com" in _SMPL_ASSETS_BASE_URL:
                parts = _SMPL_ASSETS_BASE_URL.replace("https://storage.googleapis.com/", "").split("/", 1)
                bucket_name = parts[0]
                prefix = parts[1] if len(parts) > 1 else ""
                object_name = f"{prefix}/{asset_file}".strip("/")
                
                client = storage.Client()
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(object_name)
                
                # Generate signed URL valid for 1 hour
                asset_url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(hours=1),
                    method="GET"
                )
            else:
                # Fallback to direct URL
                asset_url = f"{_SMPL_ASSETS_BASE_URL.rstrip('/')}/{asset_file}"
        except Exception as e:
            logger.warning(f"Failed to generate signed URL: {e}")
            asset_url = f"{_SMPL_ASSETS_BASE_URL.rstrip('/')}/{asset_file}" if _SMPL_ASSETS_BASE_URL else None
    
    bmi = None
    try:
        if height and weight and height > 0:
            bmi = round(weight / ((height / 100.0) ** 2), 1)
    except Exception:
        bmi = None
    return {
        "status": "ok",
        "patient_id": patient_id,
        "model": selected,
        "asset_file": asset_file,
        "asset_url": asset_url,
        "parameters": {
            "height_cm": height,
            "weight_kg": weight,
            "gender": gender,
            "beta1": beta1,
            "bmi": bmi,
        },
    }

# --- Firebase Admin SDK Initialization ---
try:
    # Check if we're running on Google Cloud (Cloud Run, GAE, etc.)
    # If so, use the default service account
    if os.getenv("K_SERVICE") or os.getenv("GOOGLE_CLOUD_PROJECT"):
        # Running on Google Cloud - use default service account
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized using Google Cloud default service account.")
        db = firestore.client()
    else:
        # Local or non-GCP: support both path-based and JSON env-based service account
        cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", "airavat-a3a10-firebase-adminsdk-fbsvc-7b24d935c3.json")
        cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        try:
            if cred_json:
                import json as _json
                cred_dict = _json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized from FIREBASE_SERVICE_ACCOUNT_JSON env.")
                db = firestore.client()
            elif os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                logger.info(f"Firebase Admin SDK initialized using {cred_path}.")
                db = firestore.client()
            else:
                logger.warning(f"Warning: Firebase credentials not provided. Set FIREBASE_SERVICE_ACCOUNT_JSON or place key at {cred_path}.")
                db = None
        except Exception as cred_e:
            logger.exception(f"Failed to initialize Firebase Admin SDK with provided credentials: {cred_e}")
            db = None
except Exception as e:
    logger.exception(f"CRITICAL: Error initializing Firebase Admin SDK: {e}")
    db = None # Ensure db is None if initialization fails
# --- End Firebase Admin SDK Initialization ---

if db is None:
    logger.error("Firestore client (db) is None. The MedicalAgent may not function correctly.")

# --- MCP Database Engine Initialization ---
mcp_db_engine = None
mcp_agent = None

try:
    # Initialize MCP Medical Agent with database engine and Firestore service
    firestore_service = FirestoreService(db) if db else None
    mcp_agent = MCPMedicalAgent(
        db_engine=mcp_db_engine,
        firestore_service=firestore_service
    )
    logger.info("MCP Medical Agent initialized successfully with lifelong memory capabilities.")
except Exception as e:
    logger.exception(f"Error initializing MCP components: {e}")
    mcp_agent = None
    mcp_db_engine = None
# --- End MCP Database Engine Initialization ---

# Initialize the agent globally or manage its lifecycle as needed
# For simplicity, a single global instance is created here.
# In a production system, you might manage this differently (e.g., with dependency injection).
medical_agent = MedicalAgent(db=db, mcp_agent=mcp_agent) # Pass Firestore client and MCP agent to the agent

# Initialize additional services (optional)
genetic_service = None
notification_service = None
user_data_service = None

# Always initialize GeneticAnalysisService if available, even without Firestore
if GENETIC_AVAILABLE:
    try:
        genetic_service = GeneticAnalysisService(db=db)
        logger.info("Genetic Analysis Service initialized successfully (serverless mode supported).")
    except Exception as e:
        logger.warning(f"Failed to initialize Genetic Analysis Service: {e}")

if NOTIFICATION_AVAILABLE and db:
    try:
        notification_service = NotificationService(db=db)
        logger.info("Notification Service initialized successfully.")
    except Exception as e:
        logger.warning(f"Failed to initialize Notification Service: {e}")

if USER_DATA_AVAILABLE and db:
    try:
        user_data_service = UserDataService(db=db)
        logger.info("User Data Service initialized successfully.")
    except Exception as e:
        logger.warning(f"Failed to initialize User Data Service: {e}")

@app.post("/agent/query", response_model=AgentResponse)
async def query_agent(patient_query: PatientQuery):
    """
    Receives a patient query, processes it through the Medical Agent,
    and returns the agent's response including any treatment suggestions.
    """
    logger.info(f"Received query for patient: {patient_query.patient_id}")
    try:
        # The agent instance now has access to db if initialized
        response = await medical_agent.process_query(patient_query)
        return response
    except Exception as e:
        # Log the exception for debugging
        logger.exception(f"Error processing agent query for patient {patient_query.patient_id}: {e}")
        # You might want to return a more specific error response structure
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.post("/agent/feedback", response_model=Dict[str, str]) # Simple response model for feedback
async def submit_feedback(feedback_data: FeedbackDataModel):
    logger.info(f"Received feedback for request_id: {feedback_data.request_id}, patient: {feedback_data.patient_id}")
    if not medical_agent.db: # Check if agent has DB, critical for feedback processing
        logger.error(f"Feedback cannot be processed: MedicalAgent has no database instance.")
        raise HTTPException(status_code=503, detail="Feedback system temporarily unavailable due to database misconfiguration.")
    try:
        result = await medical_agent.process_feedback(feedback_data)
        if result.get("status") == "error":
            # Avoid raising HTTPException for some internal errors if they are handled and a message is returned
            logger.warning(f"Feedback processing for {feedback_data.request_id} resulted in handled error: {result.get('message')}")
            # Return a 200 OK but with an error message in the body, or choose a specific HTTP error code
            return {"status": "error_handled", "message": result.get("message", "Could not process feedback fully.")}
        return result # {"status": "success", "message": "..."}
    except Exception as e:
        logger.exception(f"Unhandled error processing feedback for request_id {feedback_data.request_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred while processing feedback: {str(e)}")

@app.get("/agent/memory/{patient_id}")
async def get_patient_memory(patient_id: str):
    """
    Retrieves the patient's complete memory and context from MCP agent.
    This includes conversation history, treatment preferences, health goals, and session data.
    """
    logger.info(f"Retrieving memory for patient: {patient_id}")
    try:
        memory_data = await medical_agent.get_patient_memory(patient_id)
        return {
            "patient_id": patient_id,
            "memory_data": memory_data,
            "timestamp": "2024-01-01T00:00:00Z"  # You can add actual timestamp logic
        }
    except Exception as e:
        logger.exception(f"Error retrieving memory for patient {patient_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.post("/agent/update_treatment_plan")
async def update_treatment_plan(plan_update: TreatmentPlanUpdate):
    """
    Updates the patient's treatment plan using MCP agent for persistent storage.
    """
    logger.info(f"Updating treatment plan for patient: {plan_update.patient_id}")
    try:
        success = await medical_agent.update_treatment_plan(plan_update.patient_id, plan_update.treatment_plan)
        if success:
            return {
                "status": "success",
                "message": f"Treatment plan updated successfully for patient {plan_update.patient_id}",
                "patient_id": plan_update.patient_id,
                "plan_type": plan_update.plan_type,
                "priority": plan_update.priority
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to update treatment plan for patient {plan_update.patient_id}",
                "patient_id": plan_update.patient_id
            }
    except Exception as e:
        logger.exception(f"Error updating treatment plan for patient {plan_update.patient_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint for AWS load balancer and monitoring"""
    try:
        # Basic health checks
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "environment": "aws-production",
            "services": {
                "database": "unknown",
                "notification_service": False,
                "email_service": False
            }
        }
        
        # Check database connection (Firestore)
        try:
            if medical_agent and medical_agent.db:
                # Simple test query
                test_collection = medical_agent.db.collection('health_check')
                test_doc = test_collection.document('test')
                test_doc.set({'timestamp': datetime.utcnow()})
                health_status["services"]["database"] = "healthy"
            else:
                health_status["services"]["database"] = "unavailable"
        except Exception as e:
            health_status["services"]["database"] = f"error: {str(e)}"
        
        # Check notification service
        if medical_agent and medical_agent.notification_service:
            health_status["services"]["notification_service"] = True
        
        # Check email service
        if medical_agent and medical_agent.email_service:
            health_status["services"]["email_service"] = True
        
        return health_status
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Airavat Medical Agent API. Use /agent/query, /agent/feedback, /agent/memory/{patient_id}, and /agent/update_treatment_plan endpoints."}

@app.get("/agent/patient/{patient_id}/context")
async def get_patient_context(patient_id: str):
    """Get complete patient context including profile, treatment plans, biomarkers, and memory"""
    try:
        if not medical_agent:
            return {"status": "error", "message": "Medical agent not available"}
        
        # Get patient data from Firestore
        patient_ref = db.collection('patients').document(patient_id)
        patient_doc = patient_ref.get()  # Remove await - this is not async
        
        # Get memory data from MCP
        memory_data = None
        if medical_agent.mcp_agent:
            try:
                memory_data = await medical_agent.mcp_agent.get_memory(patient_id)
            except Exception as e:
                logger.warning(f"MCP memory retrieval failed: {e}")
        
        # Get conversation history
        conversation_history = []
        try:
            history_ref = db.collection('conversations').document(patient_id)
            history_doc = history_ref.get()  # Remove await - this is not async
            if history_doc.exists:
                history_data = history_doc.to_dict()
                conversation_history = history_data.get('messages', [])
        except Exception as e:
            logger.warning(f"Conversation history retrieval failed: {e}")
        
        # Compile context
        context = {
            'patient_id': patient_id,
            'profile': {},
            'treatment_plans': [],
            'biomarkers': {},
            'conversation_history': conversation_history,
            'mcp_memory': memory_data or {},
            'last_updated': datetime.utcnow().isoformat()
        }
        
        if patient_doc.exists:
            patient_data = patient_doc.to_dict()
            context['profile'] = patient_data.get('profile', {})
            context['treatment_plans'] = patient_data.get('treatmentPlans', [])
            context['biomarkers'] = patient_data.get('biomarkers', {})
        
        return {
            "status": "success",
            "context": context
        }
        
    except Exception as e:
        logger.error(f"Error retrieving patient context: {e}")
        return {"status": "error", "message": f"Failed to retrieve patient context: {str(e)}"}

@app.get("/agent/patient/{patient_id}/conversation-history")
async def get_conversation_history(patient_id: str, limit: int = 10):
    """Get conversation history for a patient"""
    try:
        if not db:
            return {"status": "error", "message": "Database not available"}
        
        # Get conversation history from Firestore
        history_ref = db.collection('conversations').document(patient_id)
        history_doc = history_ref.get()  # Remove await - this is not async
        
        conversation_history = []
        if history_doc.exists:
            history_data = history_doc.to_dict()
            messages = history_data.get('messages', [])
            # Return the most recent messages
            conversation_history = messages[:limit]  # Fix: use slice instead of take()
        
        return {
            "status": "success",
            "conversation_history": conversation_history
        }
        
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        return {"status": "error", "message": f"Failed to retrieve conversation history: {str(e)}"}

@app.get("/agent/memory/{patient_id}")
async def get_patient_memory(patient_id: str):
    """Get patient memory data from MCP"""
    try:
        if not medical_agent or not medical_agent.mcp_agent:
            return {"status": "error", "message": "MCP agent not available"}
        
        memory_data = await medical_agent.mcp_agent.get_memory(patient_id)
        
        return {
            "status": "success",
            "memory_data": memory_data
        }
        
    except Exception as e:
        logger.error(f"Error retrieving patient memory: {e}")
        return {"status": "error", "message": f"Failed to retrieve patient memory: {str(e)}"}

@app.post("/agent/patient/{patient_id}/treatment-plan")
async def update_patient_treatment_plan(patient_id: str, treatment_plan: dict):
    """
    Update patient's treatment plan in Firestore and MCP memory.
    """
    logger.info(f"Updating treatment plan for patient: {patient_id}")
    try:
        success = await medical_agent.update_patient_treatment_plan(patient_id, treatment_plan)
        if success:
            return {
                "status": "success",
                "message": "Treatment plan updated successfully",
                "patient_id": patient_id
            }
        else:
            return {
                "status": "error",
                "message": "Failed to update treatment plan",
                "patient_id": patient_id
            }
    except Exception as e:
        logger.exception(f"Error updating treatment plan for patient {patient_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.post("/agent/patient/{patient_id}/feedback")
async def submit_patient_feedback(patient_id: str, feedback: dict):
    """
    Submit feedback for a patient interaction.
    """
    logger.info(f"Received feedback for patient: {patient_id}")
    try:
        feedback_data = FeedbackDataModel(
            request_id=feedback.get("request_id", ""),
            patient_id=patient_id,
            outcome_works=feedback.get("outcome_works", False),
            feedback_text=feedback.get("feedback_text", "")
        )
        result = await medical_agent.process_feedback(feedback_data)
        return result
    except Exception as e:
        logger.exception(f"Error processing feedback for patient {patient_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.get("/agent/patient/{patient_id}/biomarkers")
async def get_patient_biomarkers(patient_id: str):
    """
    Get latest biomarkers for a patient.
    """
    logger.info(f"Retrieving biomarkers for patient: {patient_id}")
    try:
        if medical_agent.firestore_service:
            biomarkers = await medical_agent.firestore_service.get_latest_biomarkers(patient_id)
            return {
                "status": "success",
                "patient_id": patient_id,
                "biomarkers": biomarkers
            }
        else:
            return {
                "status": "error",
                "message": "Firestore service not available",
                "patient_id": patient_id
            }
    except Exception as e:
        logger.exception(f"Error retrieving biomarkers for patient {patient_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# =============================================================================
# GENETIC ANALYSIS ENDPOINTS
# =============================================================================

@app.post("/genetic/upload")
async def upload_genetic_report(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    report_type: str = Form("unknown")
):
    """
    Upload a genetic report file for analysis
    """
    logger.info(f"Uploading genetic report for user: {user_id}")
    try:
        if not genetic_service:
            raise HTTPException(status_code=503, detail="Genetic analysis service not available")
        
        # Read file data
        file_data = await file.read()
        
        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(file_data) > max_size:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB")
        
        # Upload and process
        report_id = await genetic_service.upload_genetic_report(
            user_id=user_id,
            file_data=file_data,
            filename=file.filename,
            report_type=report_type
        )
        
        return {
            "status": "success",
            "message": "Genetic report uploaded successfully",
            "report_id": report_id,
            "user_id": user_id,
            "filename": file.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error uploading genetic report: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.post("/genetic/analyze")
async def analyze_genetic_file_serverless(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    report_type: str = Form("unknown")
):
    """
    Serverless genetic file analysis - no storage, direct HF inference
    """
    logger.info(f"Serverless genetic analysis for user: {user_id}, file: {file.filename}")
    try:
        if not genetic_service:
            raise HTTPException(status_code=503, detail="Genetic analysis service not available")
        
        # Read file data
        file_data = await file.read()
        
        # Check file size (5MB limit for serverless)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(file_data) > max_size:
            raise HTTPException(status_code=413, detail="File too large for serverless analysis. Maximum size is 5MB")
        
        # Perform serverless analysis
        result = await genetic_service.analyze_file_serverless(
            user_id=user_id,
            file_data=file_data,
            filename=file.filename,
            report_type=report_type
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in serverless genetic analysis: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.get("/genetic/reports/{report_id}")
async def get_genetic_report(report_id: str):
    """
    Get a specific genetic report by ID
    """
    logger.info(f"Retrieving genetic report: {report_id}")
    try:
        if not genetic_service:
            raise HTTPException(status_code=503, detail="Genetic analysis service not available")
        
        report = await genetic_service.get_genetic_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Genetic report not found")
        
        return {
            "status": "success",
            "report": report
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving genetic report: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.get("/genetic/reports/user/{user_id}")
async def get_user_genetic_reports(user_id: str):
    """
    Get all genetic reports for a user
    """
    logger.info(f"Retrieving genetic reports for user: {user_id}")
    try:
        if not genetic_service:
            raise HTTPException(status_code=503, detail="Genetic analysis service not available")
        
        reports = await genetic_service.get_user_reports(user_id)
        
        return {
            "status": "success",
            "user_id": user_id,
            "reports": reports,
            "count": len(reports)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving user genetic reports: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# =============================================================================
# NOTIFICATION ENDPOINTS
# =============================================================================

@app.post("/notifications/create")
async def create_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "general_reminder",
    priority: str = "medium",
    scheduled_time: str = None
):
    """
    Create a new notification for a user
    """
    logger.info(f"Creating notification for user: {user_id}")
    try:
        # Check if notification service is available
        if not notification_service:
            logger.warning("Notification service not available, using Firestore fallback")
            
            # Fallback: Create notification directly in Firestore
            notification_data = {
                'user_id': user_id,
                'title': title,
                'message': message,
                'notification_type': notification_type,
                'priority': priority,
                'created_at': firestore.SERVER_TIMESTAMP,
                'scheduled_time': scheduled_time,
                'status': 'pending'
            }
            
            # Store in Firestore
            notification_ref = db.collection('notifications').document()
            notification_ref.set(notification_data)
            
            return {
                "status": "success",
                "message": "Notification created successfully (fallback mode)",
                "user_id": user_id,
                "notification_id": notification_ref.id
            }
        
        # Use notification service if available
        from .notification_service import NotificationType, NotificationPriority
        
        # Parse notification type and priority
        try:
            notif_type = NotificationType(notification_type)
            notif_priority = NotificationPriority(priority)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid notification type or priority")
        
        # Create notification
        success = await notification_service.send_immediate_notification(
            patient_id=user_id,
            title=title,
            message=message,
            notification_type=notif_type,
            priority=notif_priority
        )
        
        if success:
            return {
                "status": "success",
                "message": "Notification created successfully",
                "user_id": user_id
            }
        else:
            return {
                "status": "error",
                "message": "Failed to create notification",
                "user_id": user_id
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating notification: {e}")
        # Return error response instead of 500 status
        return {
            "status": "error",
            "message": f"Failed to create notification: {str(e)}",
            "user_id": user_id
        }

@app.get("/notifications/user/{user_id}")
async def get_user_notifications(user_id: str, limit: int = 50):
    """
    Get notifications for a user
    """
    logger.info(f"Retrieving notifications for user: {user_id}")
    try:
        if not db:
            logger.warning("Database not available, returning empty notifications")
            return {
                "status": "success",
                "user_id": user_id,
                "notifications": [],
                "count": 0,
                "message": "Database not available"
            }
        
        notifications = []
        
        try:
            # Try to get notifications with ordering first
            notifications_ref = db.collection('notifications')
            query = notifications_ref.where('user_id', '==', user_id).order_by('created_at', direction=firestore.Query.DESCENDING).limit(limit)
            docs = query.get()
            
            for doc in docs:
                notification_data = doc.to_dict()
                notification_data['id'] = doc.id
                notifications.append(notification_data)
                
        except Exception as order_error:
            logger.warning(f"Order by failed, trying without ordering: {order_error}")
            try:
                # Fallback: Get notifications without ordering
                notifications_ref = db.collection('notifications')
                query = notifications_ref.where('user_id', '==', user_id).limit(limit)
                docs = query.get()
                
                for doc in docs:
                    notification_data = doc.to_dict()
                    notification_data['id'] = doc.id
                    notifications.append(notification_data)
                    
                # Sort in Python if we have created_at field
                notifications.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                
            except Exception as fallback_error:
                logger.warning(f"Fallback query also failed: {fallback_error}")
                # Return empty notifications rather than error
                notifications = []
        
        return {
            "status": "success",
            "user_id": user_id,
            "notifications": notifications,
            "count": len(notifications)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving notifications: {e}")
        # Return empty notifications instead of 500 error
        return {
            "status": "error",
            "user_id": user_id,
            "notifications": [],
            "count": 0,
            "error": str(e)
        }

@app.post("/notifications/medication-reminder")
async def create_medication_reminder(
    user_id: str,
    medication_name: str,
    reminder_time: str,
    frequency: str = "daily"
):
    """
    Create a medication reminder
    """
    logger.info(f"Creating medication reminder for user: {user_id}")
    try:
        if not notification_service:
            raise HTTPException(status_code=503, detail="Notification service not available")
        
        from datetime import datetime
        from .notification_service import NotificationType
        
        # Parse reminder time
        try:
            reminder_datetime = datetime.fromisoformat(reminder_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid reminder time format")
        
        # Create reminder
        success = await notification_service.create_medication_reminder(
            patient_id=user_id,
            medication_name=medication_name,
            reminder_time=reminder_datetime,
            frequency=frequency
        )
        
        if success:
            return {
                "status": "success",
                "message": "Medication reminder created successfully",
                "user_id": user_id,
                "medication": medication_name
            }
        else:
            return {
                "status": "error",
                "message": "Failed to create medication reminder",
                "user_id": user_id
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating medication reminder: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# =============================================================================
# TASK MANAGEMENT ENDPOINTS
# =============================================================================

@app.post("/tasks/create")
async def create_task(
    user_id: str,
    title: str,
    description: str,
    due_date: str = None,
    priority: str = "medium",
    task_type: str = "general"
):
    """
    Create a new task for a user
    """
    logger.info(f"Creating task for user: {user_id}")
    try:
        # This would integrate with the notification service for reminders
        # For now, return a placeholder
        return {
            "status": "success",
            "message": "Task created successfully",
            "user_id": user_id,
            "task_id": f"task_{user_id}_{int(datetime.utcnow().timestamp())}",
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
            "task_type": task_type
        }
        
    except Exception as e:
        logger.exception(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.get("/tasks/user/{user_id}")
async def get_user_tasks(user_id: str, status: str = "all"):
    """
    Get tasks for a user
    """
    logger.info(f"Retrieving tasks for user: {user_id}")
    try:
        # This would query the database for user tasks
        # For now, return a placeholder
        return {
            "status": "success",
            "user_id": user_id,
            "tasks": [],
            "count": 0
        }
        
    except Exception as e:
        logger.exception(f"Error retrieving tasks: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# =============================================================================
# USER MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/user/profile/{user_id}")
async def get_user_profile(user_id: str):
    """
    Get user profile information
    """
    logger.info(f"Retrieving profile for user: {user_id}")
    try:
        if not user_data_service:
            raise HTTPException(status_code=503, detail="User data service not available")
        
        profile = await user_data_service.get_user_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        return {
            "status": "success",
            "profile": profile
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving user profile: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.put("/user/profile/{user_id}")
async def update_user_profile(user_id: str, profile_data: dict):
    """
    Update user profile information
    """
    logger.info(f"Updating profile for user: {user_id}")
    try:
        if not user_data_service:
            raise HTTPException(status_code=503, detail="User data service not available")
        
        success = await user_data_service.update_user_profile(user_id, profile_data)
        
        if success:
            return {
                "status": "success",
                "message": "Profile updated successfully",
                "user_id": user_id
            }
        else:
            return {
                "status": "error",
                "message": "Failed to update profile",
                "user_id": user_id
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating user profile: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.post("/files/analyze")
async def analyze_file(file: UploadFile = File(...)):
    try:
        # Ensure Gemini is configured
        if not _gemini_available():
            raise HTTPException(status_code=503, detail="Gemini is not configured. Set GOOGLE_API_KEY or GEMINI_API_KEY.")

        # Read file bytes
        content = await file.read()
        mime = file.content_type or "application/octet-stream"

        # Create a temporary file for upload
        import tempfile
        import os as temp_os
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename or 'upload.txt'}") as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Upload file to Gemini File API
            uploaded = genai.upload_file(
                path=temp_file_path,
                mime_type=mime,
                display_name=file.filename or "upload"
            )

            # Use the configured model from gemini_service ONLY
            model = _gemini_model
            if not model:
                raise Exception("Gemini model not available from gemini_service")
            prompt = (
                "You are a medical assistant. Read the uploaded file and provide: "
                "1) A concise medical summary (<= 8 bullet points). "
                "2) Key biomarkers/values if any. "
                "3) Possible next steps or questions for the clinician. "
                "Return JSON with fields: summary, biomarkers, next_steps."
            )
            resp = model.generate_content([
                prompt,
                uploaded,
            ])

            text = resp.text or ""
            return {"status": "success", "analysis": text}
        finally:
            # Clean up temporary file
            try:
                temp_os.unlink(temp_file_path)
            except:
                pass
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File analysis failed: {e}")

@app.get("/agent/check_gemini_config")
async def check_gemini_config():
    """Check if Gemini API is properly configured"""
    try:
        from .gemini_service import is_gemini_available
        gemini_available = is_gemini_available()
        api_key_env = "GEMINI_API_KEY" if os.getenv("GEMINI_API_KEY") else ("GOOGLE_API_KEY" if os.getenv("GOOGLE_API_KEY") else None)
        return {
            "gemini_configured": gemini_available,
            "message": "Gemini API is properly configured and available" if gemini_available else "Gemini API key not found or invalid",
            "status": "enabled" if gemini_available else "disabled",
            "api_key_present": api_key_env is not None,
            "api_key_env": api_key_env
        }
    except Exception as e:
        return {
            "gemini_configured": False,
            "message": f"Error checking Gemini configuration: {str(e)}",
            "status": "error"
        }

@app.get("/debug/config")
async def debug_config():
    """Debug endpoint: show which critical envs are visible in Cloud Run and basic service availability."""
    try:
        hf_present = bool(os.getenv("HF_TOKEN"))
        gemini_env = "GEMINI_API_KEY" if os.getenv("GEMINI_API_KEY") else ("GOOGLE_API_KEY" if os.getenv("GOOGLE_API_KEY") else None)
        return {
            "env": {
                "GEMINI_KEY_PRESENT": gemini_env is not None,
                "GEMINI_KEY_ENV": gemini_env,
                "HF_TOKEN_PRESENT": hf_present,
                "ALLOWED_ORIGINS": os.getenv("ALLOWED_ORIGINS"),
                "SMPL_ASSETS_BASE_URL": os.getenv("SMPL_ASSETS_BASE_URL"),
            },
            "services": {
                "gemini_available": _gemini_available(),
                "genetic_service": bool(genetic_service is not None),
                "hf_client_initialized": bool(getattr(genetic_service, "hf_client", None)) if genetic_service else False,
                "context_retriever": bool(getattr(medical_agent, "context_retriever", None)),
            }
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/hf_test")
async def debug_hf_test():
    """Debug endpoint: run a minimal HF token_classification with a tiny input to verify HF_TOKEN works."""
    try:
        if not genetic_service or not getattr(genetic_service, "hf_client", None):
            return {"ok": False, "why": "HF client not initialized", "HF_TOKEN_PRESENT": bool(os.getenv("HF_TOKEN"))}
        client = genetic_service.hf_client
        sample = "BRCA1 variant"
        res = client.token_classification(sample, model="OpenMed/OpenMed-NER-GenomeDetect-SuperClinical-434M")
        return {"ok": True, "count": len(res), "sample": sample, "first": res[0] if res else None}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/debug/gemini_test")
async def debug_gemini_test():
    """Debug endpoint: test Gemini API connection at runtime"""
    from .gemini_service import test_gemini_connection
    return await test_gemini_connection()

# Consolidated deep-diagnostic endpoint for Gemini, HF, and ContextRetriever
@app.get("/debug/full_diagnostics")
async def full_diagnostics(patient_id: str | None = None, sample_text: str | None = "BRCA1 variant and TP53 mutation"):
    try:
        diagnostics: Dict[str, Any] = {"env": {}, "gemini": {}, "hf": {}, "context": {}}
        # Env
        diagnostics["env"] = {
            "GEMINI_KEY_PRESENT": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
            "GEMINI_KEY_ENV": "GEMINI_API_KEY" if os.getenv("GEMINI_API_KEY") else ("GOOGLE_API_KEY" if os.getenv("GOOGLE_API_KEY") else None),
            "HF_TOKEN_PRESENT": bool(os.getenv("HF_TOKEN")),
        }
        # Gemini
        try:
            from .gemini_service import is_gemini_available
            diagnostics["gemini"]["available"] = bool(is_gemini_available())
        except Exception as e:
            diagnostics["gemini"]["error"] = str(e)
        # HF
        try:
            if genetic_service and getattr(genetic_service, "hf_client", None):
                client = genetic_service.hf_client
                res = client.token_classification(sample_text or "BRCA1 variant", model="OpenMed/OpenMed-NER-GenomeDetect-SuperClinical-434M")
                diagnostics["hf"] = {"ok": True, "count": len(res), "first": res[0] if res else None}
            else:
                diagnostics["hf"] = {"ok": False, "why": "HF client not initialized"}
        except Exception as e:
            diagnostics["hf"] = {"ok": False, "error": str(e)}
        # Context retriever
        try:
            ctx_preview = None
            if patient_id and medical_agent and getattr(medical_agent, "context_retriever", None):
                ctx_preview = await medical_agent.context_retriever.retrieve(patient_id, "diagnostics check", max_chars=800)
            diagnostics["context"] = {
                "has_retriever": bool(getattr(medical_agent, "context_retriever", None) is not None),
                "preview_tokens": (ctx_preview or {}).get("approx_tokens") if ctx_preview else None,
                "preview_excerpt": (ctx_preview or {}).get("trimmed_context_text", "")[:200] if ctx_preview else None,
            }
        except Exception as e:
            diagnostics["context"] = {"error": str(e)}
        return diagnostics
    except Exception as e:
        return {"error": str(e)}

# To run this app directly (for development):
# uvicorn ai_fastapi_agent.ai-services.main_agent.main:app --reload
# Ensure your PYTHONPATH is set up correctly if you run it this way,
# or run from the ai-services directory: uvicorn main_agent.main:app --reload

# if __name__ == "__main__":
#     # This is for development only. For production, use a process manager like Gunicorn with Uvicorn workers.
#     uvicorn.run(app, host="0.0.0.0", port=8000) 