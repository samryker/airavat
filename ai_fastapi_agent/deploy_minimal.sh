#!/bin/bash

# Airavat Minimal Backend Deployment Script
# This script deploys with just the essential environment variables

set -e  # Exit on any error

# Configuration
PROJECT_ID="airavat-a3a10"
SERVICE_NAME="airavat-backend"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Starting Airavat Minimal Backend Deployment..."

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed. Please install it first."
    exit 1
fi

# Check if GEMINI_API_KEY is set
if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ Error: GEMINI_API_KEY environment variable is not set."
    echo "Please set it first:"
    echo "export GEMINI_API_KEY=your_gemini_api_key_here"
    exit 1
fi

# Set the project
echo "📋 Setting Google Cloud project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required Google Cloud APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com

# Build and push the Docker image
echo "🏗️ Building and pushing Docker image..."
gcloud builds submit --tag $IMAGE_NAME

# Deploy to Cloud Run with minimal environment variables
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8000 \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --concurrency 80 \
    --max-instances 10 \
    --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY" \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')

echo "✅ Deployment completed successfully!"
echo "🌐 Service URL: $SERVICE_URL"
echo "📊 Health Check: $SERVICE_URL/health"
echo "📚 API Documentation: $SERVICE_URL/docs"

# Test the deployment
echo "🧪 Testing deployment..."
sleep 10  # Wait for the service to be ready
curl -s "$SERVICE_URL/health" | head -n 5 || echo "⚠️ Health check failed, but deployment might still be working"

echo "🎉 Airavat Backend is now deployed and ready!"
echo "💡 Next steps:"
echo "   1. Test the health endpoint: $SERVICE_URL/health"
echo "   2. Deploy the frontend with: cd ../airavat_flutter && ./deploy_frontend.sh $SERVICE_URL"
echo "   3. Run end-to-end tests" 