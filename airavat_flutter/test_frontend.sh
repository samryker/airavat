#!/bin/bash
echo "🧪 Testing Airavat Frontend..."
FRONTEND_URL="https://airavat-a3a10.web.app"
echo "Testing: $FRONTEND_URL"

echo "1. Frontend Accessibility:"
curl -s -I "$FRONTEND_URL" | head -1

echo -e "\n2. Backend Connectivity:"
BACKEND_URL="https://airavat-backend-u3hyo7liyq-uc.a.run.app"
curl -s "$BACKEND_URL/health"

echo -e "\n✅ Frontend tests completed!"
