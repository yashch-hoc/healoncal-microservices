"""
Google Secret Manager integration for HealOnCal API.
This module handles loading secrets from Google Secret Manager for GCP deployment.
Use either: one secret named ENV_FILE with full .env content (KEY=VALUE per line),
or individual secrets (MYSQL_HOST, MYSQL_PASSWORD, GEMINI_API_KEY, etc.).
"""
import os
import logging
from typing import Optional, Dict, Any
from google.cloud import secretmanager
from google.auth.exceptions import DefaultCredentialsError

logger = logging.getLogger(__name__)


def get_gcp_project_id() -> Optional[str]:
    """
    Get GCP project ID for Secret Manager.
    Tries: GOOGLE_CLOUD_PROJECT env, then GCLOUD_PROJECT, then GCP metadata server (Cloud Run/GKE).
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    if project_id:
        return project_id
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        return None

class SecretManager:
    """Handles Google Secret Manager operations."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Secret Manager client."""
        try:
            self.client = secretmanager.SecretManagerServiceClient()
            logger.info("✅ Secret Manager client initialized successfully")
        except DefaultCredentialsError:
            logger.warning("⚠️ Default credentials not found. Running in development mode.")
            self.client = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize Secret Manager client: {e}")
            self.client = None
    
    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """
        Retrieve a secret from Google Secret Manager.
        
        Args:
            secret_name: Name of the secret
            version: Version of the secret (default: "latest")
            
        Returns:
            Secret value or None if not found
        """
        if not self.client:
            logger.warning(f"⚠️ Secret Manager not available, using environment variable for {secret_name}")
            return os.getenv(secret_name)
        
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            response = self.client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            logger.info(f"✅ Successfully retrieved secret: {secret_name}")
            return secret_value
        except Exception as e:
            logger.error(f"❌ Failed to retrieve secret {secret_name}: {e}")
            # Fallback to environment variable
            return os.getenv(secret_name)
    
    def create_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Create a new secret in Google Secret Manager.
        
        Args:
            secret_name: Name of the secret
            secret_value: Value of the secret
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.error("❌ Secret Manager client not available")
            return False
        
        try:
            # Create the secret
            parent = f"projects/{self.project_id}"
            secret = {
                "replication": {
                    "automatic": {}
                }
            }
            
            # Check if secret already exists
            try:
                self.client.get_secret(request={"name": f"{parent}/secrets/{secret_name}"})
                logger.info(f"📝 Secret {secret_name} already exists, updating version...")
            except Exception:
                # Secret doesn't exist, create it
                self.client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": secret_name,
                        "secret": secret
                    }
                )
                logger.info(f"✅ Created secret: {secret_name}")
            
            # Add secret version
            self.client.add_secret_version(
                request={
                    "parent": f"{parent}/secrets/{secret_name}",
                    "payload": {"data": secret_value.encode("UTF-8")}
                }
            )
            logger.info(f"✅ Added new version to secret: {secret_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create secret {secret_name}: {e}")
            return False

# Optional: name of a single secret in GCP that holds the full .env file content (KEY=VALUE per line).
# If this secret exists, it is loaded first; then individual secrets below can override.
ENV_FILE_SECRET_NAME = "ENV_FILE"


def _parse_env_content(content: str) -> Dict[str, str]:
    """Parse .env-style content (KEY=VALUE lines) into a dict. Skips comments and empty lines."""
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key:
            if len(value) >= 2 and (
                (value.startswith('"') and value.endswith('"'))
                or (value.startswith("'") and value.endswith("'"))
            ):
                value = value[1:-1].replace("\\n", "\n").replace("\\t", "\t")
            result[key] = value
    return result


def load_env_file_from_secret_manager(project_id: str, secret_name: str = ENV_FILE_SECRET_NAME) -> bool:
    """
    Load a single secret from GCP Secret Manager that contains .env-style content (KEY=VALUE per line)
    and set each key in os.environ. Use this when you store the whole .env in one secret for GCP deployment.

    Args:
        project_id: Google Cloud project ID
        secret_name: Name of the secret (default: ENV_FILE)

    Returns:
        True if the secret was found and loaded, False otherwise
    """
    secrets_manager = SecretManager(project_id)
    if not secrets_manager.client:
        return False
    try:
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = secrets_manager.client.access_secret_version(request={"name": name})
        content = response.payload.data.decode("UTF-8")
        parsed = _parse_env_content(content)
        for k, v in parsed.items():
            os.environ[k] = v
        logger.info("✅ Loaded %s variables from secret %s", len(parsed), secret_name)
        return True
    except Exception as e:
        logger.debug("Secret %s not found or failed (optional): %s", secret_name, e)
        return False


def load_secrets_from_secret_manager(project_id: str) -> Dict[str, str]:
    """
    Load secrets from Google Secret Manager for GCP deployment.

    Option A – One secret with full .env:
        Create a secret named ENV_FILE with value = full .env content (KEY=VALUE per line).
        All variables are loaded from that; no need to create individual secrets.

    Option B – Individual secrets (names must match exactly):
        MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE,
        GEMINI_API_KEY,
        GCS_BUCKET_NAME, GCS_SKIN_SCANS_PREFIX.
        You can also use ENV_FILE first; individual secrets override ENV_FILE.

    Project ID is taken from GOOGLE_CLOUD_PROJECT, GCLOUD_PROJECT, or the GCP metadata server
    (Cloud Run / GKE set this automatically).

    Returns:
        Dictionary of secret names and values that were loaded.
    """
    secrets_manager = SecretManager(project_id)

    # Optional: load whole .env from a single secret first
    load_env_file_from_secret_manager(project_id, ENV_FILE_SECRET_NAME)

    secret_names = [
        # MySQL (Dockerised on GCP)
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_DATABASE",
        # Gemini
        "GEMINI_API_KEY",
        # Google Cloud Storage (image storage)
        "GCS_BUCKET_NAME",
        "GCS_SKIN_SCANS_PREFIX",
    ]

    secrets = {}
    for secret_name in secret_names:
        secret_value = secrets_manager.get_secret(secret_name)
        if secret_value:
            secrets[secret_name] = secret_value
            os.environ[secret_name] = secret_value
        else:
            logger.warning("⚠️ Secret %s not found in Secret Manager or environment", secret_name)
    return secrets

def create_secrets_in_secret_manager(project_id: str, secrets: Dict[str, str]) -> bool:
    """
    Create secrets in Google Secret Manager.
    
    Args:
        project_id: Google Cloud project ID
        secrets: Dictionary of secret names and values
        
    Returns:
        True if all secrets were created successfully
    """
    secrets_manager = SecretManager(project_id)
    success = True
    
    for secret_name, secret_value in secrets.items():
        if not secrets_manager.create_secret(secret_name, secret_value):
            success = False
    
    return success
        