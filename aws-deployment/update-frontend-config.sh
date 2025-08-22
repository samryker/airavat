#!/bin/bash

# Update Frontend Configuration for New Firebase and AWS Backend
# This script updates all frontend configuration files

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() { echo -e "${BLUE}🔄 $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

print_status "Updating Frontend Configuration for Migration"

# Step 1: Backup old configuration
print_status "Step 1: Backing up old configuration..."
cp airavat_flutter/lib/firebase_options.dart airavat_flutter/lib/firebase_options.dart.backup.$(date +%Y%m%d-%H%M%S)
cp airavat_flutter/web/index.html airavat_flutter/web/index.html.backup.$(date +%Y%m%d-%H%M%S)
cp airavat_flutter/lib/config/backend_config.dart airavat_flutter/lib/config/backend_config.dart.backup.$(date +%Y%m%d-%H%M%S)
print_success "Old configuration backed up"

# Step 2: Collect new configuration
print_warning "You will need to provide configuration for your NEW Firebase project and AWS backend"
echo ""

print_status "=== New Firebase Configuration ==="
read -p "Enter your NEW Firebase API Key: " NEW_FIREBASE_API_KEY
read -p "Enter your NEW Firebase Project ID: " NEW_FIREBASE_PROJECT_ID
read -p "Enter your NEW Firebase Auth Domain (usually PROJECT_ID.firebaseapp.com): " NEW_FIREBASE_AUTH_DOMAIN
read -p "Enter your NEW Firebase Storage Bucket (usually PROJECT_ID.appspot.com): " NEW_FIREBASE_STORAGE_BUCKET
read -p "Enter your NEW Firebase Messaging Sender ID: " NEW_FIREBASE_MESSAGING_SENDER_ID
read -p "Enter your NEW Firebase App ID: " NEW_FIREBASE_APP_ID
read -p "Enter your NEW Firebase Measurement ID (optional): " NEW_FIREBASE_MEASUREMENT_ID

echo ""
print_status "=== New AWS Backend Configuration ==="
read -p "Enter your NEW AWS backend URL (e.g., https://your-alb.region.elb.amazonaws.com): " NEW_BACKEND_URL

# Step 3: Update Firebase options
print_status "Step 3: Updating Firebase configuration..."
cat > airavat_flutter/lib/firebase_options.dart << EOF
import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, TargetPlatform, kIsWeb;

/// NEW Firebase Configuration - Security Migration
class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return FirebaseOptions(
        apiKey: '$NEW_FIREBASE_API_KEY',
        authDomain: '$NEW_FIREBASE_AUTH_DOMAIN',
        projectId: '$NEW_FIREBASE_PROJECT_ID',
        storageBucket: '$NEW_FIREBASE_STORAGE_BUCKET',
        messagingSenderId: '$NEW_FIREBASE_MESSAGING_SENDER_ID',
        appId: '$NEW_FIREBASE_APP_ID',
        measurementId: '$NEW_FIREBASE_MEASUREMENT_ID',
      );
    }
    throw UnsupportedError('DefaultFirebaseOptions only supported on web.');
  }
}
EOF

# Step 4: Update web index.html
print_status "Step 4: Updating web index.html..."
sed -i.bak "s/apiKey: \".*\"/apiKey: \"$NEW_FIREBASE_API_KEY\"/g" airavat_flutter/web/index.html
sed -i.bak "s/authDomain: \".*\"/authDomain: \"$NEW_FIREBASE_AUTH_DOMAIN\"/g" airavat_flutter/web/index.html
sed -i.bak "s/projectId: \".*\"/projectId: \"$NEW_FIREBASE_PROJECT_ID\"/g" airavat_flutter/web/index.html
sed -i.bak "s/storageBucket: \".*\"/storageBucket: \"$NEW_FIREBASE_STORAGE_BUCKET\"/g" airavat_flutter/web/index.html
sed -i.bak "s/messagingSenderId: \".*\"/messagingSenderId: \"$NEW_FIREBASE_MESSAGING_SENDER_ID\"/g" airavat_flutter/web/index.html
sed -i.bak "s/appId: \".*\"/appId: \"$NEW_FIREBASE_APP_ID\"/g" airavat_flutter/web/index.html

# Step 5: Update backend configuration
print_status "Step 5: Updating backend configuration..."
cat > airavat_flutter/lib/config/backend_config.dart << EOF
/// Backend Configuration - Updated for AWS Migration
class BackendConfig {
  // AWS Backend URL (replaces Google Cloud Run)
  static const String baseUrl = '$NEW_BACKEND_URL';
  
  // API endpoints
  static const String chatEndpoint = '\$baseUrl/agent/chat';
  static const String healthEndpoint = '\$baseUrl/health';
  static const String notificationsEndpoint = '\$baseUrl/notifications';
  
  // Security: All sensitive configuration moved to AWS Secrets Manager
  static const bool isProduction = true;
  static const String environment = 'aws-production';
  
  // Timeout configurations
  static const int timeoutSeconds = 30;
  static const int retryAttempts = 3;
}
EOF

# Step 6: Update .firebaserc if it exists
print_status "Step 6: Updating Firebase project reference..."
if [ -f "airavat_flutter/.firebaserc" ]; then
    cat > airavat_flutter/.firebaserc << EOF
{
  "projects": {
    "default": "$NEW_FIREBASE_PROJECT_ID"
  }
}
EOF
    print_success "Updated .firebaserc"
else
    print_warning ".firebaserc not found - you may need to run 'firebase init' in the frontend directory"
fi

# Step 7: Create deployment script for new Firebase
print_status "Step 7: Creating new deployment script..."
cat > airavat_flutter/deploy-to-new-firebase.sh << 'EOF'
#!/bin/bash

# Deploy to New Firebase Project - Security Migration

set -e

print_status() { echo -e "\033[0;34m🔄 $1\033[0m"; }
print_success() { echo -e "\033[0;32m✅ $1\033[0m"; }

print_status "Deploying to NEW Firebase project..."

# Build the Flutter web app
print_status "Building Flutter web app..."
flutter build web --release

# Deploy to Firebase Hosting
print_status "Deploying to Firebase Hosting..."
firebase deploy --only hosting

print_success "Deployment to new Firebase completed!"
EOF

chmod +x airavat_flutter/deploy-to-new-firebase.sh

print_success "🎉 Frontend configuration updated!"
echo ""
print_warning "Important Next Steps:"
echo "1. Go to your NEW Firebase console and set up:"
echo "   - Authentication (enable sign-in methods)"
echo "   - Firestore Database (create database)"
echo "   - Storage (if needed)"
echo "   - Security Rules"
echo ""
echo "2. Test the configuration:"
echo "   cd airavat_flutter"
echo "   flutter run -d chrome"
echo ""
echo "3. Deploy to new Firebase:"
echo "   cd airavat_flutter"
echo "   firebase login  # if not already logged in"
echo "   firebase init    # select your NEW project"
echo "   ./deploy-to-new-firebase.sh"
echo ""
print_status "New Firebase Console: https://console.firebase.google.com/project/$NEW_FIREBASE_PROJECT_ID"
print_status "New Backend URL: $NEW_BACKEND_URL" 