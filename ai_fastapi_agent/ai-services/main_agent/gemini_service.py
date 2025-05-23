import os
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, Any, List
from .data_models import PatientQuery
import datetime # For formatting timestamps

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it in your .env file.")
genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-pro"

try:
    model = genai.GenerativeModel(MODEL_NAME)
except Exception as e:
    print(f"Error initializing Gemini model ({MODEL_NAME}): {e}")
    raise

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

async def get_treatment_suggestion_from_gemini(patient_query: PatientQuery, firestore_context: Dict[str, Any] = None) -> str:
    if not model:
        return "Error: Gemini model not initialized."

    # Oncologist Persona added to the system prompt
    prompt_parts = [
        "You are Airavat, an AI medical assistant with a specialization as an oncologist. Your role is to provide preliminary insights and suggestions based on the information provided, with a focus on oncological conditions if relevant, but also considering general health. You are not a substitute for a human doctor. Always advise the user to consult with a qualified healthcare professional for diagnosis and treatment.",
        "Please analyze the following patient information and provide a thoughtful, step-by-step preliminary suggestion. Consider potential next steps, relevant questions to ask the patient, or areas of focus for a human doctor, especially from an oncological perspective if applicable.",
        f"\nPatient Query: {patient_query.query_text}"
    ]

    if patient_query.symptoms:
        prompt_parts.append(f"Reported Symptoms: {', '.join(patient_query.symptoms)}")
    if patient_query.medical_history:
        prompt_parts.append(f"Relevant Medical History (as reported by user): {', '.join(patient_query.medical_history)}")
    if patient_query.current_medications:
        prompt_parts.append(f"Current Medications (as reported by user): {', '.join(patient_query.current_medications)}")

    prompt_parts.append("\n--- Patient Record Information (from Firebase) ---")
    data_to_format = None
    if firestore_context and firestore_context.get("data_from_firestore"):
        data_to_format = firestore_context["data_from_firestore"].get("patient_record")
    
    if data_to_format:
        formatted_context_parts = format_patient_record_for_prompt(data_to_format)
        prompt_parts.extend(formatted_context_parts)
    elif firestore_context and firestore_context.get("error"):
        prompt_parts.append(f"  Note: There was an issue retrieving full patient records: {firestore_context.get('error')}")
        prompt_parts.append("  No patient record data could be used.")
    else:
        prompt_parts.append("  No additional patient context was available from records for this query.")
    
    prompt_parts.append("\n--- End of Patient Record Information ---")
    prompt_parts.append("\nBased on all the above information (user query and patient record), what are your preliminary suggestions and insights? Be cautious, empathetic, and maintain your oncologist persona where relevant. Provide clear, actionable steps if appropriate, and always emphasize consultation with a human doctor for diagnosis and treatment.")
    
    full_prompt = "\n".join(prompt_parts)

    print("\n--- Sending Prompt to Gemini ---")
    print(full_prompt)
    print("--- End of Prompt ---\n")

    try:
        response = await model.generate_content_async(full_prompt)
        if response and response.parts:
            suggestion_text = ''.join(part.text for part in response.parts if hasattr(part, 'text'))
            if not suggestion_text and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                 suggestion_text = ''.join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
        elif response and hasattr(response, 'text'):
            suggestion_text = response.text
        else:
            suggestion_text = "No suggestion was generated or the response format is unexpected."
            print(f"Unexpected Gemini response structure: {response}")
        return suggestion_text.strip()
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return f"Error: Could not get suggestion from AI model due to: {str(e)}"

# Example usage (can be run directly for testing if needed)
# if __name__ == '__main__':
#     import asyncio
#     async def main():
#         test_query = "I have a persistent cough and slight fever for 3 days."
#         # response_text = await get_gemini_response(f"What are common causes for: {test_query}")
#         response_text = await get_treatment_suggestion_from_gemini(test_query)
#         print(f"Gemini Response: {response_text}")
#     asyncio.run(main()) 