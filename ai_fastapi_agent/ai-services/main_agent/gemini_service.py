import os
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, Any, List, Union
from .data_models import PatientQuery, StructuredGeminiOutput, GeminiResponseFeatures
import datetime
import asyncio
import json
import logging

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables (respect existing env set by deployment)
load_dotenv()  # do not override real env injected by platform
try:
    _module_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(_module_env_path)  # local dev convenience only
except Exception:
    pass

# Initialize Gemini service (support both GEMINI_API_KEY and GOOGLE_API_KEY)
_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if _API_KEY:
    try:
        # Configure with explicit API key
        genai.configure(api_key=_API_KEY)
        
        # Use the most stable model name for Generative AI API
        # Don't test during initialization to avoid startup failures
        model = genai.GenerativeModel("gemini-pro")
        logger.info("Gemini service initialized with model: gemini-pro")
            
    except Exception as _e:
        logger.exception(f"Failed to initialize Gemini service: {_e}")
        model = None
else:
    model = None
    logger.warning("Gemini/Google API key not found - service will use fallback responses")

def is_gemini_available() -> bool:
    """Check if Gemini API is available and configured."""
    return model is not None

async def test_gemini_connection() -> Dict[str, Any]:
    """Test Gemini API connection at runtime (not during initialization)"""
    if not model:
        return {"available": False, "error": "Model not initialized"}
    
    try:
        # Test with a simple query
        if hasattr(model, "generate_content_async"):
            response = await model.generate_content_async("Hello")
        else:
            response = await asyncio.to_thread(model.generate_content, "Hello")
        
        if response and hasattr(response, 'text') and response.text:
            return {"available": True, "test_response": response.text[:100]}
        else:
            return {"available": False, "error": "Empty response from API"}
            
    except Exception as e:
        return {"available": False, "error": str(e)}

def format_firestore_timestamp(timestamp_obj) -> str:
    """Safely formats a Firestore Timestamp (or datetime object) to a string."""
    if isinstance(timestamp_obj, datetime.datetime):
        return timestamp_obj.strftime("%Y-%m-%d %H:%M:%S UTC")
    # Add handling for google.cloud.firestore_v1.base_timestamp.Timestamp if necessary
    # This can occur if the raw data from Firestore isn't automatically converted to datetime
    if hasattr(timestamp_obj, 'strftime'): # Duck typing for datetime-like objects
         return timestamp_obj.strftime("%Y-%m-%d %H:%M:%S UTC")
    if hasattr(timestamp_obj, 'to_datetime'): # For Firestore Timestamp
        try:
            return timestamp_obj.to_datetime().strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return str(timestamp_obj) # Fallback
    return str(timestamp_obj) # Fallback if not a recognized timestamp type

def format_patient_record_for_prompt(patient_record: Dict[str, Any]) -> List[str]:
    """Helper function to format the structured patient record for the LLM prompt."""
    context_prompt_parts = []

    if not patient_record:
        context_prompt_parts.append("  No detailed patient record was available.")
        return context_prompt_parts

    # Core profile fields (example)
    core_fields = ['email', 'bmiIndex', 'medicines', 'allergies', 'history', 'goal', 'age', 'race', 'gender']
    context_prompt_parts.append("  Patient Profile Data:")
    for key in core_fields:
        value = patient_record.get(key)
        if value is not None:
             # For lists like 'habits', join them into a string
            if isinstance(value, list):
                context_prompt_parts.append(f"    {key.replace('_', ' ').title()}: {', '.join(map(str, value))}")
            else:
                context_prompt_parts.append(f"    {key.replace('_', ' ').title()}: {value}")
        else:
            context_prompt_parts.append(f"    {key.replace('_', ' ').title()}: Not provided")
    
    # Habits (if stored separately or needs special formatting)
    habits = patient_record.get('habits')
    if habits and isinstance(habits, list) and 'habits' not in core_fields: # if not already processed
        context_prompt_parts.append(f"    Habits: {', '.join(habits)}")
    elif 'habits' not in core_fields:
        context_prompt_parts.append(f"    Habits: Not provided")

    # Embedded Treatment Plans
    treatment_plans = patient_record.get("treatmentPlans") # From your Flutter code
    if treatment_plans and isinstance(treatment_plans, list):
        context_prompt_parts.append("  Treatment Plans (from patient record):")
        for i, plan in enumerate(treatment_plans):
            context_prompt_parts.append(f"    Plan {i+1}:")
            for key, value in plan.items():
                if value is not None:
                    if key in ['startDate', 'endDate']:
                        value = format_firestore_timestamp(value)
                    context_prompt_parts.append(f"      {key.replace('_', ' ').title()}: {value}")
    else:
        context_prompt_parts.append("  Treatment Plans: None found in record or not applicable.")

    # Lab Reports Metadata (Placeholder - from subcollection)
    lab_reports_metadata = patient_record.get("recent_lab_reports_metadata")
    if lab_reports_metadata and isinstance(lab_reports_metadata, list):
        context_prompt_parts.append("  Recent Lab Reports Metadata (up to 5 newest - filename/type, date):")
        for i, report_meta in enumerate(lab_reports_metadata):
            context_prompt_parts.append(f"    Report Meta {i+1}:")
            # Example: customize based on fields in your lab_reports metadata documents
            report_name = report_meta.get('reportName', 'N/A')
            report_date_obj = report_meta.get('reportDate')
            report_date = format_firestore_timestamp(report_date_obj) if report_date_obj else 'N/A'
            file_url = report_meta.get('fileUrl', 'N/A') # If you store a URL to the file
            extracted_text_preview = report_meta.get('extractedText', '')[:100] + '...' if report_meta.get('extractedText') else 'N/A'

            context_prompt_parts.append(f"      Name/Type: {report_name}")
            context_prompt_parts.append(f"      Date: {report_date}")
            if file_url != 'N/A': context_prompt_parts.append(f"      File Reference: {file_url}")
            if extracted_text_preview != 'N/A': context_prompt_parts.append(f"      Extracted Text Preview: {extracted_text_preview}")
            # Add other relevant metadata fields
    else:
        context_prompt_parts.append("  Recent Lab Reports Metadata: None found or available.")
    
    fetch_warnings = patient_record.get("context_fetch_warnings")
    if fetch_warnings:
        context_prompt_parts.append("  Important Notes on Context Retrieval:")
        if isinstance(fetch_warnings, list):
            for warning in fetch_warnings:
                context_prompt_parts.append(f"    - {warning}")
        else:
            context_prompt_parts.append(f"    - {fetch_warnings}")

    return context_prompt_parts

