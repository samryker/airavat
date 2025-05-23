from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class PatientQuery(BaseModel):
    patient_id: str
    query_text: str
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