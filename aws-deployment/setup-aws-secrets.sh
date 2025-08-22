#!/bin/bash

# AWS Secrets Manager Setup for Airavat
# This script creates secrets in AWS Secrets Manager for secure configuration

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

AWS_REGION=${AWS_REGION:-us-east-1}

print_status "Setting up AWS Secrets Manager for Airavat"

# Function to create or update a secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2
    local description=$3
    
    print_status "Processing secret: $secret_name"
    
    # Check if secret exists
    if aws secretsmanager describe-secret --secret-id "$secret_name" --region "$AWS_REGION" &> /dev/null; then
        print_status "Updating existing secret: $secret_name"
        aws secretsmanager update-secret \
            --secret-id "$secret_name" \
            --secret-string "$secret_value" \
            --region "$AWS_REGION" > /dev/null
    else
        print_status "Creating new secret: $secret_name"
        aws secretsmanager create-secret \
            --name "$secret_name" \
            --description "$description" \
            --secret-string "$secret_value" \
            --region "$AWS_REGION" > /dev/null
    fi
    
    print_success "Secret $secret_name configured"
}

# Prompt for values
echo ""
print_warning "You will be prompted to enter sensitive values. These will be stored securely in AWS Secrets Manager."
echo ""

# Firebase configuration
print_status "=== Firebase Configuration ==="
read -p "Enter your NEW Firebase Project ID: " FIREBASE_PROJECT_ID
echo ""
print_status "Enter your NEW Firebase Service Account JSON (paste the entire JSON, then press Ctrl+D):"
FIREBASE_SERVICE_ACCOUNT=$(cat)
FIREBASE_SERVICE_ACCOUNT_BASE64=$(echo "$FIREBASE_SERVICE_ACCOUNT" | base64 -w 0)

# SMTP configuration
print_status "=== SMTP Configuration ==="
read -p "Enter SMTP server (e.g., smtp.gmail.com): " SMTP_SERVER
read -p "Enter SMTP port (default 587): " SMTP_PORT
SMTP_PORT=${SMTP_PORT:-587}
read -p "Enter SMTP username: " SMTP_USERNAME
read -s -p "Enter SMTP password: " SMTP_PASSWORD
echo ""
read -p "Enter FROM email address: " EMAIL_FROM

# Database configuration (if using RDS)
print_status "=== Database Configuration (Optional - for RDS) ==="
read -p "Enter database host (leave empty if using Firebase only): " DB_HOST
if [ -n "$DB_HOST" ]; then
    read -p "Enter database name: " DB_NAME
    read -p "Enter database username: " DB_USER
    read -s -p "Enter database password: " DB_PASSWORD
    echo ""
fi

# Create secrets
print_status "Creating secrets in AWS Secrets Manager..."

# Firebase secrets
create_or_update_secret "airavat/firebase-project-id" "$FIREBASE_PROJECT_ID" "Firebase Project ID for Airavat"
create_or_update_secret "airavat/firebase-service-account" "$FIREBASE_SERVICE_ACCOUNT_BASE64" "Base64 encoded Firebase Service Account JSON for Airavat"

# SMTP secrets
create_or_update_secret "airavat/smtp-server" "$SMTP_SERVER" "SMTP server for Airavat email notifications"
create_or_update_secret "airavat/smtp-port" "$SMTP_PORT" "SMTP port for Airavat email notifications"
create_or_update_secret "airavat/smtp-username" "$SMTP_USERNAME" "SMTP username for Airavat email notifications"
create_or_update_secret "airavat/smtp-password" "$SMTP_PASSWORD" "SMTP password for Airavat email notifications"
create_or_update_secret "airavat/email-from" "$EMAIL_FROM" "FROM email address for Airavat notifications"

# Database secrets (if provided)
if [ -n "$DB_HOST" ]; then
    create_or_update_secret "airavat/db-host" "$DB_HOST" "Database host for Airavat"
    create_or_update_secret "airavat/db-name" "$DB_NAME" "Database name for Airavat"
    create_or_update_secret "airavat/db-username" "$DB_USER" "Database username for Airavat"
    create_or_update_secret "airavat/db-password" "$DB_PASSWORD" "Database password for Airavat"
fi

# Other configuration secrets
create_or_update_secret "airavat/smpl-assets-url" "https://storage.googleapis.com/airavat-mira-models/models" "SMPL assets base URL for Airavat"

echo ""
print_success "🎉 All secrets have been created in AWS Secrets Manager!"
echo ""
print_warning "Important Security Notes:"
echo "1. These secrets are now securely stored in AWS Secrets Manager"
echo "2. ECS tasks will retrieve these values at runtime"
echo "3. Never store these values in code or configuration files"
echo "4. Regularly rotate these secrets for security"
echo ""
print_status "Secrets created in region: $AWS_REGION"
print_status "You can view them in the AWS Secrets Manager console:"
echo "https://console.aws.amazon.com/secretsmanager/home?region=$AWS_REGION#!/home"
echo ""
print_status "Next step: Run the AWS deployment script:"
echo "cd aws-deployment && chmod +x deploy-to-aws.sh && ./deploy-to-aws.sh" 