# 🚨 URGENT SECURITY MIGRATION GUIDE

## IMMEDIATE SECURITY BREACH RESPONSE

**Someone has stolen your API keys and is misusing them for video creation, causing huge billing spikes!**

This guide will help you quickly migrate to a new Firebase project and AWS infrastructure with proper security.

---

## ⚡ IMMEDIATE ACTIONS (DO FIRST!)

### 1. SECURE YOUR COMPROMISED ACCOUNTS

```bash
# Google Cloud Console
1. Go to https://console.cloud.google.com
2. Go to "APIs & Services" > "Credentials"
3. DELETE the compromised Gemini API key immediately
4. Disable billing alerts and set spending limits to $0
5. Review usage reports for unauthorized charges

# Firebase Console
1. Go to https://console.firebase.google.com
2. Select your current project
3. Go to "Project Settings" > "Service Accounts"
4. Generate NEW service account keys
5. Revoke all existing keys

# Change all passwords and enable 2FA everywhere!
```

---

## 🏗️ PHASE 1: SETUP NEW INFRASTRUCTURE (1-2 hours)

### Step 1: Create New Firebase Project

1. **Create New Firebase Project**
   ```bash
   # Go to https://console.firebase.google.com
   # Click "Create a project"
   # Choose a NEW project name (different from the old one)
   # Enable Google Analytics (optional)
   ```

2. **Enable Required Services**
   ```bash
   # In your new Firebase project:
   # 1. Authentication > Get Started > Enable Email/Password
   # 2. Firestore Database > Create Database > Start in test mode
   # 3. Storage > Get Started
   # 4. Hosting > Get Started
   ```

3. **Get New Firebase Configuration**
   ```bash
   # In Firebase Console:
   # Project Settings > General > Your apps > Web app > Config
   # Copy the configuration values (you'll need these later)
   ```

### Step 2: Setup New AWS Account

1. **Create New AWS Account**
   ```bash
   # Go to https://aws.amazon.com
   # Create a new account (use different email if possible)
   # Set up billing alerts and spending limits
   ```

2. **Configure AWS CLI**
   ```bash
   # Install AWS CLI if not already installed
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   
   # Configure with your new AWS account
   aws configure
   # Enter your new AWS Access Key ID
   # Enter your new AWS Secret Access Key
   # Default region: us-east-1
   # Default output format: json
   ```

---

## 🔒 PHASE 2: SECURE CODE MIGRATION (2-3 hours)

### Step 1: Prepare Your Codebase

The codebase has already been secured with all API keys removed. Verify this:

```bash
# Check that no API keys remain in code
cd /Users/unbxd/Desktop/judwaa/airavat
grep -r "AIzaSy" . --exclude-dir=node_modules --exclude-dir=.git || echo "✅ No API keys found in code"

# Verify security changes
echo "✅ All GEMINI_API_KEY references removed"
echo "✅ Dockerfile optimized for AWS"
echo "✅ Environment variables externalized"
echo "✅ AWS deployment scripts ready"
```

### Step 2: Setup AWS Secrets Manager

```bash
# Make the script executable and run it
cd aws-deployment
chmod +x setup-aws-secrets.sh
./setup-aws-secrets.sh
```

This will prompt you for:
- New Firebase configuration
- SMTP settings for emails
- Database credentials (if using RDS)

---

## 🚀 PHASE 3: DEPLOY TO AWS (2-3 hours)

### Step 1: Deploy Backend to AWS

```bash
# Make deployment script executable
chmod +x deploy-to-aws.sh

# Deploy to AWS ECS Fargate
./deploy-to-aws.sh
```

This script will:
- ✅ Create ECR repository
- ✅ Build and push Docker image
- ✅ Create ECS cluster
- ✅ Deploy to Fargate
- ✅ Set up load balancer health checks

### Step 2: Update Frontend Configuration

```bash
# Update frontend for new Firebase and AWS backend
chmod +x update-frontend-config.sh
./update-frontend-config.sh
```

This will prompt you for:
- New Firebase project configuration
- New AWS backend URL

### Step 3: Deploy Frontend to New Firebase

```bash
cd ../airavat_flutter

# Login to Firebase with your NEW account
firebase logout
firebase login

# Initialize for your NEW project
firebase init hosting

# Deploy to new Firebase
./deploy-to-new-firebase.sh
```

