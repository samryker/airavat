# tests for digital twin service
import pytest
from fastapi.testclient import TestClient
from main_agent.main import app
from digital_twin_service import router as dt_router

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/digital_twin/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_upsert_and_get_twin():
    payload = {"height_cm": 180.0, "weight_kg": 75.0, "biomarkers": {"bmi": 23.1}}
    response = client.put("/digital_twin/patient123", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "patient123"
    assert data["height_cm"] == 180.0
    assert data["biomarkers"]["bmi"] == 23.1

    get_resp = client.get("/digital_twin/patient123")
    assert get_resp.status_code == 200
    retrieved = get_resp.json()
    assert retrieved["patient_id"] == "patient123"
    assert retrieved["weight_kg"] == 75.0


def test_get_twin_not_found():
    response = client.get("/digital_twin/unknown")
    assert response.status_code == 404


def test_process_treatment(monkeypatch):
    class DummyLLM:
        async def ainvoke(self, prompt):
            class R:
                content = "rest"
            return R()

    class DummyDoc:
        def __init__(self):
            self.data = None
        def set(self, data):
            self.data = data

    class DummyCollection:
        def __init__(self):
            self.doc = DummyDoc()
            self.name = None
        def document(self, doc_id):
            return self.doc

    class DummyDB:
        def __init__(self):
            self.collection_name = None
            self.collection_obj = DummyCollection()
        def collection(self, name):
            self.collection_name = name
            return self.collection_obj

    dt_router._llm = DummyLLM()
    dt_router._db_client = DummyDB()

    payload = {"height_cm": 170.0, "weight_kg": 70.0, "report": "report text"}
    resp = client.post("/digital_twin/patientABC/treatment", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["inference"] == "rest"
    assert data["stored"] is True
