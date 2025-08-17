#!/bin/bash
echo "🧪 Testing Airavat Deployment..."
SERVICE_URL=$(gcloud run services describe airavat-backend --region=us-central1 --format="value(status.url)")
echo "Testing: $SERVICE_URL"

echo "1. Health Check:"
curl -s "$SERVICE_URL/health"

echo -e "\n2. AI Query Test:"
curl -s -X POST "$SERVICE_URL/agent/query" \
    -H "Content-Type: application/json" \
    -d '{"patient_id": "test_123", "query_text": "Hello, how are you?"}'

echo -e "\n3. Context Retrieval Test:"
curl -s "$SERVICE_URL/agent/patient/test_123/context"

echo -e "\n✅ Tests completed!"
