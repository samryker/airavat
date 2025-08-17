from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid

# --- Core Query and Response Models ---
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

class AgentResponse(BaseModel):
    request_id: str
    response_text: str
    suggestions: Optional[List[TreatmentSuggestion]] = None

# --- Structured Gemini Output and Feedback Models ---
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

class TreatmentPlanUpdate(BaseModel):
    patient_id: str
    treatment_plan: Dict[str, Any] = Field(description="Complete treatment plan data to be stored")
    plan_type: Optional[str] = Field(default="general", description="Type of treatment plan")
    priority: Optional[str] = Field(default="medium", description="Priority level: low, medium, high")
    notes: Optional[str] = Field(default=None, description="Additional notes about the treatment plan")

# --- Patient Context and Digital Twin Models ---
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

# --- Genetic Analysis Models ---
class GeneticReportUpload(BaseModel):
    user_id: str
    file_content: str  # Base64 encoded file content
    filename: str
    report_type: Optional[str] = "unknown"

class GeneticReportResponse(BaseModel):
    success: bool
    report_id: Optional[str] = None
    analysis_data: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None

# --- Patient Context Sync Models ---
class PatientContextSync(BaseModel):
    patient_id: str
    profile_data: Dict[str, Any]
    treatment_plans: List[Dict[str, Any]]
    biomarkers: Optional[Dict[str, Any]] = None
    genetic_data: Optional[Dict[str, Any]] = None

# --- Questionnaire and RL Training Models ---
class QuestionnaireResponse(BaseModel):
    patient_id: str
    request_id: str
    questions: List[Dict[str, Any]]
    answers: List[Dict[str, Any]]
    outcome_works: bool
    feedback_text: Optional[str] = None

# --- Notification and Reminder Models ---
class NotificationRequest(BaseModel):
    patient_id: str
    notification_type: str  # "reminder", "email", "emergency"
    title: str
    message: str
    scheduled_time: Optional[str] = None
    recipient_email: Optional[str] = None

# --- 3D Twin Models ---
class TwinCreationRequest(BaseModel):
    patient_id: str
    twin_config: Optional[Dict[str, Any]] = None

class TwinCreationResponse(BaseModel):
    success: bool
    twin_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None 