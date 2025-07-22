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

    async def _fallback_process_query(self, patient_query: PatientQuery) -> AgentResponse:
        """Fallback method to process queries when MCP agent is not available"""
        try:
            # Get patient context from multiple sources
            patient_context = {}
            
            # First try to get from Firestore
            if self.firestore_service:
                try:
                    patient_context = await self.get_patient_context(patient_query.patient_id)
                except Exception as e:
                    print(f"Error getting patient context from Firestore: {e}")
                    patient_context = {}
            
            # Then check if patient context is provided in additional_data
            if patient_query.additional_data and patient_query.additional_data.get("patient_context"):
                # Merge with Firestore data, with additional_data taking precedence
                firestore_context = patient_context
                additional_context = patient_query.additional_data["patient_context"]
                
                # Merge the contexts
                if isinstance(firestore_context, dict) and isinstance(additional_context, dict):
                    patient_context = {**firestore_context, **additional_context}
                else:
                    patient_context = additional_context
                
                print(f"Using patient context from additional_data: {patient_context}")
            
            # Use the actual Gemini service instead of hardcoded responses
            firestore_context = {
                "data_from_firestore": {
                    "patient_record": patient_context
                }
            }
            
            # Call the real Gemini API
            gemini_response = await get_treatment_suggestion_from_gemini(patient_query, firestore_context)
            
            # Create suggestions from Gemini response
            suggestions = [
                TreatmentSuggestion(
                    suggestion_text=gemini_response.text,
                    confidence_score=0.9,
                    supporting_evidence_ids=None
                )
            ]
            
            # Add additional suggestions based on response features
            if gemini_response.features and gemini_response.features.actionable_steps_present:
                suggestions.append(
                    TreatmentSuggestion(
                        suggestion_text="Follow up with your healthcare provider for personalized advice",
                        confidence_score=0.8
                    )
                )
            
            return AgentResponse(
                request_id=patient_query.request_id,
                response_text=gemini_response.text,
                suggestions=suggestions
            )
            
        except Exception as e:
            print(f"Error in fallback query processing: {e}")
            # Even in error case, try to get a basic response from Gemini
            try:
                basic_query = PatientQuery(
                    patient_id=patient_query.patient_id,
                    query_text=patient_query.query_text,
                    request_id=patient_query.request_id
                )
                gemini_response = await get_treatment_suggestion_from_gemini(basic_query, None)
                return AgentResponse(
                    request_id=patient_query.request_id,
                    response_text=gemini_response.text,
                    suggestions=[
                        TreatmentSuggestion(
                            suggestion_text=gemini_response.text,
                            confidence_score=0.7
                        )
                    ]
                )
            except Exception as gemini_error:
                print(f"Error calling Gemini API: {gemini_error}")
                return AgentResponse(
                    request_id=patient_query.request_id,
                    response_text="I apologize, but I'm having trouble processing your request right now. Please try again later or contact your healthcare provider directly.",
                    suggestions=[]
                )

    def _generate_headache_response(self, patient_context: Dict[str, Any], query: str) -> str:
        """Generate personalized headache response"""
        response = "I understand you're experiencing a headache. "
        
        # Check for specific headache types
        if "migraine" in query:
            response += "Migraines can be debilitating and often require specific treatment approaches. "
            response += "Common triggers include stress, certain foods, hormonal changes, and environmental factors. "
        elif "tension" in query or "stress" in query:
            response += "Tension headaches are often related to stress, poor posture, or muscle tension. "
            response += "They typically respond well to relaxation techniques and stress management. "
        elif "cluster" in query:
            response += "Cluster headaches are severe and require immediate medical attention. "
            response += "They often occur in cycles and can be extremely painful. "
        else:
            response += "Headaches can have various causes including stress, dehydration, lack of sleep, or underlying medical conditions. "
        
        # Add context-specific advice
        if patient_context and not patient_context.get("error"):
            if patient_context.get("bmiIndex") == "Underweight":
                response += "Given your current weight status, ensure you're eating regular meals as low blood sugar can trigger headaches. "
            if patient_context.get("habits"):
                response += "Consider reviewing your daily habits and stress levels. "
        
        response += "If your headache is severe, sudden, or accompanied by other symptoms like vision changes, seek immediate medical attention."
        
        return response

    def _generate_headache_suggestions(self, patient_context: Dict[str, Any]) -> List[TreatmentSuggestion]:
        """Generate headache-specific suggestions"""
        suggestions = [
            TreatmentSuggestion(
                suggestion_text="Try relaxation techniques like deep breathing or meditation",
                confidence_score=0.8
            ),
            TreatmentSuggestion(
                suggestion_text="Ensure adequate hydration and regular meals",
                confidence_score=0.7
            ),
            TreatmentSuggestion(
                suggestion_text="Consider over-the-counter pain relievers if appropriate",
                confidence_score=0.6
            )
        ]
        
        if patient_context and not patient_context.get("error"):
            if patient_context.get("bmiIndex") == "Underweight":
                suggestions.append(TreatmentSuggestion(
                    suggestion_text="Schedule a nutrition consultation to address dietary needs",
                    confidence_score=0.7
                ))
        
        return suggestions

    def _generate_pain_response(self, patient_context: Dict[str, Any], query: str) -> str:
        """Generate personalized pain response"""
        response = "I understand you're experiencing pain. "
        
        if "chest" in query:
            response += "Chest pain requires immediate medical attention as it could indicate a serious condition. "
            response += "Please seek emergency care if you experience chest pain, especially if it's severe or accompanied by shortness of breath. "
        elif "back" in query:
            response += "Back pain is common and often related to posture, muscle strain, or underlying conditions. "
            response += "Gentle stretching and proper ergonomics can help. "
        elif "joint" in query:
            response += "Joint pain can be caused by various factors including arthritis, injury, or overuse. "
            response += "Rest, ice, and gentle movement may help. "
        else:
            response += "Pain can have many causes and it's important to identify the underlying issue. "
        
        response += "If pain is severe, persistent, or accompanied by other concerning symptoms, please consult a healthcare provider."
        
        return response

    def _generate_pain_suggestions(self, patient_context: Dict[str, Any]) -> List[TreatmentSuggestion]:
        """Generate pain-specific suggestions"""
        return [
            TreatmentSuggestion(
                suggestion_text="Apply ice or heat therapy as appropriate",
                confidence_score=0.7
            ),
            TreatmentSuggestion(
                suggestion_text="Practice gentle stretching and movement",
                confidence_score=0.6
            ),
            TreatmentSuggestion(
                suggestion_text="Schedule a medical evaluation for persistent pain",
                confidence_score=0.8
            )
        ]

    def _generate_fever_response(self, patient_context: Dict[str, Any], query: str) -> str:
        """Generate personalized fever response"""
        response = "I understand you have a fever. "
        
        response += "Fever is often a sign that your body is fighting an infection. "
        response += "Monitor your temperature and stay hydrated. "
        response += "If your fever is high (above 103°F/39.4°C), persistent, or accompanied by other symptoms like severe headache or rash, seek medical attention immediately. "
        
        return response

    def _generate_fever_suggestions(self, patient_context: Dict[str, Any]) -> List[TreatmentSuggestion]:
        """Generate fever-specific suggestions"""
        return [
            TreatmentSuggestion(
                suggestion_text="Monitor your temperature regularly",
                confidence_score=0.9
            ),
            TreatmentSuggestion(
                suggestion_text="Stay hydrated with water and clear fluids",
                confidence_score=0.8
            ),
            TreatmentSuggestion(
                suggestion_text="Get plenty of rest and avoid strenuous activity",
                confidence_score=0.7
            ),
            TreatmentSuggestion(
                suggestion_text="Seek medical care if fever persists or worsens",
                confidence_score=0.8
            )
        ]

    def _generate_fatigue_response(self, patient_context: Dict[str, Any], query: str) -> str:
        """Generate personalized fatigue response"""
        response = "I understand you're feeling tired or fatigued. "
        
        response += "Fatigue can be caused by various factors including lack of sleep, stress, poor nutrition, or underlying medical conditions. "
        
        if patient_context and not patient_context.get("error"):
            if patient_context.get("bmiIndex") == "Underweight":
                response += "Given your current weight status, fatigue might be related to nutritional deficiencies. "
                response += "Consider consulting with a nutritionist to ensure adequate calorie and nutrient intake. "
        
        response += "If fatigue is persistent, severe, or accompanied by other symptoms, it's important to consult a healthcare provider."
        
        return response

    def _generate_fatigue_suggestions(self, patient_context: Dict[str, Any]) -> List[TreatmentSuggestion]:
        """Generate fatigue-specific suggestions"""
        suggestions = [
            TreatmentSuggestion(
                suggestion_text="Ensure 7-9 hours of quality sleep per night",
                confidence_score=0.8
            ),
            TreatmentSuggestion(
                suggestion_text="Maintain a balanced diet with regular meals",
                confidence_score=0.7
            ),
            TreatmentSuggestion(
                suggestion_text="Practice stress management techniques",
                confidence_score=0.6
            )
        ]
        
        if patient_context and not patient_context.get("error"):
            if patient_context.get("bmiIndex") == "Underweight":
                suggestions.append(TreatmentSuggestion(
                    suggestion_text="Schedule a nutrition consultation",
                    confidence_score=0.7
                ))
        
        return suggestions

    def _generate_dizziness_response(self, patient_context: Dict[str, Any], query: str) -> str:
        """Generate personalized dizziness response"""
        response = "I understand you're experiencing dizziness. "
        
        response += "Dizziness can be caused by various factors including inner ear problems, low blood pressure, dehydration, or medication side effects. "
        response += "If dizziness is severe, accompanied by chest pain, or causes fainting, seek immediate medical attention. "
        
        return response

    def _generate_dizziness_suggestions(self, patient_context: Dict[str, Any]) -> List[TreatmentSuggestion]:
        """Generate dizziness-specific suggestions"""
        return [
            TreatmentSuggestion(
                suggestion_text="Sit or lie down when feeling dizzy",
                confidence_score=0.8
            ),
            TreatmentSuggestion(
                suggestion_text="Stay hydrated and avoid sudden movements",
                confidence_score=0.7
            ),
            TreatmentSuggestion(
                suggestion_text="Schedule a medical evaluation for persistent dizziness",
                confidence_score=0.8
            )
        ]

    def _generate_nausea_response(self, patient_context: Dict[str, Any], query: str) -> str:
        """Generate personalized nausea response"""
        response = "I understand you're experiencing nausea. "
        
        response += "Nausea can be caused by various factors including gastrointestinal issues, medication side effects, or underlying medical conditions. "
        response += "If nausea is severe, persistent, or accompanied by other symptoms like severe abdominal pain, seek medical attention. "
        
        return response

    def _generate_nausea_suggestions(self, patient_context: Dict[str, Any]) -> List[TreatmentSuggestion]:
        """Generate nausea-specific suggestions"""
        return [
            TreatmentSuggestion(
                suggestion_text="Try small, bland meals and clear fluids",
                confidence_score=0.7
            ),
            TreatmentSuggestion(
                suggestion_text="Avoid strong odors and spicy foods",
                confidence_score=0.6
            ),
            TreatmentSuggestion(
                suggestion_text="Schedule a medical evaluation for persistent nausea",
                confidence_score=0.8
            )
        ]

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
            
            # Store in interaction_logs collection (remove await)
            doc_ref = self.firestore_service.db.collection('interaction_logs').document()
            doc_ref.set(interaction_data)
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
            
            # Store in response_logs collection (remove await)
            doc_ref = self.firestore_service.db.collection('response_logs').document()
            doc_ref.set(response_data)
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