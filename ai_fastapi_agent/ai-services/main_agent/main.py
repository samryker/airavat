from fastapi import FastAPI, HTTPException
from .data_models import PatientQuery, AgentResponse
from .agent_core import MedicalAgent
import uvicorn # For running the app directly if needed
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

app = FastAPI(
    title="Airavat Medical Agent API",
    description="API for interacting with the AI Medical Agent.",
    version="0.1.0",
)

# --- Firebase Admin SDK Initialization ---
try:
    # Path to your service account key file
    # IMPORTANT: Set GOOGLE_APPLICATION_CREDENTIALS in your environment
    # or provide the path directly. For local dev, you can use a relative path
    # but ensure it's .gitignored.
    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", "firebase-service-account-key.json") # Default for local
    
    # Check if the credentials file exists if a path is provided
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and not os.path.exists(cred_path):
        print(f"Warning: Firebase credentials file not found at {cred_path}. Firebase features will not work.")
        db = None # Firestore client
    else:
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            # GOOGLE_APPLICATION_CREDENTIALS is set, SDK will use it
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK initialized using GOOGLE_APPLICATION_CREDENTIALS.")
        else:
            # Use the local file path
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            print(f"Firebase Admin SDK initialized using {cred_path}.")
        
        db = firestore.client() # Initialize Firestore client
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")
    db = None # Ensure db is None if initialization fails
# --- End Firebase Admin SDK Initialization ---


# Initialize the agent globally or manage its lifecycle as needed
# For simplicity, a single global instance is created here.
# In a production system, you might manage this differently (e.g., with dependency injection).
medical_agent = MedicalAgent(db=db) # Pass Firestore client to the agent

@app.post("/agent/query", response_model=AgentResponse)
async def query_agent(patient_query: PatientQuery):
    """
    Receives a patient query, processes it through the Medical Agent,
    and returns the agent's response including any treatment suggestions.
    """
    try:
        # The agent instance now has access to db if initialized
        response = await medical_agent.process_query(patient_query)
        return response
    except Exception as e:
        # Log the exception for debugging
        print(f"Error processing agent query: {e}")
        # You might want to return a more specific error response structure
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Airavat Medical Agent API. Use the /agent/query endpoint to interact with the agent."}

# To run this app directly (for development):
# uvicorn ai_fastapi_agent.ai-services.main_agent.main:app --reload
# Ensure your PYTHONPATH is set up correctly if you run it this way,
# or run from the ai-services directory: uvicorn main_agent.main:app --reload

# if __name__ == "__main__":
#     # This is for development only. For production, use a process manager like Gunicorn with Uvicorn workers.
#     uvicorn.run(app, host="0.0.0.0", port=8000) 