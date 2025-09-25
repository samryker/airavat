#!/bin/bash

# Setup Google Secret Manager for Airavat
# This script creates secrets in Google Secret Manager and updates Cloud Run to use them

set -e

PROJECT_ID="mira-470320"
REGION="us-central1"
SERVICE_NAME="airavat-backend"

echo "🔐 Setting up Google Secret Manager for Airavat..."

# Enable Secret Manager API
echo "Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project=$PROJECT_ID

# Create secrets (you'll need to provide the actual values)
echo "Creating secrets in Secret Manager..."
echo "Please provide your Gemini API Key:"
read -s GEMINI_KEY
echo "$GEMINI_KEY" | gcloud secrets create gemini-api-key --data-file=- --project=$PROJECT_ID

echo "Please provide your Hugging Face Token:"
read -s HF_TOKEN
echo "$HF_TOKEN" | gcloud secrets create hf-token --data-file=- --project=$PROJECT_ID

# Grant Cloud Run service account access to secrets
SERVICE_ACCOUNT_EMAIL="github-actions-deployer@mira-470320.iam.gserviceaccount.com"

echo "Granting access to secrets..."
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID

gcloud secrets add-iam-policy-binding hf-token \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID

# Update Cloud Run service to use Secret Manager
echo "Updating Cloud Run service to use Secret Manager..."
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,HF_TOKEN=hf-token:latest" \
    --project=$PROJECT_ID

echo "✅ Secret Manager setup complete!"
echo "Your API keys are now securely stored in Google Secret Manager and accessible to Cloud Run."
