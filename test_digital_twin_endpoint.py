#!/usr/bin/env python3
"""
Test script for the new Digital Twin autonomous agent endpoint
"""

import requests
import json
import os

# Test configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TEST_PATIENT_ID = "test_user_123"

def test_health_endpoint():
    """Test that the backend is running"""
    print("\n🔍 Testing backend health endpoint...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend health check failed: {e}")
        return False

def test_digital_twin_health():
    """Test Digital Twin service health"""
    print("\n🔍 Testing Digital Twin service health...")
    try:
        response = requests.get(f"{BACKEND_URL}/digital_twin/health", timeout=5)
        if response.status_code == 200:
            print("✅ Digital Twin service is running")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Digital Twin service returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Digital Twin health check failed: {e}")
        return False

def test_analyze_lab_report():
    """Test the new autonomous agent lab report analysis endpoint"""
    print("\n🔍 Testing lab report analysis endpoint...")
    
    # Create a test lab report
    test_report_content = """
    LABORATORY TEST REPORT
    
    Patient: Test User
    Date: 2025-10-11
    
    BLOOD WORK RESULTS:
    
    Hemoglobin: 12.5 g/dL (Normal: 13.5-17.5)
    WBC Count: 7500 /μL (Normal: 4000-11000)
    Glucose (Fasting): 110 mg/dL (Normal: 70-100) - ELEVATED
    Cholesterol Total: 220 mg/dL (Normal: <200) - ELEVATED
    HDL: 45 mg/dL (Normal: >40)
    LDL: 150 mg/dL (Normal: <100) - ELEVATED
    Triglycerides: 180 mg/dL (Normal: <150) - ELEVATED
    
    NOTES:
    - Mild anemia detected
    - Pre-diabetic glucose levels
    - Dyslipidemia (elevated cholesterol and triglycerides)
    - Recommend lifestyle modifications and follow-up in 3 months
    """
    
    try:
        # Prepare multipart file upload
        files = {
            'file': ('test_lab_report.txt', test_report_content.encode('utf-8'), 'text/plain')
        }
        
        url = f"{BACKEND_URL}/digital_twin/{TEST_PATIENT_ID}/analyze-lab-report"
        print(f"   POST {url}")
        
        response = requests.post(url, files=files, timeout=60)
        
        if response.status_code == 200:
            print("✅ Lab report analysis successful!")
            data = response.json()
            
            print(f"\n📊 ANALYSIS RESULTS:")
            print(f"   Patient ID: {data.get('patient_id')}")
            print(f"   Filename: {data.get('filename')}")
            print(f"   Confidence Score: {data.get('confidence_score')}%")
            print(f"   Severity: {data.get('severity')}")
            print(f"   Priority: {data.get('priority')}")
            print(f"   Saved to Firestore: {data.get('saved_to_firestore')}")
            
            print(f"\n🔬 PRIMARY ANALYSIS:")
            print(f"   {data.get('primary_analysis', 'N/A')[:200]}...")
            
            print(f"\n💡 MEDICAL INFERENCES:")
            print(f"   {data.get('medical_inferences', 'N/A')[:200]}...")
            
            print(f"\n🎯 PROACTIVE RECOMMENDATIONS:")
            print(f"   {data.get('proactive_recommendations', 'N/A')[:200]}...")
            
            print(f"\n✅ Processing Steps:")
            steps = data.get('processing_steps', {})
            print(f"   - HF Analysis: {'✅' if steps.get('hf_completed') else '❌'}")
            print(f"   - Tokenization: {'✅' if steps.get('tokenization_completed') else '❌'}")
            print(f"   - Gemini Analysis: {'✅' if steps.get('gemini_completed') else '❌'}")
            
            return True
        else:
            print(f"❌ Analysis failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Lab report analysis test failed: {e}")
        return False

def test_get_analysis_history():
    """Test getting analysis history"""
    print("\n🔍 Testing analysis history endpoint...")
    try:
        url = f"{BACKEND_URL}/digital_twin/{TEST_PATIENT_ID}/analysis-history"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Analysis history retrieved")
            print(f"   Patient ID: {data.get('patient_id')}")
            print(f"   Total Analyses: {data.get('total_analyses')}")
            
            analyses = data.get('analyses', [])
            if analyses:
                print(f"\n   Recent analyses:")
                for i, analysis in enumerate(analyses[:3], 1):
                    print(f"   {i}. {analysis.get('filename')} - Confidence: {analysis.get('confidence_score')}%")
            
            return True
        else:
            print(f"❌ History retrieval returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Analysis history test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("🧪 DIGITAL TWIN AUTONOMOUS AGENT - ENDPOINT TESTS")
    print("=" * 70)
    
    results = []
    
    # Test 1: Backend health
    results.append(("Backend Health", test_health_endpoint()))
    
    # Test 2: Digital Twin service health
    results.append(("Digital Twin Health", test_digital_twin_health()))
    
    # Test 3: Analyze lab report (main feature)
    results.append(("Lab Report Analysis", test_analyze_lab_report()))
    
    # Test 4: Get analysis history
    results.append(("Analysis History", test_get_analysis_history()))
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 TEST SUMMARY")
    print("=" * 70)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:30} {status}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, result in results if result)
    
    print(f"\n{passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! The Digital Twin service is working perfectly!")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed. Please check the logs above.")
    
    print("=" * 70)

if __name__ == "__main__":
    main()

