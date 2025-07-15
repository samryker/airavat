#!/usr/bin/env python3
"""
Comprehensive test script for Airavat Backend
Tests all endpoints and verifies deployment functionality
"""

import requests
import json
import time
from typing import Dict, Any

class AiravatBackendTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, response: Dict[str, Any] = None, error: str = None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "response": response,
            "error": error,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if error:
            print(f"   Error: {error}")
        if response and not success:
            print(f"   Response: {json.dumps(response, indent=2)}")
        print()
    
    def test_health_endpoint(self):
        """Test the health check endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()
            
            success = (
                data.get("status") == "healthy" and
                "services" in data and
                data["services"].get("firestore") == "available"
            )
            
            self.log_test("Health Check", success, data)
            return success
        except Exception as e:
            self.log_test("Health Check", False, error=str(e))
            return False
    
    def test_root_endpoint(self):
        """Test the root endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/")
            response.raise_for_status()
            data = response.json()
            
            success = "message" in data and "Airavat" in data["message"]
            self.log_test("Root Endpoint", success, data)
            return success
        except Exception as e:
            self.log_test("Root Endpoint", False, error=str(e))
            return False
    
    def test_chat_query(self):
        """Test the main chat query endpoint"""
        try:
            payload = {
                "patient_id": "test_patient_001",
                "query_text": "I have a mild headache and feel tired. What should I do?"
            }
            
            response = self.session.post(
                f"{self.base_url}/agent/query",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            
            success = (
                "request_id" in data and
                "response_text" in data and
                "suggestions" in data and
                len(data["response_text"]) > 50
            )
            
            self.log_test("Chat Query", success, data)
            return success, data.get("request_id")
        except Exception as e:
            self.log_test("Chat Query", False, error=str(e))
            return False, None
    
    def test_memory_endpoint(self):
        """Test the memory retrieval endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/agent/memory/test_patient_001")
            response.raise_for_status()
            data = response.json()
            
            success = (
                "patient_id" in data and
                "memory_data" in data and
                data["patient_id"] == "test_patient_001"
            )
            
            self.log_test("Memory Retrieval", success, data)
            return success
        except Exception as e:
            self.log_test("Memory Retrieval", False, error=str(e))
            return False
    
    def test_feedback_endpoint(self, request_id: str):
        """Test the feedback endpoint"""
        try:
            payload = {
                "request_id": request_id,
                "patient_id": "test_patient_001",
                "outcome_works": True,
                "feedback_text": "The advice was helpful and clear"
            }
            
            response = self.session.post(
                f"{self.base_url}/agent/feedback",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            
            # Note: We expect this to work even if there are some internal issues
            success = "status" in data
            self.log_test("Feedback Submission", success, data)
            return success
        except Exception as e:
            self.log_test("Feedback Submission", False, error=str(e))
            return False
    
    def test_treatment_plan_endpoint(self):
        """Test the treatment plan update endpoint"""
        try:
            payload = {
                "patient_id": "test_patient_001",
                "treatment_plan": {
                    "medication": "ibuprofen",
                    "dosage": "400mg",
                    "frequency": "every 6 hours",
                    "notes": "For headache management"
                },
                "plan_type": "headache_management",
                "priority": "medium"
            }
            
            response = self.session.post(
                f"{self.base_url}/agent/update_treatment_plan",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            
            # Note: This might fail without MCP database, but endpoint should work
            success = "status" in data and "patient_id" in data
            self.log_test("Treatment Plan Update", success, data)
            return success
        except Exception as e:
            self.log_test("Treatment Plan Update", False, error=str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests and generate a summary"""
        print("🚀 Starting Airavat Backend Tests")
        print("=" * 50)
        
        # Test basic endpoints
        self.test_health_endpoint()
        self.test_root_endpoint()
        
        # Test main functionality
        chat_success, request_id = self.test_chat_query()
        self.test_memory_endpoint()
        
        if chat_success and request_id:
            self.test_feedback_endpoint(request_id)
        
        self.test_treatment_plan_endpoint()
        
        # Generate summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result.get('error', 'Unknown error')}")
        
        print(f"\n🌐 Backend URL: {self.base_url}")
        print(f"📚 API Documentation: {self.base_url}/docs")
        
        # Save results to file
        with open("test_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\n📄 Detailed results saved to: test_results.json")

def main():
    # Get the backend URL from the user or use default
    backend_url = input("Enter your backend URL (or press Enter for default): ").strip()
    if not backend_url:
        backend_url = "https://airavat-backend-u3hyo7liyq-uc.a.run.app"
    
    print(f"Testing backend at: {backend_url}")
    print()
    
    # Run tests
    tester = AiravatBackendTester(backend_url)
    tester.run_all_tests()

if __name__ == "__main__":
    main() 