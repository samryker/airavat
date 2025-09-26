"""
Simplified Medical Agent with reliable Gemini 1.5 Pro integration
Rewritten to eliminate all configuration conflicts and ensure consistent responses
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from .data_models import PatientQuery, AgentResponse, TreatmentSuggestion
from .gemini_service_simple import simple_gemini_service
from .firestore_service import FirestoreService
from .user_data_service import UserDataService
from .genetic_analysis_service import genetic_analysis_service
from firebase_admin import firestore

logger = logging.getLogger(__name__)

class SimpleMedicalAgent:
    """Simplified Medical Agent with reliable Gemini integration"""
    
    def __init__(self, db: Optional[firestore.client] = None):
        self.db = db
        
        # Initialize services
        if self.db:
            self.firestore_service = FirestoreService(db)
            self.user_data_service = UserDataService(db)
            logger.info("SimpleMedicalAgent initialized with Firestore")
        else:
            self.firestore_service = None
            self.user_data_service = None
            logger.warning("SimpleMedicalAgent initialized without Firestore")
    
    async def process_query(self, patient_query: PatientQuery) -> AgentResponse:
        """Process patient query with reliable Gemini responses"""
        
        try:
            logger.info(f"Processing query for patient: {patient_query.patient_id}")
            
            # Step 1: Get patient context
            patient_context = await self._get_patient_context(patient_query)
            
            # Step 2: Get Gemini response
            gemini_response = await simple_gemini_service.get_medical_response(
                patient_query, patient_context
            )
            
            # Step 3: Generate suggestions
            suggestions = self._generate_suggestions(gemini_response.text, patient_query)
            
            # Step 4: Log interaction
            await self._log_interaction(patient_query, gemini_response.text)
            
            return AgentResponse(
                request_id=patient_query.request_id,
                response_text=gemini_response.text,
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return self._get_emergency_response(patient_query)
    
    async def _get_patient_context(self, patient_query: PatientQuery) -> Dict[str, Any]:
        """Get comprehensive patient context"""
        
        context = {
            'patient_id': patient_query.patient_id,
            'query': patient_query.query_text,
            'symptoms': patient_query.symptoms or [],
            'medical_history': patient_query.medical_history or [],
            'current_medications': patient_query.current_medications or [],
            'additional_data': patient_query.additional_data or {}
        }
        
        # Get patient profile if available
        if self.user_data_service:
            try:
                profile = await self.user_data_service.get_user_profile(patient_query.patient_id)
                if profile:
                    context['patient_profile'] = {
                        'age': profile.age,
                        'gender': profile.gender,
                        'bmi_index': profile.bmiIndex,
                        'medicines': profile.medicines,
                        'allergies': profile.allergies,
                        'history': profile.history,
                        'goal': profile.goal,
                        'habits': profile.habits or []
                    }
            except Exception as e:
                logger.warning(f"Could not get patient profile: {e}")
        
        # Get conversation history if available
        if self.firestore_service:
            try:
                history = await self.firestore_service.get_conversation_history(
                    patient_query.patient_id, limit=3
                )
                context['conversation_history'] = history
            except Exception as e:
                logger.warning(f"Could not get conversation history: {e}")
        
        # Get genetic insights if available
        try:
            genetic_insights = await genetic_analysis_service.get_genetic_insights_for_llm(
                patient_query.patient_id
            )
            if genetic_insights and genetic_insights.get('has_genetic_data'):
                context['genetic_data'] = genetic_insights
        except Exception as e:
            logger.warning(f"Could not get genetic insights: {e}")
        
        return context
    
    def _generate_suggestions(self, response_text: str, patient_query: PatientQuery) -> List[TreatmentSuggestion]:
        """Generate treatment suggestions based on response"""
        
        # Basic suggestions that are always relevant
        suggestions = [
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
        
        # Add query-specific suggestions
        query_lower = patient_query.query_text.lower()
        
        if any(word in query_lower for word in ['pain', 'hurt', 'ache']):
            suggestions.insert(0, TreatmentSuggestion(
                suggestion_text="Apply appropriate pain management as advised by your doctor",
                confidence_score=0.7
            ))
        
        if any(word in query_lower for word in ['bleeding', 'blood']):
            suggestions.insert(0, TreatmentSuggestion(
                suggestion_text="Seek immediate medical attention for bleeding symptoms",
                confidence_score=0.9
            ))
        
        if any(word in query_lower for word in ['cancer', 'tumor', 'malignant']):
            suggestions.insert(0, TreatmentSuggestion(
                suggestion_text="Consult with an oncologist for cancer-related concerns",
                confidence_score=0.9
            ))
        
        return suggestions[:4]  # Return max 4 suggestions
    
    async def _log_interaction(self, patient_query: PatientQuery, response_text: str):
        """Log interaction to Firestore"""
        
        if not self.firestore_service:
            return
        
        try:
            interaction_data = {
                'patient_id': patient_query.patient_id,
                'query_text': patient_query.query_text,
                'response_text': response_text[:500],  # Truncate for storage
                'timestamp': datetime.utcnow(),
                'request_id': patient_query.request_id,
                'symptoms': patient_query.symptoms or [],
                'gemini_model': 'gemini-1.5-pro'
            }
            
            # Store in interaction_logs collection
            doc_ref = self.firestore_service.db.collection('interaction_logs').document()
            doc_ref.set(interaction_data)
            logger.info(f"Interaction logged for patient {patient_query.patient_id}")
            
        except Exception as e:
            logger.warning(f"Failed to log interaction: {e}")
    
    def _get_emergency_response(self, patient_query: PatientQuery) -> AgentResponse:
        """Emergency fallback response"""
        
        return AgentResponse(
            request_id=patient_query.request_id,
            response_text="I'm experiencing technical difficulties right now. Please try again later or consult with a healthcare professional for immediate assistance.",
            suggestions=[
                TreatmentSuggestion(
                    suggestion_text="Try again in a few moments",
                    confidence_score=0.7
                ),
                TreatmentSuggestion(
                    suggestion_text="Contact your healthcare provider for immediate concerns",
                    confidence_score=0.9
                )
            ]
        )

# Global instance
simple_medical_agent = SimpleMedicalAgent()
