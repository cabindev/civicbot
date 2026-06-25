"""Thin async wrapper around the Google Gemini API (google-genai SDK)."""

import logging
from typing import List, Dict

from google import genai
from google.genai import types

from config import Config

logger = logging.getLogger(__name__)


class GeminiClient:
    """Generates replies from Gemini using a CivicSpace system prompt."""

    def __init__(self):
        # Lazy: don't create the client (or require the key) at construction
        # time, so a missing GEMINI_API_KEY never crashes the whole app on
        # startup — the health endpoint stays up and errors are debuggable.
        self._client = None
        self._config = types.GenerateContentConfig(
            system_instruction=Config.SYSTEM_PROMPT,
            temperature=Config.TEMPERATURE,
        )

    def _ensure_client(self):
        """Create the genai client on first use; None if no API key."""
        if self._client is None:
            if not Config.GEMINI_API_KEY:
                logger.error("GEMINI_API_KEY is not set — cannot call Gemini")
                return None
            self._client = genai.Client(api_key=Config.GEMINI_API_KEY)
        return self._client

    async def generate_reply(self, history: List[Dict[str, str]]) -> str:
        """Generate a reply given conversation history.

        ``history`` is a list of ``{"role": "user"|"model", "text": str}``
        entries, oldest first, with the latest user message last.
        """
        client = self._ensure_client()
        if client is None:
            return (
                "ขออภัยครับ ระบบยังไม่พร้อมใช้งาน (ไม่พบการตั้งค่า GEMINI_API_KEY) "
                "กรุณาแจ้งทีมงานครับ"
            )

        contents = [
            types.Content(role=turn["role"], parts=[types.Part(text=turn["text"])])
            for turn in history
        ]

        try:
            # google-genai exposes a native async client under `.aio`.
            response = await client.aio.models.generate_content(
                model=Config.GEMINI_MODEL,
                contents=contents,
                config=self._config,
            )
            text = (response.text or "").strip()
            if text:
                return text
            logger.warning("Gemini returned an empty response")
        except Exception:  # noqa: BLE001 - surface a friendly message instead
            logger.exception("Gemini request failed")

        return "ขออภัยครับ ระบบขัดข้องชั่วคราว กรุณาลองใหม่อีกครั้งนะครับ"
