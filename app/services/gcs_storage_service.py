"""
Google Cloud Storage Service for Healoncal images.

Stores skin scan images and heatmaps in Google Cloud Storage (GCS).
Session and analysis metadata are stored in MySQL.

This mirrors the public interface of the former S3 service so the rest
of the codebase can switch storage backends with minimal changes.
"""
import logging
import re
from typing import Optional, Tuple
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)

_GCS_HOST_RE = re.compile(
    r"^(?P<bucket>[a-z0-9.\-_]+)\.storage\.googleapis\.com$", re.I
)


def _parse_gcs_url(image_url: str) -> Optional[Tuple[str, str]]:
    """
    Return (bucket, blob_name) for common GCS URLs, else None.

    Supports:
    - https://storage.googleapis.com/bucket/path/to/object
    - https://bucket.storage.googleapis.com/path/to/object
    - gs://bucket/path/to/object
    """
    if not image_url:
        return None

    if image_url.startswith("gs://"):
        # gs://bucket/path/to/blob
        without_scheme = image_url[len("gs://") :]
        parts = without_scheme.split("/", 1)
        if len(parts) != 2:
            return None
        return parts[0], parts[1]

    parsed = urlparse(image_url)
    host = parsed.netloc.split("@")[-1].lower()

    if host == "storage.googleapis.com":
        # /bucket/blob
        path = parsed.path.lstrip("/")
        parts = path.split("/", 1)
        if len(parts) != 2:
            return None
        bucket, blob = parts[0], parts[1]
        return bucket, unquote(blob)

    m = _GCS_HOST_RE.match(host)
    if m:
        bucket = m.group("bucket")
        blob = parsed.path.lstrip("/")
        return bucket, unquote(blob)

    return None


def _get_gcs_client():
    """
    Get google-cloud-storage client using app config.

    Returns (client, bucket_name, prefix) or (None, None, None) if not configured.
    """
    try:
        from app.core.config import settings

        bucket_name = getattr(settings, "GCS_BUCKET_NAME", "") or ""
        prefix = getattr(settings, "GCS_SKIN_SCANS_PREFIX", "skin-scans")
        if not bucket_name:
            return None, None, None

        from google.cloud import storage

        client = storage.Client()
        return client, bucket_name, prefix
    except Exception as e:
        logger.warning(f"[GCS] Failed to create GCS client: {e}")
        return None, None, None


def upload_image(file_path: str, image_data: bytes, content_type: str = "image/jpeg") -> str:
    """
    Upload image bytes to GCS and return the public URL.

    file_path is the object key under the configured prefix, e.g.:
    users/{user_id}/healoncal/{session_id}/{angle}_{timestamp}.jpg
    """
    client, bucket_name, prefix = _get_gcs_client()
    if not client or not bucket_name:
        raise Exception("GCS not configured - set GCS_BUCKET_NAME and credentials")

    try:
        bucket = client.bucket(bucket_name)
        # Preserve same logical key structure; allow optional prefix
        key = f"{prefix.rstrip('/')}/{file_path.lstrip('/')}" if prefix else file_path.lstrip("/")
        blob = bucket.blob(key)
        blob.upload_from_string(image_data, content_type=content_type)
        # Make object publicly readable if bucket policy allows it; otherwise
        # callers can use signed URLs instead.
        try:
            blob.make_public()
        except Exception as e:
            logger.info(f"[GCS] Could not set public ACL (likely private bucket): {e}")
        image_url = blob.public_url
        logger.info("[GCS STORAGE] Upload successful: %s", key)
        return image_url
    except Exception as e:
        logger.error(f"[GCS STORAGE ERROR] Upload failed: {e}")
        raise Exception(f"Storage error: {e}")


def delete_object_key(key: str) -> None:
    """Best-effort delete of an object key under the configured prefix."""
    client, bucket_name, prefix = _get_gcs_client()
    if not client or not bucket_name or not key:
        return
    try:
        bucket = client.bucket(bucket_name)
        full_key = f"{prefix.rstrip('/')}/{key.lstrip('/')}" if prefix else key.lstrip("/")
        blob = bucket.blob(full_key)
        blob.delete()
        logger.info("[GCS STORAGE] Deleted key after failed persist: %s", full_key)
    except Exception as e:
        logger.warning("[GCS STORAGE] Delete failed (non-fatal): %s — %s", key, e)


def download_image(image_url: str) -> Optional[bytes]:
    """
    Download image bytes from GCS by URL (used as fallback when HTTP get fails).

    Returns bytes or None if not a GCS URL or download fails.
    """
    parsed = _parse_gcs_url(image_url)
    if not parsed:
        return None
    bucket_name, blob_name = parsed
    try:
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        data = blob.download_as_bytes()
        if data:
            logger.info(
                "[GCS STORAGE] Downloaded %s bytes bucket=%s blob=%s",
                len(data),
                bucket_name,
                blob_name[:80],
            )
        return data
    except Exception as e:
        logger.error(
            "[GCS STORAGE ERROR] Download failed bucket=%s blob=%s… : %s",
            bucket_name,
            blob_name[:80] if blob_name else "",
            e,
        )
        return None


def is_gcs_configured() -> bool:
    """Return True if GCS bucket is configured."""
    client, bucket_name, _ = _get_gcs_client()
    return client is not None and bool(bucket_name)


def get_signed_url(image_url: str, expires_in: int = 3600) -> Optional[str]:
    """
    Return a signed URL for a GCS object so the browser can load it from a private bucket.
    If not a GCS URL or GCS not configured, returns the original URL.
    """
    parsed = _parse_gcs_url(image_url)
    if not parsed:
        return image_url
    bucket_name, blob_name = parsed
    try:
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        url = blob.generate_signed_url(version="v4", expiration=expires_in, method="GET")
        return url
    except Exception as e:
        logger.warning(f"[GCS] Signed URL generation failed for {image_url[:80]}: {e}")
        return image_url

