"""
SageMaker inference for acne detection + hyperpigmentation segmentation +
early-aging analysis (Glogau / texture / wrinkles).

All endpoints accept `{"image": <base64>}` and return JSON. See
`SAGEMAKER_ACNE_ENDPOINT_NAME`, `SAGEMAKER_HYPERPIG_ENDPOINT_NAME` and
`SAGEMAKER_AGING_ENDPOINT_NAME` in settings.
"""
import asyncio
import base64
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CLIENT_CACHE = None


def _get_client():
    global _CLIENT_CACHE
    if _CLIENT_CACHE is not None:
        return _CLIENT_CACHE
    try:
        import boto3
        from botocore.config import Config
        from app.core.config import settings
        region = getattr(settings, "SAGEMAKER_REGION", "") or getattr(settings, "AWS_REGION", "") or "ap-south-1"
        _CLIENT_CACHE = boto3.client(
            "sagemaker-runtime",
            region_name=region,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}, read_timeout=60, connect_timeout=10),
        )
        return _CLIENT_CACHE
    except Exception as e:
        logger.warning(f"[SAGEMAKER] Failed to create client: {e}")
        return None


def _invoke_sync(endpoint_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    client = _get_client()
    if client is None:
        return {"success": False, "error": "SageMaker client unavailable"}
    try:
        r = client.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Accept="application/json",
            Body=json.dumps(payload),
        )
        body = r["Body"].read()
        data = json.loads(body)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"[SAGEMAKER] {endpoint_name} invoke failed: {e}")
        return {"success": False, "error": str(e)}


async def detect_acne(image_bytes: bytes) -> Dict[str, Any]:
    """Run the 6-class acne detection model. Returns {success, data|error}."""
    from app.core.config import settings
    name = getattr(settings, "SAGEMAKER_ACNE_ENDPOINT_NAME", "") or ""
    if not name:
        return {"success": False, "error": "SAGEMAKER_ACNE_ENDPOINT_NAME not configured"}
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return await asyncio.to_thread(_invoke_sync, name, {"image": b64})


async def detect_hyperpigmentation(image_bytes: bytes, preprocess: bool = True) -> Dict[str, Any]:
    """Run the hyperpigmentation segmentation model. Returns {success, data|error}."""
    from app.core.config import settings
    name = getattr(settings, "SAGEMAKER_HYPERPIG_ENDPOINT_NAME", "") or ""
    if not name:
        return {"success": False, "error": "SAGEMAKER_HYPERPIG_ENDPOINT_NAME not configured"}
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload: Dict[str, Any] = {"image": b64, "config": {"preprocess": preprocess}}
    return await asyncio.to_thread(_invoke_sync, name, payload)


async def detect_aging(image_bytes: bytes) -> Dict[str, Any]:
    """Run the early-aging model (Glogau classification, texture, wrinkle zones,
    composite aging score). Returns {success, data|error}."""
    from app.core.config import settings
    name = getattr(settings, "SAGEMAKER_AGING_ENDPOINT_NAME", "") or ""
    if not name:
        return {"success": False, "error": "SAGEMAKER_AGING_ENDPOINT_NAME not configured"}
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return await asyncio.to_thread(_invoke_sync, name, {"image": b64})


async def run_all(image_bytes: bytes) -> Dict[str, Any]:
    """Fire all detectors concurrently on the same image. Returns
    {acne, hyperpigmentation, aging}, each {success, data|error}."""
    acne, hyperpig, aging = await asyncio.gather(
        detect_acne(image_bytes),
        detect_hyperpigmentation(image_bytes),
        detect_aging(image_bytes),
        return_exceptions=False,
    )
    return {"acne": acne, "hyperpigmentation": hyperpig, "aging": aging}


# Backwards-compatible alias (previously ran only acne + hyperpigmentation).
run_both = run_all
