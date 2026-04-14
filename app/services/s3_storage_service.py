"""
AWS S3 storage service for Healoncal images.

    upload_image(file_path, image_data, content_type) -> str
    delete_object_key(key) -> None
    download_image(image_url) -> Optional[bytes]
    is_s3_configured() -> bool
    get_signed_url(image_url, expires_in) -> Optional[str]

Configured via settings:
    S3_BUCKET_NAME, S3_PREFIX, AWS_REGION
and the standard AWS creds env vars (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
or IAM role when running on EC2.
"""
import logging
import re
from typing import Optional, Tuple
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)

_S3_VIRTUAL_HOST_RE = re.compile(
    r"^(?P<bucket>[a-z0-9.\-]+)\.s3[.\-](?:(?P<region>[a-z0-9\-]+)\.)?amazonaws\.com$",
    re.I,
)


def _parse_s3_url(image_url: str) -> Optional[Tuple[str, str]]:
    """
    Return (bucket, key) for common S3 URLs, else None.

    Supports:
    - s3://bucket/key
    - https://bucket.s3.amazonaws.com/key
    - https://bucket.s3.<region>.amazonaws.com/key
    - https://s3.<region>.amazonaws.com/bucket/key
    """
    if not image_url:
        return None

    if image_url.startswith("s3://"):
        without_scheme = image_url[len("s3://"):]
        parts = without_scheme.split("/", 1)
        if len(parts) != 2:
            return None
        return parts[0], unquote(parts[1])

    parsed = urlparse(image_url)
    host = parsed.netloc.split("@")[-1].lower()
    path = parsed.path.lstrip("/")

    # Path-style: s3.<region>.amazonaws.com/<bucket>/<key>
    if host.startswith("s3.") and host.endswith("amazonaws.com"):
        parts = path.split("/", 1)
        if len(parts) != 2:
            return None
        return parts[0], unquote(parts[1])

    # Virtual-host style
    m = _S3_VIRTUAL_HOST_RE.match(host)
    if m:
        return m.group("bucket"), unquote(path)

    return None


# Cached boto3 client. Building a new client per upload costs ~50-200ms (credential
# resolution, endpoint discovery, etc). Pin it at module level and reuse.
_S3_CLIENT_CACHE: Optional[Tuple[object, str, str, Optional[str]]] = None


def _get_s3_client():
    """
    Return (client, bucket_name, prefix, region) or (None, None, None, None) if not configured.
    Client is cached after first successful build.
    """
    global _S3_CLIENT_CACHE
    if _S3_CLIENT_CACHE is not None:
        return _S3_CLIENT_CACHE

    try:
        from app.core.config import settings

        bucket_name = getattr(settings, "S3_BUCKET_NAME", "") or ""
        prefix = getattr(settings, "S3_PREFIX", "skin-scans") or ""
        region = getattr(settings, "AWS_REGION", "") or None
        if not bucket_name:
            return None, None, None, None

        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            region_name=region,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                # Bump connection pool so ~21 concurrent heatmap uploads don't
                # serialise on the default 10-conn pool.
                max_pool_connections=32,
            ),
        )
        _S3_CLIENT_CACHE = (client, bucket_name, prefix, region)
        return _S3_CLIENT_CACHE
    except Exception as e:
        logger.warning(f"[S3] Failed to create S3 client: {e}")
        return None, None, None, None


def _full_key(file_path: str, prefix: str) -> str:
    if prefix:
        return f"{prefix.rstrip('/')}/{file_path.lstrip('/')}"
    return file_path.lstrip("/")


def upload_image(file_path: str, image_data: bytes, content_type: str = "image/jpeg") -> str:
    """
    Upload bytes to S3 and return a URL. Object is private; downstream code
    should call get_signed_url() before handing the URL to a browser.
    """
    client, bucket_name, prefix, region = _get_s3_client()
    if not client or not bucket_name:
        raise Exception("S3 not configured - set S3_BUCKET_NAME and AWS credentials")

    key = _full_key(file_path, prefix)
    try:
        client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=image_data,
            ContentType=content_type,
        )
        # Return a stable virtual-host URL. It will 403 for anonymous clients;
        # use get_signed_url() to produce a temporary browser-accessible link.
        if region:
            url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{key}"
        else:
            url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
        logger.info("[S3 STORAGE] Upload successful: %s", key)
        return url
    except Exception as e:
        logger.error(f"[S3 STORAGE ERROR] Upload failed: {e}")
        raise Exception(f"Storage error: {e}")


def delete_object_key(key: str) -> None:
    """Best-effort delete of an object key under the configured prefix."""
    client, bucket_name, prefix, _ = _get_s3_client()
    if not client or not bucket_name or not key:
        return
    try:
        full_key = _full_key(key, prefix)
        client.delete_object(Bucket=bucket_name, Key=full_key)
        logger.info("[S3 STORAGE] Deleted key: %s", full_key)
    except Exception as e:
        logger.warning("[S3 STORAGE] Delete failed (non-fatal): %s — %s", key, e)


def download_image(image_url: str) -> Optional[bytes]:
    """Fetch image bytes from S3 by URL. Returns None if not S3 or fails."""
    parsed = _parse_s3_url(image_url)
    if not parsed:
        return None
    bucket_name, key = parsed
    client, _, _, _ = _get_s3_client()
    if client is None:
        try:
            import boto3
            from botocore.config import Config
            client = boto3.client("s3", config=Config(signature_version="s3v4"))
        except Exception as e:
            logger.error("[S3 STORAGE] boto3 unavailable: %s", e)
            return None
    try:
        obj = client.get_object(Bucket=bucket_name, Key=key)
        data = obj["Body"].read()
        if data:
            logger.info(
                "[S3 STORAGE] Downloaded %s bytes bucket=%s key=%s",
                len(data), bucket_name, key[:80],
            )
        return data
    except Exception as e:
        logger.error(
            "[S3 STORAGE ERROR] Download failed bucket=%s key=%s… : %s",
            bucket_name, key[:80] if key else "", e,
        )
        return None


def is_s3_configured() -> bool:
    """Legacy name kept for caller compatibility — returns True if S3 is configured."""
    client, bucket_name, _, _ = _get_s3_client()
    return client is not None and bool(bucket_name)


def get_signed_url(image_url: str, expires_in: int = 3600) -> Optional[str]:
    """
    Return a presigned GET URL for an S3 object so the browser can load it
    from a private bucket. If input is not an S3 URL, return it unchanged.
    """
    parsed = _parse_s3_url(image_url)
    if not parsed:
        return image_url
    bucket_name, key = parsed
    client, _, _, _ = _get_s3_client()
    if client is None:
        try:
            import boto3
            from botocore.config import Config
            client = boto3.client("s3", config=Config(signature_version="s3v4"))
        except Exception as e:
            logger.warning("[S3] boto3 unavailable, returning raw url: %s", e)
            return image_url
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": key},
            ExpiresIn=int(expires_in),
        )
    except Exception as e:
        logger.warning(f"[S3] Presign failed for {image_url[:80]}: {e}")
        return image_url
