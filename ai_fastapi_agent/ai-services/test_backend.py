import pytest
import json
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from main_agent.main import app
from main_agent.data_models import PatientQuery, AgentResponse, FeedbackDataModel, TreatmentPlanUpdate
import tempfile
import os
from datetime import datetime, timedelta

# Create test client
client = TestClient(app)

# Test data constants
TEST_PATIENT_ID = "test_patient_123"
TEST_REQUEST_ID = "test_request_456"
TEST_USER_ID = "test_user_789"
TEST_REPORT_ID = "test_report_101"

class TestHealthEndpoints:
    """Test health check and root endpoints"""
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Airavat Medical AI Assistant" in data["message"]

class TestAgentEndpoints:
    """Test agent-related endpoints"""
    
    @patch('main_agent.main.MedicalAgent')
    def test_query_agent_success(self, mock_agent_class):
        """Test successful agent query"""
        # Mock the agent
        mock_agent = Mock()
        mock_agent.query.return_value = {
            "request_id": TEST_REQUEST_ID,
            "response_text": "Based on your symptoms, I recommend...",
            "suggestions": [
                {
                    "suggestion_text": "Take rest and stay hydrated",
                    "confidence_score": 0.85
                }
            ]
        }
        mock_agent_class.return_value = mock_agent
        
        # Test data
        query_data = {
            "patient_id": TEST_PATIENT_ID,
            "query_text": "I have a headache and fever",
            "request_id": TEST_REQUEST_ID,
            "symptoms": ["headache", "fever"],
            "medical_history": ["hypertension"],
            "current_medications": ["aspirin"]
        }
        
        response = client.post("/agent/query", json=query_data)
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == TEST_REQUEST_ID
        assert "response_text" in data
        assert "suggestions" in data
    
    @patch('main_agent.main.MedicalAgent')
    def test_query_agent_missing_patient_id(self, mock_agent_class):
        """Test agent query with missing patient_id"""
        query_data = {
            "query_text": "I have a headache"
        }
        
        response = client.post("/agent/query", json=query_data)
        assert response.status_code == 422  # Validation error
    
    @patch('main_agent.main.MedicalAgent')
    def test_query_agent_empty_query(self, mock_agent_class):
        """Test agent query with empty query text"""
        query_data = {
            "patient_id": TEST_PATIENT_ID,
            "query_text": ""
        }
        
        response = client.post("/agent/query", json=query_data)
        assert response.status_code == 422  # Validation error
    
    @patch('main_agent.main.MedicalAgent')
    def test_query_agent_agent_error(self, mock_agent_class):
        """Test agent query when agent raises an error"""
        # Mock the agent to raise an exception
        mock_agent = Mock()
        mock_agent.query.side_effect = Exception("Agent error")
        mock_agent_class.return_value = mock_agent
        
        query_data = {
            "patient_id": TEST_PATIENT_ID,
            "query_text": "I have a headache"
        }
        
        response = client.post("/agent/query", json=query_data)
        assert response.status_code == 500
    
    def test_submit_feedback_success(self):
        """Test successful feedback submission"""
        feedback_data = {
            "request_id": TEST_REQUEST_ID,
            "patient_id": TEST_PATIENT_ID,
            "outcome_works": True,
            "feedback_text": "The suggestion was very helpful"
        }
        
        response = client.post("/agent/feedback", json=feedback_data)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_submit_feedback_missing_fields(self):
        """Test feedback submission with missing required fields"""
        feedback_data = {
            "patient_id": TEST_PATIENT_ID,
            "outcome_works": True
        }
        
        response = client.post("/agent/feedback", json=feedback_data)
        assert response.status_code == 422
    
    @patch('main_agent.main.FirestoreService')
    def test_get_patient_memory_success(self, mock_firestore_class):
        """Test successful retrieval of patient memory"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_patient_memory.return_value = {
            "conversations": ["conversation1", "conversation2"],
            "treatment_plans": ["plan1", "plan2"]
        }
        
        response = client.get(f"/agent/memory/{TEST_PATIENT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data
        assert "treatment_plans" in data
    
    @patch('main_agent.main.FirestoreService')
    def test_get_patient_memory_not_found(self, mock_firestore_class):
        """Test patient memory retrieval for non-existent patient"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_patient_memory.return_value = None
        
        response = client.get(f"/agent/memory/nonexistent_patient")
        assert response.status_code == 404
    
    def test_update_treatment_plan_success(self):
        """Test successful treatment plan update"""
        plan_data = {
            "patient_id": TEST_PATIENT_ID,
            "treatment_plan": {
                "medications": ["aspirin", "ibuprofen"],
                "lifestyle_changes": ["rest", "hydration"],
                "follow_up": "1 week"
            },
            "plan_type": "acute_care",
            "priority": "high",
            "notes": "Patient has severe symptoms"
        }
        
        response = client.post("/agent/update_treatment_plan", json=plan_data)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_update_treatment_plan_invalid_data(self):
        """Test treatment plan update with invalid data"""
        plan_data = {
            "patient_id": TEST_PATIENT_ID,
            "treatment_plan": "invalid_data"  # Should be dict
        }
        
        response = client.post("/agent/update_treatment_plan", json=plan_data)
        assert response.status_code == 422

