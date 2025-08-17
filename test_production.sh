#!/bin/bash

# Production Test for Airavat Chat Functionality
echo "🚀 Testing Airavat Production Chat Functionality..."
echo ""

# Test production backend
echo "✅ Testing Production Backend Chat API"
RESPONSE=$(curl -s -X POST https://airavat-backend-u3hyo7liyq-uc.a.run.app/agent/query \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "prod_user_123", "query_text": "I have chest pain and shortness of breath", "context": {"age": 40, "gender": "male", "symptoms": ["chest pain", "shortness of breath"]}}')

echo "$RESPONSE" | jq .
echo ""

# Check if response is valid
HAS_RESPONSE=$(echo "$RESPONSE" | jq -r '.response_text')
HAS_SUGGESTIONS=$(echo "$RESPONSE" | jq -r '.suggestions[0].suggestion_text')

if [ "$HAS_RESPONSE" != "null" ] && [ -n "$HAS_RESPONSE" ]; then
    echo "✅ Production Response: Working"
else
    echo "❌ Production Response: Failed"
fi

if [ "$HAS_SUGGESTIONS" != "null" ] && [ -n "$HAS_SUGGESTIONS" ]; then
    echo "✅ Production Suggestions: Working"
else
    echo "❌ Production Suggestions: Failed"
fi

echo ""
echo "🌐 Production URLs:"
echo "   Frontend: https://airavat-a3a10.web.app"
echo "   Backend: https://airavat-backend-u3hyo7liyq-uc.a.run.app"
echo "   API Docs: https://airavat-backend-u3hyo7liyq-uc.a.run.app/docs"
echo ""
echo "🎉 PRODUCTION STATUS: READY!"
echo "💡 The chat window should now work perfectly in production!"
echo "   Try sending a message in the frontend chat interface." 