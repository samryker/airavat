"""
Direct HTTP Gemini API service - bypasses Google AI SDK completely
Uses direct HTTP calls to generativelanguage.googleapis.com
"""

import os
import asyncio
import logging
import json
import aiohttp
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from .data_models import PatientQuery, StructuredGeminiOutput, GeminiResponseFeatures

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class DirectGeminiService:
    """Direct HTTP Gemini service - bypasses SDK routing issues"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model_name = "gemini-1.5-pro"
        
        if self.api_key:
            logger.info("✅ Direct Gemini HTTP service initialized with API key")
        else:
            logger.warning("❌ No Gemini API key found for direct HTTP service")
    
    def is_available(self) -> bool:
        """Check if service is available"""
        return bool(self.api_key)
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test direct HTTP connection to Gemini"""
        if not self.is_available():
            return {"available": False, "error": "No API key"}
        
        try:
            response = await self._make_gemini_request("Hello, please respond with 'Direct HTTP API working'")
            
            if response:
                return {
                    "available": True,
                    "method": "direct_http",
                    "model": self.model_name,
                    "test_response": response[:100]
                }
            else:
                return {"available": False, "error": "Empty response"}
                
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def get_medical_response(self, patient_query: PatientQuery, patient_context: Dict[str, Any] = None) -> StructuredGeminiOutput:
        """Get medical response using direct HTTP API"""
        
        if not self.is_available():
            return self._get_fallback_response(patient_query)
        
        try:
            # Create medical prompt
            prompt = self._create_medical_prompt(patient_query, patient_context)
            
            # Make direct HTTP request
            response_text = await self._make_gemini_request_with_retry(prompt)
            
            if response_text and "I'm currently unable" not in response_text:
                logger.info("✅ Direct HTTP Gemini response successful")
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
                logger.warning("Direct HTTP Gemini returned empty response")
                return self._get_fallback_response(patient_query)
                
        except Exception as e:
            logger.error(f"Error in direct HTTP Gemini call: {e}")
            return self._get_fallback_response(patient_query)
    
    async def _make_gemini_request_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Make Gemini request with retry logic"""
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Direct HTTP Gemini attempt {attempt + 1}/{max_retries}")
                
                response = await self._make_gemini_request(prompt)
                
                if response:
                    logger.info(f"✅ Direct HTTP call successful on attempt {attempt + 1}")
                    return response
                else:
                    raise Exception("Empty response from direct HTTP API")
                    
            except Exception as e:
                logger.warning(f"Direct HTTP attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {max_retries} direct HTTP attempts failed")
                    return None
        
        return None
    
    async def _make_gemini_request(self, prompt: str) -> Optional[str]:
        """Make direct HTTP request to Gemini API"""
        
        url = f"{self.base_url}/{self.model_name}:generateContent"
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 2048
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract text from response
                        candidates = data.get("candidates", [])
                        if candidates and candidates[0].get("content"):
                            parts = candidates[0]["content"].get("parts", [])
                            if parts and parts[0].get("text"):
                                return parts[0]["text"]
                        
                        logger.warning("No text found in Gemini response")
                        return None
                    else:
                        error_text = await response.text()
                        logger.error(f"HTTP {response.status}: {error_text}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Gemini API request timed out")
            return None
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            return None
    
    def _create_medical_prompt(self, patient_query: PatientQuery, patient_context: Dict[str, Any] = None) -> str:
        """Create medical prompt for Gemini"""
        
        context_str = ""
        if patient_context:
            profile = patient_context.get('patient_profile', {})
            if profile:
                context_str += f"\nPatient Profile: Age {profile.get('age', 'unknown')}, Gender {profile.get('gender', 'unknown')}"
                if profile.get('medicines'):
                    context_str += f"\nCurrent Medications: {profile['medicines']}"
                if profile.get('allergies'):
                    context_str += f"\nAllergies: {profile['allergies']}"
                if profile.get('history'):
                    context_str += f"\nMedical History: {profile['history']}"
        
        return f"""You are a knowledgeable medical AI assistant. Provide helpful, accurate medical information while emphasizing the importance of professional medical consultation.

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
    
    def _get_fallback_response(self, patient_query: PatientQuery) -> StructuredGeminiOutput:
        """Get fallback response when direct HTTP fails"""
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
direct_gemini_service = DirectGeminiService()
