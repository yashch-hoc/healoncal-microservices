# HealOnCal API Deployment Script for Google Cloud Run (PowerShell)
# This script handles the complete deployment process

Write-Host "🚀 Starting HealOnCal API deployment to Google Cloud Run" -ForegroundColor Green

# Configuration
$PROJECT_ID = "tranquil-racer-470308-n3"
$SERVICE_NAME = "healoncal-api"
$REGION = "asia-south1"

Write-Host "📋 Deployment Configuration:" -ForegroundColor Cyan
Write-Host "  Project ID: $PROJECT_ID"
Write-Host "  Service Name: $SERVICE_NAME"
Write-Host "  Region: $REGION"

# Check if gcloud is installed and authenticated
Write-Host "🔍 Checking gcloud CLI..." -ForegroundColor Yellow
try {
    gcloud version | Out-Null
    Write-Host "✅ gcloud CLI found" -ForegroundColor Green
} catch {
    Write-Host "❌ gcloud CLI not found. Please install Google Cloud SDK." -ForegroundColor Red
    exit 1
}

# Set the project
Write-Host "🔧 Setting Google Cloud project..." -ForegroundColor Yellow
gcloud config set project $PROJECT_ID

# Enable required APIs
Write-Host "🔌 Enabling required Google Cloud APIs..." -ForegroundColor Yellow
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Set up secrets in Secret Manager (optional - skip if secrets are already set up manually)
if (Test-Path "setup_secrets.py") {
    Write-Host "🔐 Setting up secrets in Google Secret Manager..." -ForegroundColor Yellow
    python setup_secrets.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to set up secrets. Please check your .env file and try again." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "🔐 Skipping secret setup (setup_secrets.py not found - using manually configured secrets)" -ForegroundColor Cyan
}

# Build and deploy the application
Write-Host "🏗️ Building and deploying to Google Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
    --source . `
    --platform managed `
    --region $REGION `
    --allow-unauthenticated `
    --memory 8Gi `
    --cpu 4 `
    --timeout 1000 `
    --concurrency 80 `
    --max-instances 2 `
    --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID" `
    --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Deployment successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "🌐 Your HealOnCal API is now running on Google Cloud Run!" -ForegroundColor Green
    Write-Host "📊 Check the deployment status with:" -ForegroundColor Cyan
    Write-Host "   gcloud run services describe $SERVICE_NAME --region=$REGION"
    Write-Host ""
    Write-Host "📝 View logs with:" -ForegroundColor Cyan
    Write-Host "   gcloud run logs tail $SERVICE_NAME --region=$REGION"
    Write-Host ""
    Write-Host "🔗 Get the service URL with:" -ForegroundColor Cyan
    Write-Host "   gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)'"
} else {
    Write-Host "❌ Deployment failed. Please check the logs above for details." -ForegroundColor Red
    exit 1
}
