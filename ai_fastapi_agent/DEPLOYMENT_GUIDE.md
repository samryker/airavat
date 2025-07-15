# Airavat Backend Deployment Guide

## Prerequisites

1. **Google Cloud CLI** installed and authenticated
2. **Docker** (optional, Cloud Build will handle this)
3. **Environment Variables** set up

## Environment Variables Setup

### Required Variables

```bash
# Google Cloud Project
export GOOGLE_CLOUD_PROJECT=airavat-a3a10

# Gemini API (Required for AI features)
export GEMINI_API_KEY=your_gemini_api_key_here

# MCP Database (Optional - for lifelong memory)
export MCP_DB_TYPE=alloydb  # or cloudsql
export ALLOYDB_HOST=your_alloydb_host
export ALLOYDB_PORT=5432
export ALLOYDB_USER=your_db_user
export ALLOYDB_PASSWORD=your_db_password
export ALLOYDB_DATABASE=your_db_name
```

### Quick Setup (Minimal)

For a basic deployment with just Gemini AI (no MCP database):

```bash
export GOOGLE_CLOUD_PROJECT=airavat-a3a10
export GEMINI_API_KEY=your_gemini_api_key_here
```

## Deployment Steps

1. **Set environment variables** (see above)

2. **Run the deployment script:**
   ```bash
   ./deploy_backend.sh
   ```

3. **Verify deployment:**
   ```bash
   # Get the service URL
   gcloud run services describe airavat-backend --region=us-central1 --format='value(status.url)'
   
   # Test health endpoint
   curl https://your-service-url/health
   ```

## Troubleshooting

### Common Issues

1. **Container fails to start:**
   - Check logs: `gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=airavat-backend"`
   - Ensure GEMINI_API_KEY is set

2. **Missing environment variables:**
   - The deployment script now handles missing variables gracefully
   - Check the health endpoint to see which services are available

3. **Import errors:**
   - Ensure all dependencies are in requirements.txt
   - Check that the Dockerfile is correct

### Health Check Endpoints

- **Health:** `GET /health` - Shows service status
- **Root:** `GET /` - Welcome message
- **API Docs:** `GET /docs` - Swagger documentation

## Post-Deployment

1. **Update frontend configuration** with the new backend URL
2. **Test all endpoints** using the provided test scripts
3. **Monitor logs** for any issues

## Environment Variables in Cloud Run Console

You can also set environment variables directly in the Google Cloud Console:

1. Go to Cloud Run → airavat-backend → Edit & Deploy New Revision
2. Under "Environment variables, secrets and connections"
3. Add your environment variables
4. Deploy the new revision 