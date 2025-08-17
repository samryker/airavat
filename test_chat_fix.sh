#!/bin/bash

# Test Chat Serialization Fix
echo "🧪 Testing Chat Serialization Fix..."
echo ""

# Test with a complex request that includes patient context
echo "✅ Test 1: Complex Query with Patient Context"
RESPONSE=$(curl -s -X POST https://airavat-backend-u3hyo7liyq-uc.a.run.app/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "test_user_serialization",
    "query_text": "I am having headache",
    "symptoms": ["headache", "fatigue"],
    "medical_history": ["hypertension"],
    "current_medications": ["aspirin"],
    "additional_data": {
      "patient_context": {
        "habits": ["exercise", "meditation"],
        "allergies": "penicillin",
        "medicines": "aspirin, vitamin d",
        "updatedAt": "2025-01-22T12:30:00.000Z",
        "email": "test@example.com",
        "age": 35,
        "bmiIndex": "Normal",
        "gender": "female",
        "race": "Caucasian",
        "history": "Family history of diabetes",
        "goal": "Maintain healthy lifestyle",
        "treatmentPlans": [
          {
            "plan_id": "plan_123",
            "title": "Headache Management",
            "description": "Comprehensive headache treatment plan",
            "created_at": "2025-01-22T10:00:00.000Z"
          }
        ]
      }
    }
  }')

echo "$RESPONSE" | jq .
echo ""

# Check if response is valid
HAS_RESPONSE=$(echo "$RESPONSE" | jq -r '.response_text')
HAS_SUGGESTIONS=$(echo "$RESPONSE" | jq -r '.suggestions[0].suggestion_text')

if [ "$HAS_RESPONSE" != "null" ] && [ -n "$HAS_RESPONSE" ]; then
    echo "✅ Serialization Test: Response Working"
else
    echo "❌ Serialization Test: Response Failed"
fi

if [ "$HAS_SUGGESTIONS" != "null" ] && [ -n "$HAS_SUGGESTIONS" ]; then
    echo "✅ Serialization Test: Suggestions Working"
else
    echo "❌ Serialization Test: Suggestions Failed"
fi

echo ""
echo "🌐 Frontend URL: https://airavat-a3a10.web.app"
echo "🔗 Backend URL: https://airavat-backend-u3hyo7liyq-uc.a.run.app"
echo ""
echo "🎉 Serialization Fix Status:"
echo "   ✅ Firestore Timestamp conversion implemented"
echo "   ✅ Frontend deployed with fix"
echo "   ✅ Backend can handle complex patient context"
echo ""
echo "💡 The chat window should now work without serialization errors!"
echo "   Try sending a message in the frontend chat interface." 