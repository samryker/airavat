#!/bin/bash

# Airavat Frontend Deployment Script for Firebase Hosting
# This script builds and deploys the Flutter web app

set -e  # Exit on any error

# Configuration
PROJECT_ID="airavat-a3a10"  # Your Firebase Project ID
BACKEND_URL=""  # Will be set from command line argument

echo "🚀 Starting Airavat Frontend Deployment..."

# Check if Flutter is installed
if ! command -v flutter &> /dev/null; then
    echo "❌ Error: Flutter is not installed. Please install it first."
    exit 1
fi

# Check if Firebase CLI is installed
if ! command -v firebase &> /dev/null; then
    echo "❌ Error: Firebase CLI is not installed. Please install it first."
    exit 1
fi

# Get backend URL from command line argument
if [ -z "$1" ]; then
    echo "❌ Error: Please provide the backend URL as an argument."
    echo "Usage: ./deploy_frontend.sh <BACKEND_URL>"
    echo "Example: ./deploy_frontend.sh https://airavat-backend-xxxxx-uc.a.run.app"
    exit 1
fi

BACKEND_URL=$1
echo "🔗 Backend URL: $BACKEND_URL"

# Check Flutter version and dependencies
echo "📋 Checking Flutter setup..."
flutter doctor

# Get Flutter dependencies
echo "📦 Getting Flutter dependencies..."
flutter pub get

# Create config directory if it doesn't exist
mkdir -p lib/config

# Create environment configuration for the backend URL
echo "⚙️ Configuring backend URL..."
cat > lib/config/backend_config.dart << EOF
class BackendConfig {
  static const String baseUrl = '$BACKEND_URL';
  static const String apiUrl = '\$baseUrl/agent';
  
  // API Endpoints
  static const String queryEndpoint = '\$apiUrl/query';
  static const String feedbackEndpoint = '\$apiUrl/feedback';
  static const String memoryEndpoint = '\$apiUrl/memory';
  static const String treatmentPlanEndpoint = '\$apiUrl/update_treatment_plan';
  static const String healthEndpoint = '\$baseUrl/health';
}
EOF

# Build the Flutter web app
echo "🏗️ Building Flutter web app..."
flutter build web --release --web-renderer html

# Check if build was successful
if [ ! -d "build/web" ]; then
    echo "❌ Error: Flutter build failed. build/web directory not found."
    exit 1
fi

# Deploy to Firebase Hosting
echo "🚀 Deploying to Firebase Hosting..."

# Set the Firebase project
firebase use $PROJECT_ID

# Deploy to Firebase Hosting
firebase deploy --only hosting

# Get the hosting URL
HOSTING_URL=$(firebase hosting:channel:list --json | jq -r '.result.channels[0].url' 2>/dev/null || echo "https://$PROJECT_ID.web.app")

echo "✅ Frontend deployment completed successfully!"
echo "🌐 Hosting URL: $HOSTING_URL"
echo "🔗 Backend URL: $BACKEND_URL"

# Test the deployment
echo "🧪 Testing frontend deployment..."
curl -s "$HOSTING_URL" | head -n 5 || echo "⚠️ Frontend test failed"

echo "🎉 Airavat Frontend is now deployed and ready!"
echo "💡 Next steps:"
echo "   1. Test the complete application at: $HOSTING_URL"
echo "   2. Run end-to-end tests"
echo "   3. Monitor the application logs" 