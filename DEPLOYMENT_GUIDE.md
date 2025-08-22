# 🚀 Airavat Medical AI Assistant - Deployment Guide

## Overview

This guide explains the new unified deployment system that automatically handles environment variables and deploys both backend and frontend in one go.

## 🎯 Problem Solved

**Before:** You had to run multiple scripts and manually fix the Gemini API key issue every time:
1. `deploy_backend.sh`
2. `fix_env_variables.sh` (because the API key wasn't set)
3. `deploy_frontend.sh`

**After:** One script handles everything automatically:
1. `deploy_airavat_complete.sh` - Deploys everything with proper environment variables

## 📁 New Deployment Scripts

### 1. Master Deployment Script
```bash
./deploy_airavat_complete.sh
```
**What it does:**
- ✅ Deploys backend with environment variables automatically
- ✅ Deploys frontend with correct backend URL
- ✅ Tests both deployments
- ✅ Creates test scripts for future use

### 2. Backend Deployment Script
```bash
./ai_fastapi_agent/deploy_complete_with_env.sh
```
**What it does:**
- ✅ Gemini API disabled for security (no API key required)
- ✅ Sets environment variables in Cloud Run
- ✅ Deploys backend with proper configuration
- ✅ Tests the deployment

### 3. Frontend Deployment Script
```bash
./airavat_flutter/deploy_frontend_with_backend.sh
```
**What it does:**
- ✅ Gets backend URL from Cloud Run
- ✅ Updates frontend configuration
- ✅ Builds and deploys Flutter web app
- ✅ Tests the deployment

## 🚀 Quick Start

### Prerequisites
1. Docker running
2. gcloud authenticated
3. Firebase CLI installed
4. Flutter installed

### One-Command Deployment
```bash
# From the project root directory
./deploy_airavat_complete.sh
```

That's it! This single command will:
1. Deploy the backend with Gemini API key
2. Deploy the frontend with correct backend URL
3. Test everything
4. Give you the URLs to access your app

## 🔧 What Gets Deployed

### Backend (FastAPI)
- ✅ AI Chatbot with Gemini integration
- ✅ Context retrieval system
- ✅ Patient memory management
- ✅ Treatment plan management
- ✅ Notification system
- ✅ Feedback processing
- ✅ All API endpoints

### Frontend (Flutter Web)
- ✅ AI Chatbot Interface
- ✅ Context History Widget
- ✅ Patient Dashboard
- ✅ Medical Profile Management
- ✅ Treatment Plan Interface
- ✅ Notification System

## 🧪 Testing

After deployment, you can test everything with:
```bash
./test_complete_deployment.sh
```

This will test:
- Backend health
- AI endpoint
- Context retrieval
- Frontend accessibility

## 🔑 Environment Variables

The system automatically handles:
- **GEMINI API**: Disabled for security reasons
- **Backend URL**: Automatically detected and configured
- **Firebase Configuration**: Handled by Firebase CLI

## 📋 File Structure

```
airavat/
├── deploy_airavat_complete.sh          # Master deployment script
├── test_complete_deployment.sh         # Complete testing script
├── ai_fastapi_agent/
│   ├── deploy_complete_with_env.sh     # Backend deployment
│   └── test_deployment.sh              # Backend testing
└── airavat_flutter/
    ├── deploy_frontend_with_backend.sh # Frontend deployment
    └── test_frontend.sh                # Frontend testing
```

## 🎉 Benefits

1. **No More Manual Steps**: Everything is automated
2. **No More API Key Issues**: Environment variables are set automatically
3. **Consistent Deployments**: Same process every time
4. **Built-in Testing**: Automatic verification after deployment
5. **Easy Troubleshooting**: Clear error messages and status updates

## 🚨 Troubleshooting

### Common Issues

1. **Docker not running**
   ```
   ❌ Docker is not running. Please start Docker and try again.
   ```
   **Solution:** Start Docker Desktop

2. **gcloud not authenticated**
   ```
   ❌ Not authenticated with gcloud. Please run 'gcloud auth login'
   ```
   **Solution:** Run `gcloud auth login`

3. **Missing .env file**
   ```
   ❌ .env file not found at ai-services/main_agent/.env
   ```
   **Solution:** API key requirements have been removed for security

4. **Flutter not installed**
   ```
   ❌ Flutter is not installed or not in PATH
   ```
   **Solution:** Install Flutter and add to PATH

### Manual Testing

If you need to test individual components:

```bash
# Test backend only
cd ai_fastapi_agent
./test_deployment.sh

# Test frontend only
cd airavat_flutter
./test_frontend.sh

# Test everything
./test_complete_deployment.sh
```

## 🔄 Updating

To update your deployment:

1. Make your code changes
2. Run the deployment script again:
   ```bash
   ./deploy_airavat_complete.sh
   ```

The script will automatically:
- Deploy the updated backend
- Set environment variables
- Deploy the updated frontend
- Test everything

## 📞 Support

If you encounter issues:

1. Check the error messages in the deployment output
2. Run the test scripts to identify the problem
3. Check that all prerequisites are met
4. Note: API key requirements have been removed for security

## 🎯 Success Indicators

After successful deployment, you should see:

```
🎉 COMPLETE DEPLOYMENT SUCCESSFUL!
=================================
✅ Backend URL: https://airavat-backend-xxx.run.app
✅ Frontend URL: https://airavat-a3a10.web.app
✅ GEMINI API: Disabled for security
✅ AI Chatbot: Working with intelligent responses
✅ Context History: Working
✅ All endpoints: Functional
```

Your Airavat Medical AI Assistant is now ready to use! 🚀 