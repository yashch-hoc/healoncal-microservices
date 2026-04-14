"""
Gemini AI Product Recommendation Service

This service uses Gemini AI to generate intelligent product recommendations
based on Healoncal analysis results.
"""
import asyncio
import logging
import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from google import genai

logger = logging.getLogger(__name__)


def _normalize_detected_diseases(raw: Any) -> List[Any]:
    """Coerce detected_diseases to a list of dict/str for prompt building."""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return [raw] if raw.strip() else []
    if not isinstance(raw, list):
        return [raw] if raw else []
    return raw


def _format_disease_prompt_line(disease: Any) -> str:
    """One bullet line for prompt; DB rows use disease_name, analysis may use name or plain str."""
    if isinstance(disease, str):
        return f"- {disease}"
    if not isinstance(disease, dict):
        return f"- {disease}"
    name = disease.get("disease_name") or disease.get("name") or "Unknown"
    sev = disease.get("severity_level") or disease.get("severity") or "mild"
    c = disease.get("confidence_score")
    if c is None:
        c = disease.get("confidence", 0)
    try:
        c = float(c or 0)
    except (TypeError, ValueError):
        c = 0.0
    pct = c * 100 if c <= 1.0 else c
    return f"- {name} ({sev}) - Confidence: {pct:.1f}%"