---

## 🔍 PHASE 4: TESTING & VERIFICATION (1 hour)

### Step 1: Test Backend Health

```bash
# Test the health endpoint
curl https://your-new-aws-backend.region.elb.amazonaws.com/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-01-18T...",
  "version": "1.0.0",
  "environment": "aws-production",
  "services": {
    "database": "healthy",
    "notification_service": true,
    "email_service": true
  }
}
```

### Step 2: Test Frontend

```bash
# Open your new Firebase URL
https://your-new-project.web.app

# Verify:
# ✅ Login/signup works
# ✅ Dashboard loads
# ✅ Chat functionality works
# ✅ Notifications work
# ✅ No console errors
```

### Step 3: Test Integration

```bash
# Test a complete user flow:
# 1. Register new account
# 2. Complete onboarding
# 3. Send a chat message
# 4. Check notifications
# 5. View dashboard data
```

---

## 🛡️ PHASE 5: PRODUCTION HARDENING (1-2 hours)

### Step 1: Set up Application Load Balancer

```bash
# Create ALB for production
aws elbv2 create-load-balancer \
    --name airavat-alb \
    --subnets subnet-xxx subnet-yyy \
    --security-groups sg-xxx \
    --scheme internet-facing \
    --type application
```

### Step 2: Configure SSL Certificate

```bash
# Request SSL certificate from ACM
aws acm request-certificate \
    --domain-name yourdomain.com \
    --validation-method DNS
```

### Step 3: Set up Monitoring

```bash
# CloudWatch alarms
aws cloudwatch put-metric-alarm \
    --alarm-name "airavat-high-cpu" \
    --alarm-description "High CPU usage" \
    --metric-name CPUUtilization \
    --namespace AWS/ECS \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold
```

---

## ✅ SECURITY CHECKLIST

### Infrastructure Security
- [ ] All API keys removed from code
- [ ] Secrets stored in AWS Secrets Manager
- [ ] Docker image runs as non-root user
- [ ] Network security groups configured
- [ ] Load balancer with SSL termination
- [ ] CloudWatch logging enabled

### Firebase Security
- [ ] New Firebase project with fresh credentials
- [ ] Firestore security rules configured
- [ ] Authentication properly configured
- [ ] Old Firebase project disabled

### Monitoring & Alerts
- [ ] CloudWatch monitoring set up
- [ ] Billing alerts configured
- [ ] Error tracking implemented
- [ ] Performance monitoring active

---

## 📞 EMERGENCY CONTACTS & SUPPORT

### If Something Goes Wrong:
1. **AWS Support**: Create support case in AWS Console
2. **Firebase Support**: Firebase Console > Support
3. **Rollback Plan**: Keep old environment until migration is fully verified

### Important URLs:
- **New AWS Console**: https://console.aws.amazon.com
- **New Firebase Console**: https://console.firebase.google.com/project/YOUR_NEW_PROJECT
- **ECS Service**: https://console.aws.amazon.com/ecs/home?region=us-east-1#/clusters/airavat-cluster
- **Secrets Manager**: https://console.aws.amazon.com/secretsmanager/home?region=us-east-1

---

## 🎯 SUCCESS CRITERIA

✅ **Migration Complete When:**
- Backend running on AWS ECS Fargate
- Frontend deployed to new Firebase
- All functionality working
- No API keys in code
- Monitoring and alerts active
- Old infrastructure disabled

✅ **Security Restored When:**
- All compromised keys revoked
- New infrastructure isolated
- Spending under control
- Proper access controls in place

---

## 💰 COST OPTIMIZATION

### Expected AWS Costs:
- **ECS Fargate**: ~$30-50/month for 2 tasks
- **Load Balancer**: ~$20/month
- **ECR Storage**: ~$1-5/month
- **CloudWatch Logs**: ~$5-10/month
- **Secrets Manager**: ~$1/month

### Firebase Costs:
- **Hosting**: Free for reasonable usage
- **Firestore**: Pay per operation
- **Authentication**: Free up to 50k MAU

**Total Estimated Monthly Cost: $60-90** (much better than stolen API usage!)

---

**🚨 Remember: Time is critical! Follow this guide step-by-step to get back online securely as soon as possible.** 