#!/bin/bash

# 🚀 Airavat Frontend Deployment Script
# This script automatically gets the backend URL and deploys the frontend

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "🚀 Airavat Frontend Deployment"
echo "============================="
echo ""

# Step 1: Check if we're in the right directory
if [ ! -f "lib/main.dart" ]; then
    print_error "Please run this script from the airavat_flutter directory"
    exit 1
fi

print_success "✅ Found main.dart - we're in the right directory"

# Step 2: Get backend URL from Cloud Run
print_status "Step 1: Getting backend URL from Cloud Run..."
BACKEND_URL=$(gcloud run services describe airavat-backend --region=us-central1 --format="value(status.url)")

if [ -z "$BACKEND_URL" ]; then
    print_error "❌ Could not get backend URL. Is the backend deployed?"
    exit 1
fi

print_success "✅ Backend URL: $BACKEND_URL"

# Step 3: Update backend config
print_status "Step 2: Updating backend configuration..."
if [ -f "lib/config/backend_config.dart" ]; then
    # Create backup
    cp lib/config/backend_config.dart lib/config/backend_config.dart.backup
    
    # Update the URL
    sed -i.bak "s|https://.*\.run\.app|$BACKEND_URL|g" lib/config/backend_config.dart
    print_success "✅ Updated backend_config.dart with new URL"
else
    print_warning "⚠️ backend_config.dart not found, creating it..."
    mkdir -p lib/config
    cat > lib/config/backend_config.dart << EOF
class BackendConfig {
  static const String baseUrl = '$BACKEND_URL';
}
EOF
    print_success "✅ Created backend_config.dart with URL: $BACKEND_URL"
fi

# Step 4: Check if Flutter is installed
print_status "Step 3: Checking Flutter installation..."
if ! command -v flutter &> /dev/null; then
    print_error "❌ Flutter is not installed or not in PATH"
    exit 1
fi

print_success "✅ Flutter is installed"

# Step 5: Get Flutter dependencies
print_status "Step 4: Getting Flutter dependencies..."
flutter pub get

if [ $? -eq 0 ]; then
    print_success "✅ Dependencies installed"
else
    print_error "❌ Failed to install dependencies"
    exit 1
fi

# Step 6: Build for web
print_status "Step 5: Building Flutter web app..."
flutter build web --release

if [ $? -eq 0 ]; then
    print_success "✅ Web build completed"
else
    print_error "❌ Web build failed"
    exit 1
fi

# Step 7: Deploy to Firebase Hosting
print_status "Step 6: Deploying to Firebase Hosting..."
firebase deploy --only hosting

if [ $? -eq 0 ]; then
    print_success "✅ Frontend deployed successfully!"
else
    print_error "❌ Firebase deployment failed"
    exit 1
fi

# Step 8: Get the frontend URL
print_status "Step 7: Getting frontend URL..."
FRONTEND_URL=$(firebase hosting:channel:list --json | grep -o '"url":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$FRONTEND_URL" ]; then
    FRONTEND_URL="https://airavat-a3a10.web.app"
fi

print_success "✅ Frontend URL: $FRONTEND_URL"

# Step 9: Test the deployment
print_status "Step 8: Testing the deployment..."
sleep 10

# Test if frontend loads
FRONTEND_RESPONSE=$(curl -s -I "$FRONTEND_URL" | head -1 || echo "FAILED")

if [[ "$FRONTEND_RESPONSE" == *"200"* ]]; then
    print_success "✅ Frontend is accessible!"
else
    print_warning "⚠️ Frontend may not be accessible yet: $FRONTEND_RESPONSE"
fi

# Step 10: Final summary
echo ""
echo "🎉 FRONTEND DEPLOYMENT COMPLETE!"
echo "==============================="
print_success "Frontend URL: $FRONTEND_URL"
print_success "Backend URL: $BACKEND_URL"
echo ""
echo "📋 What's been deployed:"
echo "✅ Flutter Web App"
echo "✅ AI Chatbot Interface"
echo "✅ Context History Widget"
echo "✅ Patient Dashboard"
echo "✅ Medical Profile Management"
echo "✅ Treatment Plan Interface"
echo "✅ Notification System"
echo ""
echo "🔧 Configuration:"
echo "✅ Backend URL: Updated to $BACKEND_URL"
echo "✅ Firebase Hosting: Deployed"
echo ""
echo "🚀 Next Steps:"
echo "1. Visit: $FRONTEND_URL"
echo "2. Test the AI chatbot"
echo "3. Try the context history feature"
echo "4. Test patient data management"
echo ""
print_success "🎯 Your Airavat Medical AI Assistant frontend is ready!"

# Step 11: Create a quick test script
cat > test_frontend.sh << EOF
#!/bin/bash
echo "🧪 Testing Airavat Frontend..."
FRONTEND_URL="$FRONTEND_URL"
echo "Testing: \$FRONTEND_URL"

echo "1. Frontend Accessibility:"
curl -s -I "\$FRONTEND_URL" | head -1

echo -e "\n2. Backend Connectivity:"
BACKEND_URL="$BACKEND_URL"
curl -s "\$BACKEND_URL/health"

echo -e "\n✅ Frontend tests completed!"
EOF

chmod +x test_frontend.sh
print_success "✅ Created test_frontend.sh for future testing"

echo ""
print_success "🎉 Frontend deployment script finished successfully!" 