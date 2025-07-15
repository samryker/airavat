import os
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, Any, List, Union
from .data_models import PatientQuery, StructuredGeminiOutput, GeminiResponseFeatures
import datetime
import json
import logging

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
model = None

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        MODEL_NAME = "gemini-1.5-pro"
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        model = genai.GenerativeModel(MODEL_NAME, generation_config=generation_config)
        logger.info(f"Gemini model ({MODEL_NAME}) initialized successfully with JSON mode.")
    except Exception as e:
        logger.exception(f"Error initializing Gemini model ({MODEL_NAME}): {e}")
        model = None
else:
    logger.warning("GEMINI_API_KEY not found in environment variables. Gemini features will be disabled.")

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

async def get_treatment_suggestion_from_gemini(patient_query: PatientQuery, firestore_context: Dict[str, Any] = None) -> StructuredGeminiOutput:
    default_error_features = GeminiResponseFeatures(category="error_response", urgency="unknown", actionable_steps_present=False)
    if not model:
        logger.warning("Gemini model not available. Returning fallback response.")
        return StructuredGeminiOutput(
            text="I'm here to help with your health questions. Please note that AI features are currently limited. For medical advice, always consult with a qualified healthcare professional.",
            features=GeminiResponseFeatures(
                category="general_advice",
                urgency="low",
                keywords=["health", "consultation"],
                actionable_steps_present=True
            )
        )

    # Construct JSON schema based on Pydantic model for the prompt
    json_schema_prompt = f"""\
Please respond ONLY with a JSON object matching the following Pydantic model schema:
```json
{{
  \"text\": \"string (The main textual suggestion for the user)\",
  \"features\": {{
    \"category\": \"string (e.g., general_advice, specific_recommendation, further_questions, error_response)\",
    \"urgency\": \"string (e.g., low, medium, high)\",
    \"keywords\": [\"string (important keywords from suggestion)\"],
    \"actionable_steps_present\": \"boolean (True if suggestion has clear actionable steps)\"
  }}
}}
```
Ensure the entire response is a single, valid JSON object and nothing else.
"""

    prompt_parts = [
        "You are Airavat, an AI medical assistant specializing in oncology... Always advise user to consult with a qualified healthcare professional...",
        f"Patient Query: {patient_query.query_text}",
    ]

    if patient_query.symptoms:
        prompt_parts.append(f"Reported Symptoms: {', '.join(patient_query.symptoms)}")
    if patient_query.medical_history:
        prompt_parts.append(f"Relevant Medical History: {', '.join(patient_query.medical_history)}")
    if patient_query.current_medications:
        prompt_parts.append(f"Current Medications: {', '.join(patient_query.current_medications)}")

    prompt_parts.append("\n--- Patient Record Information (from Firebase) ---")
    data_to_format = firestore_context.get("data_from_firestore", {}).get("patient_record") if firestore_context else None
    
    if data_to_format:
        prompt_parts.extend(format_patient_record_for_prompt(data_to_format))
    elif firestore_context and firestore_context.get("error"):
        prompt_parts.append(f"  Note: Error retrieving records: {firestore_context.get('error')}")
    else:
        prompt_parts.append("  No additional patient context available from records.")
    
    prompt_parts.append("\n--- End of Patient Record Information ---")
    prompt_parts.append("\nBased on all the above, provide your preliminary suggestions and insights.")
    prompt_parts.append(json_schema_prompt)
    
    full_prompt = "\n".join(prompt_parts)
    logger.info(f"\n--- Sending Prompt to Gemini (expecting JSON) ---\n{full_prompt}\n--- End of Prompt ---\n")

    try:
        response = await model.generate_content_async(full_prompt)
        raw_response_text = response.text
        logger.info(f"Raw Gemini JSON response: {raw_response_text}")
        
        parsed_json = json.loads(raw_response_text)
        structured_output = StructuredGeminiOutput(**parsed_json)
        return structured_output
    
    except json.JSONDecodeError as e_json:
        logger.error(f"JSONDecodeError parsing Gemini response: {e_json}. Raw response: '{raw_response_text[:500]}...'")
        return StructuredGeminiOutput(text=f"Error: Could not parse AI model JSON response. Raw: {raw_response_text}", features=default_error_features)
    except Exception as e:
        logger.exception(f"Error calling Gemini API or processing its response: {e}")
        return StructuredGeminiOutput(text=f"Error: Could not get suggestion from AI model due to: {str(e)}", features=default_error_features)

# Example usage (can be run directly for testing if needed)
# if __name__ == '__main__':
#     import asyncio
#     async def main():
#         test_query = "I have a persistent cough and slight fever for 3 days."
#         # response_text = await get_gemini_response(f"What are common causes for: {test_query}")
#         response_text = await get_treatment_suggestion_from_gemini(test_query)
#         print(f"Gemini Response: {response_text}")
#     asyncio.run(main()) 