from .data_models import PatientQuery, AgentResponse, TreatmentSuggestion, StructuredGeminiOutput, GeminiResponseFeatures, FeedbackDataModel
from .gemini_service import get_treatment_suggestion_from_gemini
from .firestore_service import FirestoreService
from .planner import generate_dynamic_plan
from .rl_service import PatientRLAgent, determine_severity_level, calculate_reward
from .mcp_medical_agent import MCPMedicalAgent
from firebase_admin import firestore
from typing import List, Dict, Any, Optional
import uuid
import logging
import asyncio
import datetime

logger = logging.getLogger(__name__)
# Assuming basicConfig is set elsewhere or you can set it here if this is the main entry for this logger

class MedicalAgent:
    def __init__(self, db: Optional[firestore.client] = None, mcp_agent: Optional[MCPMedicalAgent] = None):
        """
        Initializes the MedicalAgent with MCP support for lifelong memory.
        Args:
            db: An initialized Firestore client from firebase_admin.firestore.
            mcp_agent: MCP-based medical agent for persistent memory and context.
        """
        self.db = db
        self.mcp_agent = mcp_agent
        self.patient_rl_agents: Dict[str, PatientRLAgent] = {} # Cache for RL agents
        
        if self.db:
            logger.info("MedicalAgent initialized with Firestore client.")
            self.firestore_service = FirestoreService(db)
        else:
            logger.warning("Warning: MedicalAgent initialized WITHOUT Firestore client. Contextual data, planner, and RL features will be limited.")
            self.firestore_service = None
            
        if self.mcp_agent:
            logger.info("MedicalAgent initialized with MCP agent for lifelong memory.")
        else:
            logger.warning("Warning: MedicalAgent initialized WITHOUT MCP agent. Lifelong memory features will be limited.")

    async def _get_or_create_rl_agent(self, patient_id: str) -> Optional[PatientRLAgent]:
        if not self.db: # RL Agent requires DB
            logger.warning(f"RL Agent cannot be created for {patient_id}: Firestore DB not available.")
            return None
        if patient_id not in self.patient_rl_agents:
            logger.info(f"Creating new RL agent instance for patient: {patient_id}")
            agent = PatientRLAgent(patient_id, self.db)
            try:
                await agent.load_model() # Load existing model from Firestore
            except Exception as e_load:
                logger.error(f"Error loading RL model for patient {patient_id}: {e_load}")
                # Agent still created but with an empty Q-table
            self.patient_rl_agents[patient_id] = agent
        return self.patient_rl_agents[patient_id]

    async def get_patient_data(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Fetches the main patient document from the 'patients' collection."""
        if not self.db: return None
        try:
            patient_doc_ref = self.db.collection(u'patients').document(patient_id)
            patient_doc = await patient_doc_ref.get() 
            if patient_doc.exists:
                return patient_doc.to_dict()
            logger.info(f"No document found for patient_id: {patient_id} in 'patients' collection.")
            return None
        except Exception as e:
            logger.error(f"Error fetching patient data for {patient_id}: {e}")
            return None

    async def get_lab_reports_metadata(self, patient_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetches lab report metadata from a subcollection 'lab_reports'."""
        if not self.db: return []
        reports = []
        try:
            reports_query = self.db.collection(u'patients').document(patient_id).collection(u'lab_reports').order_by(u'reportDate', direction=firestore.Query.DESCENDING).limit(limit)
            docs_stream = reports_query.stream() 
            async for doc in docs_stream:
                reports.append(doc.to_dict())
            if not reports:
                logger.info(f"No lab reports found in subcollection for patient {patient_id}")
            return reports
        except Exception as e:
            logger.error(f"Error fetching lab reports metadata for {patient_id}: {e}")
            return []
            
    async def get_patient_context_from_firestore(self, patient_id: str) -> Dict[str, Any]:
        """Fetches and structures comprehensive patient context from Firestore."""
        if not self.db:
            return {"error": "Firestore client not available."}
        
        if not patient_id:
            return {"error": "Patient ID is required to fetch context."}

        logger.info(f"Attempting to fetch comprehensive context for patient ID: {patient_id}")
        context_data = {}
        errors = []
        patient_document_data = await self.get_patient_data(patient_id)

        if patient_document_data:
            context_data["patient_record"] = patient_document_data 
        else:
            errors.append(f"Critical: Patient document not found for ID '{patient_id}' in 'patients' collection.")
            return {"error": ". ".join(errors), "data_from_firestore": context_data} 

        lab_reports_meta = await self.get_lab_reports_metadata(patient_id, limit=5)
        if lab_reports_meta:
            if "patient_record" not in context_data:
                 context_data["patient_record"] = {}
            context_data["patient_record"]["recent_lab_reports_metadata"] = lab_reports_meta
        else:
            logger.info(f"No lab reports metadata retrieved for patient {patient_id}.")

        if not context_data.get("patient_record"):
             return {"error": f"No data found in Firestore for patient ID '{patient_id}'.", "data_from_firestore": {}}
            
        return {"patient_id": patient_id, "data_from_firestore": context_data, "fetch_errors": errors if errors else None}

    async def process_query(self, patient_query: PatientQuery) -> AgentResponse:
        """Process a patient query with enhanced context and memory"""
        try:
            # Log the interaction to Firestore for conversation history
            await self._log_interaction(patient_query)
            
            # Use MCP agent if available, otherwise fallback to basic agent
            if self.mcp_agent:
                print(f"Using MCP agent for patient {patient_query.patient_id}")
                response = await self.mcp_agent.process_query(patient_query)
            else:
                print(f"Using fallback agent for patient {patient_query.patient_id}")
                response = await self._fallback_process_query(patient_query)
            
            # Log the response
            await self._log_response(patient_query.patient_id, response)
            
            return response
            
        except Exception as e:
            print(f"Error processing query: {e}")
            return AgentResponse(
                request_id=patient_query.request_id,
                response_text=f"I apologize, but I encountered an error processing your request. Please try again or contact support if the issue persists. Error: {str(e)}",
                suggestions=[]
            )

    async def _log_interaction(self, patient_query: PatientQuery):
        """Log patient interaction to Firestore for conversation history"""
        if not self.firestore_service:
            return
            
        try:
            interaction_data = {
                'patient_id': patient_query.patient_id,
                'query_text': patient_query.query_text,
                'timestamp': datetime.datetime.utcnow(),
                'symptoms': patient_query.symptoms or [],
                'medical_history': patient_query.medical_history or [],
                'current_medications': patient_query.current_medications or [],
                'additional_data': patient_query.additional_data or {},
                'session_id': f"session_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            }
            
            # Store in interaction_logs collection
            doc_ref = self.firestore_service.db.collection('interaction_logs').document()
            await doc_ref.set(interaction_data)
            print(f"Logged interaction for patient {patient_query.patient_id}")
            
        except Exception as e:
            print(f"Error logging interaction: {e}")

    async def _log_response(self, patient_id: str, response: AgentResponse):
        """Log AI response to Firestore"""
        if not self.firestore_service:
            return
            
        try:
            response_data = {
                'patient_id': patient_id,
                'request_id': response.request_id,
                'response_text': response.response_text,
                'timestamp': datetime.datetime.utcnow(),
                'suggestions_count': len(response.suggestions) if response.suggestions else 0
            }
            
            # Store in response_logs collection
            doc_ref = self.firestore_service.db.collection('response_logs').document()
            await doc_ref.set(response_data)
            print(f"Logged response for patient {patient_id}")
            
        except Exception as e:
            print(f"Error logging response: {e}")

    async def get_patient_context(self, patient_id: str) -> Dict[str, Any]:
        """Get complete patient context including profile, treatment plans, and conversation history"""
        try:
            if self.firestore_service:
                return await self.firestore_service.get_complete_patient_context(patient_id)
            else:
                return {"error": "Firestore service not available"}
        except Exception as e:
            print(f"Error getting patient context: {e}")
            return {"error": str(e)}

    async def update_patient_treatment_plan(self, patient_id: str, treatment_plan: Dict[str, Any]) -> bool:
        """Update patient's treatment plan in Firestore"""
        try:
            if self.firestore_service:
                # Get current patient data
                patient_data = await self.firestore_service.get_patient_data(patient_id)
                if patient_data:
                    # Update treatment plans
                    current_plans = patient_data.get('treatmentPlans', [])
                    current_plans.append(treatment_plan)
                    
                    # Update patient document
                    await self.firestore_service.db.collection('patients').document(patient_id).update({
                        'treatmentPlans': current_plans,
                        'updatedAt': datetime.datetime.utcnow()
                    })
                    
                    # Update MCP memory if available
                    if self.mcp_agent:
                        await self.mcp_agent.update_treatment_plan(patient_id, treatment_plan)
                    
                    print(f"Updated treatment plan for patient {patient_id}")
                    return True
                else:
                    print(f"No patient data found for {patient_id}")
                    return False
            else:
                print("Firestore service not available")
                return False
        except Exception as e:
            print(f"Error updating treatment plan: {e}")
            return False

    async def _log_interaction_for_feedback(self, request_id: str, log_data: Dict[str, Any]):
        """Logs interaction data for feedback processing."""
        if not self.db: return
        try:
            feedback_collection = self.db.collection(u'interaction_logs')
            await feedback_collection.document(request_id).set(log_data)
            logger.info(f"Interaction logged for feedback: {request_id}")
        except Exception as e:
            logger.error(f"Error logging interaction for feedback: {e}")

    async def process_feedback(self, feedback_data: FeedbackDataModel) -> Dict[str, Any]:
        """Processes feedback for continuous learning."""
        if not self.db:
            return {"status": "error", "message": "Database not available for feedback processing."}
        
        try:
            # Log feedback
            feedback_collection = self.db.collection(u'feedback')
            await feedback_collection.document(feedback_data.request_id).set({
                "patient_id": feedback_data.patient_id,
                "request_id": feedback_data.request_id,
                "outcome_works": feedback_data.outcome_works,
                "feedback_text": feedback_data.feedback_text,
                "timestamp": asyncio.get_event_loop().time()
            })

            # Update RL agent if available
            patient_rl_agent = await self._get_or_create_rl_agent(feedback_data.patient_id)
            if patient_rl_agent:
                try:
                    # Get the original interaction
                    interaction_collection = self.db.collection(u'interaction_logs')
                    interaction_doc = await interaction_collection.document(feedback_data.request_id).get()
                    
                    if interaction_doc.exists:
                        interaction_data = interaction_doc.to_dict()
                        severity_level = interaction_data.get("severity_level", "medium")
                        reward = calculate_reward(feedback_data.outcome_works, severity_level)
                        await patient_rl_agent.update_model(severity_level, reward)
                        logger.info(f"RL agent updated for patient {feedback_data.patient_id} with reward {reward}")
                except Exception as e:
                    logger.error(f"Error updating RL agent: {e}")

            return {"status": "success", "message": "Feedback processed successfully."}
        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
            return {"status": "error", "message": f"Error processing feedback: {str(e)}"}

    async def get_patient_memory(self, patient_id: str) -> Dict[str, Any]:
        """Get patient's complete memory and context using MCP agent."""
        if self.mcp_agent:
            return await self.mcp_agent.get_patient_memory(patient_id)
        else:
            logger.warning("MCP agent not available for memory retrieval")
            return {}

    async def update_treatment_plan(self, patient_id: str, treatment_plan: Dict[str, Any]) -> bool:
        """Update patient's treatment plan using MCP agent."""
        if self.mcp_agent:
            return await self.mcp_agent.update_treatment_plan(patient_id, treatment_plan)
        else:
            logger.warning("MCP agent not available for treatment plan updates")
            return False

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