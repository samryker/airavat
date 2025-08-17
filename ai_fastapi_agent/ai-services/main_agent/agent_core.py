from .data_models import PatientQuery, AgentResponse, TreatmentSuggestion, StructuredGeminiOutput, GeminiResponseFeatures, FeedbackDataModel, NotificationRequest
from .gemini_service import get_treatment_suggestion_from_gemini
from .firestore_service import FirestoreService
from .planner import generate_dynamic_plan
from .rl_service import PatientRLAgent, determine_severity_level, calculate_reward
from .mcp_medical_agent import MCPMedicalAgent
from .intent_detector import intent_detector, IntentType
from .genetic_analysis_service import genetic_analysis_service
from firebase_admin import firestore
from typing import List, Dict, Any, Optional
import uuid
import logging
import asyncio
import datetime
import os
import google.generativeai as genai
from dotenv import load_dotenv
from .user_data_service import UserDataService
from .notification_service import NotificationService
from .email_service import EmailService

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
        
        # Initialize Gemini for dynamic suggestions
        load_dotenv()
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel('gemini-1.5-pro')
            logger.info("Gemini model initialized for dynamic suggestions.")
        else:
            self.model = None
            logger.warning("GEMINI_API_KEY not found. Dynamic suggestions will use fallback.")
        
        # Initialize services
        if self.db:
            logger.info("MedicalAgent initialized with Firestore client.")
            self.firestore_service = FirestoreService(db)
            self.user_data_service = UserDataService(db)
            
            # Initialize notification and email services
            try:
                self.notification_service = NotificationService(db)
                logger.info("Notification service initialized successfully.")
            except Exception as e:
                logger.warning(f"Notification service initialization failed: {e}")
                self.notification_service = None
                
            try:
                self.email_service = EmailService()
                logger.info("Email service initialized successfully.")
            except Exception as e:
                logger.warning(f"Email service initialization failed: {e}")
                self.email_service = None
        else:
            logger.warning("Warning: MedicalAgent initialized WITHOUT Firestore client. Contextual data, planner, and RL features will be limited.")
            self.firestore_service = None
            self.user_data_service = None
            self.notification_service = None
            self.email_service = None
            
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
        """
        Process a patient query and return an appropriate response.
        This method routes ALL queries through Gemini for comprehensive LLM responses.
        """
        try:
            # Log the interaction to Firestore for conversation history
            await self._log_interaction(patient_query)
            
            # Detect intent for potential notification creation
            intent = self._detect_query_intent(patient_query.query_text)
            
            # Get comprehensive patient context
            patient_context = await self._get_comprehensive_context(patient_query)
            
            # Route ALL queries through Gemini for full LLM response
            gemini_response = await self._get_gemini_response(patient_query, patient_context)
            
            # Handle specific intents after getting Gemini response
            if intent == 'set_reminder':
                await self._handle_reminder_intent(patient_query, gemini_response.response_text)
            
            # Log the response
            await self._log_response(patient_query.patient_id, gemini_response)
            
            return gemini_response
                
        except Exception as e:
            logger.exception(f"Error in process_query: {e}")
            # Only use fallback if Gemini is completely unavailable
            return await self._emergency_fallback_response(patient_query)

    async def _get_comprehensive_context(self, patient_query: PatientQuery) -> Dict[str, Any]:
        """
        Get comprehensive patient context including genetic data for enhanced LLM responses
        """
        context = {
            'patient_id': patient_query.patient_id,
            'query': patient_query.query_text,
            'symptoms': patient_query.symptoms or [],
            'medical_history': patient_query.medical_history or [],
            'current_medications': patient_query.current_medications or [],
            'additional_data': patient_query.additional_data or {},
            'genetic_data': {},
            'conversation_history': [],
            'treatment_plans': [],
            'biomarkers': {},
            'risk_factors': [],
            'recommendations': []
        }
        
        try:
            # Get genetic context for enhanced responses
            genetic_insights = await genetic_analysis_service.get_genetic_insights_for_llm(patient_query.patient_id)
            if genetic_insights and genetic_insights.get('has_genetic_data'):
                context['genetic_data'] = genetic_insights
                context['risk_factors'].extend(genetic_insights.get('risk_factors', []))
                context['recommendations'].extend(genetic_insights.get('recommendations', []))
                
                # Add genetic-specific context
                context['genetic_context'] = {
                    'has_genetic_data': True,
                    'risk_factors': genetic_insights.get('risk_factors', []),
                    'clinical_significance': genetic_insights.get('clinical_significance', []),
                    'key_findings': genetic_insights.get('key_findings', []),
                    'crispr_opportunities': genetic_insights.get('crispr_opportunities', []),
                    'markers_count': genetic_insights.get('markers_count', 0),
                    'crispr_targets_count': genetic_insights.get('crispr_targets_count', 0),
                    'last_analysis_date': genetic_insights.get('last_analysis_date')
                }
            
            # Get patient profile data
            if self.user_data_service:
                try:
                    profile = await self.user_data_service.get_user_profile(patient_query.patient_id)
                    if profile:
                        context['patient_profile'] = {
                            'age': profile.age,
                            'gender': profile.gender,
                            'bmi_index': profile.bmiIndex,
                            'race': profile.race,
                            'medicines': profile.medicines,
                            'allergies': profile.allergies,
                            'history': profile.history,
                            'goal': profile.goal,
                            'habits': profile.habits or []
                        }
                        
                        # Add treatment plans
                        if profile.treatmentPlans:
                            context['treatment_plans'] = profile.treatmentPlans
                except Exception as e:
                    logger.error(f"Error retrieving patient data for {patient_query.patient_id}: {e}")
            
            # Get conversation history
            if self.firestore_service:
                try:
                    history = await self.firestore_service.get_conversation_history(patient_query.patient_id, limit=5)
                    context['conversation_history'] = history
                except Exception as e:
                    logger.error(f"Error retrieving conversation history for {patient_query.patient_id}: {e}")
            
            # Get biomarkers
            if self.user_data_service:
                try:
                    biomarkers = await self.user_data_service.get_user_biomarkers(patient_query.patient_id)
                    if biomarkers:
                        context['biomarkers'] = biomarkers
                except Exception as e:
                    logger.error(f"Error retrieving biomarkers for {patient_query.patient_id}: {e}")
        
            # Get MCP agent context if available
            if self.mcp_agent:
                try:
                    mcp_context = await self.mcp_agent.get_patient_context(patient_query.patient_id)
                    if mcp_context:
                        context['mcp_context'] = mcp_context
                except Exception as e:
                    logger.error(f"Error retrieving MCP context for {patient_query.patient_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error getting comprehensive context: {e}")
        
        return context

    async def _get_gemini_response(self, patient_query: PatientQuery, patient_context: Dict[str, Any]) -> AgentResponse:
        """
        Get comprehensive response from Gemini for ALL types of queries
        """
        try:
            # Create a comprehensive prompt that includes all context
            prompt = self._create_comprehensive_prompt(patient_query, patient_context)
            
            # Get response from Gemini
            gemini_output = await get_treatment_suggestion_from_gemini(patient_query, patient_context)
            
            # Extract suggestions from Gemini response dynamically
            suggestions = []
            if gemini_output and hasattr(gemini_output, 'text'):
                # Let Gemini generate suggestions based on the actual response content
                suggestions = await self._generate_dynamic_suggestions(gemini_output.text, patient_query.query_text, patient_context)
            
            return AgentResponse(
                request_id=patient_query.request_id,
                response_text=gemini_output.text if gemini_output else "I'm processing your request. Please try again.",
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Error getting Gemini response: {e}")
            # Return a response that encourages the user to try again
            return AgentResponse(
                request_id=patient_query.request_id,
                response_text="I'm having trouble processing your request right now. Please try again or rephrase your question.",
                suggestions=[
                    TreatmentSuggestion(
                        suggestion_text="Try rephrasing your question",
                        confidence_score=0.8
                    ),
                    TreatmentSuggestion(
                        suggestion_text="Contact your healthcare provider for immediate concerns",
                        confidence_score=0.9
                    )
                ]
            )

    async def _generate_dynamic_suggestions(self, response_text: str, original_query: str, patient_context: Dict[str, Any]) -> List[TreatmentSuggestion]:
        """
        Generate dynamic suggestions based on Gemini's response and the actual query content
        """
        try:
            if not hasattr(self, 'model') or not self.model:
                # Fallback to basic suggestions if Gemini is not available
                return self._generate_fallback_suggestions(original_query)
            
            # Create a prompt for Gemini to generate suggestions based on the response
            suggestion_prompt = f"""
            Based on this medical response and the patient's query, generate 3-5 actionable suggestions.
            
            Patient Query: "{original_query}"
            AI Response: "{response_text}"
            
            Generate suggestions that are:
            1. Relevant to the specific query and response
            2. Actionable and practical
            3. Appropriate for the patient's context
            4. Include confidence scores (0.0-1.0)
            
            Return as JSON array with format:
            [
                {{
                    "suggestion_text": "specific actionable suggestion",
                    "confidence_score": 0.8
                }}
            ]
            
            Focus on the actual content of the query and response, not generic patterns.
            """
            
            # Get suggestions from Gemini
            response = self.model.generate_content(suggestion_prompt)
            
            try:
                import json
                suggestions_data = json.loads(response.text)
                if isinstance(suggestions_data, list):
                    return [
                        TreatmentSuggestion(
                            suggestion_text=item.get("suggestion_text", ""),
                            confidence_score=item.get("confidence_score", 0.7)
                        )
                        for item in suggestions_data
                        if item.get("suggestion_text")
                    ]
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error parsing Gemini suggestions: {e}")
            
            # Fallback if JSON parsing fails
            return self._generate_fallback_suggestions(original_query)
            
        except Exception as e:
            logger.error(f"Error generating dynamic suggestions: {e}")
            return self._generate_fallback_suggestions(original_query)

    def _generate_fallback_suggestions(self, original_query: str) -> List[TreatmentSuggestion]:
        """
        Generate basic fallback suggestions when dynamic generation fails
        """
        return [
            TreatmentSuggestion(
                suggestion_text="Schedule a consultation with your healthcare provider",
                confidence_score=0.8
            ),
            TreatmentSuggestion(
                suggestion_text="Monitor your symptoms and keep a detailed log",
                confidence_score=0.7
            ),
            TreatmentSuggestion(
                suggestion_text="Follow up with your doctor for personalized advice",
                confidence_score=0.8
            )
        ]

    def _create_comprehensive_prompt(self, patient_query: PatientQuery, patient_context: Dict[str, Any]) -> str:
        """
        Create a comprehensive prompt for Gemini that includes all relevant context
        """
        prompt_parts = []
        
        # Add patient context
        if patient_context.get("firestore_data"):
            firestore_data = patient_context["firestore_data"]
            if firestore_data.get("profile"):
                profile = firestore_data["profile"]
                prompt_parts.append(f"Patient Profile: Age: {profile.get('age', 'Unknown')}, Gender: {profile.get('gender', 'Unknown')}, BMI: {profile.get('bmiIndex', 'Unknown')}")
            
            if firestore_data.get("treatment_plans"):
                plans = firestore_data["treatment_plans"]
                prompt_parts.append(f"Current Treatment Plans: {len(plans)} active plans")
            
            if firestore_data.get("biomarkers"):
                biomarkers = firestore_data["biomarkers"]
                prompt_parts.append(f"Recent Biomarkers: Available")
        
        # Add MCP memory if available
        if patient_context.get("mcp_memory"):
            mcp_memory = patient_context["mcp_memory"]
            if mcp_memory.get("conversation_history"):
                prompt_parts.append(f"Previous Conversations: {len(mcp_memory['conversation_history'])} interactions")
        
        # Add current query context
        if "query_data" in patient_context:
            query_data = patient_context["query_data"]
            if query_data.get("symptoms"):
                prompt_parts.append(f"Current Symptoms: {', '.join(query_data['symptoms'])}")
            if query_data.get("current_medications"):
                prompt_parts.append(f"Current Medications: {', '.join(query_data['current_medications'])}")
        else:
            # Use patient_query directly if query_data not in context
            if patient_query.symptoms:
                prompt_parts.append(f"Current Symptoms: {', '.join(patient_query.symptoms)}")
            if patient_query.current_medications:
                prompt_parts.append(f"Current Medications: {', '.join(patient_query.current_medications)}")
        
        # Create the main prompt
        context_summary = " | ".join(prompt_parts) if prompt_parts else "No specific context available"
        
        prompt = f"""
        You are Airavat, an advanced medical AI assistant. Provide comprehensive, personalized medical guidance.

        Patient Context: {context_summary}
        
        Patient Query: "{patient_query.query_text}"
        
        Please provide:
        1. A detailed, personalized response addressing the patient's specific situation
        2. Multiple actionable suggestions with confidence scores (0.0-1.0)
        3. If the query involves setting reminders, notifications, or genetic analysis, provide guidance on how to proceed
        4. Consider the patient's medical history, current medications, and symptoms
        5. Always emphasize consulting healthcare providers for serious concerns
        
        Format your response as natural conversation with clear, actionable next steps.
        """
        
        return prompt

    # Removed _extract_actionable_suggestions method - replaced with dynamic generation

    async def _emergency_fallback_response(self, patient_query: PatientQuery) -> AgentResponse:
        """
        Emergency fallback response when Gemini is completely unavailable
        """
        return AgentResponse(
            request_id=patient_query.request_id,
            response_text="I apologize, but I'm experiencing technical difficulties right now. For immediate medical concerns, please contact your healthcare provider directly. You can also try again in a few moments.",
            suggestions=[
                TreatmentSuggestion(
                    suggestion_text="Contact your healthcare provider for immediate concerns",
                    confidence_score=0.9
                ),
                TreatmentSuggestion(
                    suggestion_text="Try again in a few moments",
                    confidence_score=0.7
                )
            ]
        )

    def _detect_query_intent(self, query_text: str) -> str:
        """
        Detect the intent of the user query (kept for potential future use)
        """
        query_lower = query_text.lower()
        
        # Notification/reminder keywords
        notification_keywords = [
            'remind me', 'set reminder', 'schedule reminder', 'set notification',
            'remind me to', 'set alarm', 'schedule', 'reminder', 'notification',
            'wake me up', 'call me', 'text me', 'email me', 'ping me',
            'set timer', 'set schedule', 'daily reminder', 'weekly reminder'
        ]
        
        # Genetic analysis keywords
        genetic_keywords = [
            'genetic', 'dna', 'gene', 'crispr', 'genome', 'mutation',
            'genetic test', 'dna test', 'gene analysis', 'genetic report',
            'upload genetic', 'genetic data', 'genetic file'
        ]
        
        # Check for notification intent
        for keyword in notification_keywords:
            if keyword in query_lower:
                return 'set_reminder'
        
        # Check for genetic analysis intent
        for keyword in genetic_keywords:
            if keyword in query_lower:
                return 'genetic_analysis'
        
        # Default to medical query
        return 'medical_query'

    async def _handle_reminder_intent(self, patient_query: PatientQuery, response_text: str):
        """
        Handles the 'set_reminder' intent by creating a notification.
        This method is called after Gemini response is processed.
        """
        if not self.notification_service:
            logger.warning("Notification service not available to handle reminder intent.")
            return

        try:
            # Extract potential reminder details from the query text (not response)
            query_text = patient_query.query_text.lower()
            
            # Create a basic notification for reminder requests
            title = "Health Reminder"
            message = f"Reminder created based on your request: {patient_query.query_text[:100]}"
            
            # Check for specific types
            if "medication" in query_text or "medicine" in query_text:
                title = "Medication Reminder"
                message = "Time to take your medication as discussed with your AI assistant."
            elif "appointment" in query_text or "doctor" in query_text:
                title = "Appointment Reminder"
                message = "Don't forget about your upcoming appointment."
            elif "exercise" in query_text or "workout" in query_text:
                title = "Exercise Reminder"
                message = "Time for your exercise routine!"

            # Create a NotificationRequest object
            notification = NotificationRequest(
                patient_id=patient_query.patient_id,
                notification_type="reminder",
                title=title,
                message=message,
                scheduled_time=(datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
            )

            # Create the notification
            await self.notification_service.create_notification(notification)
            logger.info(f"Created reminder notification for patient {patient_query.patient_id}")

        except Exception as e:
            logger.error(f"Error handling reminder intent: {e}")

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
        """Update patient's treatment plan"""
        try:
            if not self.db:
                return False
            
            # Update in Firestore
            patient_ref = self.db.collection('patients').document(patient_id)
            await patient_ref.update({
                'treatmentPlans': treatment_plan,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            # Update MCP context
            if self.mcp_agent:
                await self.mcp_agent.update_treatment_plan(patient_id, treatment_plan)
            
            return True
        except Exception as e:
            logger.error(f"Error updating treatment plan: {e}")
            return False

    # New methods for complete patient flow

    async def sync_patient_context_to_mcp(
        self, 
        patient_id: str, 
        profile_data: Dict[str, Any], 
        treatment_plans: List[Dict[str, Any]], 
        biomarkers: Optional[Dict[str, Any]] = None,
        genetic_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Sync patient context to MCP server after account setup"""
        try:
            logger.info(f"Syncing patient context to MCP for: {patient_id}")
            
            # Create comprehensive context
            context = {
                'patient_id': patient_id,
                'profile': profile_data,
                'treatment_plans': treatment_plans,
                'biomarkers': biomarkers or {},
                'genetic_data': genetic_data or {},
                'synced_at': datetime.datetime.now().isoformat(),
                'version': '1.0'
            }
            
            # Update Firestore
            if self.db:
                await self.db.collection('patient_contexts').document(patient_id).set(context)
            
            # Update MCP agent
            if self.mcp_agent:
                await self.mcp_agent.get_patient_context(patient_id)
            
            logger.info(f"Patient context synced successfully for: {patient_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing patient context: {e}")
            return False

    async def get_complete_patient_context(self, patient_id: str) -> Dict[str, Any]:
        """Get complete patient context for login"""
        try:
            logger.info(f"Getting complete patient context for: {patient_id}")
            
            context = {
                'patient_id': patient_id,
                'profile': {},
                'treatment_plans': [],
                'biomarkers': {},
                'genetic_data': {},
                'mcp_memory': {},
                'conversation_history': []
            }
            
            # Get profile data
            if self.user_data_service:
                profile = await self.user_data_service.get_user_profile(patient_id)
                if profile:
                    context['profile'] = {
                        'age': profile.age,
                        'gender': profile.gender,
                        'bmi_index': profile.bmiIndex,
                        'race': profile.race,
                        'medicines': profile.medicines,
                        'allergies': profile.allergies,
                        'history': profile.history,
                        'goal': profile.goal,
                        'habits': profile.habits or []
                    }
            
            # Get treatment plans
            if self.user_data_service:
                treatment_plans = await self.user_data_service.get_user_treatment_plans(patient_id)
                context['treatment_plans'] = treatment_plans
            
            # Get biomarkers
            if self.user_data_service:
                biomarkers = await self.user_data_service.get_user_biomarkers(patient_id)
                if biomarkers:
                    context['biomarkers'] = biomarkers
            
            # Get genetic data
            genetic_insights = await genetic_analysis_service.get_genetic_insights_for_llm(patient_id)
            if genetic_insights:
                context['genetic_data'] = genetic_insights
            
            # Get MCP memory
            if self.mcp_agent:
                mcp_context = await self.mcp_agent.get_patient_context(patient_id)
                if mcp_context:
                    context['mcp_memory'] = mcp_context
            
            # Get conversation history
            if self.firestore_service:
                history = await self.firestore_service.get_conversation_history(patient_id, limit=10)
                context['conversation_history'] = history
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting complete patient context: {e}")
            return {'patient_id': patient_id, 'error': str(e)}

    async def process_questionnaire_response(self, response: 'QuestionnaireResponse') -> Dict[str, Any]:
        """Process questionnaire for RL training"""
        try:
            logger.info(f"Processing questionnaire for patient: {response.patient_id}")
            
            # Get RL agent
            patient_rl_agent = await self._get_or_create_rl_agent(response.patient_id)
            
            # Process questionnaire answers
            questionnaire_data = {
                'patient_id': response.patient_id,
                'request_id': response.request_id,
                'questions': response.questions,
                'answers': response.answers,
                'outcome_works': response.outcome_works,
                'feedback_text': response.feedback_text,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            # Store questionnaire data
            if self.db:
                await self.db.collection('questionnaires').document(response.request_id).set(questionnaire_data)
            
            # Update RL model with questionnaire feedback
            if patient_rl_agent:
                # Extract features from questionnaire
                features = self._extract_questionnaire_features(response.questions, response.answers)
                
                # Update RL model
                await patient_rl_agent.update_model(
                    gemini_features_state=features,
                    risk_assessment_state=None,
                    action_taken=0,  # Default action
                    reward=3 if response.outcome_works else -1,
                    gemini_features_next_state=None,
                    risk_assessment_next_state=None
                )
            
            return {
                'success': True,
                'message': 'Questionnaire processed successfully',
                'rl_updated': patient_rl_agent is not None
            }
            
        except Exception as e:
            logger.error(f"Error processing questionnaire: {e}")
            return {'success': False, 'error': str(e)}

    def _extract_questionnaire_features(self, questions: List[Dict[str, Any]], answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract features from questionnaire for RL training"""
        features = {
            'category': 'questionnaire_feedback',
            'urgency': 'low',
            'keywords': [],
            'actionable_steps_present': False
        }
        
        # Extract keywords from questions and answers
        for question, answer in zip(questions, answers):
            if 'text' in question:
                features['keywords'].extend(question['text'].lower().split())
            if 'text' in answer:
                features['keywords'].extend(answer['text'].lower().split())
        
        return features

    async def create_notification(self, notification: 'NotificationRequest') -> Dict[str, Any]:
        """Create notification/reminder/email"""
        try:
            logger.info(f"Creating notification for patient: {notification.patient_id}")
            
            notification_data = {
                'patient_id': notification.patient_id,
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'scheduled_time': notification.scheduled_time,
                'recipient_email': notification.recipient_email,
                'created_at': datetime.datetime.now().isoformat(),
                'status': 'pending'
            }
            
            # Store notification
            if self.db:
                await self.db.collection('notifications').add(notification_data)
            
            # Handle different notification types
            if notification.notification_type == 'reminder':
                # Create reminder
                if self.notification_service:
                    await self.notification_service.create_reminder(
                        patient_id=notification.patient_id,
                        title=notification.title,
                        message=notification.message,
                        scheduled_time=notification.scheduled_time
                    )
            
            elif notification.notification_type == 'email':
                # Send email
                if self.email_service:
                    await self.email_service.send_medical_alert(
                        user_id=notification.patient_id,
                        email=notification.recipient_email or 'patient@example.com',
                        user_name='Patient',
                        alert_title=notification.title,
                        alert_message=notification.message,
                        recommended_actions=[],
                        priority_level='medium'
                    )
            
            elif notification.notification_type == 'emergency':
                # Send immediate notification
                if self.notification_service:
                    await self.notification_service.send_emergency_notification(
                        patient_id=notification.patient_id,
                        title=notification.title,
                        message=notification.message
                    )
            
            return {
                'success': True,
                'message': f'{notification.notification_type} notification created successfully'
            }
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return {'success': False, 'error': str(e)}

    async def create_3d_twin(self, patient_id: str) -> Dict[str, Any]:
        """Trigger 3D twin creation after account setup"""
        try:
            logger.info(f"Creating 3D twin for patient: {patient_id}")
            
            # Get patient data for twin creation
            context = await self.get_complete_patient_context(patient_id)
            
            # Create twin data
            twin_data = {
                'patient_id': patient_id,
                'created_at': datetime.datetime.now().isoformat(),
                'biomarkers': context.get('biomarkers', {}),
                'profile': context.get('profile', {}),
                'treatment_plans': context.get('treatment_plans', []),
                'status': 'created'
            }
            
            # Store twin data
            if self.db:
                await self.db.collection('3d_twins').document(patient_id).set(twin_data)
            
            # Trigger 3D twin creation (this would integrate with your 3D service)
            # For now, we'll just mark it as created
            
            return {
                'success': True,
                'message': '3D twin created successfully',
                'twin_id': patient_id
            }
            
        except Exception as e:
            logger.error(f"Error creating 3D twin: {e}")
            return {'success': False, 'error': str(e)}

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