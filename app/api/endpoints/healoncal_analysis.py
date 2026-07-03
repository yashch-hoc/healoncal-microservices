"""
Healoncal Medical-Grade Analysis Endpoints

These are the ONLY analysis endpoints - focused exclusively on Healoncal medical-grade functionality.
All other analysis methods have been removed.
"""
import asyncio
import json
import logging
import io
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.healoncal_service import healoncal_service
from app.services.bedrock_recommendation_service import bedrock_recommendation_service as recommendation_service
from app.services.treatment_storage_service import treatment_storage_service
from app.services.metrics_service import metrics_service
from app.services.report_chat_service import report_chat_service
from app.services.s3_storage_service import get_signed_url as s3_presign, download_image as s3_download_image
from app.services import sagemaker_inference_service as sagemaker_inference

logger = logging.getLogger(__name__)
router = APIRouter()


def _round_metric(value: Any) -> Any:
    """Round numeric metrics to 2 decimal places (e.g. 32.01). Non-numbers returned as-is."""
    if value is None:
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    return value

class AnalysisRequest(BaseModel):
    user_id: str


class CompleteAnalysisRequest(BaseModel):
    user_id: str
    include_recommendations: Optional[bool] = True


class RecommendationRequest(BaseModel):
    session_id: str
    user_preferences: Optional[Dict[str, Any]] = None


class ChatOnReportRequest(BaseModel):
    session_id: str
    message: str


