from .data_models import PatientQuery, AgentResponse, TreatmentSuggestion
from .gemini_service import get_treatment_suggestion_from_gemini
from firebase_admin import firestore
from typing import List, Dict, Any, Optional
# We will integrate LangChain here later for more complex agent logic, tools, and memory.

class MedicalAgent:
    def __init__(self, db: Optional[firestore.client] = None):
        """
        Initializes the MedicalAgent.
        Args:
            db: An initialized Firestore client from firebase_admin.firestore.
        """
        self.db = db
        if self.db:
            print("MedicalAgent initialized with Firestore client.")
        else:
            print("Warning: MedicalAgent initialized WITHOUT Firestore client. Contextual data will be unavailable.")

    async def get_patient_data(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Fetches the main patient document from the 'patients' collection."""
        if not self.db: return None
        try:
            # Corrected collection name to 'patients'
            patient_doc_ref = self.db.collection(u'patients').document(patient_id)
            patient_doc = await patient_doc_ref.get()
            if patient_doc.exists:
                return patient_doc.to_dict()
            print(f"No document found for patient_id: {patient_id} in 'patients' collection.")
            return None
        except Exception as e:
            print(f"Error fetching patient data for {patient_id}: {e}")
            return None

    async def get_lab_reports_metadata(self, patient_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """ 
        Placeholder: Fetches lab report metadata from a subcollection 'lab_reports'.
        Adjust this based on actual Firestore structure for lab reports.
        """
        if not self.db: return []
        reports = []
        try:
            # ASSUMPTION: Lab reports are in a subcollection named 'lab_reports'
            # Order by 'reportDate' descending if such a field exists
            reports_query = self.db.collection(u'patients').document(patient_id).collection(u'lab_reports').order_by(u'reportDate', direction=firestore.Query.DESCENDING).limit(limit)
            docs_stream = await reports_query.stream()
            async for doc in docs_stream:
                reports.append(doc.to_dict())
            if not reports:
                print(f"No lab reports found in subcollection for patient {patient_id}")
            return reports
        except Exception as e:
            # This will often fail if the subcollection or 'reportDate' field doesn't exist as assumed.
            print(f"Error fetching lab reports metadata for {patient_id} (check Firestore structure and indexes): {e}")
            print("Common reasons: Subcollection 'lab_reports' doesn't exist, or field 'reportDate' for ordering is missing, or Firestore indexes are not set up for this query.")
            return []
            
    async def get_patient_context_from_firestore(self, patient_id: str) -> Dict[str, Any]:
        """
        Fetches and structures comprehensive patient context from Firestore.
        This assumes a specific Firestore structure:
        - 'patients/{patient_id}' for profile
        - 'patients/{patient_id}/lab_reports' for lab reports (ordered, limited)
        """
        if not self.db:
            return {"error": "Firestore client not available."}
        
        if not patient_id:
            return {"error": "Patient ID is required to fetch context."}

        print(f"Attempting to fetch comprehensive context for patient ID: {patient_id}")

        context_data = {}
        errors = []

        patient_document_data = await self.get_patient_data(patient_id)

        if patient_document_data:
            # Patient profile and embedded treatment plans are in patient_document_data
            context_data["patient_record"] = patient_document_data 
            # No separate fetch for treatment plans needed as they are embedded.
            # Treatment plans are expected under patient_document_data['treatmentPlans'] (List of Maps)
        else:
            errors.append(f"Critical: Patient document not found for ID '{patient_id}' in 'patients' collection.")
            return {"error": ". ".join(errors), "data_from_firestore": context_data}

        # Fetch lab reports metadata (placeholder - adjust based on actual structure)
        lab_reports_meta = await self.get_lab_reports_metadata(patient_id, limit=5)
        if lab_reports_meta:
            # Add to context_data under a specific key if found
            context_data["patient_record"]["recent_lab_reports_metadata"] = lab_reports_meta
        else:
            print(f"No lab reports metadata retrieved for patient {patient_id}. This might be normal or indicate an issue with fetching/structure.")

        if not context_data.get("patient_record"):
             return {"error": f"No data found in Firestore for patient ID '{patient_id}'.", "data_from_firestore": {}}
            
        return {"patient_id": patient_id, "data_from_firestore": context_data, "fetch_errors": errors if errors else None}

    async def process_query(self, patient_query: PatientQuery) -> AgentResponse:
        """
        Processes the patient query, incorporating context from Firestore if available,
        and then gets treatment suggestions from Gemini.
        """
        print(f"Processing query for patient: {patient_query.patient_id}")
        print(f"Query text: {patient_query.query_text}")

        # 1. Fetch patient context from Firestore
        effective_firestore_context = {} # This will hold the data to be passed to Gemini
        raw_firestore_result = {} # This holds the full result from get_patient_context_from_firestore

        if patient_query.patient_id and self.db:
            print(f"Fetching Firestore context for patient: {patient_query.patient_id}")
            raw_firestore_result = await self.get_patient_context_from_firestore(patient_query.patient_id)
            
            if raw_firestore_result.get("error"):
                print(f"Warning/Error during Firestore context fetch: {raw_firestore_result.get('error')}")
                if raw_firestore_result.get("data_from_firestore", {}).get("patient_record"):
                    print("Proceeding with potentially partial patient record context.")
                    effective_firestore_context = {"data_from_firestore": raw_firestore_result.get("data_from_firestore")}
                # else, effective_firestore_context remains empty, and Gemini gets no specific record data
            elif raw_firestore_result.get("data_from_firestore"):
                effective_firestore_context = {"data_from_firestore": raw_firestore_result.get("data_from_firestore")}
        
        # Include any fetch_errors in the context if they exist, for Gemini to be aware
        if raw_firestore_result and raw_firestore_result.get("fetch_errors"):
            if not effective_firestore_context.get("data_from_firestore"):
                effective_firestore_context["data_from_firestore"] = {}
            if not effective_firestore_context["data_from_firestore"].get("patient_record"):
                effective_firestore_context["data_from_firestore"]["patient_record"] = {}
            effective_firestore_context["data_from_firestore"]["patient_record"]["context_fetch_warnings"] = raw_firestore_result.get("fetch_errors")

        # 2. Get treatment suggestion using Gemini (or other LLM)
        treatment_suggestion_text = await get_treatment_suggestion_from_gemini(
            patient_query=patient_query, 
            firestore_context=effective_firestore_context # Pass the structured context
        )

        return AgentResponse(
            request_id=patient_query.patient_id + "_" + str(hash(patient_query.query_text)), # Example request ID
            response_text="Based on your query and available context, here are some initial thoughts.",
            suggestions=[TreatmentSuggestion(suggestion_text=treatment_suggestion_text, confidence_score=0.85)] # Example
        )

# Example of how you might use it (won't be run from here directly in FastAPI context)
# async def example_usage():
#     # This example requires a running Firestore emulator or actual Firebase connection
#     # and the service account key to be correctly set up.
#     # For simplicity, direct instantiation with None for db if not testing Firestore part.
#     agent = MedicalAgent(db=None) # Pass a mock/real db instance for full test
#     query = PatientQuery(
#         patient_id="test_patient_001",
#         query_text="I've had a headache and nausea for two days.",
#         symptoms=["headache", "nausea"],
#         medical_history=["migraine"],
#         current_medications=["painkiller"]
#     )
#     response = await agent.process_query(query)
#     print(f"Request ID: {response.request_id}")
#     print(f"Response Text: {response.response_text}")
#     if response.suggestions:
#         for suggestion in response.suggestions:
#             print(f"- Suggestion: {suggestion.suggestion_text} (Confidence: {suggestion.confidence_score})")

# if __name__ == '__main__':
#     import asyncio
#     # Ensure you have a .env file with GEMINI_API_KEY and firebase service account setup
#     # to run this example directly with Firestore integration.
#     # You would also need to initialize firebase_admin in this scope if not done by FastAPI startup.
#     asyncio.run(example_usage()) 