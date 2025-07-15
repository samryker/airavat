from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid

class PatientQuery(BaseModel):
    patient_id: str
    query_text: str
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    symptoms: Optional[List[str]] = None
    medical_history: Optional[List[str]] = None
    current_medications: Optional[List[str]] = None
    additional_data: Optional[Dict[str, Any]] = None

class TreatmentSuggestion(BaseModel):
    suggestion_text: str
    confidence_score: Optional[float] = None
    supporting_evidence_ids: Optional[List[str]] = None # IDs from MCP knowledge base
    # Add more structured output fields as the agent develops

class AgentResponse(BaseModel):
    request_id: str
    response_text: str
    suggestions: Optional[List[TreatmentSuggestion]] = None
    # Add other relevant response fields 

# --- New Models for Structured Gemini Output and Feedback ---
class GeminiResponseFeatures(BaseModel):
    category: str = Field(default="unknown", description="Category of the response, e.g., general_advice, specific_recommendation, further_questions, error_response")
    urgency: str = Field(default="medium", description="Perceived urgency, e.g., low, medium, high")
    keywords: List[str] = Field(default_factory=list, description="List of important keywords from the suggestion")
    actionable_steps_present: bool = Field(default=False, description="True if the suggestion contains clear actionable steps")

class StructuredGeminiOutput(BaseModel):
    text: str = Field(description="The main textual suggestion for the user.")
    features: GeminiResponseFeatures = Field(description="Structured features of the response for RL agent.")

class FeedbackDataModel(BaseModel):
    request_id: str # To link feedback to the original interaction log
    patient_id: str
    outcome_works: bool
    feedback_text: Optional[str] = None
    # Optional: patient_context_at_feedback (dict for current Hgb, risk, therapy when giving feedback)
    # This would help determine the "next_state" more accurately.

class TreatmentPlanUpdate(BaseModel):
    patient_id: str
    treatment_plan: Dict[str, Any] = Field(description="Complete treatment plan data to be stored")
    plan_type: Optional[str] = Field(default="general", description="Type of treatment plan")
    priority: Optional[str] = Field(default="medium", description="Priority level: low, medium, high")
    notes: Optional[str] = Field(default=None, description="Additional notes about the treatment plan")

# --- New Models for Digital Twin Functionality ---
class PatientContext(BaseModel):
    patient_id: str
    profile: Optional[Dict[str, Any]] = None
    treatment_plans: Optional[List[Dict[str, Any]]] = None
    biomarkers: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None
    last_updated: Optional[str] = None

class ConversationHistory(BaseModel):
    patient_id: str
    conversation_history: List[Dict[str, Any]]
    count: int
    limit: int

class BiomarkerData(BaseModel):
    patient_id: str
    biomarkers: Optional[Dict[str, Any]] = None 