"""
Application configuration settings.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
from typing import List, Optional
import os
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = Field(default="Skin Analysis API", description="Name of the application")
    DEBUG: bool = Field(default=True, description="Enable debug mode")
    
    # Server settings
    HOST: str = Field(default="0.0.0.0", description="Host to bind the server to")
    PORT: int = Field(default=8000, description="Port to run the server on")
    
    # MySQL: Cloud SQL or Docker MySQL (GCP)
    MYSQL_HOST: str = Field(
        default="localhost",
        description="MySQL host: Cloud SQL private IP, Docker MySQL on GCP VM, or other host",
    )
    MYSQL_PORT: int = Field(
        default=3306,
        description="MySQL TCP port (3306 for Cloud SQL or Docker MySQL)",
    )
    MYSQL_USER: str = Field(default="", description="MySQL user")
    MYSQL_PASSWORD: str = Field(default="", description="MySQL password")
    MYSQL_DATABASE: str = Field(default="", description="MySQL database name")
    MYSQL_UNIX_SOCKET: Optional[str] = Field(
        default=None,
        description="Optional Cloud SQL Unix socket path, e.g. /cloudsql/PROJECT:REGION:INSTANCE",
    )
    
    # AWS S3 settings (image storage; metadata and results in MySQL).
    # Legacy GCS_* aliases are kept so existing callers/env files still work.
    S3_BUCKET_NAME: str = Field(default="", description="S3 bucket name for skin scan images")
    S3_PREFIX: str = Field(default="skin-scans", description="Object key prefix in S3")
    AWS_REGION: str = Field(default="ap-south-1", description="AWS region for S3")

    # Legacy (unused by the S3 backend; preserved to avoid breaking old .envs)
    GCS_BUCKET_NAME: str = Field(default="", description="[deprecated] alias for S3_BUCKET_NAME")
    GCS_SKIN_SCANS_PREFIX: str = Field(default="skin-scans", description="[deprecated] alias for S3_PREFIX")

    # Storage settings
    STORAGE_DIR: str = Field(
        default=str(Path("data").absolute()),
        description="Directory to store uploaded files and analysis results"
    )
    
    # Analysis settings
    CAPTURE_ANGLES: List[str] = Field(
        default=["front", "left", "right"],
        description="List of angles to capture for analysis"
    )
    MAX_RETRIES: int = Field(
        default=3,
        description="Maximum number of retry attempts for image capture"
    )
    
    # Model settings
    MODEL_PATH: str = Field(
        default="models/skin_analysis_model.pth",
        description="Path to the skin analysis model"
    )
    
    # Gemini API settings
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini API key for analysis summarization"
    )
    GEMINI_MODEL: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model to use for analysis summarization"
    )

    # SageMaker inference endpoints (ap-south-1). Empty string disables the call.
    SAGEMAKER_REGION: str = Field(
        default="ap-south-1",
        description="AWS region where the SageMaker inference endpoints live"
    )
    SAGEMAKER_ACNE_ENDPOINT_NAME: str = Field(
        default="acne-detection-6class-endpoint",
        description="SageMaker endpoint for the acne detection model"
    )
    SAGEMAKER_HYPERPIG_ENDPOINT_NAME: str = Field(
        default="pytorch-inference-2026-03-14-17-07-36-902",
        description="SageMaker endpoint for the hyperpigmentation segmentation model"
    )
    SAGEMAKER_AGING_ENDPOINT_NAME: str = Field(
        default="healoncal-aging-20260504-060553",
        description="SageMaker endpoint for the early aging detection model (Glogau/texture/wrinkles)"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env file

# Create instance - will be updated with secrets later
settings = Settings()

def update_settings_with_secrets():
    """Update settings with secrets loaded from GCP Secret Manager (for GCP deployment)."""
    global settings

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    if not project_id:
        try:
            from app.core.secrets import get_gcp_project_id
            project_id = get_gcp_project_id()
        except Exception:
            pass
    if project_id:
        try:
            from app.core.secrets import load_secrets_from_secret_manager
            logger.info("🔐 Loading secrets from Google Secret Manager for project: %s", project_id)
            load_secrets_from_secret_manager(project_id)
        except Exception as e:
            logger.warning("⚠️ Failed to load secrets from Secret Manager: %s", e)
            logger.info("📝 Falling back to environment variables")
    else:
        logger.info("📝 No GCP project ID (GOOGLE_CLOUD_PROJECT / metadata); using .env or environment only")

    # Reload settings to pick up any new environment variables
    settings = Settings()
    # Create storage directories
    Path(settings.STORAGE_DIR).mkdir(parents=True, exist_ok=True)
    
    # Reinitialize MySQL client with the loaded secrets
    try:
        from app.services.mysql_client_service import mysql_service
        mysql_service.reinitialize()
        logger.info("🔄 MySQL client reinitialized with loaded secrets")
    except Exception as e:
        logger.warning(f"⚠️ Failed to reinitialize MySQL client: {e}")

# Create storage directories
Path(settings.STORAGE_DIR).mkdir(parents=True, exist_ok=True)
