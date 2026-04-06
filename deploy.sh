#!/bin/bash

# HealOnCal API Deployment Script for Google Cloud Run
# This script handles the complete deployment process

set -e  # Exit on any error

echo "🚀 Starting HealOnCal API deployment to Google Cloud Run"

# Configuration
PROJECT_ID="tranquil-racer-470308-n3"
SERVICE_NAME="healoncal-api"
REGION="asia-south1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "📋 Deployment Configuration:"
echo "  Project ID: ${PROJECT_ID}"
echo "  Service Name: ${SERVICE_NAME}"
echo "  Region: ${REGION}"
echo "  Image: ${IMAGE_NAME}"

# Check if gcloud is installed and authenticated
echo "🔍 Checking gcloud CLI..."
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

# Set the project
echo "🔧 Setting Google Cloud project..."
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "🔌 Enabling required Google Cloud APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Set up secrets in Secret Manager (optional - skip if secrets are already set up manually)
if [ -f "setup_secrets.py" ]; then
    echo "🔐 Setting up secrets in Google Secret Manager..."
    python setup_secrets.py
    if [ $? -ne 0 ]; then
        echo "❌ Failed to set up secrets. Please check your .env file and try again."
        exit 1
    fi
else
    echo "🔐 Skipping secret setup (setup_secrets.py not found - using manually configured secrets)"
fi

# Build and deploy the application
echo "🏗️ Building and deploying to Google Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --source . \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 8Gi \
    --cpu 4 \
    --timeout 1000 \
    --concurrency 80 \
    --max-instances 2 \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
    --quiet

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful!"
    echo ""
    echo "🌐 Your HealOnCal API is now running on Google Cloud Run!"
    echo "📊 Check the deployment status with:"
    echo "   gcloud run services describe ${SERVICE_NAME} --region=${REGION}"
    echo ""
    echo "📝 View logs with:"
    echo "   gcloud run logs tail ${SERVICE_NAME} --region=${REGION}"
    echo ""
    echo "🔗 Get the service URL with:"
    echo "   gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)'"
else
    echo "❌ Deployment failed. Please check the logs above for details."
    exit 1
fi
