#!/usr/bin/env python3
"""Test script to verify Hugging Face token is valid"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    print("❌ HF_TOKEN not found in environment")
    sys.exit(1)

print(f"✅ HF_TOKEN loaded: {HF_TOKEN[:10]}...{HF_TOKEN[-5:]}")
print(f"   Token length: {len(HF_TOKEN)} characters")

# Test 1: Verify token format
if not HF_TOKEN.startswith("hf_"):
    print("⚠️  Warning: Token doesn't start with 'hf_' prefix")

# Test 2: Try to use the token with Hugging Face InferenceClient
try:
    from huggingface_hub import InferenceClient
    print("\n📦 InferenceClient imported successfully")
    
    client = InferenceClient(token=HF_TOKEN)
    print("✅ InferenceClient initialized")
    
    # Test 3: Try a simple NER request
    print("\n🧪 Testing token with a sample NER request...")
    test_text = "BRCA1 gene mutation associated with breast cancer risk"
    
    try:
        result = client.token_classification(
            test_text,
            model="OpenMed/OpenMed-NER-GenomeDetect-SuperClinical-434M"
        )
        
        print(f"✅ HF API call successful!")
        print(f"   Found {len(result)} entities")
        if result:
            print(f"   First entity: {result[0]}")
        
    except Exception as api_error:
        print(f"❌ HF API call failed: {api_error}")
        print(f"\n🔍 Error details:")
        print(f"   Type: {type(api_error).__name__}")
        print(f"   Message: {str(api_error)}")
        
        # Check if it's an authentication error
        if "401" in str(api_error) or "403" in str(api_error) or "invalid" in str(api_error).lower():
            print("\n⚠️  This looks like an authentication error!")
            print("   Possible causes:")
            print("   1. Token is invalid or expired")
            print("   2. Token doesn't have required permissions")
            print("   3. Token format is incorrect")
            print("\n💡 To fix:")
            print("   1. Go to https://huggingface.co/settings/tokens")
            print("   2. Create a new token with 'Read' permissions")
            print("   3. Update your .env file and GitHub secrets")
        
        sys.exit(1)
        
except ImportError as e:
    print(f"❌ Failed to import huggingface_hub: {e}")
    print("   Run: pip install huggingface-hub")
    sys.exit(1)

print("\n✅ All tests passed! HF token is valid and working.")

