#!/bin/bash

# 🚨 URGENT AWS DEPLOYMENT SCRIPT - Security Breach Response
# This script deploys Airavat to AWS ECS Fargate with proper security

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_status() {
    echo -e "${BLUE}🔄 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
ECR_REPOSITORY_NAME="airavat-backend"
CLUSTER_NAME="airavat-cluster"
SERVICE_NAME="airavat-service"
TASK_DEFINITION_FAMILY="airavat-backend"

print_status "Starting AWS deployment for Airavat (Security Breach Response)"

# Step 1: Verify AWS CLI and credentials
print_status "Step 1: Verifying AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured. Run 'aws configure' first."
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
print_success "AWS Account ID: $AWS_ACCOUNT_ID"

# Step 2: Create ECR repository if it doesn't exist
print_status "Step 2: Setting up ECR repository..."
if ! aws ecr describe-repositories --repository-names $ECR_REPOSITORY_NAME --region $AWS_REGION &> /dev/null; then
    print_status "Creating ECR repository: $ECR_REPOSITORY_NAME"
    aws ecr create-repository \
        --repository-name $ECR_REPOSITORY_NAME \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true
    print_success "ECR repository created"
else
    print_success "ECR repository already exists"
fi

# Step 3: Build and push Docker image
print_status "Step 3: Building and pushing Docker image..."
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI

# Build image
print_status "Building Docker image..."
docker build -f aws-deployment/Dockerfile.optimized -t $ECR_REPOSITORY_NAME .

# Tag and push
docker tag $ECR_REPOSITORY_NAME:latest $ECR_URI:latest
docker tag $ECR_REPOSITORY_NAME:latest $ECR_URI:$(date +%Y%m%d-%H%M%S)

print_status "Pushing image to ECR..."
docker push $ECR_URI:latest
docker push $ECR_URI:$(date +%Y%m%d-%H%M%S)

print_success "Docker image pushed to ECR"

# Step 4: Create ECS cluster if it doesn't exist
print_status "Step 4: Setting up ECS cluster..."
if ! aws ecs describe-clusters --clusters $CLUSTER_NAME --region $AWS_REGION --query 'clusters[?status==`ACTIVE`]' --output text &> /dev/null; then
    print_status "Creating ECS cluster: $CLUSTER_NAME"
    aws ecs create-cluster \
        --cluster-name $CLUSTER_NAME \
        --capacity-providers FARGATE \
        --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
        --region $AWS_REGION
    print_success "ECS cluster created"
else
    print_success "ECS cluster already exists"
fi

# Step 5: Create CloudWatch log group
print_status "Step 5: Setting up CloudWatch logs..."
LOG_GROUP="/aws/ecs/airavat-backend"
if ! aws logs describe-log-groups --log-group-name-prefix $LOG_GROUP --region $AWS_REGION --query 'logGroups[?logGroupName==`'$LOG_GROUP'`]' --output text &> /dev/null; then
    aws logs create-log-group --log-group-name $LOG_GROUP --region $AWS_REGION
    print_success "CloudWatch log group created"
else
    print_success "CloudWatch log group already exists"
fi

# Step 6: Update task definition with current image URI
print_status "Step 6: Updating task definition..."
sed "s/ACCOUNT_ID/$AWS_ACCOUNT_ID/g; s/REGION/$AWS_REGION/g" aws-deployment/aws-ecs-task-definition.json > /tmp/task-definition.json

# Register task definition
TASK_DEFINITION_ARN=$(aws ecs register-task-definition \
    --cli-input-json file:///tmp/task-definition.json \
    --region $AWS_REGION \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

print_success "Task definition registered: $TASK_DEFINITION_ARN"

# Step 7: Create or update ECS service
print_status "Step 7: Deploying ECS service..."

# Check if service exists
if aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION --query 'services[?status==`ACTIVE`]' --output text &> /dev/null; then
    print_status "Updating existing service..."
    aws ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --task-definition $TASK_DEFINITION_FAMILY \
        --region $AWS_REGION
else
    print_status "Creating new service..."
    # Note: You'll need to replace these subnet and security group IDs with your own
    aws ecs create-service \
        --cluster $CLUSTER_NAME \
        --service-name $SERVICE_NAME \
        --task-definition $TASK_DEFINITION_FAMILY \
        --desired-count 2 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxx,subnet-yyyyyy],securityGroups=[sg-xxxxxxxx],assignPublicIp=ENABLED}" \
        --region $AWS_REGION
fi

print_success "ECS service deployment initiated"

# Step 8: Wait for deployment to complete
print_status "Step 8: Waiting for deployment to stabilize..."
aws ecs wait services-stable --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION

print_success "Deployment completed successfully!"

# Step 9: Get service endpoint
print_status "Step 9: Getting service endpoint..."
TASK_ARNS=$(aws ecs list-tasks --cluster $CLUSTER_NAME --service-name $SERVICE_NAME --region $AWS_REGION --query 'taskArns[0]' --output text)

if [ "$TASK_ARNS" != "None" ] && [ -n "$TASK_ARNS" ]; then
    PUBLIC_IP=$(aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $TASK_ARNS --region $AWS_REGION --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text | xargs -I {} aws ec2 describe-network-interfaces --network-interface-ids {} --region $AWS_REGION --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
    
    if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "None" ]; then
        print_success "Service deployed at: http://$PUBLIC_IP:8000"
        print_success "Health check: http://$PUBLIC_IP:8000/health"
    else
        print_warning "Could not determine public IP. Check ECS console for service details."
    fi
else
    print_warning "No running tasks found. Check ECS console for service status."
fi

echo ""
print_success "🎉 AWS deployment completed!"
echo ""
echo "Next steps:"
echo "1. Set up Application Load Balancer (ALB) for production"
echo "2. Configure domain name and SSL certificate"
echo "3. Set up AWS Secrets Manager for sensitive configuration"
echo "4. Configure monitoring and alerting"
echo ""
echo "Important URLs:"
echo "📊 ECS Console: https://console.aws.amazon.com/ecs/home?region=$AWS_REGION#/clusters/$CLUSTER_NAME"
echo "📦 ECR Repository: https://console.aws.amazon.com/ecr/repositories/$ECR_REPOSITORY_NAME?region=$AWS_REGION"
echo "📝 CloudWatch Logs: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logsV2:log-groups/log-group/%2Faws%2Fecs%2Fairavat-backend" 