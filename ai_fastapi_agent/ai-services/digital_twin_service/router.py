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
        "Given the following patient data and report, provide a concise treatment update. Always proacively provie the patient with tests if needed and suggestive lifestyle changes :\n"
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


@router.get("/{patient_id}/live", response_model=Dict[str, Any])
async def get_live_twin_data(patient_id: str) -> Dict[str, Any]:
    """Get complete live twin data combining SMPL model + biomarkers + AI insights."""
    try:
        # Get SMPL model data
        smpl_data = {}
        twin_record = _twin_store.get(patient_id)
        if twin_record:
            smpl_data = {
                "height_cm": twin_record.height_cm,
                "weight_kg": twin_record.weight_kg,
                "bmi": round(twin_record.weight_kg / ((twin_record.height_cm / 100) ** 2), 1),
                "biomarkers": twin_record.biomarkers or {}
            }
        
        # Get biomarkers from Firestore
        biomarkers = {}
        db = _get_db()
        if db:
            try:
                # Get from twin_customizations collection
                twin_doc = db.collection("twin_customizations").document(patient_id).get()
                if twin_doc.exists:
                    twin_data = twin_doc.to_dict()
                    biomarkers = twin_data.get("biomarkers", {})
                
                # Also check biomarkers collection
                biomarker_docs = db.collection("biomarkers").document(patient_id).collection("reports").order_by("timestamp", direction="desc").limit(1).get()
                for doc in biomarker_docs:
                    latest_biomarkers = doc.to_dict().get("biomarkers", {})
                    biomarkers.update(latest_biomarkers)
                    
            except Exception as e:
                print(f"Error fetching biomarkers: {e}")
        
        # Generate AI insights
        ai_insights = ""
        if biomarkers and smpl_data:
            prompt = f"""
            Analyze this patient's live data and provide 3-4 key health insights:
            
            Physical: Height {smpl_data.get('height_cm', 'unknown')}cm, Weight {smpl_data.get('weight_kg', 'unknown')}kg, BMI {smpl_data.get('bmi', 'unknown')}
            Biomarkers: {biomarkers}
            
            Provide brief, actionable insights about their health status.Be suugestive and proactive about the patient's health.
            """
            try:
                result = await _llm.ainvoke(prompt)
                ai_insights = getattr(result, "content", "AI insights temporarily unavailable")
            except Exception:
                ai_insights = "AI insights temporarily unavailable"
        
        return {
            "patient_id": patient_id,
            "smpl_data": smpl_data,
            "biomarkers": biomarkers,
            "ai_insights": ai_insights,
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "data_sources": {
                "smpl": bool(twin_record),
                "biomarkers": bool(biomarkers),
                "ai_insights": bool(ai_insights)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting live twin data: {str(e)}")


@router.post("/{patient_id}/biomarkers")
async def update_biomarkers(patient_id: str, biomarkers: Dict[str, Any]) -> Dict[str, Any]:
    """Update patient biomarkers for live twin visualization."""
    try:
        db = _get_db()
        if not db:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Store in biomarkers collection
        biomarker_data = {
            "biomarkers": biomarkers,
            "timestamp": datetime.utcnow(),
            "reportType": "live_update"
        }
        
        db.collection("biomarkers").document(patient_id).collection("reports").add(biomarker_data)
        
        # Also update twin_customizations for quick access
        db.collection("twin_customizations").document(patient_id).set({
            "userId": patient_id,
            "biomarkers": biomarkers,
            "lastUpdated": datetime.utcnow()
        }, merge=True)
        
        return {
            "status": "success",
            "message": "Biomarkers updated successfully",
            "patient_id": patient_id,
            "biomarker_count": len(biomarkers)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating biomarkers: {str(e)}")
