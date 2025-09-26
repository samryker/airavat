"""
Simple, reliable Gemini service using ONLY Gemini 1.5 Pro
Completely rewritten to avoid all routing and configuration issues
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional
import google.generativeai as genai
from dotenv import load_dotenv
from .data_models import PatientQuery, StructuredGeminiOutput, GeminiResponseFeatures

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class SimpleGeminiService:
    """Simple, reliable Gemini service with single configuration"""
    
    def __init__(self):
        self.model = None
        self.api_key = None
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Initialize Gemini with clean configuration"""
        try:
            # Get API key
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            
            if not self.api_key:
                logger.warning("No Gemini API key found")
                return
            
            # Clean environment to avoid Vertex AI routing
            vertex_vars = [
                'GOOGLE_CLOUD_PROJECT', 'GOOGLE_CLOUD_REGION', 'GCLOUD_PROJECT',
                'GOOGLE_APPLICATION_CREDENTIALS', 'CLOUDSDK_CORE_PROJECT'
            ]
            
            for var in vertex_vars:
                if var in os.environ:
                    logger.info(f"Removing {var} to force Generative AI API")
                    del os.environ[var]
            
            # Configure Gemini with clean state
            genai.configure(api_key=self.api_key)
            
            # Use ONLY Gemini 1.5 Pro
            self.model = genai.GenerativeModel("gemini-1.5-pro")
            logger.info("✅ Simple Gemini service initialized with Gemini 1.5 Pro")
            
        except Exception as e:
            logger.error(f"Failed to initialize Simple Gemini service: {e}")
            self.model = None
    
    def is_available(self) -> bool:
        """Check if Gemini is available"""
        return self.model is not None and self.api_key is not None
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Gemini connection"""
        if not self.is_available():
            return {"available": False, "error": "Service not initialized"}
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, 
                "Hello, please respond with 'Gemini 1.5 Pro is working'"
            )
            
            if response and response.text:
                return {
                    "available": True, 
                    "model": "gemini-1.5-pro",
                    "test_response": response.text[:100]
                }
            else:
                return {"available": False, "error": "Empty response"}
                
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def get_medical_response(self, patient_query: PatientQuery, patient_context: Dict[str, Any] = None) -> StructuredGeminiOutput:
        """Get medical response from Gemini 1.5 Pro"""
        
        if not self.is_available():
            logger.warning("Gemini not available, returning fallback")
            return self._get_fallback_response(patient_query)
        
        try:
            # Create medical prompt
            prompt = self._create_medical_prompt(patient_query, patient_context)
            
            # Call Gemini with retry logic
            response_text = await self._call_gemini_with_retry(prompt)
            
            if response_text and "I'm currently unable" not in response_text:
                logger.info("✅ Gemini 1.5 Pro response successful")
                return StructuredGeminiOutput(
                    text=response_text,
                    features=GeminiResponseFeatures(
                        category="medical_query",
                        urgency="medium",
                        keywords=patient_query.symptoms or [],
                        actionable_steps_present=True
                    )
                )
            else:
                logger.warning("Gemini returned empty or error response")
                return self._get_fallback_response(patient_query)
                
        except Exception as e:
            logger.error(f"Error in get_medical_response: {e}")
            return self._get_fallback_response(patient_query)
    
    async def _call_gemini_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Call Gemini with retry logic"""
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Gemini attempt {attempt + 1}/{max_retries}")
                
                # Reinitialize if model seems broken
                if attempt > 0:
                    logger.info("Reinitializing Gemini for retry")
                    self._initialize_gemini()
                
                if not self.model:
                    raise Exception("Model not available after initialization")
                
                # Make the API call
                response = await asyncio.to_thread(self.model.generate_content, prompt)
                
                if response and hasattr(response, 'text') and response.text:
                    logger.info(f"✅ Gemini call successful on attempt {attempt + 1}")
                    return response.text
                else:
                    raise Exception("Empty response from Gemini")
                    
            except Exception as e:
                logger.warning(f"Gemini attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {max_retries} Gemini attempts failed")
                    return None
        
        return None
    
    def _create_medical_prompt(self, patient_query: PatientQuery, patient_context: Dict[str, Any] = None) -> str:
        """Create medical prompt for Gemini"""
        
        context_str = ""
        if patient_context:
            # Extract relevant context
            profile = patient_context.get('patient_profile', {})
            history = patient_context.get('conversation_history', [])
            
            if profile:
                context_str += f"\nPatient Profile: Age {profile.get('age', 'unknown')}, Gender {profile.get('gender', 'unknown')}"
                if profile.get('medicines'):
                    context_str += f"\nCurrent Medications: {profile['medicines']}"
                if profile.get('allergies'):
                    context_str += f"\nAllergies: {profile['allergies']}"
                if profile.get('history'):
                    context_str += f"\nMedical History: {profile['history']}"
        
        prompt = f"""You are a knowledgeable medical AI assistant. Provide helpful, accurate medical information while emphasizing the importance of professional medical consultation.

Patient Query: {patient_query.query_text}
Patient ID: {patient_query.patient_id}
Symptoms: {', '.join(patient_query.symptoms) if patient_query.symptoms else 'None specified'}
{context_str}

Please provide:
1. A helpful and informative response to the patient's query
2. Relevant medical information and insights
3. Appropriate recommendations for next steps
4. Important disclaimers about consulting healthcare professionals

Remember to:
- Be empathetic and supportive
- Provide accurate medical information
- Always recommend professional medical consultation for serious concerns
- Avoid giving specific medical diagnoses
- Focus on education and general guidance

Respond in a conversational, caring tone."""
        
        return prompt
    
    def _get_fallback_response(self, patient_query: PatientQuery) -> StructuredGeminiOutput:
        """Get fallback response when Gemini fails"""
        return StructuredGeminiOutput(
            text="I'm currently unable to process your medical query. Please consult with a healthcare professional for personalized medical advice.",
            features=GeminiResponseFeatures(
                category="system_error",
                urgency="medium",
                keywords=patient_query.symptoms or [],
                actionable_steps_present=False
            )
        )

# Global instance
simple_gemini_service = SimpleGeminiService()
