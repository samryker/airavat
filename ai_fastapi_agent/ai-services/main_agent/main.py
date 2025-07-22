from fastapi import FastAPI, HTTPException
from .data_models import PatientQuery, AgentResponse, FeedbackDataModel, TreatmentPlanUpdate
from .agent_core import MedicalAgent
from .mcp_medical_agent import MCPMedicalAgent
from .firestore_service import FirestoreService
from mcp_config import get_mcp_db_engine, is_mcp_available
import uvicorn # For running the app directly if needed
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
import logging # Added logging
from typing import Dict, Any
from fastapi.middleware.cors import CORSMiddleware

load_dotenv() # Load environment variables from .env

# Setup logging for the main application
logger = logging.getLogger("api") # Can use a specific name
logging.basicConfig(level=logging.INFO) # Basic config, can be more sophisticated

app = FastAPI(
    title="Airavat Medical Agent API",
    description="API for interacting with the AI Medical Agent, including dynamic planning and RL-based feedback.",
    version="0.2.0", # Incremented version
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://airavat-a3a10.web.app",  # Firebase hosting domain
        "https://airavat-a3a10.firebaseapp.com",  # Alternative Firebase domain
        "http://localhost:3000",  # Local development
        "http://localhost:3001",  # Local development
        "http://127.0.0.1:3000",  # Local development
        "http://127.0.0.1:3001",  # Local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        # Local development - use service account key file
        cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", "airavat-a3a10-firebase-adminsdk-fbsvc-7b24d935c3.json")
        
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            logger.info(f"Firebase Admin SDK initialized using {cred_path}.")
            db = firestore.client()
        else:
            logger.warning(f"Warning: Firebase credentials file not found at {cred_path}. Firebase features will be severely limited.")
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
    if is_mcp_available():
        mcp_db_engine = get_mcp_db_engine()
        if mcp_db_engine:
            logger.info("MCP database engine initialized successfully.")
            
            # Initialize MCP Medical Agent with database engine and Firestore service
            firestore_service = FirestoreService(db) if db else None
            mcp_agent = MCPMedicalAgent(
                db_engine=mcp_db_engine,
                firestore_service=firestore_service
            )
            logger.info("MCP Medical Agent initialized successfully with lifelong memory capabilities.")
        else:
            logger.warning("MCP database engine could not be initialized. MCP features will be unavailable.")
    else:
        logger.info("MCP is not available (missing environment variables or dependencies). MCP features will be unavailable.")
except Exception as e:
    logger.exception(f"Error initializing MCP components: {e}")
    mcp_agent = None
    mcp_db_engine = None
# --- End MCP Database Engine Initialization ---

# Initialize the agent globally or manage its lifecycle as needed
# For simplicity, a single global instance is created here.
# In a production system, you might manage this differently (e.g., with dependency injection).
medical_agent = MedicalAgent(db=db, mcp_agent=mcp_agent) # Pass Firestore client and MCP agent to the agent

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
    """
    Health check endpoint to verify the API is running and check service status.
    """
    health_status = {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",  # You can add actual timestamp logic
        "services": {
            "firestore": "available" if medical_agent.db else "unavailable",
            "mcp_agent": "available" if medical_agent.mcp_agent else "unavailable",
            "mcp_database": "available" if mcp_db_engine else "unavailable"
        },
        "mcp_config": {
            "available": is_mcp_available(),
            "db_type": os.getenv("MCP_DB_TYPE", "not_set")
        }
    }
    return health_status

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Airavat Medical Agent API. Use /agent/query, /agent/feedback, /agent/memory/{patient_id}, and /agent/update_treatment_plan endpoints."}

@app.get("/agent/patient/{patient_id}/context")
async def get_patient_context(patient_id: str):
    """
    Get complete patient context including profile, treatment plans, biomarkers, and conversation history.
    This provides the digital twin with comprehensive patient information.
    """
    logger.info(f"Retrieving complete context for patient: {patient_id}")
    try:
        context = await medical_agent.get_patient_context(patient_id)
        return {
            "status": "success",
            "patient_id": patient_id,
            "context": context,
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        logger.exception(f"Error retrieving context for patient {patient_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.get("/agent/patient/{patient_id}/conversation-history")
async def get_conversation_history(patient_id: str, limit: int = 10):
    """
    Get conversation history for a patient from Firestore interaction logs.
    """
    logger.info(f"Retrieving conversation history for patient: {patient_id}")
    try:
        if medical_agent.firestore_service:
            history = await medical_agent.firestore_service.get_conversation_history(patient_id, limit)
            return {
                "status": "success",
                "patient_id": patient_id,
                "conversation_history": history,
                "count": len(history),
                "limit": limit
            }
        else:
            return {
                "status": "error",
                "message": "Firestore service not available",
                "patient_id": patient_id
            }
    except Exception as e:
        logger.exception(f"Error retrieving conversation history for patient {patient_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

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

# To run this app directly (for development):
# uvicorn ai_fastapi_agent.ai-services.main_agent.main:app --reload
# Ensure your PYTHONPATH is set up correctly if you run it this way,
# or run from the ai-services directory: uvicorn main_agent.main:app --reload

# if __name__ == "__main__":
#     # This is for development only. For production, use a process manager like Gunicorn with Uvicorn workers.
#     uvicorn.run(app, host="0.0.0.0", port=8000) 