class GeminiRecommendationService:
    """Service for generating AI-powered product recommendations using Gemini (google-genai SDK)."""
    
    def __init__(self):
        """Initialize Gemini recommendation service."""
        self.client = None
        self._initialized = False
        # Allow model selection from environment; fall back to a sane default.
        # Example in .env: GEMINI_MODEL_NAME=gemini-2.5-flash
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

    def _ensure_initialized(self):
        """Ensure the service is properly initialized."""
        if self._initialized:
            return
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
        
        
        
        
        
        
        
        
        
            raise Exception("Gemini API key not configured - medical recommendations require proper AI configuration")
        try:
            self.client = genai.Client(api_key=api_key)
            self._initialized = True
            logger.info("[GEMINI SUCCESS] Recommendation service initialized with %s", self.model_name)
        except Exception as e:
            logger.error("[GEMINI ERROR] Failed to initialize: %s", e)
            raise Exception("Gemini initialization failed: %s" % e)
    
    async def generate_product_recommendations(
        self, 
        healoncal_results: Dict[str, Any], 
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate personalized product recommendations based on Healoncal analysis.
        This is defined as async so FastAPI can await it, but the underlying
        google-genai client is sync. To avoid blocking the event loop (and to
        reduce perceived latency under concurrent load), the actual Gemini call
        is executed in a thread pool via run_in_executor.
        """
        try:
            logger.info("[GEMINI] Generating product recommendations based on Healoncal analysis")
            
            # Ensure service is initialized
            self._ensure_initialized()
            
            # Extract key analysis data
            analysis_summary = self._extract_analysis_summary(healoncal_results)
            
            # Create Gemini prompt (small, structured text only)
            prompt = self._create_recommendation_prompt(analysis_summary, user_preferences)
            
            logger.info("[GEMINI] Sending prompt to Gemini API")
            # Offload blocking SDK call to a worker thread so the event loop
            # stays free to serve other requests while Gemini is processing.
            loop = asyncio.get_running_loop()

            async def _call_gemini():
                return await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                    ),
                )

            # Enforce an upper bound on Gemini latency so the overall request
            # completes within a predictable time budget.
            timeout_sec = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "35"))
            try:
                response = await asyncio.wait_for(_call_gemini(), timeout=timeout_sec)
            except asyncio.TimeoutError:
                logger.error(f"[GEMINI ERROR] Gemini call exceeded {timeout_sec}s timeout")
                raise Exception(f"Gemini API timeout after {timeout_sec} seconds")
            text = response.text if hasattr(response, "text") else (response.candidates[0].content.parts[0].text if response.candidates else "")
            logger.info("[GEMINI] Received response from Gemini: %s...", (text[:200] if text else ""))
            recommendations = self._parse_gemini_response(text)
            logger.info(f"[GEMINI] Parsed recommendations: {recommendations}")
            
            # Add metadata
            recommendations.update({
                "analysis_session_id": healoncal_results.get("session_id"),
                "recommendation_timestamp": datetime.now().isoformat(),
                "ai_confidence": self._calculate_recommendation_confidence(analysis_summary),
                "personalization_level": "high" if user_preferences else "standard"
            })
            
            logger.info(f"[GEMINI SUCCESS] Generated {len(recommendations.get('products', []))} recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"[GEMINI ERROR] Failed to generate recommendations: {e}")
            raise Exception("Gemini API call failed - medical recommendations cannot be generated without proper AI response")

    def stream_recommendation_text(self, healoncal_results: Dict[str, Any], user_preferences: Optional[Dict[str, Any]] = None):
        """Sync generator: same prompt as generate_product_recommendations, yields text chunks for streaming."""
        self._ensure_initialized()
        analysis_summary = self._extract_analysis_summary(healoncal_results)
        prompt = self._create_recommendation_prompt(analysis_summary, user_preferences)
        logger.info("[GEMINI] Streaming recommendation text")
        for chunk in self.client.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
        ):
            if getattr(chunk, "text", None):
                yield chunk.text
    
    def _extract_analysis_summary(self, healoncal_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key analysis data for recommendation generation."""
        try:
            # Get combined analysis if available, otherwise use individual results
            combined = healoncal_results.get("healoncal_results", {}).get("combined_analysis")
            individual = healoncal_results.get("healoncal_results", {}).get("individual_analyses", [])
            
            if combined:
                return {
                    "skin_type": combined.get("final_skin_type_classification", "Normal"),
                    "skin_tone": combined.get("final_skin_tone_classification", "Medium"),
                    "primary_concerns": self._extract_primary_concerns(combined),
                    "overall_accuracy": combined.get("overall_diagnostic_accuracy", 75.0),
                    "key_metrics": {
                        "hydration": combined.get("combined_hydration_score", 50.0),
                        "oiliness": combined.get("combined_oiliness_score", 50.0),
                        "wrinkles": combined.get("combined_wrinkles_score", 30.0),
                        "pigmentation": combined.get("combined_pigmentation_score", 20.0),
                        "redness": combined.get("combined_redness_score", 15.0),
                        "pores": combined.get("combined_pores_score", 40.0),
                        "acne": combined.get("combined_acne_score", 0.0),
                        "elasticity": combined.get("combined_elasticity_score", 50.0),
                        "fine_lines": combined.get("combined_fine_lines_score", 20.0)
                    },
                    "detected_diseases": combined.get("detected_diseases", []),
                    "analysis_completeness": combined.get("analysis_completeness", 100.0),
                    "data_quality_score": combined.get("data_quality_score", 85.0)
                }
            elif individual:
                # Aggregate individual results
                sample = individual[0]  # Use first result as representative
                return {
                    "skin_type": sample.get("skin_type_classification", "Normal"),
                    "skin_tone": sample.get("skin_tone_classification", "Medium"),
                    "primary_concerns": [
                        concern for concern, score in [
                            ("wrinkles", sample.get("wrinkles_score", 0)),
                            ("acne", sample.get("acne_score", 0)),
                            ("pigmentation", sample.get("pigmentation_score", 0)),
                            ("redness", sample.get("redness_score", 0)),
                            ("pores", sample.get("pores_score", 0)),
                            ("fine_lines", sample.get("fine_lines_score", 0)),
                            ("oiliness", sample.get("oiliness_score", 0))
                        ] if score > 50
                    ],
                    "overall_accuracy": sample.get("diagnostic_accuracy", 75.0),
                    "key_metrics": {
                        "hydration": sample.get("hydration_score", 50.0),
                        "oiliness": sample.get("oiliness_score", 50.0),
                        "wrinkles": sample.get("wrinkles_score", 30.0),
                        "fine_lines": sample.get("fine_lines_score", 20.0),
                        "pigmentation": sample.get("pigmentation_score", 20.0),
                        "redness": sample.get("redness_score", 15.0),
                        "pores": sample.get("pores_score", 40.0),
                        "acne": sample.get("acne_score", 0.0),
                        "elasticity": sample.get("elasticity_score", 50.0),
                        "overall_health": sample.get("overall_skin_health_score", 60.0)
                    },
                    "detected_diseases": [],  # Individual results don't have diseases
                    "analysis_completeness": 100.0,
                    "data_quality_score": sample.get("image_quality_score", 85.0)
                }
            else:
                # Fallback default
                return {
                    "skin_type": "Normal",
                    "skin_tone": "Medium",
                    "primary_concerns": [],
                    "overall_accuracy": 50.0,
                    "key_metrics": {
                        "hydration": 50.0,
                        "oiliness": 50.0,
                        "wrinkles": 30.0,
                        "pigmentation": 20.0,
                        "redness": 15.0,
                        "pores": 40.0,
                        "overall_health": 60.0
                    }
                }
                
        except Exception as e:
            logger.error(f"[GEMINI ERROR] Failed to extract analysis summary: {e}")
            return {"skin_type": "Normal", "primary_concerns": [], "key_metrics": {}}
    
    def _extract_primary_concerns(self, combined_analysis: Dict[str, Any]) -> List[str]:
        """Extract primary skin concerns from combined analysis."""
        concerns = []
        
        # Check various metrics and identify top concerns
        metrics = {
            "wrinkles": combined_analysis.get("combined_wrinkles_score", 0),
            "acne": combined_analysis.get("combined_acne_score", 0),
            "pigmentation": combined_analysis.get("combined_pigmentation_score", 0),
            "redness": combined_analysis.get("combined_redness_score", 0),
            "pores": combined_analysis.get("combined_pores_score", 0),
            "dryness": 100 - combined_analysis.get("combined_hydration_score", 50),
            "fine_lines": combined_analysis.get("combined_fine_lines_score", 0),
            "oiliness": combined_analysis.get("combined_oiliness_score", 0)
        }
        
        # Add concerns with scores above threshold
        for concern, score in metrics.items():
            if score > 50:  # Threshold for significant concern
                concerns.append(concern)
        
        return concerns[:3]  # Return top 3 concerns
    
    def _create_recommendation_prompt(
        self, 
        analysis_summary: Dict[str, Any], 
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a compact, efficient prompt for Gemini AI."""
        
        skin_type = analysis_summary.get("skin_type", "Normal")
        skin_tone = analysis_summary.get("skin_tone", "Medium")
        concerns = analysis_summary.get("primary_concerns", [])
        metrics = analysis_summary.get("key_metrics", {})
        accuracy = analysis_summary.get("overall_accuracy", 75.0)
        detected_diseases = _normalize_detected_diseases(
            analysis_summary.get("detected_diseases", [])
        )
        analysis_completeness = analysis_summary.get("analysis_completeness", 100.0)
        data_quality = analysis_summary.get("data_quality_score", 85.0)
        
        # Compact preferences context
        preferences_context = {}
        if user_preferences:
            preferences_context = {
                "budget": user_preferences.get("budget", "moderate"),
                "skin_sensitivity": user_preferences.get("skin_sensitivity", "normal"),
                "preferred_brands": user_preferences.get("preferred_brands", "any"),
            }
        
        # Compact detected diseases list
        diseases_lines = []
        if detected_diseases:
            diseases_lines = [
                _format_disease_prompt_line(d) for d in detected_diseases[:5]
            ]
        
        # Build a minimal, machine-friendly context plus strict JSON instruction.
        prompt = f"""
You are a dermatologist and skincare expert.
Use the analysis JSON below to generate structured skincare recommendations.
Return ONLY valid JSON, no extra text.

ANALYSIS_CONTEXT = {{
  "accuracy": {accuracy:.1f},
  "analysis_completeness": {analysis_completeness:.1f},
  "data_quality": {data_quality:.1f},
  "skin_type": "{skin_type}",
  "skin_tone": "{skin_tone}",
  "primary_concerns": {json.dumps(concerns)},
  "metrics": {json.dumps(metrics)},
  "detected_diseases": {json.dumps(diseases_lines)},
  "user_preferences": {json.dumps(preferences_context)}
}}

Respond in this JSON format:
{{
  "routine_type": "morning/evening/both",
  "products": [
    {{
      "category": "cleanser/moisturizer/serum/sunscreen/treatment",
      "product_name": "specific product name",
      "brand": "brand name",
      "key_ingredients": ["ingredient1", "ingredient2"],
      "target_concern": "primary concern addressed",
      "usage_instructions": "how to use",
      "priority": "high/medium/low",
      "price_range": "budget/mid-range/luxury",
      "why_recommended": "explanation based on analysis",
      "medical_grade": true/false,
      "dermatologist_approved": true/false
    }}
  ],
  "routine_steps": {{
    "morning": ["step1", "step2", "step3"],
    "evening": ["step1", "step2", "step3"]
  }},
  "medical_recommendations": {{
    "dermatologist_consultation": "when to see a dermatologist",
    "prescription_treatments": ["treatment1", "treatment2"],
    "professional_treatments": ["treatment1", "treatment2"]
  }},
  "beautician_recommendations": {{
    "facials": ["facial1", "facial2"],
    "treatments": ["treatment1", "treatment2"],
    "frequency": "how often"
  }},
  "home_care": {{
    "daily_routine": ["step1", "step2"],
    "weekly_treatments": ["treatment1", "treatment2"],
    "lifestyle_changes": ["change1", "change2"]
  }},
  "key_advice": [
    "advice point 1",
    "advice point 2"
  ],
  "ingredients_to_avoid": ["ingredient1", "ingredient2"],
  "ingredients_to_seek": ["ingredient1", "ingredient2"],
  "expected_timeline": "when to expect results",
  "follow_up_schedule": "when to reassess"
}}
"""
        
        return prompt
    
    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and structure Gemini's response."""
        try:
            # Try to extract JSON from the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                # Validate and clean the parsed response
                return {
                    "routine_type": parsed.get("routine_type", "both"),
                    "products": parsed.get("products", []),
                    "routine_steps": parsed.get("routine_steps", {"morning": [], "evening": []}),
                    "key_advice": parsed.get("key_advice", []),
                    "ingredients_to_avoid": parsed.get("ingredients_to_avoid", []),
                    "expected_timeline": parsed.get("expected_timeline", "4-6 weeks"),
                    "ai_generated": True,
                    "recommendation_quality": "high"
                }
            else:
                # If no JSON found, create structured response from text
                return self._structure_text_response(response_text)
                
        except json.JSONDecodeError as e:
            logger.warning(f"[GEMINI WARNING] Failed to parse JSON response: {e}")
            return self._structure_text_response(response_text)
        except Exception as e:
            logger.error(f"[GEMINI ERROR] Failed to parse response: {e}")
            return {"error": "Failed to parse AI response", "raw_response": response_text}
    
    def _structure_text_response(self, text: str) -> Dict[str, Any]:
        """Structure a text response when JSON parsing fails."""
        return {
            "routine_type": "both",
            "products": [],
            "routine_steps": {"morning": [], "evening": []},
            "key_advice": [text[:200] + "..." if len(text) > 200 else text],
            "ingredients_to_avoid": [],
            "expected_timeline": "4-6 weeks",
            "ai_generated": True,
            "recommendation_quality": "text_only",
            "raw_response": text
        }
    
    def _calculate_recommendation_confidence(self, analysis_summary: Dict[str, Any]) -> float:
        """Calculate confidence score for recommendations based on analysis quality."""
        base_confidence = 0.6
        
        # Boost confidence based on analysis accuracy
        accuracy = analysis_summary.get("overall_accuracy", 50.0)
        accuracy_boost = (accuracy - 50) / 200  # 0 to 0.25 boost
        
        # Boost confidence based on analysis completeness
        completeness = analysis_summary.get("analysis_completeness", 100.0)
        completeness_boost = (completeness - 50) / 200  # 0 to 0.25 boost
        
        # Boost confidence based on data quality
        data_quality = analysis_summary.get("data_quality_score", 85.0)
        quality_boost = (data_quality - 50) / 200  # 0 to 0.25 boost
        
        # Boost confidence if we have clear concerns identified
        concerns = analysis_summary.get("primary_concerns", [])
        concerns_boost = min(len(concerns) * 0.05, 0.1)  # Up to 0.1 boost
        
        # Boost confidence if we have detected diseases (more specific data)
        detected_diseases = analysis_summary.get("detected_diseases", [])
        diseases_boost = min(len(detected_diseases) * 0.1, 0.2)  # Up to 0.2 boost
        
        final_confidence = min(base_confidence + accuracy_boost + completeness_boost + quality_boost + concerns_boost + diseases_boost, 1.0)
        return round(final_confidence, 2)
    
    # Mock recommendations removed - medical products cannot use mock data

# Global instance
gemini_recommendation_service = GeminiRecommendationService()
try:
    gemini_recommendation_service._ensure_initialized()
except Exception as _e:
    logger.warning("[GEMINI] Eager init skipped: %s", _e)
    