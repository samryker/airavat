from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

from firebase_admin import firestore

try:  # LLM integration
    from main_agent.mcp_medical_agent import RealGeminiLLM, AIMessage
    _llm = RealGeminiLLM(
        model="gemini-1.5-pro",
        temperature=0.1,
        max_tokens=512,
        convert_system_message_to_human=True,
    )
except Exception:  # Fallback dummy model when LLM not available
    class AIMessage:  # minimal stand-in
        def __init__(self, content: str):
            self.content = content

    class _DummyLLM:
        async def ainvoke(self, prompt: str) -> AIMessage:
            return AIMessage("LLM service unavailable")

    _llm = _DummyLLM()


_db_client: Optional[firestore.Client] = None


def _get_db() -> Optional[firestore.Client]:
    """Lazily acquire Firestore client after firebase_admin initialization."""
    global _db_client
    if _db_client is None:
        try:
            _db_client = firestore.client()
        except Exception:
            _db_client = None
    return _db_client

router = APIRouter(prefix="/digital_twin", tags=["Digital Twin"])


class DigitalTwinPayload(BaseModel):
    """Incoming payload for updating a digital twin."""
    height_cm: float
    weight_kg: float
    biomarkers: Optional[Dict[str, float]] = None


class DigitalTwinRecord(DigitalTwinPayload):
    """Stored representation of a digital twin."""
    patient_id: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)


_twin_store: Dict[str, DigitalTwinRecord] = {}


class TreatmentUpdatePayload(DigitalTwinPayload):
    """Payload containing real-time data and a report from chat assistant."""
    report: str


class TreatmentUpdateResponse(BaseModel):
    twin: DigitalTwinRecord
    inference: str
    stored: bool


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Simple health check for the digital twin service."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.put("/{patient_id}", response_model=DigitalTwinRecord)
async def upsert_twin(patient_id: str, payload: DigitalTwinPayload) -> DigitalTwinRecord:
    """Create or update a digital twin for the specified patient."""
    record = DigitalTwinRecord(patient_id=patient_id, **payload.model_dump())
    _twin_store[patient_id] = record
    return record


@router.get("/{patient_id}", response_model=DigitalTwinRecord)
async def get_twin(patient_id: str) -> DigitalTwinRecord:
    """Retrieve the digital twin for a patient."""
    record = _twin_store.get(patient_id)
    if not record:
        raise HTTPException(status_code=404, detail="Digital twin not found")
    return record


@router.post("/{patient_id}/treatment", response_model=TreatmentUpdateResponse)
async def process_treatment(patient_id: str, payload: TreatmentUpdatePayload) -> TreatmentUpdateResponse:
    """Update twin, infer treatment via LLM, and store in Firestore."""
    record = DigitalTwinRecord(patient_id=patient_id, **payload.model_dump(exclude={"report"}))
    _twin_store[patient_id] = record

    prompt = (
        "Given the following patient data and report, provide a concise treatment update:\n"
        f"Data: {payload.model_dump(exclude={'report'})}\nReport: {payload.report}"
    )
    result = await _llm.ainvoke(prompt)
    inference = getattr(result, "content", str(result))

    stored = False
    db = _get_db()
    if db:
        try:
            db.collection("updated_treatment").document(patient_id).set(
                {
                    "patient_id": patient_id,
                    "twin": record.model_dump(),
                    "report": payload.report,
                    "inference": inference,
                    "updated_at": datetime.utcnow(),
                }
            )
            stored = True
        except Exception:
            stored = False

    return TreatmentUpdateResponse(twin=record, inference=inference, stored=stored)
