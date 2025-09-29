#!/usr/bin/env python3
"""
Test script to validate Gemini API configuration
Run this locally to test the API before deployment
"""

import os
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_gemini_api():
    """Test the Gemini API configuration"""
    
    # Get API key
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("❌ No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")
        return False
    
    print(f"✅ API key found: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Test different model names
        model_names = ["gemini-1.5-pro-latest", "gemini-1.5-pro", "gemini-pro"]
        
        for model_name in model_names:
            print(f"\n🧪 Testing model: {model_name}")
            try:
                model = genai.GenerativeModel(model_name)
                
                # Test with a simple query
                response = model.generate_content("Hello! Can you respond with a simple greeting?")
                
                if response and response.text:
                    print(f"✅ {model_name} works! Response: {response.text[:100]}...")
                    return True
                else:
                    print(f"❌ {model_name} returned empty response")
                    
            except Exception as e:
                print(f"❌ {model_name} failed: {e}")
        
        print("\n❌ All models failed")
        return False
        
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        return False

async def test_medical_query():
    """Test with a medical query similar to what the app uses"""
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return False
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        
        prompt = """You are a medical AI assistant. A patient asks: "I have a headache and feel tired. What could be causing this?"

Please provide a helpful response that:
1. Acknowledges their symptoms
2. Suggests possible common causes
3. Recommends consulting a healthcare professional
4. Avoids specific diagnoses

Keep the response under 200 words."""

        print("\n🏥 Testing medical query...")
        response = model.generate_content(prompt)
        
        if response and response.text:
            print("✅ Medical query successful!")
            print(f"Response preview: {response.text[:200]}...")
            return True
        else:
            print("❌ Medical query failed - empty response")
            return False
            
    except Exception as e:
        print(f"❌ Medical query failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Gemini API Configuration")
    print("=" * 50)
    
    # Run basic test
    basic_success = asyncio.run(test_gemini_api())
    
    if basic_success:
        # Run medical query test
        medical_success = asyncio.run(test_medical_query())
        
        if medical_success:
            print("\n🎉 All tests passed! Your Gemini API is working correctly.")
        else:
            print("\n⚠️ Basic API works but medical queries are failing.")
    else:
        print("\n💥 Gemini API is not working. Check your API key and configuration.")
