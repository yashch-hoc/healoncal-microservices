"""
Treatment Storage Service

Stores treatment recommendations and detected diseases in MySQL.
"""
import logging
import os
from typing import Dict, List, Any, Optional

from app.services.mysql_client_service import mysql_service

logger = logging.getLogger(__name__)

# VARCHAR(100) caused MySQL 1406 when Gemini returned long text. Default 100 stays safe
# pre-migration; after migrations/alter_expected_timeline_to_text.sql set EXPECTED_TIMELINE_MAX_CHARS=2000 (or similar).
def _expected_timeline_max_len() -> int:
    try:
        n = int(os.getenv("EXPECTED_TIMELINE_MAX_CHARS", "100"))
        return max(20, min(n, 16000))
    except ValueError:
        return 100


def _clip_expected_timeline(value: Any) -> str:
    max_len = _expected_timeline_max_len()
    s = (value if isinstance(value, str) else str(value or "")).strip() or "4-6 weeks"
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


class TreatmentStorageService:
    """Service for storing treatment recommendations and disease detection results."""

    def __init__(self):
        logger.info("[TREATMENT STORAGE] Service initialized")
        try:
            if mysql_service.is_available():
                row = mysql_service.fetch_one(
                    "SELECT id FROM treatment_recommendations LIMIT 1"
                )
                logger.info(
                    "[TREATMENT STORAGE] Database connection test successful: %s records found",
                    "1" if row else "0",
                )
            else:
                logger.warning("[TREATMENT STORAGE] MySQL not configured")
        except Exception as e:
            logger.warning(
                "[TREATMENT STORAGE] Database connection test failed (non-fatal): %s",
                e,
            )

    async def store_treatment_recommendations(
        self,
        session_id: str,
        user_id: str,
        recommendations: Dict[str, Any],
        analysis_summary: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Store treatment recommendations in the database."""
        try:
            logger.info("[TREATMENT STORAGE] Storing recommendations for session %s", session_id)

            personalization_mapping = {
                "high": "premium",
                "medium": "advanced",
                "low": "standard",
                "basic": "basic",
            }
            budget_mapping = {
                "budget": "budget",
                "moderate": "mid-range",
                "mid-range": "mid-range",
                "premium": "premium",
                "luxury": "luxury",
            }
            raw_personalization = recommendations.get("personalization_level", "standard")
            mapped_personalization = personalization_mapping.get(raw_personalization, "standard")
            budget = "mid-range"
            if user_preferences and isinstance(user_preferences.get("budget"), str):
                budget = budget_mapping.get(user_preferences["budget"], "mid-range")

            treatment_record = {
                "session_id": session_id,
                "user_id": user_id,
                "ai_model_version": "gemini-2.5-flash",
                "ai_confidence": recommendations.get("ai_confidence", 0.0),
                "personalization_level": mapped_personalization,
                "routine_type": recommendations.get("routine_type", "both"),
                "products": recommendations.get("products", []),
                "routine_steps": recommendations.get("routine_steps", {}),
                "key_advice": recommendations.get("key_advice", []),
                "ingredients_to_avoid": recommendations.get("ingredients_to_avoid", []),
                "expected_timeline": _clip_expected_timeline(
                    recommendations.get("expected_timeline", "4-6 weeks")
                ),
                "primary_skin_concerns": self._extract_concerns_from_analysis(analysis_summary),
                "skin_type": analysis_summary.get("skin_type", "Normal"),
                "skin_tone": analysis_summary.get("skin_tone", "Medium"),
                "overall_accuracy": analysis_summary.get("overall_accuracy", 0.0),
                "user_preferences": user_preferences or {},
                "budget_range": budget,
                "medical_flags": [],
                "dermatologist_referral_needed": False,
                "urgency_level": "routine",
                "status": "active",
                "effectiveness_rating": 0.0,
                "user_feedback": {},
            }

            if not mysql_service.is_available():
                logger.warning("[TREATMENT STORAGE] MySQL not configured - skipping storage")
                raise Exception("Database storage failed - MySQL not configured")

            recommendation_id = mysql_service.insert("treatment_recommendations", treatment_record)
            if recommendation_id:
                logger.info("[TREATMENT STORAGE SUCCESS] Stored recommendations: %s", recommendation_id)
                return recommendation_id
            raise Exception("No id returned from database insert")
        except Exception as e:
            logger.error("[TREATMENT STORAGE ERROR] Failed to store recommendations: %s", e)
            raise

    async def store_detected_diseases(
        self,
        session_id: str,
        analysis_result_id: str,
        user_id: str,
        detected_diseases: List[Dict[str, Any]],
    ) -> List[str]:
        """Store detected diseases in the database."""
        try:
            if not detected_diseases:
                logger.info("[DISEASE STORAGE] No diseases to store for session %s", session_id)
                return []

            def make_json_safe(value):
                import numpy as np
                if getattr(np, "bool_", None) and isinstance(value, np.bool_):
                    return bool(value)
                if getattr(np, "integer", None) and isinstance(value, np.integer):
                    return int(value)
                if getattr(np, "floating", None) and isinstance(value, np.floating):
                    return float(value)
                if isinstance(value, getattr(np, "ndarray", type(None))):
                    return value.tolist()
                return value

            disease_category_mapping = {
                "fungal": "infectious",
                "bacterial": "infectious",
                "viral": "infectious",
                "inflammatory": "inflammatory",
                "pigmentary": "pigmentary",
                "structural": "structural",
                "hormonal": "hormonal",
                "genetic": "genetic",
                "environmental": "environmental",
                "unknown": "structural",
            }
            def _normalize_severity(s) -> str:
                if s is None:
                    return "mild"
                s = str(s).lower().strip()
                if s in ("very_mild", "mild", "moderate", "severe", "very_severe"):
                    return s
                if s in ("low", "minimal"):
                    return "very_mild"
                if s == "high":
                    return "severe"
                return "mild"

            if not mysql_service.is_available():
                raise Exception("MySQL not configured - cannot store diseases")

            disease_ids = []
            for disease in detected_diseases:
                record = {
                    "session_id": session_id,
                    "analysis_result_id": analysis_result_id,
                    "user_id": user_id,
                    "disease_name": str(disease.get("name", "Unknown")),
                    "disease_category": disease_category_mapping.get(
                        disease.get("category", "unknown"), "structural"
                    ),
                    "confidence_score": make_json_safe(disease.get("confidence", 0.0)),
                    "severity_level": _normalize_severity(disease.get("severity", "mild")),
                    "affected_area": str(disease.get("affected_area", "face")),
                    "detection_method": "healoncal_analysis",
                    "model_version": "Healoncal_v2.0",
                    "requires_medical_attention": make_json_safe(
                        disease.get("requires_medical_attention", False)
                    ),
                    "recommended_specialist": "dermatologist"
                    if disease.get("requires_medical_attention")
                    else "general_practitioner",
                    "urgency_level": "urgent"
                    if disease.get("requires_medical_attention")
                    else "routine",
                    "symptoms_noted": make_json_safe(disease.get("symptoms", [])),
                    "risk_factors": [],
                    "notes": "Detected via automated analysis with {:.1%} confidence".format(
                        make_json_safe(disease.get("confidence", 0.0))
                    ),
                }
                did = mysql_service.insert("detected_skin_diseases", record)
                if did:
                    disease_ids.append(did)
            logger.info("[DISEASE STORAGE] Stored %s diseases for session %s", len(disease_ids), session_id)
            return disease_ids
        except Exception as e:
            logger.error("[DISEASE STORAGE ERROR] Failed to store diseases: %s", e)
            raise

    async def get_treatment_recommendations(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve treatment recommendations for a session."""
        try:
            if not mysql_service.is_available():
                return None
            row = mysql_service.fetch_one(
                "SELECT * FROM treatment_recommendations WHERE session_id = %s LIMIT 1",
                (session_id,),
            )
            return row
        except Exception as e:
            logger.error("[TREATMENT STORAGE ERROR] Failed to retrieve recommendations: %s", e)
            return None

    async def get_detected_diseases(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve detected diseases for a session."""
        try:
            if not mysql_service.is_available():
                return []
            rows = mysql_service.fetch_all(
                "SELECT * FROM detected_skin_diseases WHERE session_id = %s",
                (session_id,),
            )
            return rows
        except Exception as e:
            logger.error("[TREATMENT STORAGE ERROR] Failed to retrieve diseases: %s", e)
            return []

    async def get_comprehensive_treatment_data(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive treatment data from the view."""
        try:
            if not mysql_service.is_available():
                return {}
            row = mysql_service.fetch_one(
                "SELECT * FROM comprehensive_treatment_view WHERE session_id = %s LIMIT 1",
                (session_id,),
            )
            return row or {}
        except Exception as e:
            logger.error("[TREATMENT STORAGE ERROR] Failed to retrieve comprehensive data: %s", e)
            return {}

    def _extract_concerns_from_analysis(self, analysis_summary: Dict[str, Any]) -> List[str]:
        concerns = []
        for key, value in analysis_summary.items():
            if isinstance(value, (int, float)) and value > 50:
                if "acne" in key.lower():
                    concerns.append("acne")
                elif "wrinkle" in key.lower():
                    concerns.append("wrinkles")
                elif "pigment" in key.lower():
                    concerns.append("pigmentation")
                elif "redness" in key.lower():
                    concerns.append("redness")
                elif "pores" in key.lower():
                    concerns.append("large_pores")
        return list(set(concerns))


treatment_storage_service = TreatmentStorageService()
