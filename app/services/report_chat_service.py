"""
RAG-style chat on Healoncal analysis report using Gemini.

User can ask up to 5 questions per report (session). Context is the analysis result;
answers are generated only from that report.
Uses google.genai (new SDK); google.generativeai is deprecated.
"""
import logging
import os
from typing import Dict, Any, List, Optional

from google import genai

logger = logging.getLogger(__name__)

MAX_PROMPTS_PER_SESSION = 5
MODEL_NAME = "gemini-2.5-flash"


class ReportChatService:
    """Chat on analysis report with Gemini; max 5 user prompts per session."""

    def __init__(self):
        self.api_key = None
        self.client = None
        self._initialized = False
        self._prompt_count: Dict[str, int] = {}
        self._history: Dict[str, List[Dict[str, str]]] = {}

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise Exception("Gemini API key not configured for report chat")
        try:
            self.client = genai.Client(api_key=self.api_key)
            self._initialized = True
            logger.info("[REPORT-CHAT] Gemini initialized for report chat (%s)", MODEL_NAME)
        except Exception as e:
            logger.error("[REPORT-CHAT] Gemini init failed: %s", e)
            raise

    def get_prompt_count(self, session_id: str) -> int:
        """Return how many user prompts have been used for this session."""
        return self._prompt_count.get(session_id, 0)

    def chat(
        self,
        session_id: str,
        message: str,
        report_context: str,
    ) -> Dict[str, Any]:
        """
        Answer one user question based on the report. Enforces max 5 prompts per session.

        Args:
            session_id: Analysis session id (used for limit tracking).
            message: User's question.
            report_context: Serialized report (e.g. JSON or text) to use as RAG context.

        Returns:
            {
                "reply": str,
                "prompts_used": int,
                "prompts_remaining": int,
                "limit_reached": bool,
            }
        """
        self._ensure_initialized()
        session_id = session_id.strip()
        used = self._prompt_count.get(session_id, 0)
        if used >= MAX_PROMPTS_PER_SESSION:
            return {
                "reply": "You have reached the maximum of 5 questions for this report. No further questions can be answered for this session.",
                "prompts_used": used,
                "prompts_remaining": 0,
                "limit_reached": True,
            }
        history = self._history.get(session_id, [])
        prompt = self._build_prompt(report_context, history, message)
        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )
            if response and getattr(response, "text", None):
                reply = response.text
            elif response and getattr(response, "candidates", None) and response.candidates:
                parts = getattr(response.candidates[0].content, "parts", None) or []
                reply = parts[0].text if parts else "I couldn't generate a response. Please try again."
            else:
                reply = "I couldn't generate a response. Please try again."
        except Exception as e:
            logger.error(f"[REPORT-CHAT] Gemini error: {e}")
            return {
                "reply": f"Sorry, an error occurred while answering: {str(e)}",
                "prompts_used": used,
                "prompts_remaining": MAX_PROMPTS_PER_SESSION - used,
                "limit_reached": False,
            }
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        self._history[session_id] = history
        self._prompt_count[session_id] = used + 1
        remaining = MAX_PROMPTS_PER_SESSION - (used + 1)
        return {
            "reply": reply,
            "prompts_used": used + 1,
            "prompts_remaining": remaining,
            "limit_reached": remaining <= 0,
        }

    def _build_prompt(self, report_context: str, history: List[Dict[str, str]], message: str) -> str:
        parts = [
            "You are a helpful medical skin analysis assistant. Answer ONLY based on the following comprehensive skin analysis report.",
            "The report contains: individual analyses with biomarkers, combined results, detected diseases, and detailed AI-generated treatment recommendations including personalized skin care routines.",
            "Do not invent or assume information not explicitly in the report. Keep answers concise, clear, and medically accurate.",
            "When users ask about routine, skincare, products, or care instructions - refer to these sections in order of priority:",
            "1. 'treatment_recommendations_and_skincare_routine' section with 'routine_steps', 'morning_routine', 'evening_routine', 'products', and 'key_advice'",
            "2. 'combined_analysis_results' section which may contain 'comprehensive_routine' and 'consolidated_recommendations'",
            "3. 'priority_concerns' section for main areas to focus on",
            "If recommendations data exists in any section, use it. Do NOT say recommendations are pending or unavailable if they appear anywhere in the report.",
            "",
            "--- COMPREHENSIVE SKIN ANALYSIS REPORT ---",
            report_context,
            "--- END REPORT ---",
            "",
        ]
        if history:
            parts.append("Previous conversation:")
            for turn in history:
                role = "User" if turn["role"] == "user" else "Assistant"
                parts.append(f"{role}: {turn['content']}")
            parts.append("")
        parts.append(f"User: {message}")
        parts.append("Assistant:")
        return "\n".join(parts)


report_chat_service = ReportChatService()