@router.post("/capture")
async def capture_image_healoncal(
    user_id: str = Form(...),
    angle: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Capture image for Healoncal analysis. Accepts multipart/form-data: user_id, angle, file (image).
    
    Behaviour:
    - Client only sends user_id + angle + file.
    - Server uses DB-level transaction/locking to either reuse the latest pending/ready
      session with < 3 images for that user, or create a new one, in a way that is safe
      across multiple workers.
    """
    try:
        logger.info(f"[HEALONCAL] Capturing {angle} image for user {user_id}")
        content_type = file.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Invalid file type: {content_type}. Expected image.")
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image file.")
        # Create or reuse session for this user (DB transaction ensures one pending session
        # with < 3 images per user even across multiple workers)
        session_id = await healoncal_service.create_analysis_session(user_id)
        result = await healoncal_service.capture_image(
            session_id=session_id,
            user_id=user_id,
            angle=angle,
            image_data=image_bytes,
        )
        if result["success"]:
            logger.info(f"[HEALONCAL SUCCESS] Captured {angle} - Quality: {result['quality_score']:.1f}")
            return {
                "success": True,
                "session_id": session_id,
                "image_id": result["image_id"],
                "quality_score": result["quality_score"],
                "face_detected": result["face_detected"],
                "message": f"Image captured successfully with {result['quality_score']:.1f}% quality",
            }
        if "Database connection not available" in result["error"]:
            raise HTTPException(status_code=503, detail="Database connection not available")
        if "Invalid image data" in result["error"]:
            raise HTTPException(status_code=400, detail="Invalid image data")
        raise HTTPException(status_code=500, detail=result["error"])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HEALONCAL ERROR] Capture failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze")
async def analyze_healoncal(request: AnalysisRequest):
    """
    Start Healoncal analysis for a user.
    This is the ONLY analysis endpoint.
    """
    try:
        logger.info(f"[HEALONCAL] Starting analysis for user {request.user_id}")
        
        # Find the latest session for this user
        try:
            db = healoncal_service._get_db()
            if not db.is_available():
                raise HTTPException(status_code=503, detail="Database connection not available")
            user_id_str = str(request.user_id) if request.user_id else None
            logger.info("[HEALONCAL] Finding latest session for user_id: %s", user_id_str)
            sessions_result = db.fetch_all(
                "SELECT * FROM healoncal_analysis_sessions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
                (user_id_str,),
            )
            if not sessions_result:
                return {
                    "success": False,
                    "message": f"No analysis sessions found for user '{user_id_str}'. Please capture images first using the /capture endpoint.",
                    "error": "No sessions found",
                    "user_id": user_id_str
                }
            
            session_id = sessions_result[0]["id"]
            found_user_id = sessions_result[0].get("user_id", "unknown")
            logger.info("[HEALONCAL] Found session %s for user_id: %s", session_id, found_user_id)
            images_result = db.fetch_all("SELECT * FROM healoncal_captured_images WHERE session_id = %s", (session_id,))
            if len(images_result) < 3:
                return {
                    "success": False,
                    "message": f"Need 3 images for complete analysis. Currently have {len(images_result)} images.",
                    "session_id": session_id,
                    "images_captured": len(images_result),
                    "required_images": 3,
                    "error": "Insufficient images for analysis"
                }
            
        except Exception as db_error:
            logger.warning(f"[HEALONCAL WARNING] Database query failed: {db_error}")
            # If database query fails, we can't proceed with analysis
            raise HTTPException(status_code=503, detail="Database connection failed. Please try again later.")
        
        # Start analysis
        analysis_result = await healoncal_service.analyze_session(session_id)
        
        if analysis_result["success"]:
            logger.info(f"[HEALONCAL SUCCESS] Analysis completed for session {session_id}")
            return {
                "success": True,
                "session_id": session_id,
                "processed_images": analysis_result["processed_images"],
                "message": "Healoncal analysis completed successfully"
            }
        else:
            # Return detailed error information instead of just raising exception
            error_detail = analysis_result.get("error", "Unknown error")
            error_details = analysis_result.get("error_details", {})
            failure_summary = analysis_result.get("failure_summary", {})
            
            # Determine appropriate status code
            status_code = 500
            if "No images found" in error_detail:
                status_code = 404
            elif "Database connection" in error_detail:
                status_code = 503
            
            # Return detailed error response
            error_response = {
                "success": False,
                "session_id": session_id,
                "error": error_detail,
                "error_details": error_details,
                "failure_summary": failure_summary,
                "processed_images": analysis_result.get("processed_images", 0),
                "total_images": analysis_result.get("total_images", 0)
            }
            
            raise HTTPException(status_code=status_code, detail=error_response)
            
    except Exception as e:
        logger.error(f"[HEALONCAL ERROR] Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/diagnostic/schema")
async def diagnostic_schema():
    """
    Diagnostic endpoint to check database schema and UUID conversion.
    Shows how TEXT user_id is converted to UUID for analysis_results table.
    """
    try:
        db = healoncal_service._get_db()
        if not db.is_available():
            return {"error": "Database connection not available"}
        diagnostics = {
            "success": True,
            "database": "MySQL",
            "schema_info": {
                "healoncal_analysis_sessions": {"user_id_type": "VARCHAR(255)", "status": "OK"},
                "healoncal_captured_images": {"user_id_type": "VARCHAR(255)", "status": "OK"},
                "healoncal_analysis_results": {"user_id_type": "VARCHAR(255)", "status": "OK"},
                "healoncal_combined_results": {"user_id_type": "VARCHAR(255)", "status": "OK"},
                "detected_skin_diseases": {"user_id_type": "VARCHAR(255)", "status": "OK"},
                "treatment_recommendations": {"user_id_type": "VARCHAR(255)", "status": "OK"},
            },
            "example": {},
        }
        try:
            sample = db.fetch_one("SELECT user_id FROM healoncal_analysis_sessions LIMIT 1")
            if sample:
                diagnostics["example"] = {"user_id": sample.get("user_id")}
        except Exception as e:
            diagnostics["example"] = {"error": str(e)}
        return diagnostics
    except Exception as e:
        return {"error": str(e)}


async def _read_image_upload(u: UploadFile, name: str = "image") -> bytes:
    ct = u.content_type or ""
    if not ct.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"Invalid file type for {name}: {ct}. Expected image.")
    data = await u.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"Empty file for {name}.")
    return data


@router.post("/detect/acne")
async def detect_acne_route(image: UploadFile = File(...)):
    """
    Run the SageMaker acne detection model on a single uploaded image.
    Returns the raw SageMaker response (boxes, scores, severity, annotated_image, ...).
    """
    image_bytes = await _read_image_upload(image, "image")
    result = await sagemaker_inference.detect_acne(image_bytes)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=f"Acne detection failed: {result.get('error')}")
    return result["data"]


@router.post("/detect/hyperpigmentation")
async def detect_hyperpigmentation_route(
    image: UploadFile = File(...),
    preprocess: str = Form("true"),
):
    """
    Run the SageMaker hyperpigmentation segmentation model on a single uploaded image.
    Returns the raw SageMaker response (mMASI, class_statistics, colored_mask_b64, ...).
    """
    image_bytes = await _read_image_upload(image, "image")
    do_preprocess = preprocess.lower() not in ("false", "0", "no")
    result = await sagemaker_inference.detect_hyperpigmentation(image_bytes, preprocess=do_preprocess)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=f"Hyperpigmentation detection failed: {result.get('error')}")
    return result["data"]


@router.post("/detect/aging")
async def detect_aging_route(image: UploadFile = File(...)):
    """
    Run the SageMaker early-aging model on a single uploaded image.
    Returns the raw SageMaker response (aging_analysis: glogau, texture,
    wrinkles, composite; plus mask_b64, disclaimer).
    """
    image_bytes = await _read_image_upload(image, "image")
    result = await sagemaker_inference.detect_aging(image_bytes)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=f"Aging detection failed: {result.get('error')}")
    return result["data"]


def _build_results_response(clean_session_id: str, results: Dict[str, Any]) -> Dict[str, Any]:
    """Build Healoncal results response from get_analysis_results payload. Shared by GET /results and GET /complete-results."""
    response = {
        "success": True,
        "session_id": clean_session_id,
        "session_info": results["session"],
        "healoncal_results": {
            "individual_analyses": [],
            "detected_diseases": results["detected_diseases"],
            "treatment_recommendations": results["treatment_recommendations"],
            "heatmap_visualizations": results.get("heatmap_results", []),
            "analysis_summary": {
                "total_images": len(results["individual_results"]),
                "analysis_status": results["session"]["status"],
                "processing_time": results["session"].get("processing_time_ms", 0)
            }
        }
    }
    for result in results["individual_results"]:
        response["healoncal_results"]["individual_analyses"].append({
            "angle": result["angle"],
            "captured_image_url": result.get("captured_image_url", ""),
            "healoncal_metrics": {
                "diagnostic_accuracy": _round_metric(result["diagnostic_accuracy"]),
                "biomarkers_analyzed": result["biomarkers_analyzed"],
                "image_quality_score": _round_metric(result["image_quality_score"]),
                "analysis_confidence": _round_metric(result["analysis_confidence"])
            },
            "skin_classification": {
                "skin_type": result["skin_type_classification"],
                "skin_tone": result["skin_tone_classification"],
                "estimated_age": result["skin_age_estimate"]
            },
            "skin_health_metrics": {
                "wrinkles_score": _round_metric(result.get("wrinkles_score")),
                "fine_lines_score": _round_metric(result.get("fine_lines_score")),
                "dark_circles_score": _round_metric(result.get("dark_circles_score")),
                "pores_score": _round_metric(result.get("pores_score")),
                "pigmentation_score": _round_metric(result.get("pigmentation_score")),
                "redness_score": _round_metric(result.get("redness_score")),
                "acne_score": _round_metric(result.get("acne_score")),
                "hydration_score": _round_metric(result.get("hydration_score")),
                "oiliness_score": _round_metric(result.get("oiliness_score")),
                "skin_firmness_score": _round_metric(result.get("skin_firmness_score")),
                "elasticity_score": _round_metric(result.get("elasticity_score")),
                "overall_skin_health_score": _round_metric(result.get("overall_skin_health_score"))
            },
            "recommendations": {
                "treatments": result["treatment_recommendations"],
                "routine": result["personalized_routine"]
            },
            "analysis_metadata": {
                "processing_time_ms": result["processing_time_ms"],
                "model_version": result["model_version"],
                "analysis_timestamp": result["analysis_timestamp"]
            }
        })
    return response



@router.get("/results/{session_id}")
async def get_healoncal_results(session_id: str):
    """
    Get Healoncal analysis results.
    This returns the exact Healoncal format results.
    """
    try:
        # Clean the session ID to remove any extra spaces
        clean_session_id = session_id.strip()
        logger.info(f"[HEALONCAL] Getting results for session {clean_session_id} (length: {len(clean_session_id)})")
        logger.info(f"[HEALONCAL] Raw session_id received: '{session_id}' (length: {len(session_id)})")
        
        results = await healoncal_service.get_analysis_results(clean_session_id)
        if results["success"]:
            logger.info(f"[HEALONCAL SUCCESS] Results retrieved for session {clean_session_id}")
            return _build_results_response(clean_session_id, results)
        else:
            # Handle different error types appropriately
            if "Session not found" in results["error"]:
                raise HTTPException(status_code=404, detail="Session not found")
            elif "Database connection not available" in results["error"]:
                raise HTTPException(status_code=503, detail="Database connection not available")
            else:
                raise HTTPException(status_code=500, detail=results["error"])
            
    except Exception as e:
        logger.error(f"[HEALONCAL ERROR] Failed to get results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{user_id}/latest")
async def get_latest_session(user_id: str):
    """Get the latest session for a user."""
    try:
        db = healoncal_service._get_db()
        if not db.is_available():
            return {"success": False, "message": "Database connection not available"}
        sessions_result = db.fetch_all(
            "SELECT * FROM healoncal_analysis_sessions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        if not sessions_result:
            return {"success": False, "message": "No sessions found"}
        session = sessions_result[0]
        images_result = db.fetch_all("SELECT * FROM healoncal_captured_images WHERE session_id = %s", (session["id"],))
        return {
            "success": True,
            "session": session,
            "images_captured": len(images_result),
            "images_required": 3,
        }
    except Exception as e:
        logger.error("[HEALONCAL ERROR] Failed to get latest session: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


async def _fetch_heatmaps_for_session(clean_session_id: str) -> Dict[str, Any]:
    """
    Fetch and organize heatmaps for a session (by angle).
    Shared by GET /heatmaps/{session_id} and GET /complete-results/{session_id}.
    """
    db = healoncal_service._get_db()
    if not db.is_available():
        raise HTTPException(status_code=503, detail="Database connection not available")
    heatmap_rows = db.fetch_all("SELECT * FROM disease_heatmaps WHERE session_id = %s", (clean_session_id,))
    images = {
        "front": {"individual_heatmaps": [], "combined_heatmap": None},
        "left": {"individual_heatmaps": [], "combined_heatmap": None},
        "right": {"individual_heatmaps": [], "combined_heatmap": None},
    }
    for heatmap in heatmap_rows:
        heatmap_url = heatmap.get("heatmap_url", "")
        angle = "front"
        if "_front_" in heatmap_url:
            angle = "front"
        elif "_left_" in heatmap_url:
            angle = "left"
        elif "_right_" in heatmap_url:
            angle = "right"
        else:
            if "combined_heatmap" in heatmap_url:
                if "combined_heatmap_front_" in heatmap_url:
                    angle = "front"
                elif "combined_heatmap_left_" in heatmap_url:
                    angle = "left"
                elif "combined_heatmap_right_" in heatmap_url:
                    angle = "right"
            else:
                if "front" in heatmap_url.lower():
                    angle = "front"
                elif "left" in heatmap_url.lower():
                    angle = "left"
                elif "right" in heatmap_url.lower():
                    angle = "right"

        # Colors column is stored as JSON in MySQL; when fetched it may be a JSON string or a dict.
        raw_colors = heatmap.get("colors")
        if isinstance(raw_colors, str):
            try:
                colors = json.loads(raw_colors) or {}
            except Exception:
                colors = {}
        elif isinstance(raw_colors, dict):
            colors = raw_colors or {}
        else:
            colors = {}

        raw_url = heatmap.get("heatmap_url", "")
        # Use signed URL so browser can load images from private S3 bucket
        display_url = s3_presign(raw_url) if raw_url else ""
        heatmap_data = {
            "disease_name": heatmap["disease_name"],
            "category": heatmap.get("category", "cosmetic"),
            "confidence": float(heatmap.get("confidence", 0)),
            "severity": heatmap.get("severity", "mild"),
            "url": display_url,
            "index": heatmap.get("heatmap_index", 0),
            "colors": {
                "alpha": colors.get("alpha", 0.7),
                "primary": colors.get("primary", "#9370DB"),
                "secondary": colors.get("secondary", "#800080"),
                "pinpoint": colors.get("pinpoint"),
            },
            "type": "individual" if heatmap.get("heatmap_type") != "combined" else "combined"
        }
        if heatmap.get("heatmap_type") == "combined":
            images[angle]["combined_heatmap"] = heatmap_data
        else:
            images[angle]["individual_heatmaps"].append(heatmap_data)
    for angle in images:
        images[angle]["individual_heatmaps"].sort(key=lambda x: x.get("index", 0))
    total_heatmaps = sum(
        len(images[a]["individual_heatmaps"]) + (1 if images[a]["combined_heatmap"] else 0) for a in images
    )
    angles_available = [a for a in ("front", "left", "right") if images[a]["individual_heatmaps"] or images[a]["combined_heatmap"]]
    return {
        "success": True,
        "session_id": clean_session_id,
        "images": images,
        "total_heatmaps": total_heatmaps,
        "angles_available": angles_available,
        "message": "No heatmaps found for this session" if total_heatmaps == 0 else None
    }


@router.get("/heatmaps/{session_id}")
async def get_heatmap_visualizations(session_id: str):
    """
    Get ALL heat map visualizations for a session.
    Automatically fetches and returns all heatmaps for all images (front, left, right)
    organized by image angle with individual and combined heatmaps.

    Additionally, in parallel, we generate Gemini-powered product recommendations
    based on the same session's analysis results so callers get both payloads
    in a single round trip while their latencies overlap.
    """
    try:
        clean_session_id = session_id.strip()
        logger.info(f"[HEATMAP] Getting heatmaps for session {clean_session_id}")
        # Run heatmap fetch and Gemini recommendations in parallel so their
        # latencies overlap instead of being sequential.
        async def heatmaps_task():
            return await _fetch_heatmaps_for_session(clean_session_id)

        async def gemini_task():
            try:
                # We need full analysis results to build the Gemini payload
                analysis_results = await healoncal_service.get_analysis_results(clean_session_id)
                if not analysis_results.get("success"):
                    logger.error(
                        "[HEATMAP+GEMINI] Analysis results not available for session %s: %s",
                        clean_session_id,
                        analysis_results.get("error", "unknown error"),
                    )
                    return {"success": False, "error": "Analysis results not available"}

                formatted_results = {
                    "session_id": clean_session_id,
                    "healoncal_results": {
                        "individual_analyses": analysis_results.get("individual_results", []),
                        "combined_analysis": analysis_results.get("combined_results"),
                    },
                }

                return await recommendation_service.generate_product_recommendations(
                    formatted_results,
                    user_preferences=None,
                )
            except Exception as rec_err:
                logger.error(f"[HEATMAP+GEMINI] Gemini recommendations failed: {rec_err}")
                return {"success": False, "error": str(rec_err)}

        heatmaps_payload, recommendations = await asyncio.gather(
            heatmaps_task(),
            gemini_task(),
        )

        # Preserve existing heatmap response shape and add recommendations.
        if isinstance(heatmaps_payload, dict):
            heatmaps_payload["recommendations"] = recommendations
            return heatmaps_payload
        return {
            "success": False,
            "error": "Unexpected heatmap payload format",
            "raw_heatmaps": heatmaps_payload,
            "recommendations": recommendations,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HEATMAP ERROR] Failed to get heatmaps: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get heatmaps: {str(e)}")


@router.post("/submit-and-analyze")
async def submit_and_analyze(
    user_id: str = Form(...),
    image_front: UploadFile = File(...),
    image_left: UploadFile = File(...),
    image_right: UploadFile = File(...),
    include_recommendations: str = Form("true"),
):
    """
    Single-call flow: send 3 images (multipart) + user_id → backend captures all 3, runs analysis,
    and returns standard Healoncal results plus heatmaps (no combined report wrapper).
    Accepts multipart/form-data only (no base64).
    """
    try:
        user_id_str = (user_id or "").strip()
        if not user_id_str:
            raise HTTPException(status_code=400, detail="user_id is required")
        include_recs = include_recommendations.lower() not in ("false", "0", "no")
        logger.info(f"[HEALONCAL SUBMIT-AND-ANALYZE] Starting for user_id: {user_id_str}")

        async def read_and_validate(u: UploadFile, name: str) -> bytes:
            ct = u.content_type or ""
            if not ct.startswith("image/"):
                raise HTTPException(status_code=400, detail=f"Invalid file type for {name}: {ct}. Expected image.")
            data = await u.read()
            if not data:
                raise HTTPException(status_code=400, detail=f"Empty file for {name}.")
            return data

        image_front_bytes, image_left_bytes, image_right_bytes = await asyncio.gather(
            read_and_validate(image_front, "image_front"),
            read_and_validate(image_left, "image_left"),
            read_and_validate(image_right, "image_right"),
        )

        # Kick off SageMaker detections (acne + hyperpigmentation) per angle
        # immediately so they run concurrently with capture + analysis.
        detection_tasks = {
            "front": asyncio.create_task(sagemaker_inference.run_both(image_front_bytes)),
            "left": asyncio.create_task(sagemaker_inference.run_both(image_left_bytes)),
            "right": asyncio.create_task(sagemaker_inference.run_both(image_right_bytes)),
        }

        # Always create a fresh session for this combined submit, then attach all 3 images
        session_id = await healoncal_service.create_analysis_session(user_id_str)

        capture_specs = [
            ("front", image_front_bytes),
            ("left", image_left_bytes),
            ("right", image_right_bytes),
        ]
        capture_results = await asyncio.gather(
            *[
                healoncal_service.capture_image(
                    session_id=session_id,
                    user_id=user_id_str,
                    angle=angle,
                    image_data=image_bytes,
                )
                for angle, image_bytes in capture_specs
            ],
            return_exceptions=True,
        )
        for (angle, _), result in zip(capture_specs, capture_results):
            if isinstance(result, Exception):
                raise HTTPException(status_code=500, detail=f"Capture failed for {angle}: {result}")
            if not result.get("success"):
                err = result.get("error", "Unknown error")
                if "Database connection" in err:
                    raise HTTPException(status_code=503, detail="Database connection not available")
                if "Invalid image" in err:
                    raise HTTPException(status_code=400, detail=f"Capture failed for {angle}: {err}")
                raise HTTPException(status_code=500, detail=f"Capture failed for {angle}: {err}")

        # Run analysis with limited heatmap generation.
        # Heatmaps are generated only for the top 2–3 diseases per angle (ranked by
        # severity and confidence) to keep submit-and-analyze latency within target.
        analysis_result = await healoncal_service.analyze_session(session_id, generate_heatmaps=True)
        if not analysis_result["success"]:
            error_detail = analysis_result.get("error", "Unknown error")
            status_code = 500
            if "No images found" in error_detail:
                status_code = 404
            elif "Database connection" in error_detail:
                status_code = 503
            raise HTTPException(
                status_code=status_code,
                detail={
                    "success": False,
                    "session_id": session_id,
                    "error": error_detail,
                    "error_details": analysis_result.get("error_details", {}),
                    "failure_summary": analysis_result.get("failure_summary", {}),
                    "processed_images": analysis_result.get("processed_images", 0),
                    "total_images": analysis_result.get("total_images", 0),
                },
            )

        logger.info(f"[HEALONCAL SUBMIT-AND-ANALYZE] Analysis done for session {session_id}, fetching results and limited heatmaps")
        clean_session_id = session_id.strip()
        # Fetch standard results
        results = await healoncal_service.get_analysis_results(clean_session_id)
        if not results.get("success"):
            if "Session not found" in results.get("error", ""):
                raise HTTPException(status_code=404, detail="Session not found")
            if "Database connection" in results.get("error", ""):
                raise HTTPException(status_code=503, detail="Database connection not available")
            raise HTTPException(status_code=500, detail=results.get("error", "Failed to get results"))

        response_results = _build_results_response(clean_session_id, results)

        # Build the payload used for Gemini recommendations once, then fetch heatmaps
        # and call Gemini in parallel so their latencies overlap.
        formatted_results = {
            "session_id": clean_session_id,
            "healoncal_results": {
                "individual_analyses": results.get("individual_results", []),
                "combined_analysis": None,
            },
        }

        async def fetch_heatmaps_task():
            return await _fetch_heatmaps_for_session(clean_session_id)

        async def gemini_task():
            try:
                return await recommendation_service.generate_product_recommendations(
                    formatted_results,
                    user_preferences=None,
                )
            except Exception as rec_err:
                logger.error(f"[HEALONCAL SUBMIT-AND-ANALYZE] Gemini recommendations failed: {rec_err}")
                return {"success": False, "error": str(rec_err)}

        heatmaps_payload, recommendations, det_front, det_left, det_right = await asyncio.gather(
            fetch_heatmaps_task(),
            gemini_task(),
            detection_tasks["front"],
            detection_tasks["left"],
            detection_tasks["right"],
        )

        return {
            "success": True,
            "session_id": clean_session_id,
            "results": response_results,
            "heatmaps": heatmaps_payload,
            "recommendations": recommendations,
            "detections": {
                "front": det_front,
                "left": det_left,
                "right": det_right,
            },
            "analysis": {
                "success": True,
                "processed_images": analysis_result.get("processed_images", 0),
                "message": "Submit and analyze completed successfully",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HEALONCAL SUBMIT-AND-ANALYZE] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _sse(event: str, data: Any) -> bytes:
    """Format a single Server-Sent Events frame."""
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@router.post("/submit-and-analyze/stream")
async def submit_and_analyze_stream(
    user_id: str = Form(...),
    image_front: UploadFile = File(...),
    image_left: UploadFile = File(...),
    image_right: UploadFile = File(...),
    include_recommendations: str = Form("true"),
):
    """
    Server-Sent Events version of /submit-and-analyze. Emits progress as each
    phase finishes so the UI can render results before heatmaps/Gemini return.

    Event sequence:
      progress   {stage: "validating"|"captured"|"analyzing"|"heatmaps_started"|...}
      results    {results: <response_results>}   (metrics, before heatmaps/recs)
      heatmaps   {heatmaps: <heatmaps_payload>}
      recommendations {recommendations: <recs>}
      done       {session_id, processed_images}
      error      {error: str}   (fatal)
    """
    user_id_str = (user_id or "").strip()
    if not user_id_str:
        raise HTTPException(status_code=400, detail="user_id is required")
    include_recs = include_recommendations.lower() not in ("false", "0", "no")

    # Read bodies outside the generator so FastAPI's UploadFile is available.
    async def read_and_validate(u: UploadFile, name: str) -> bytes:
        ct = u.content_type or ""
        if not ct.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Invalid file type for {name}: {ct}. Expected image.")
        data = await u.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"Empty file for {name}.")
        return data

    image_front_bytes, image_left_bytes, image_right_bytes = await asyncio.gather(
        read_and_validate(image_front, "image_front"),
        read_and_validate(image_left, "image_left"),
        read_and_validate(image_right, "image_right"),
    )

    async def event_stream():
        # Fire SageMaker detections in parallel with capture + analysis so they
        # arrive with the earliest results rather than serialising latency.
        detection_tasks: Dict[str, asyncio.Task] = {
            "front": asyncio.create_task(sagemaker_inference.run_both(image_front_bytes)),
            "left": asyncio.create_task(sagemaker_inference.run_both(image_left_bytes)),
            "right": asyncio.create_task(sagemaker_inference.run_both(image_right_bytes)),
        }
        detections_by_angle: Dict[str, Dict[str, Any]] = {}
        try:
            yield _sse("progress", {"stage": "validating"})

            session_id = await healoncal_service.create_analysis_session(user_id_str)
            yield _sse("progress", {"stage": "session_created", "session_id": session_id})

            # Parallel S3 captures.
            capture_specs = [
                ("front", image_front_bytes),
                ("left", image_left_bytes),
                ("right", image_right_bytes),
            ]
            capture_results = await asyncio.gather(
                *[
                    healoncal_service.capture_image(
                        session_id=session_id,
                        user_id=user_id_str,
                        angle=angle,
                        image_data=image_bytes,
                    )
                    for angle, image_bytes in capture_specs
                ],
                return_exceptions=True,
            )
            for (angle, _), result in zip(capture_specs, capture_results):
                if isinstance(result, Exception) or not (isinstance(result, dict) and result.get("success")):
                    err = (
                        str(result)
                        if isinstance(result, Exception)
                        else result.get("error", "Unknown error")
                    )
                    yield _sse("error", {"error": f"Capture failed for {angle}: {err}"})
                    return
            yield _sse("progress", {"stage": "captured"})

            # Fast analysis-only step (no heatmaps yet). Heatmaps are driven
            # per-angle below so the UI gets `results` in ~5s instead of ~25s.
            yield _sse("progress", {"stage": "analyzing"})
            analysis_result = await healoncal_service.analyze_session(
                session_id, generate_heatmaps=False
            )
            if not analysis_result.get("success"):
                yield _sse("error", {"error": analysis_result.get("error", "Analysis failed")})
                return

            clean_session_id = session_id.strip()
            results = await healoncal_service.get_analysis_results(clean_session_id)
            if not results.get("success"):
                yield _sse("error", {"error": results.get("error", "Results fetch failed")})
                return
            response_results = _build_results_response(clean_session_id, results)
            yield _sse("results", {"session_id": clean_session_id, "results": response_results})

            # Build angle → detected_diseases map (DB shape → in-memory shape
            # expected by heatmap service).
            analysis_by_arid: Dict[str, str] = {}
            for r in results.get("individual_results", []):
                arid = r.get("id")
                angle = (r.get("angle") or "").lower()
                if arid and angle:
                    analysis_by_arid[str(arid)] = angle

            diseases_by_angle: Dict[str, list] = {"front": [], "left": [], "right": []}
            for d in results.get("detected_diseases", []):
                arid = str(d.get("analysis_result_id") or "")
                angle = analysis_by_arid.get(arid)
                if not angle:
                    continue
                diseases_by_angle.setdefault(angle, []).append({
                    "name": d.get("disease_name") or d.get("name") or "Unknown",
                    "category": d.get("disease_category") or d.get("category") or "unknown",
                    "confidence": float(d.get("confidence_score") or d.get("confidence") or 0.0),
                    "severity": d.get("severity_level") or d.get("severity") or "mild",
                    "affected_area": d.get("affected_area") or "face",
                    "requires_medical_attention": bool(d.get("requires_medical_attention")),
                })

            session_user_id = user_id_str

            async def gen_and_fetch_angle(angle: str):
                diseases = diseases_by_angle.get(angle) or []
                if diseases:
                    try:
                        await healoncal_service._generate_heatmaps_parallel(
                            clean_session_id, session_user_id, diseases, angle
                        )
                    except Exception as ge:
                        logger.error(f"[HEALONCAL STREAM] Heatmap gen failed for {angle}: {ge}")
                # Always fetch whatever is there (even if zero).
                full = await _fetch_heatmaps_for_session(clean_session_id)
                images = (full or {}).get("images", {})
                return angle, {
                    "session_id": clean_session_id,
                    "angle": angle,
                    angle: images.get(angle, {"individual_heatmaps": [], "combined_heatmap": None}),
                }

            formatted_results = {
                "session_id": clean_session_id,
                "healoncal_results": {
                    "individual_analyses": results.get("individual_results", []),
                    "combined_analysis": None,
                },
            }

            if include_recs:
                async def _gemini():
                    try:
                        return await recommendation_service.generate_product_recommendations(
                            formatted_results, user_preferences=None
                        )
                    except Exception as rec_err:
                        logger.error(f"[HEALONCAL STREAM] Gemini failed: {rec_err}")
                        return {"success": False, "error": str(rec_err)}
                gemini_task = asyncio.create_task(_gemini())
            else:
                gemini_task = None

            pending: Dict[asyncio.Task, str] = {
                asyncio.create_task(gen_and_fetch_angle("front")): "heatmap_angle",
                asyncio.create_task(gen_and_fetch_angle("left")): "heatmap_angle",
                asyncio.create_task(gen_and_fetch_angle("right")): "heatmap_angle",
            }
            if gemini_task:
                pending[gemini_task] = "recommendations"
            # Add SageMaker detection tasks — they'll finish whenever ready.
            for angle, t in detection_tasks.items():
                pending[t] = f"detection:{angle}"

            final_heatmaps = {
                "success": True,
                "session_id": clean_session_id,
                "images": {
                    "front": {"individual_heatmaps": [], "combined_heatmap": None},
                    "left": {"individual_heatmaps": [], "combined_heatmap": None},
                    "right": {"individual_heatmaps": [], "combined_heatmap": None},
                },
            }

            while pending:
                done, _ = await asyncio.wait(
                    pending.keys(), return_when=asyncio.FIRST_COMPLETED
                )
                for t in done:
                    kind = pending.pop(t)
                    try:
                        value = t.result()
                    except Exception as te:
                        logger.error(f"[HEALONCAL STREAM] task {kind} error: {te}")
                        value = None

                    if kind == "heatmap_angle" and isinstance(value, tuple):
                        angle, payload = value
                        final_heatmaps["images"][angle] = payload.get(angle) or final_heatmaps["images"][angle]
                        yield _sse("heatmap_angle", payload)
                    elif kind == "recommendations":
                        yield _sse("recommendations", {"recommendations": value})
                    elif isinstance(kind, str) and kind.startswith("detection:"):
                        angle = kind.split(":", 1)[1]
                        detections_by_angle[angle] = value or {
                            "acne": {"success": False, "error": "task failed"},
                            "hyperpigmentation": {"success": False, "error": "task failed"},
                        }
                        yield _sse("detection_angle", {"angle": angle, "detection": detections_by_angle[angle]})

            # Emit a consolidated `heatmaps` event too so clients that only know
            # the v1 shape still get the full payload without a refetch.
            final_heatmaps["total_heatmaps"] = sum(
                len(a["individual_heatmaps"]) + (1 if a["combined_heatmap"] else 0)
                for a in final_heatmaps["images"].values()
            )
            yield _sse("heatmaps", {"heatmaps": final_heatmaps})

            # Consolidated detections event for clients that only see the final payload.
            yield _sse("detections", {"detections": detections_by_angle})

            yield _sse("done", {
                "session_id": clean_session_id,
                "processed_images": analysis_result.get("processed_images", 0),
            })
        except HTTPException as he:
            yield _sse("error", {"error": he.detail if isinstance(he.detail, str) else str(he.detail)})
        except Exception as e:
            logger.error(f"[HEALONCAL STREAM] Failed: {e}")
            yield _sse("error", {"error": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


def _build_report_context_for_chat(results: Dict[str, Any]) -> str:
    """
    Build a comprehensive string context from get_analysis_results for RAG chat.
    Includes all report data: combined analysis, individual results, skin metrics, 
    diseases, and treatment recommendations with skin routine.
    """
    combined_data = {}  # combined results removed; keep structure for backward compatibility
    
    # Build comprehensive individual results with all biomarker data
    individual_results_detail = []
    for r in (results.get("individual_results") or []):
        individual_results_detail.append({
            "angle": r.get("angle"),
            "diagnostics": {
                "diagnostic_accuracy": r.get("diagnostic_accuracy"),
                "biomarkers_analyzed": r.get("biomarkers_analyzed"),
                "image_quality_score": r.get("image_quality_score"),
                "analysis_confidence": r.get("analysis_confidence"),
            },
            "skin_classification": {
                "skin_type": r.get("skin_type_classification"),
                "skin_tone": r.get("skin_tone_classification"),
                "estimated_skin_age": r.get("skin_age_estimate"),
            },
            "skin_health_metrics": {
                "wrinkles_score": r.get("wrinkles_score"),
                "fine_lines_score": r.get("fine_lines_score"),
                "dark_circles_score": r.get("dark_circles_score"),
                "eye_bags_score": r.get("eye_bags_score"),
                "crows_feet_score": r.get("crows_feet_score"),
                "pores_score": r.get("pores_score"),
                "blackheads_score": r.get("blackheads_score"),
                "pigmentation_score": r.get("pigmentation_score"),
                "dark_spots_score": r.get("dark_spots_score"),
                "age_spots_score": r.get("age_spots_score"),
                "melasma_score": r.get("melasma_score"),
                "acne_score": r.get("acne_score"),
                "rosacea_score": r.get("rosacea_score"),
                "redness_score": r.get("redness_score"),
                "inflammation_score": r.get("inflammation_score"),
                "hydration_score": r.get("hydration_score"),
                "oiliness_score": r.get("oiliness_score"),
                "skin_texture_score": r.get("skin_texture_score"),
                "elasticity_score": r.get("elasticity_score"),
                "firmness_score": r.get("firmness_score"),
                "skin_firmness_score": r.get("skin_firmness_score"),
                "radiance_score": r.get("radiance_score"),
                "uv_damage_score": r.get("uv_damage_score"),
                "sensitivity_score": r.get("sensitivity_score"),
                "overall_skin_health_score": r.get("overall_skin_health_score"),
            },
            "advanced_analysis": {
                "collagen_density": r.get("collagen_density"),
                "sebum_production": r.get("sebum_production"),
                "skin_barrier_function": r.get("skin_barrier_function"),
                "moisture_retention": r.get("moisture_retention"),
            },
            "personalized_routine": r.get("personalized_routine", []),
            "treatment_recommendations": r.get("treatment_recommendations", []),
        })
    
    # Build detected diseases with medical details
    diseases_detail = []
    for disease in (results.get("detected_diseases") or []):
        diseases_detail.append({
            "disease_name": disease.get("disease_name"),
            "category": disease.get("disease_category"),
            "confidence_score": disease.get("confidence_score"),
            "severity_level": disease.get("severity_level"),
            "affected_area": disease.get("affected_area"),
            "requires_medical_attention": disease.get("requires_medical_attention"),
            "recommended_specialist": disease.get("recommended_specialist"),
            "urgency_level": disease.get("urgency_level"),
            "symptoms_noted": disease.get("symptoms_noted", []),
            "risk_factors": disease.get("risk_factors", []),
            "treatment_recommended": disease.get("treatment_recommended", []),
            "clinical_notes": disease.get("clinical_notes"),
        })
    
    # Build treatment recommendations with full details
    treatment_recs_detail = []
    has_treatment_data = False
    
    for rec in (results.get("treatment_recommendations") or []):
        has_treatment_data = True
        # Extract routine steps - can be dict or string
        routine_steps = rec.get("routine_steps", {})
        if isinstance(routine_steps, str):
            try:
                routine_steps = json.loads(routine_steps)
            except:
                routine_steps = {"morning": routine_steps, "evening": []}
        elif not isinstance(routine_steps, dict):
            routine_steps = {}
            
        # Extract products - can be list or JSON string
        products = rec.get("products", [])
        if isinstance(products, str):
            try:
                products = json.loads(products)
            except:
                products = []
        
        # Extract key_advice - can be list or string
        key_advice = rec.get("key_advice", [])
        if isinstance(key_advice, str):
            try:
                key_advice = json.loads(key_advice)
            except:
                key_advice = [key_advice] if key_advice else []
        
        treatment_recs_detail.append({
            "recommendation_id": rec.get("id"),
            "ai_model": rec.get("ai_model_version", "gemini-2.5-flash"),
            "ai_confidence": rec.get("ai_confidence", 0),
            "routine_type": rec.get("routine_type", "both"),
            "products": products if products else [],
            "routine_steps": routine_steps,
            "morning_routine": routine_steps.get("morning", []) if routine_steps else [],
            "evening_routine": routine_steps.get("evening", []) if routine_steps else [],
            "key_advice": key_advice if key_advice else [],
            "ingredients_to_avoid": rec.get("ingredients_to_avoid", []),
            "ingredients_to_seek": rec.get("ingredients_to_seek", []),
            "expected_timeline": rec.get("expected_timeline", "4-6 weeks"),
            "primary_skin_concerns": rec.get("primary_skin_concerns", []),
            "skin_type": rec.get("skin_type"),
            "skin_tone": rec.get("skin_tone"),
            "budget_range": rec.get("budget_range"),
            "medical_flags": rec.get("medical_flags", []),
            "dermatologist_referral_needed": rec.get("dermatologist_referral_needed", False),
            "urgency_level": rec.get("urgency_level", "routine"),
            "user_feedback": rec.get("user_feedback", {}),
        })
    
    # Comprehensive report context
    out = {
        "report_header": {
            "session_id": results.get("session", {}).get("id"),
            "user_id": results.get("session", {}).get("user_id"),
            "analysis_type": results.get("session", {}).get("analysis_type"),
            "status": results.get("session", {}).get("status"),
            "created_at": results.get("session", {}).get("created_at"),
            "completed_at": results.get("session", {}).get("completed_at"),
            "total_images_analyzed": results.get("session", {}).get("total_images"),
        },
        "combined_analysis_results": None,
        "individual_analyses": individual_results_detail,
        "detected_diseases": diseases_detail,
        "treatment_recommendations_and_skincare_routine": treatment_recs_detail,
        "heatmap_visualizations": [
            {
                "disease_name": h.get("disease_name"),
                "category": h.get("category"),
                "confidence": h.get("confidence"),
                "severity": h.get("severity"),
                "heatmap_type": h.get("heatmap_type"),
                "heatmap_url": h.get("heatmap_url"),
            }
            for h in (results.get("heatmap_results") or [])
        ],
    }
    return json.dumps(out, indent=2, default=str)


@router.post("/chat-on-report")
async def chat_on_report(request: ChatOnReportRequest):
    """
    RAG-style chat on the user's analysis report. Max 5 user prompts per session.
    Requires a completed analysis for the given session_id.
    """
    try:
        session_id = (request.session_id or "").strip()
        message = (request.message or "").strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        if not message:
            raise HTTPException(status_code=400, detail="message is required")
        results = await healoncal_service.get_analysis_results(session_id)
        if not results.get("success"):
            if "Session not found" in results.get("error", ""):
                raise HTTPException(status_code=404, detail="Session not found")
            if "Database connection" in results.get("error", ""):
                raise HTTPException(status_code=503, detail="Database connection not available")
            raise HTTPException(status_code=500, detail=results.get("error", "Failed to get results"))
        if results.get("session", {}).get("status") != "completed":
            raise HTTPException(
                status_code=400,
                detail="Analysis not completed for this session. Run analysis first, then chat on the report.",
            )
        report_context = _build_report_context_for_chat(results)
        response = report_chat_service.chat(session_id, message, report_context)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HEALONCAL CHAT-ON-REPORT] Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def healoncal_health_check():
    """Health check for Healoncal service."""
    try:
        db = healoncal_service._get_db()
        if not db.is_available():
            return {
                "status": "unhealthy",
                "service": "Healoncal Medical-Grade Analysis",
                "version": "2.0",
                "database": "disconnected",
                "timestamp": datetime.now().isoformat(),
            }
        db.fetch_one("SELECT id FROM healoncal_analysis_sessions LIMIT 1")
        
        return {
            "status": "healthy",
            "service": "Healoncal Medical-Grade Analysis",
            "version": "2.0",
            "database": "connected",
            "features": [
                "98% Diagnostic Accuracy",
                "150+ Facial Biomarkers",
                "20+ Skin Health Metrics",
                "LIQA Real-time Quality Assurance",
                "Clinical Classifications",
                "Personalized Recommendations",
                "AI-Powered Product Recommendations"
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "Healoncal Medical-Grade Analysis",
            "version": "2.0",
            "database": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/metrics")
async def get_metrics():
    """Get performance metrics for the API."""
    try:
        report = metrics_service.generate_report()
        return report
    except Exception as e:
        logger.error(f"[METRICS ERROR] Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@router.get("/metrics/endpoint/{endpoint:path}")
async def get_endpoint_metrics(endpoint: str):
    """Get metrics for a specific endpoint."""
    try:
        metrics = metrics_service.get_endpoint_metrics(endpoint)
        return metrics
    except Exception as e:
        logger.error(f"[METRICS ERROR] Failed to get endpoint metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get endpoint metrics: {str(e)}")

@router.get("/metrics/system")
async def get_system_metrics():
    """Get system-wide metrics."""
    try:
        from app.services.metrics_service import SystemMetrics
        metrics = metrics_service.get_system_metrics()
        return {
            "system_metrics": {
                "total_requests": metrics.total_requests,
                "total_errors": metrics.total_errors,
                "avg_response_time_ms": metrics.avg_response_time_ms,
                "requests_per_second": metrics.requests_per_second,
                "error_rate": metrics.error_rate,
                "active_sessions": metrics.active_sessions,
                "database_query_count": metrics.database_query_count,
                "database_avg_query_time_ms": metrics.database_avg_query_time_ms,
                "memory_usage_mb": metrics.memory_usage_mb,
                "cpu_usage_percent": metrics.cpu_usage_percent
            },
            "database_metrics": metrics_service.get_database_metrics(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"[METRICS ERROR] Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system metrics: {str(e)}")

@router.post("/metrics/export")
async def export_metrics():
    """Export metrics to file."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"metrics_export_{timestamp}.json"
        metrics_service.export_metrics(filepath)
        return {
            "success": True,
            "filepath": filepath,
            "message": "Metrics exported successfully"
        }
    except Exception as e:
        logger.error(f"[METRICS ERROR] Failed to export metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export metrics: {str(e)}")

@router.post("/recommendations")
async def get_product_recommendations(request: RecommendationRequest):
    """
    Get AI-powered product recommendations based on Healoncal analysis results.
    Uses Gemini AI to provide personalized skincare recommendations.
    """
    try:
        # Clean the session ID to remove any extra spaces
        clean_session_id = request.session_id.strip()
        
        # Validate session_id format (should be a UUID)
        import re
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, clean_session_id, re.IGNORECASE):
            logger.error(f"[GEMINI ERROR] Invalid session_id format: {clean_session_id}")
            raise HTTPException(status_code=400, detail="Invalid session ID format")
        
        logger.info(f"[GEMINI] Generating recommendations for session {clean_session_id}")
        
        # Get the analysis results first
        analysis_results = await healoncal_service.get_analysis_results(clean_session_id)
        
        if not analysis_results["success"]:
            raise HTTPException(status_code=404, detail="Analysis results not found")
        
        # Check if analysis is complete
        session_status = analysis_results["session"]["status"]
        if session_status != "completed":
            raise HTTPException(
                status_code=400, 
                detail=f"Analysis not complete. Current status: {session_status}"
            )
        
        # Check if we have valid analysis results
        individual_results = analysis_results.get("individual_results", [])
        if not individual_results:
            raise HTTPException(
                status_code=400,
                detail="No analysis results found. Please complete the analysis first."
            )
        
        # Format results for recommendation service
        formatted_results = {
            "session_id": request.session_id,
            "healoncal_results": {
                "individual_analyses": analysis_results["individual_results"],
                "combined_analysis": None
            }
        }
        
        # Generate recommendations using Gemini AI
        recommendations = await recommendation_service.generate_product_recommendations(
            formatted_results, 
            request.user_preferences
        )
        
        # Prepare analysis summary with safe access
        combined_results = analysis_results.get("combined_results", {})
        analysis_summary = {
            "total_images_analyzed": len(analysis_results.get("individual_results", [])),
            "overall_accuracy": combined_results.get("overall_diagnostic_accuracy") if combined_results else None,
            "analysis_date": analysis_results["session"]["created_at"],
            "skin_type": combined_results.get("final_skin_type_classification", "Normal") if combined_results else "Normal",
            "skin_tone": combined_results.get("final_skin_tone_classification", "Medium") if combined_results else "Medium"
        }
        
        # Store recommendations in database
        try:
            logger.info(f"[RECOMMENDATIONS] Attempting to store recommendations for session {clean_session_id}")
            logger.info(f"[RECOMMENDATIONS] User ID: {analysis_results['session']['user_id']}")
            logger.info(f"[RECOMMENDATIONS] Recommendations data: {recommendations}")
            
            recommendation_id = await treatment_storage_service.store_treatment_recommendations(
                session_id=clean_session_id,
                user_id=analysis_results["session"]["user_id"],
                recommendations=recommendations,
                analysis_summary=analysis_summary,
                user_preferences=request.user_preferences
            )
            logger.info(f"[TREATMENT STORAGE SUCCESS] Stored recommendations with ID: {recommendation_id}")
        except Exception as storage_error:
            logger.error(f"[TREATMENT STORAGE ERROR] Failed to store recommendations: {storage_error}")
            logger.error(f"[TREATMENT STORAGE ERROR] Session ID: {clean_session_id}")
            logger.error(f"[TREATMENT STORAGE ERROR] User ID: {analysis_results['session']['user_id']}")
            # Don't raise the error, just log it so the recommendations can still be returned
        
        logger.info(f"[GEMINI SUCCESS] Generated and stored recommendations for session {clean_session_id}")
        
        return {
            "success": True,
            "session_id": clean_session_id,
            "recommendations": recommendations,
            "analysis_summary": analysis_summary,
            "storage_status": "stored" if 'recommendation_id' in locals() else "storage_failed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GEMINI ERROR] Failed to generate recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


def _json_default(o):
    """JSON serializer that handles datetime/date/Decimal."""
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    return str(o)


def _sse_event(event: str, data: Any) -> bytes:
    """Format a Server-Sent Event frame."""
    payload = json.dumps(data, default=_json_default) if not isinstance(data, str) else json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@router.post("/complete-analysis")
async def complete_analysis(request: CompleteAnalysisRequest):
    """
    Streaming end-to-end analysis for the most recent session of a user.

    SSE events emitted:
      - init:  { results: {...}, heatmaps: {...} }  (the structured report)
      - chunk: "text"                               (progressive AI recommendation text; may repeat)
      - done:  { results, heatmaps, recommendations } (final consolidated payload)
      - error: { error: "...message..." }           (fatal; stream ends)
    """
    user_id = (request.user_id or "").strip()
    include_recs = bool(request.include_recommendations)

    async def event_stream():
        try:
            # 1) Find latest session for user
            db = healoncal_service._get_db()
            if not db.is_available():
                yield _sse_event("error", {"error": "Database connection not available"})
                return
            sessions = db.fetch_all(
                "SELECT * FROM healoncal_analysis_sessions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            )
            if not sessions:
                yield _sse_event("error", {"error": f"No sessions found for user '{user_id}'"})
                return
            session_id = sessions[0]["id"]
            images = db.fetch_all(
                "SELECT * FROM healoncal_captured_images WHERE session_id = %s",
                (session_id,),
            )
            if len(images) < 3:
                yield _sse_event("error", {"error": f"Need 3 images; have {len(images)}"})
                return

            # 2) Run analysis (idempotent if already completed)
            analyze_result = await healoncal_service.analyze_session(session_id)
            if not analyze_result.get("success"):
                yield _sse_event(
                    "error",
                    {"error": analyze_result.get("error", "Analysis failed")},
                )
                return

            # 3) Fetch results + heatmaps
            results = await healoncal_service.get_analysis_results(session_id)
            if not results.get("success"):
                yield _sse_event("error", {"error": results.get("error", "Failed to load results")})
                return
            results_payload = _build_results_response(session_id, results)

            # Frontend reads `healoncal_results.combined_analysis` (hydration,
            # elasticity, priority_concerns, etc.). `get_analysis_results`
            # returns combined_results=None, so compute it here from the
            # individual per-angle rows.
            try:
                combined = healoncal_service._create_combined_results(
                    session_id, results.get("individual_results") or []
                )
            except Exception as ce:
                logger.warning("[COMPLETE-ANALYSIS] combined_results failed: %s", ce)
                combined = {}
            results_payload.setdefault("healoncal_results", {})
            results_payload["healoncal_results"]["combined_analysis"] = combined

            heatmaps_payload = await _fetch_heatmaps_for_session(session_id)

            # Run the SageMaker models (acne / hyperpigmentation / aging) per
            # angle on the captured images, and presign the images so the report
            # can show the user's own photos next to the model-derived data.
            detections_by_angle: Dict[str, Any] = {}
            captured_images: Dict[str, Any] = {}

            async def _detect_for_angle(image_record: Dict[str, Any]) -> None:
                angle = str(image_record.get("angle") or "").lower()
                url = image_record.get("image_url")
                if not angle or not url:
                    return
                captured_images[angle] = s3_presign(url) or url
                try:
                    img_bytes = await asyncio.to_thread(s3_download_image, url)
                    if not img_bytes:
                        detections_by_angle[angle] = {"success": False, "error": "image download failed"}
                        return
                    detections_by_angle[angle] = await sagemaker_inference.run_all(img_bytes)
                except Exception as det_err:
                    logger.warning("[COMPLETE-ANALYSIS] detection failed for %s: %s", angle, det_err)
                    detections_by_angle[angle] = {"success": False, "error": str(det_err)}

            try:
                await asyncio.gather(*[_detect_for_angle(im) for im in images])
            except Exception as det_all_err:
                logger.warning("[COMPLETE-ANALYSIS] detection batch failed: %s", det_all_err)

            init_payload = {
                "results": results_payload,
                "heatmaps": heatmaps_payload,
                "detections": detections_by_angle,
                "captured_images": captured_images,
            }
            yield _sse_event("init", init_payload)

            # 4) Optionally stream recommendations
            recommendations_payload: Optional[Dict[str, Any]] = None
            if include_recs:
                try:
                    formatted = {
                        "session_id": session_id,
                        "healoncal_results": {
                            "individual_analyses": results.get("individual_results", []),
                            "combined_analysis": results.get("combined_results"),
                        },
                    }
                    recs = await recommendation_service.generate_product_recommendations(
                        formatted, None
                    )
                    # Emit a single text chunk so the UI can show something as recs are ready.
                    summary_text = recs.get("summary") if isinstance(recs, dict) else None
                    if summary_text:
                        yield _sse_event("chunk", str(summary_text))
                    # Frontend accesses recommendations.recommendations.products —
                    # mirror the shape of POST /recommendations here.
                    recommendations_payload = {
                        "success": True,
                        "session_id": session_id,
                        "recommendations": recs,
                    }
                except Exception as rec_err:
                    logger.warning("[COMPLETE-ANALYSIS] recommendations failed: %s", rec_err)
                    recommendations_payload = {
                        "success": False,
                        "error": str(rec_err),
                        "recommendations": {"products": []},
                    }

            # 5) Final done payload
            done_payload = {
                "results": results_payload,
                "heatmaps": heatmaps_payload,
                "recommendations": recommendations_payload,
                "detections": detections_by_angle,
                "captured_images": captured_images,
            }
            yield _sse_event("done", done_payload)

        except HTTPException as he:
            yield _sse_event("error", {"error": he.detail if isinstance(he.detail, str) else str(he.detail)})
        except Exception as e:
            logger.exception("[COMPLETE-ANALYSIS] unexpected error: %s", e)
            yield _sse_event("error", {"error": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