class TestPatientContextEndpoints:
    """Test patient context and history endpoints"""
    
    @patch('main_agent.main.FirestoreService')
    def test_get_patient_context_success(self, mock_firestore_class):
        """Test successful patient context retrieval"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_patient_context.return_value = {
            "patient_id": TEST_PATIENT_ID,
            "profile": {"age": 30, "gender": "male"},
            "treatment_plans": [{"id": "plan1", "type": "acute"}],
            "biomarkers": {"blood_pressure": "120/80"},
            "last_updated": "2024-01-01T00:00:00Z"
        }
        
        response = client.get(f"/agent/patient/{TEST_PATIENT_ID}/context")
        assert response.status_code == 200
        data = response.json()
        assert data["patient_id"] == TEST_PATIENT_ID
        assert "profile" in data
        assert "treatment_plans" in data
    
    @patch('main_agent.main.FirestoreService')
    def test_get_patient_context_not_found(self, mock_firestore_class):
        """Test patient context retrieval for non-existent patient"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_patient_context.return_value = None
        
        response = client.get(f"/agent/patient/nonexistent_patient/context")
        assert response.status_code == 404
    
    @patch('main_agent.main.FirestoreService')
    def test_get_conversation_history_success(self, mock_firestore_class):
        """Test successful conversation history retrieval"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_conversation_history.return_value = {
            "patient_id": TEST_PATIENT_ID,
            "conversation_history": [
                {"timestamp": "2024-01-01T00:00:00Z", "message": "Hello"},
                {"timestamp": "2024-01-01T01:00:00Z", "message": "How are you?"}
            ],
            "count": 2,
            "limit": 10
        }
        
        response = client.get(f"/agent/patient/{TEST_PATIENT_ID}/conversation-history?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["patient_id"] == TEST_PATIENT_ID
        assert "conversation_history" in data
        assert data["count"] == 2
    
    @patch('main_agent.main.FirestoreService')
    def test_get_conversation_history_with_limit(self, mock_firestore_class):
        """Test conversation history with custom limit"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_conversation_history.return_value = {
            "patient_id": TEST_PATIENT_ID,
            "conversation_history": [],
            "count": 0,
            "limit": 5
        }
        
        response = client.get(f"/agent/patient/{TEST_PATIENT_ID}/conversation-history?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
    
    def test_update_patient_treatment_plan_success(self):
        """Test successful patient treatment plan update"""
        treatment_plan = {
            "medications": ["aspirin"],
            "dosage": "500mg twice daily",
            "duration": "7 days"
        }
        
        response = client.post(f"/agent/patient/{TEST_PATIENT_ID}/treatment-plan", json=treatment_plan)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_submit_patient_feedback_success(self):
        """Test successful patient feedback submission"""
        feedback = {
            "request_id": TEST_REQUEST_ID,
            "outcome_works": True,
            "feedback_text": "The treatment worked well"
        }
        
        response = client.post(f"/agent/patient/{TEST_PATIENT_ID}/feedback", json=feedback)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    @patch('main_agent.main.FirestoreService')
    def test_get_patient_biomarkers_success(self, mock_firestore_class):
        """Test successful patient biomarkers retrieval"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_patient_biomarkers.return_value = {
            "patient_id": TEST_PATIENT_ID,
            "biomarkers": {
                "blood_pressure": "120/80",
                "heart_rate": "72 bpm",
                "temperature": "98.6°F",
                "blood_glucose": "95 mg/dL"
            }
        }
        
        response = client.get(f"/agent/patient/{TEST_PATIENT_ID}/biomarkers")
        assert response.status_code == 200
        data = response.json()
        assert data["patient_id"] == TEST_PATIENT_ID
        assert "biomarkers" in data
        assert "blood_pressure" in data["biomarkers"]

class TestGeneticAnalysisEndpoints:
    """Test genetic analysis endpoints"""
    
    def test_upload_genetic_report_success(self):
        """Test successful genetic report upload"""
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as temp_file:
            temp_file.write("Test PDF content")
            temp_file_path = temp_file.name
        
        try:
            with open(temp_file_path, 'rb') as file:
                response = client.post(
                    "/genetic/upload",
                    files={"file": ("test_report.pdf", file, "application/pdf")},
                    data={
                        "user_id": TEST_USER_ID,
                        "report_type": "health_report"
                    }
                )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "report_id" in data
        finally:
            os.unlink(temp_file_path)
    
    def test_upload_genetic_report_invalid_file(self):
        """Test genetic report upload with invalid file"""
        response = client.post(
            "/genetic/upload",
            files={"file": ("test.txt", b"invalid content", "text/plain")},
            data={
                "user_id": TEST_USER_ID,
                "report_type": "health_report"
            }
        )
        
        assert response.status_code == 400
    
    def test_upload_genetic_report_missing_user_id(self):
        """Test genetic report upload without user_id"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as temp_file:
            temp_file.write("Test PDF content")
            temp_file_path = temp_file.name
        
        try:
            with open(temp_file_path, 'rb') as file:
                response = client.post(
                    "/genetic/upload",
                    files={"file": ("test_report.pdf", file, "application/pdf")},
                    data={"report_type": "health_report"}
                )
            
            assert response.status_code == 422
        finally:
            os.unlink(temp_file_path)
    
    @patch('main_agent.main.GeneticAnalysisService')
    def test_get_genetic_report_success(self, mock_service_class):
        """Test successful genetic report retrieval"""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_report.return_value = {
            "report_id": TEST_REPORT_ID,
            "user_id": TEST_USER_ID,
            "analysis_data": {
                "risk_factors": ["diabetes", "heart_disease"],
                "recommendations": ["exercise", "diet"]
            },
            "status": "completed"
        }
        
        response = client.get(f"/genetic/reports/{TEST_REPORT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["report_id"] == TEST_REPORT_ID
        assert "analysis_data" in data
    
    @patch('main_agent.main.GeneticAnalysisService')
    def test_get_genetic_report_not_found(self, mock_service_class):
        """Test genetic report retrieval for non-existent report"""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_report.return_value = None
        
        response = client.get(f"/genetic/reports/nonexistent_report")
        assert response.status_code == 404
    
    @patch('main_agent.main.GeneticAnalysisService')
    def test_get_user_genetic_reports_success(self, mock_service_class):
        """Test successful user genetic reports retrieval"""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_user_reports.return_value = [
            {
                "report_id": "report1",
                "user_id": TEST_USER_ID,
                "status": "completed"
            },
            {
                "report_id": "report2",
                "user_id": TEST_USER_ID,
                "status": "processing"
            }
        ]
        
        response = client.get(f"/genetic/reports/user/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert all(report["user_id"] == TEST_USER_ID for report in data)

class TestNotificationEndpoints:
    """Test notification endpoints"""
    
    def test_create_notification_success(self):
        """Test successful notification creation"""
        notification_data = {
            "user_id": TEST_USER_ID,
            "title": "Medication Reminder",
            "message": "Time to take your medication",
            "notification_type": "medication_reminder",
            "priority": "high",
            "scheduled_time": "2024-01-01T10:00:00Z"
        }
        
        response = client.post("/notifications/create", json=notification_data)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_create_notification_missing_required_fields(self):
        """Test notification creation with missing required fields"""
        notification_data = {
            "user_id": TEST_USER_ID,
            "title": "Test Notification"
            # Missing message field
        }
        
        response = client.post("/notifications/create", json=notification_data)
        assert response.status_code == 422
    
    @patch('main_agent.main.NotificationService')
    def test_get_user_notifications_success(self, mock_service_class):
        """Test successful user notifications retrieval"""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_user_notifications.return_value = [
            {
                "id": "notif1",
                "user_id": TEST_USER_ID,
                "title": "Medication Reminder",
                "message": "Take your medication",
                "type": "medication_reminder",
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": "notif2",
                "user_id": TEST_USER_ID,
                "title": "Appointment Reminder",
                "message": "You have an appointment tomorrow",
                "type": "appointment_reminder",
                "created_at": "2024-01-01T01:00:00Z"
            }
        ]
        
        response = client.get(f"/notifications/user/{TEST_USER_ID}?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert all(notif["user_id"] == TEST_USER_ID for notif in data)
    
    @patch('main_agent.main.NotificationService')
    def test_get_user_notifications_with_limit(self, mock_service_class):
        """Test user notifications retrieval with custom limit"""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_user_notifications.return_value = []
        
        response = client.get(f"/notifications/user/{TEST_USER_ID}?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_medication_reminder_success(self):
        """Test successful medication reminder creation"""
        reminder_data = {
            "user_id": TEST_USER_ID,
            "medication_name": "Aspirin",
            "reminder_time": "08:00",
            "frequency": "daily"
        }
        
        response = client.post("/notifications/medication-reminder", json=reminder_data)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_create_medication_reminder_invalid_time(self):
        """Test medication reminder creation with invalid time format"""
        reminder_data = {
            "user_id": TEST_USER_ID,
            "medication_name": "Aspirin",
            "reminder_time": "invalid_time",
            "frequency": "daily"
        }
        
        response = client.post("/notifications/medication-reminder", json=reminder_data)
        assert response.status_code == 422

class TestTaskEndpoints:
    """Test task management endpoints"""
    
    def test_create_task_success(self):
        """Test successful task creation"""
        task_data = {
            "user_id": TEST_USER_ID,
            "title": "Schedule follow-up appointment",
            "description": "Call doctor to schedule follow-up",
            "due_date": "2024-01-15T00:00:00Z",
            "priority": "high",
            "task_type": "appointment"
        }
        
        response = client.post("/tasks/create", json=task_data)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_create_task_missing_required_fields(self):
        """Test task creation with missing required fields"""
        task_data = {
            "user_id": TEST_USER_ID,
            "title": "Test Task"
            # Missing description field
        }
        
        response = client.post("/tasks/create", json=task_data)
        assert response.status_code == 422
    
    @patch('main_agent.main.FirestoreService')
    def test_get_user_tasks_success(self, mock_firestore_class):
        """Test successful user tasks retrieval"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_user_tasks.return_value = [
            {
                "id": "task1",
                "user_id": TEST_USER_ID,
                "title": "Schedule appointment",
                "description": "Call doctor",
                "status": "pending",
                "due_date": "2024-01-15T00:00:00Z"
            },
            {
                "id": "task2",
                "user_id": TEST_USER_ID,
                "title": "Take medication",
                "description": "Take prescribed medication",
                "status": "completed",
                "due_date": "2024-01-10T00:00:00Z"
            }
        ]
        
        response = client.get(f"/tasks/user/{TEST_USER_ID}?status=all")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert all(task["user_id"] == TEST_USER_ID for task in data)
    
    @patch('main_agent.main.FirestoreService')
    def test_get_user_tasks_with_status_filter(self, mock_firestore_class):
        """Test user tasks retrieval with status filter"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_user_tasks.return_value = [
            {
                "id": "task1",
                "user_id": TEST_USER_ID,
                "title": "Schedule appointment",
                "description": "Call doctor",
                "status": "pending",
                "due_date": "2024-01-15T00:00:00Z"
            }
        ]
        
        response = client.get(f"/tasks/user/{TEST_USER_ID}?status=pending")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["status"] == "pending"

class TestUserProfileEndpoints:
    """Test user profile endpoints"""
    
    @patch('main_agent.main.FirestoreService')
    def test_get_user_profile_success(self, mock_firestore_class):
        """Test successful user profile retrieval"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_user_profile.return_value = {
            "user_id": TEST_USER_ID,
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "gender": "male",
            "medical_history": ["hypertension", "diabetes"],
            "emergency_contact": {
                "name": "Jane Doe",
                "phone": "+1234567890"
            }
        }
        
        response = client.get(f"/user/profile/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == TEST_USER_ID
        assert "name" in data
        assert "email" in data
        assert "medical_history" in data
    
    @patch('main_agent.main.FirestoreService')
    def test_get_user_profile_not_found(self, mock_firestore_class):
        """Test user profile retrieval for non-existent user"""
        mock_firestore = Mock()
        mock_firestore_class.return_value = mock_firestore
        mock_firestore.get_user_profile.return_value = None
        
        response = client.get(f"/user/profile/nonexistent_user")
        assert response.status_code == 404
    
    def test_update_user_profile_success(self):
        """Test successful user profile update"""
        profile_data = {
            "name": "John Doe Updated",
            "email": "john.updated@example.com",
            "age": 31,
            "medical_history": ["hypertension", "diabetes", "asthma"],
            "emergency_contact": {
                "name": "Jane Doe",
                "phone": "+1234567890",
                "relationship": "spouse"
            }
        }
        
        response = client.put(f"/user/profile/{TEST_USER_ID}", json=profile_data)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_update_user_profile_invalid_data(self):
        """Test user profile update with invalid data"""
        profile_data = {
            "age": "invalid_age",  # Should be integer
            "email": "invalid_email"  # Invalid email format
        }
        
        response = client.put(f"/user/profile/{TEST_USER_ID}", json=profile_data)
        assert response.status_code == 422

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_invalid_endpoint(self):
        """Test accessing non-existent endpoint"""
        response = client.get("/invalid/endpoint")
        assert response.status_code == 404
    
    def test_method_not_allowed(self):
        """Test using wrong HTTP method"""
        response = client.put("/health")  # Health endpoint only supports GET
        assert response.status_code == 405
    
    def test_malformed_json(self):
        """Test sending malformed JSON"""
        response = client.post(
            "/agent/query",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_large_payload(self):
        """Test sending very large payload"""
        large_query = "x" * 10000  # 10KB payload
        query_data = {
            "patient_id": TEST_PATIENT_ID,
            "query_text": large_query
        }
        
        response = client.post("/agent/query", json=query_data)
        # Should either succeed or return appropriate error
        assert response.status_code in [200, 413, 422]

class TestCORSHeaders:
    """Test CORS headers"""
    
    def test_cors_headers_present(self):
        """Test that CORS headers are present in responses"""
        response = client.get("/health")
        assert response.status_code == 200
        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"]) 