"""
Bedrock-backed product recommendation service (Amazon Bedrock Mantle,
OpenAI-compatible endpoint).

Public shape mirrors GeminiRecommendationService so it drops into the two
`healoncal_analysis` call sites without further changes:

    generate_product_recommendations(healoncal_results, user_preferences=None) -> dict
    stream_recommendation_text(healoncal_results, user_preferences=None)   -> generator[str]

The prompt-building and response-parsing helpers are reused from the Gemini
service (they're pure functions over the analysis payload — no Gemini API
contact — so composition is fine and avoids duplicating ~250 lines).
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from openai import OpenAI
from aws_bedrock_token_generator import provide_token

from app.services.gemini_recommendation_service import GeminiRecommendationService

logger = logging.getLogger(__name__)


class BedrockRecommendationService:
    """Product recommendations via Bedrock Mantle (OpenAI-compatible endpoint)."""

    def __init__(self):
        self.model_name = os.getenv(
            "BEDROCK_MANTLE_MODEL",
            "qwen.qwen3-next-80b-a3b-instruct",
        )
        self.region = os.getenv("BEDROCK_MANTLE_REGION", "ap-south-1")
        self.base_url = os.getenv(
            "BEDROCK_MANTLE_BASE_URL",
            f"https://bedrock-mantle.{self.region}.api.aws/v1",
        )
        self.project = os.getenv("BEDROCK_MANTLE_PROJECT", "default")
        self.timeout_sec = float(os.getenv("BEDROCK_TIMEOUT_SECONDS", "35"))
        self.max_completion_tokens = int(os.getenv("BEDROCK_MAX_COMPLETION_TOKENS", "2000"))
        # Reuse Gemini helpers for prompt build + response parse (no API contact).
        self._helpers = GeminiRecommendationService()

    def _new_client(self) -> OpenAI:
        """Build a fresh OpenAI client. provide_token() is a local signing
        operation over the ambient AWS creds — no network cost — so making a
        new client per call sidesteps token-expiry bookkeeping entirely."""
        return OpenAI(
            api_key=provide_token(),
            base_url=self.base_url,
            project=self.project,
        )

    async def generate_product_recommendations(
        self,
        healoncal_results: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            logger.info("[BEDROCK] Generating product recommendations")
            analysis_summary = self._helpers._extract_analysis_summary(healoncal_results)
            prompt = self._helpers._create_recommendation_prompt(analysis_summary, user_preferences)

            loop = asyncio.get_running_loop()

            def _call():
                client = self._new_client()
                return client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_completion_tokens=self.max_completion_tokens,
                    temperature=0.7,
                )

            try:
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, _call), timeout=self.timeout_sec
                )
            except asyncio.TimeoutError:
                logger.error(f"[BEDROCK ERROR] Call exceeded {self.timeout_sec}s timeout")
                raise Exception(f"Bedrock call timeout after {self.timeout_sec} seconds")

            text = ""
            if response.choices:
                text = response.choices[0].message.content or ""
            logger.info("[BEDROCK] Response head: %s", (text[:200] if text else ""))

            recommendations = self._helpers._parse_gemini_response(text)
            recommendations.update({
                "analysis_session_id": healoncal_results.get("session_id"),
                "recommendation_timestamp": datetime.now().isoformat(),
                "ai_confidence": self._helpers._calculate_recommendation_confidence(analysis_summary),
                "personalization_level": "high" if user_preferences else "standard",
                "model": self.model_name,
                "provider": "bedrock-mantle",
            })
            logger.info(
                "[BEDROCK SUCCESS] Generated %d recommendations",
                len(recommendations.get("products", [])),
            )
            return recommendations
        except Exception as e:
            logger.error(f"[BEDROCK ERROR] Failed to generate recommendations: {e}")
            raise Exception(
                "Bedrock API call failed - medical recommendations cannot be generated without proper AI response"
            )

    def stream_recommendation_text(
        self,
        healoncal_results: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None,
    ):
        """Sync generator yielding text chunks (mirrors the Gemini streamer)."""
        analysis_summary = self._helpers._extract_analysis_summary(healoncal_results)
        prompt = self._helpers._create_recommendation_prompt(analysis_summary, user_preferences)
        logger.info("[BEDROCK] Streaming recommendation text")
        client = self._new_client()
        stream = client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=self.max_completion_tokens,
            temperature=0.7,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


bedrock_recommendation_service = BedrockRecommendationService()
