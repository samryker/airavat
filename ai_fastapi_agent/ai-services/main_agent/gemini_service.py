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

# Load environment variables
load_dotenv()

# Disable Gemini service - API key removed for security
logger.warning("Gemini service disabled - API key removed for security reasons.")

# Initialize Gemini client (disabled)
model = None

def is_gemini_available() -> bool:
    """Check if Gemini API is available and configured."""
    return False

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
    Get treatment suggestion from Gemini API (DISABLED - returns fallback response)
    """
    logger.warning("Gemini service is disabled. Returning fallback response.")
    
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

# Example usage (can be run directly for testing if needed)
# if __name__ == '__main__':
#     import asyncio
#     async def main():
#         test_query = "I have a persistent cough and slight fever for 3 days."
#         # response_text = await get_gemini_response(f"What are common causes for: {test_query}")
#         response_text = await get_treatment_suggestion_from_gemini(test_query)
#         print(f"Gemini Response: {response_text}")
#     asyncio.run(main()) 