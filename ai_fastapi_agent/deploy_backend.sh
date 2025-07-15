#!/bin/bash

# Airavat Backend Deployment Script for Google Cloud Run
# This script deploys the FastAPI backend with MCP integration

set -e  # Exit on any error

# Configuration
PROJECT_ID="airavat-a3a10"  # Your Google Cloud Project ID
SERVICE_NAME="airavat-backend"
REGION="us-central1"  # Change to your preferred region
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Starting Airavat Backend Deployment..."

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed. Please install it first."
    exit 1
fi

# Set the project
echo "📋 Setting Google Cloud project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required Google Cloud APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable alloydb.googleapis.com
gcloud services enable sqladmin.googleapis.com

# Build and push the Docker image
echo "🏗️ Building and pushing Docker image..."
gcloud builds submit --tag $IMAGE_NAME

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."

# Prepare environment variables (only set if they exist)
ENV_VARS=""
if [ ! -z "$GEMINI_API_KEY" ]; then
    ENV_VARS="$ENV_VARS --set-env-vars=GEMINI_API_KEY=$GEMINI_API_KEY"
fi
if [ ! -z "$MCP_DB_TYPE" ]; then
    ENV_VARS="$ENV_VARS --set-env-vars=MCP_DB_TYPE=$MCP_DB_TYPE"
fi
if [ ! -z "$ALLOYDB_HOST" ]; then
    ENV_VARS="$ENV_VARS --set-env-vars=ALLOYDB_HOST=$ALLOYDB_HOST"
fi
if [ ! -z "$ALLOYDB_PORT" ]; then
    ENV_VARS="$ENV_VARS --set-env-vars=ALLOYDB_PORT=$ALLOYDB_PORT"
fi
if [ ! -z "$ALLOYDB_USER" ]; then
    ENV_VARS="$ENV_VARS --set-env-vars=ALLOYDB_USER=$ALLOYDB_USER"
fi
if [ ! -z "$ALLOYDB_PASSWORD" ]; then
    ENV_VARS="$ENV_VARS --set-env-vars=ALLOYDB_PASSWORD=$ALLOYDB_PASSWORD"
fi
if [ ! -z "$ALLOYDB_DATABASE" ]; then
    ENV_VARS="$ENV_VARS --set-env-vars=ALLOYDB_DATABASE=$ALLOYDB_DATABASE"
fi

# Always set the project ID
ENV_VARS="$ENV_VARS --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID"

# Deploy with environment variables
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
    $ENV_VARS

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')

echo "✅ Deployment completed successfully!"
echo "🌐 Service URL: $SERVICE_URL"
echo "📊 Health Check: $SERVICE_URL/health"
echo "📚 API Documentation: $SERVICE_URL/docs"

# Test the deployment
echo "🧪 Testing deployment..."
curl -s "$SERVICE_URL/health" | jq . || echo "⚠️ Health check failed or jq not installed"

echo "🎉 Airavat Backend is now deployed and ready!"
echo "💡 Next steps:"
echo "   1. Update your Flutter app with the new backend URL: $SERVICE_URL"
echo "   2. Deploy the Flutter frontend to Firebase Hosting"
echo "   3. Run end-to-end tests" 