async def get_treatment_suggestion_from_gemini(patient_query: PatientQuery, patient_context: Dict[str, Any] = None) -> StructuredGeminiOutput:
    """
    Get treatment suggestion from Gemini API
    """
    if not is_gemini_available():
        logger.warning("Gemini service is not available. Returning fallback response.")
        
        # Return a fallback response
        return StructuredGeminiOutput(
            text="I'm currently unable to process your medical query. Please consult with a healthcare professional for personalized medical advice.",
            features=GeminiResponseFeatures(
                category="medical_query",
                urgency="medium",
                keywords=patient_query.symptoms if patient_query.symptoms else [],
                actionable_steps_present=False
            )
        )
    
    try:
        # Create comprehensive prompt for medical consultation
        prompt = f"""You are a knowledgeable medical AI assistant. Provide helpful, accurate medical information while emphasizing the importance of professional medical consultation.

Patient Query: {patient_query.query_text}
Patient ID: {patient_query.patient_id}
Symptoms: {', '.join(patient_query.symptoms) if patient_query.symptoms else 'None specified'}

Context: {json.dumps(patient_context, default=str) if patient_context else 'No additional context provided'}

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

        # Retry logic for API calls with exponential backoff
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Compatibility: use async method if available, otherwise offload sync call
                if hasattr(model, "generate_content_async"):
                    response = await model.generate_content_async(prompt)
                else:
                    response = await asyncio.to_thread(model.generate_content, prompt)
                
                if response and hasattr(response, 'text') and response.text:
                    response_text = response.text
                    logger.info(f"Gemini API call successful on attempt {attempt + 1}")
                    break
                else:
                    raise Exception("Empty response from Gemini API")
                    
            except Exception as api_error:
                logger.warning(f"Gemini API attempt {attempt + 1} failed: {api_error}")
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    raise api_error
        else:
            response_text = "I apologize, but I'm having trouble processing your request right now. Please try again or consult with a healthcare professional."
        
        # Extract keywords from the response and query
        keywords = patient_query.symptoms if patient_query.symptoms else []
        if patient_query.query_text:
            # Simple keyword extraction (could be enhanced)
            query_words = patient_query.query_text.lower().split()
            medical_keywords = [word for word in query_words if len(word) > 3]
            keywords.extend(medical_keywords[:5])  # Limit to 5 additional keywords
        
        features = GeminiResponseFeatures(
            category="medical_query",
            urgency="medium",
            keywords=list(set(keywords)),  # Remove duplicates
            actionable_steps_present=True
        )
        
        return StructuredGeminiOutput(text=response_text, features=features)
        
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        
        # Return fallback response on error
        return StructuredGeminiOutput(
            text="I apologize, but I'm experiencing technical difficulties right now. Please try again later or consult with a healthcare professional for immediate assistance.",
            features=GeminiResponseFeatures(
                category="system_error",
                urgency="medium",
                keywords=["technical_issue"],
                actionable_steps_present=True
            )
        )

# Example usage (can be run directly for testing if needed)
# if __name__ == '__main__':
#     import asyncio
#     async def main():
#         test_query = "I have a persistent cough and slight fever for 3 days."
#         # response_text = await get_gemini_response(f"What are common causes for: {test_query}")
#         response_text = await get_treatment_suggestion_from_gemini(test_query)
#         print(f"Gemini Response: {response_text}")
#     asyncio.run(main()) 