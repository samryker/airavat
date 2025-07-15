#!/usr/bin/env python3
"""
Digital Twin Test Script for Airavat
Tests the complete digital twin functionality including:
- Patient context loading
- Conversation history
- Personalized responses
- Treatment plan updates
- MCP memory integration
"""

import requests
import json
import time
from datetime import datetime
import sys

# Configuration
BACKEND_URL = "https://airavat-backend-u3hyo7liyq-uc.a.run.app"
TEST_PATIENT_ID = "test_patient_digital_twin_001"

def print_test_header(test_name):
    """Print a formatted test header"""
    print(f"\n{'='*60}")
    print(f"🧪 TEST: {test_name}")
    print(f"{'='*60}")

def print_test_result(test_name, success, details=""):
    """Print a formatted test result"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"   📝 {details}")

def test_health_check():
    """Test the health check endpoint"""
    print_test_header("Health Check")
    
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_test_result("Health Check", True, f"Status: {data.get('status')}")
            print(f"   🔧 Services: {data.get('services')}")
            return True
        else:
            print_test_result("Health Check", False, f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_test_result("Health Check", False, f"Error: {str(e)}")
        return False

def test_patient_context():
    """Test getting patient context"""
    print_test_header("Patient Context")
    
    try:
        response = requests.get(f"{BACKEND_URL}/agent/patient/{TEST_PATIENT_ID}/context", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_test_result("Get Patient Context", True, f"Status: {data.get('status')}")
            
            context = data.get('context', {})
            if context:
                print(f"   📊 Context loaded: {list(context.keys())}")
                if context.get('profile'):
                    print(f"   👤 Profile data available")
                if context.get('treatment_plans'):
                    print(f"   💊 Treatment plans: {len(context['treatment_plans'])}")
                if context.get('biomarkers'):
                    print(f"   🩸 Biomarkers available")
                if context.get('conversation_history'):
                    print(f"   💬 Conversation history: {len(context['conversation_history'])}")
            else:
                print(f"   ⚠️ No context data found (new patient)")
            return True
        else:
            print_test_result("Get Patient Context", False, f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_test_result("Get Patient Context", False, f"Error: {str(e)}")
        return False

def test_conversation_history():
    """Test getting conversation history"""
    print_test_header("Conversation History")
    
    try:
        response = requests.get(f"{BACKEND_URL}/agent/patient/{TEST_PATIENT_ID}/conversation-history?limit=5", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_test_result("Get Conversation History", True, f"Status: {data.get('status')}")
            
            history = data.get('conversation_history', [])
            print(f"   💬 Found {len(history)} conversations")
            
            if history:
                for i, conv in enumerate(history[:3]):
                    query = conv.get('query_text', '')[:50]
                    timestamp = conv.get('timestamp', '')
                    print(f"   {i+1}. {query}... ({timestamp})")
            return True
        else:
            print_test_result("Get Conversation History", False, f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_test_result("Get Conversation History", False, f"Error: {str(e)}")
        return False

def test_personalized_query():
    """Test sending a personalized query with context"""
    print_test_header("Personalized Query")
    
    query_data = {
        "patient_id": TEST_PATIENT_ID,
        "query_text": "I have a headache and I'm feeling tired. What should I do?",
        "symptoms": ["headache", "fatigue"],
        "medical_history": ["migraine"],
        "current_medications": ["aspirin"],
        "additional_data": {
            "patient_context": {
                "age": 35,
                "gender": "female",
                "allergies": ["penicillin"],
                "goal": "manage stress and improve sleep"
            }
        }
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/agent/query",
            json=query_data,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print_test_result("Personalized Query", True, f"Request ID: {data.get('request_id')}")
            
            response_text = data.get('response_text', '')
            print(f"   🤖 Response: {response_text[:100]}...")
            
            # Check if response is personalized
            if any(word in response_text.lower() for word in ['headache', 'tired', 'fatigue', 'migraine']):
                print(f"   ✅ Response addresses the symptoms")
            else:
                print(f"   ⚠️ Response may not be personalized")
            
            return data.get('request_id')
        else:
            print_test_result("Personalized Query", False, f"Status code: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return None
    except Exception as e:
        print_test_result("Personalized Query", False, f"Error: {str(e)}")
        return None

def test_follow_up_query(request_id):
    """Test a follow-up query to test memory"""
    print_test_header("Follow-up Query (Memory Test)")
    
    if not request_id:
        print_test_result("Follow-up Query", False, "No previous request ID")
        return False
    
    query_data = {
        "patient_id": TEST_PATIENT_ID,
        "query_text": "What about the headache medication you mentioned?",
        "additional_data": {
            "previous_request_id": request_id
        }
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/agent/query",
            json=query_data,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print_test_result("Follow-up Query", True, f"Request ID: {data.get('request_id')}")
            
            response_text = data.get('response_text', '')
            print(f"   🤖 Response: {response_text[:100]}...")
            
            # Check if response references previous conversation
            if any(word in response_text.lower() for word in ['mentioned', 'previous', 'earlier', 'before']):
                print(f"   ✅ Response shows memory of previous conversation")
            else:
                print(f"   ⚠️ Response may not reference previous conversation")
            
            return True
        else:
            print_test_result("Follow-up Query", False, f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_test_result("Follow-up Query", False, f"Error: {str(e)}")
        return False

def test_treatment_plan_update():
    """Test updating treatment plan"""
    print_test_header("Treatment Plan Update")
    
    treatment_plan = {
        "treatmentName": "Headache Management Plan",
        "condition": "Chronic Headaches",
        "startDate": datetime.now().isoformat(),
        "status": "Ongoing",
        "medications": ["Ibuprofen", "Acetaminophen"],
        "lifestyle_changes": ["Reduce screen time", "Improve sleep hygiene"],
        "follow_up": "2 weeks"
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/agent/patient/{TEST_PATIENT_ID}/treatment-plan",
            json=treatment_plan,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_test_result("Update Treatment Plan", True, f"Status: {data.get('status')}")
            return True
        else:
            print_test_result("Update Treatment Plan", False, f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_test_result("Update Treatment Plan", False, f"Error: {str(e)}")
        return False

def test_biomarkers():
    """Test getting patient biomarkers"""
    print_test_header("Patient Biomarkers")
    
    try:
        response = requests.get(f"{BACKEND_URL}/agent/patient/{TEST_PATIENT_ID}/biomarkers", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_test_result("Get Biomarkers", True, f"Status: {data.get('status')}")
            
            biomarkers = data.get('biomarkers', {})
            if biomarkers:
                print(f"   🩸 Biomarkers: {list(biomarkers.keys())}")
            else:
                print(f"   ⚠️ No biomarkers found")
            return True
        else:
            print_test_result("Get Biomarkers", False, f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_test_result("Get Biomarkers", False, f"Error: {str(e)}")
        return False

def test_memory_endpoint():
    """Test MCP memory endpoint"""
    print_test_header("MCP Memory")
    
    try:
        response = requests.get(f"{BACKEND_URL}/agent/memory/{TEST_PATIENT_ID}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_test_result("Get MCP Memory", True, f"Patient ID: {data.get('patient_id')}")
            
            memory_data = data.get('memory_data', {})
            if memory_data:
                print(f"   🧠 Memory data: {list(memory_data.keys())}")
            else:
                print(f"   ⚠️ No memory data found")
            return True
        else:
            print_test_result("Get MCP Memory", False, f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_test_result("Get MCP Memory", False, f"Error: {str(e)}")
        return False

def run_comprehensive_test():
    """Run all tests"""
    print("🚀 Starting Digital Twin Comprehensive Test Suite")
    print(f"🔗 Backend URL: {BACKEND_URL}")
    print(f"👤 Test Patient ID: {TEST_PATIENT_ID}")
    print(f"⏰ Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Run all tests
    results.append(("Health Check", test_health_check()))
    results.append(("Patient Context", test_patient_context()))
    results.append(("Conversation History", test_conversation_history()))
    
    # Test personalized query
    request_id = test_personalized_query()
    results.append(("Personalized Query", request_id is not None))
    
    # Test follow-up query
    if request_id:
        results.append(("Follow-up Query", test_follow_up_query(request_id)))
    else:
        results.append(("Follow-up Query", False))
    
    results.append(("Treatment Plan Update", test_treatment_plan_update()))
    results.append(("Biomarkers", test_biomarkers()))
    results.append(("MCP Memory", test_memory_endpoint()))
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} | {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! Digital Twin functionality is working correctly.")
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
    
    return passed == total

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1) 