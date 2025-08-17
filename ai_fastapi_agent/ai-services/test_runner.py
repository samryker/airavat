#!/usr/bin/env python3
"""
Comprehensive Test Runner for Airavat Medical AI Assistant Backend
Runs all tests and generates detailed reports
"""

import subprocess
import sys
import os
import json
from datetime import datetime

def run_tests_with_coverage():
    """Run tests with coverage reporting"""
    print("🧪 Running Airavat Backend Tests with Coverage...")
    print("=" * 60)
    
    # Run component tests with coverage
    cmd = [
        "python", "-m", "pytest", 
        "test_components.py", 
        "--cov=main_agent",
        "--cov-report=term-missing",
        "--cov-report=html:coverage_html",
        "--cov-report=json:coverage.json",
        "-v"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        print("Component Tests Output:")
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Tests timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def run_individual_test_suites():
    """Run individual test suites separately"""
    test_suites = [
        ("Data Models", "test_components.py::TestDataModels"),
        ("Intent Detector", "test_components.py::TestIntentDetector"),
        ("Firestore Service", "test_components.py::TestFirestoreService"),
        ("Genetic Analysis", "test_components.py::TestGeneticAnalysisService"),
        ("Notification Service", "test_components.py::TestNotificationService"),
        ("Email Service", "test_components.py::TestEmailService"),
        ("RL Service", "test_components.py::TestRLService"),
        ("Planner", "test_components.py::TestPlanner"),
        ("Gemini Service", "test_components.py::TestGeminiService")
    ]
    
    results = {}
    
    for suite_name, test_path in test_suites:
        print(f"\n🔍 Running {suite_name} Tests...")
        print("-" * 40)
        
        cmd = ["python", "-m", "pytest", test_path, "-v", "--tb=short"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            results[suite_name] = {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr
            }
            
            if result.returncode == 0:
                print(f"✅ {suite_name} tests passed")
            else:
                print(f"❌ {suite_name} tests failed")
                print(result.stdout)
                if result.stderr:
                    print("Errors:", result.stderr)
                    
        except subprocess.TimeoutExpired:
            print(f"❌ {suite_name} tests timed out")
            results[suite_name] = {"success": False, "output": "", "errors": "Timeout"}
        except Exception as e:
            print(f"❌ Error running {suite_name} tests: {e}")
            results[suite_name] = {"success": False, "output": "", "errors": str(e)}
    
    return results

def generate_test_report(results):
    """Generate a comprehensive test report"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_suites": len(results),
            "passed_suites": sum(1 for r in results.values() if r["success"]),
            "failed_suites": sum(1 for r in results.values() if not r["success"])
        },
        "details": results
    }
    
    # Save report to file
    with open("test_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST REPORT SUMMARY")
    print("=" * 60)
    print(f"Total Test Suites: {report['summary']['total_suites']}")
    print(f"✅ Passed: {report['summary']['passed_suites']}")
    print(f"❌ Failed: {report['summary']['failed_suites']}")
    print(f"📈 Success Rate: {(report['summary']['passed_suites']/report['summary']['total_suites'])*100:.1f}%")
    
    # List failed suites
    failed_suites = [name for name, result in results.items() if not result["success"]]
    if failed_suites:
        print(f"\n❌ Failed Test Suites:")
        for suite in failed_suites:
            print(f"  - {suite}")
    
    return report

def run_api_endpoint_tests():
    """Run API endpoint tests (if the app can be imported)"""
    print("\n🌐 Testing API Endpoints...")
    print("-" * 40)
    
    try:
        # Try to import and test the main app
        from fastapi.testclient import TestClient
        from main_agent.main import app
        
        client = TestClient(app)
        
        # Test basic endpoints
        endpoints_to_test = [
            ("GET", "/health", "Health Check"),
            ("GET", "/", "Root Endpoint"),
        ]
        
        results = {}
        for method, endpoint, description in endpoints_to_test:
            try:
                if method == "GET":
                    response = client.get(endpoint)
                elif method == "POST":
                    response = client.post(endpoint)
                
                results[endpoint] = {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "description": description
                }
                
                if response.status_code < 400:
                    print(f"✅ {description} ({endpoint}): {response.status_code}")
                else:
                    print(f"❌ {description} ({endpoint}): {response.status_code}")
                    
            except Exception as e:
                print(f"❌ {description} ({endpoint}): Error - {e}")
                results[endpoint] = {
                    "success": False,
                    "status_code": None,
                    "description": description,
                    "error": str(e)
                }
        
        return results
        
    except ImportError as e:
        print(f"❌ Cannot import main app: {e}")
        return {"error": "Cannot import main app"}
    except Exception as e:
        print(f"❌ Error testing API endpoints: {e}")
        return {"error": str(e)}

def main():
    """Main test runner function"""
    print("🚀 Airavat Medical AI Assistant - Backend Test Suite")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run individual test suites
    component_results = run_individual_test_suites()
    
    # Generate component test report
    component_report = generate_test_report(component_results)
    
    # Try to run API endpoint tests
    api_results = run_api_endpoint_tests()
    
    # Run coverage tests
    coverage_success = run_tests_with_coverage()
    
    # Final summary
    print("\n" + "=" * 60)
    print("🎯 FINAL TEST SUMMARY")
    print("=" * 60)
    print(f"Component Tests: {component_report['summary']['passed_suites']}/{component_report['summary']['total_suites']} passed")
    print(f"API Endpoint Tests: {'✅ Available' if 'error' not in api_results else '❌ Not Available'}")
    print(f"Coverage Report: {'✅ Generated' if coverage_success else '❌ Failed'}")
    
    if coverage_success:
        print("\n📁 Coverage reports saved to:")
        print("  - coverage_html/ (HTML report)")
        print("  - coverage.json (JSON report)")
    
    print(f"\n📄 Detailed test report saved to: test_report.json")
    
    # Exit with appropriate code
    if component_report['summary']['failed_suites'] > 0:
        print("\n⚠️  Some tests failed. Check the report for details.")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    main() 