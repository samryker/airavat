import os
from dotenv import load_dotenv
# from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any, Optional
from .firestore_service import FirestoreService

load_dotenv()
# Gemini LLM removed for security reasons
# gemini_planner_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-thinking-exp-01-21")  # API key removed

async def generate_dynamic_plan(patient_id: str, 
                                current_patient_context: Dict[str, Any], 
                                firestore_service: FirestoreService, 
                                current_query_text: Optional[str] = None) -> Dict[str, Any]:
    """
    LLM creates a forward-looking treatment goal plan, incorporating past plans.
    Args:
        patient_id: The ID of the patient.
        current_patient_context: Dict containing current data like {"hemoglobin": 10, "risk_assessment": "...", "therapy": "..."}.
        firestore_service: Instance of FirestoreService to interact with plan history.
        current_query_text: The user's current query/input that triggered this plan generation.
    Returns:
        A dictionary containing the generated plan and potentially other metadata.
        e.g., {"plan_text": "...", "referenced_history_count": 1}
    """
    
    # 1. Fetch previous plan history (e.g., the latest plan)
    # The number of historical plans to fetch can be a parameter or a fixed number.
    plan_history = await firestore_service.get_plan_history(patient_id, limit=1) 
    previous_plan_text = "No previous plan on record." # Default if no history
    referenced_history_count = 0

    if plan_history:
        # Assuming the latest plan is the most relevant
        # The structure of plan_history items is { "timestamp": ..., "plan_details": ..., "plan_id": ... }
        # And plan_details might be {"plan_text": "..."}
        latest_plan = plan_history[0]
        if latest_plan.get("plan_details") and latest_plan["plan_details"].get("plan_text"):
            previous_plan_text = latest_plan["plan_details"]["plan_text"]
            referenced_history_count = 1
            print(f"Retrieved previous plan for patient {patient_id}: {previous_plan_text[:100]}...")
        else:
            print(f"Previous plan found for patient {patient_id} but content is missing or not in expected format.")

    # 2. Extract current context data
    hemoglobin = current_patient_context.get("hemoglobin", "N/A")
    risk_notes = current_patient_context.get("risk_assessment", "N/A")
    therapy = current_patient_context.get("therapy", "N/A")

    # 3. Create a simple fallback plan since langchain is not available
    plan_text = f"""
    **Treatment Plan for Patient {patient_id}**
    
    Current Status:
    - Hemoglobin: {hemoglobin}
    - Therapy: {therapy}
    - Risk Assessment: {risk_notes}
    
    Immediate Steps:
    • Continue current therapy as prescribed
    • Monitor hemoglobin levels regularly
    • Schedule follow-up appointment within 2 weeks
    
    Dietary Recommendations:
    • Maintain iron-rich diet
    • Stay hydrated
    • Follow any specific dietary restrictions from your doctor
    
    Next Steps:
    • Schedule next lab work in 2 weeks
    • Contact your healthcare provider if symptoms worsen
    • Keep a symptom diary
    
    Previous Plan Reference: {previous_plan_text[:100]}...
    
    Note: This is a basic plan. Please consult your healthcare provider for personalized medical advice.
    """

    # 5. Prepare plan data for storage
    plan_output_data = {
        "plan_text": plan_text,
        "referenced_history_count": referenced_history_count,
        "model_used": "fallback_planner" # Storing which model was used
    }

    # 6. Store the new plan (asynchronously, but wait for it if its ID is needed immediately)
    # The query_text used for storage should ideally be the one that led to this specific plan generation.
    new_plan_id = await firestore_service.store_plan(patient_id, plan_output_data, query_text=current_query_text)
    print(f"New plan stored for patient {patient_id} with ID: {new_plan_id}")

    return plan_output_data # Return the generated plan data
