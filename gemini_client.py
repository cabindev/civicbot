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
        if not Config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set")

        self._client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self._config = types.GenerateContentConfig(
            system_instruction=Config.SYSTEM_PROMPT,
            temperature=Config.TEMPERATURE,
        )

    async def generate_reply(self, history: List[Dict[str, str]]) -> str:
        """Generate a reply given conversation history.

        ``history`` is a list of ``{"role": "user"|"model", "text": str}``
        entries, oldest first, with the latest user message last.
        """
        contents = [
            types.Content(role=turn["role"], parts=[types.Part(text=turn["text"])])
            for turn in history
        ]

        try:
            # google-genai exposes a native async client under `.aio`.
            response = await self._client.aio.models.generate_content(
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
