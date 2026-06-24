"""CivicSpace bot: bridges Bot Framework activities to Gemini."""

import logging
from typing import Dict, List

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount

from config import Config
from gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class CivicSpaceBot(ActivityHandler):
    """Replies to user messages using Gemini, keeping per-conversation history."""

    def __init__(self, gemini: GeminiClient):
        self._gemini = gemini
        # Maps conversation id -> list of {"role", "text"} turns.
        # NOTE: in-memory store; for multi-instance deployments back this with
        # Bot Framework state storage (e.g. Cosmos DB / Blob) instead.
        self._histories: Dict[str, List[Dict[str, str]]] = {}

    async def on_members_added_activity(
        self, members_added: List[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "สวัสดีค่ะ ยินดีต้อนรับสู่ CivicSpace 🌱 "
                    "มีอะไรให้ช่วยเรื่องพื้นที่สาธารณะหรือการมีส่วนร่วมของพลเมืองไหมคะ"
                )

    async def on_message_activity(self, turn_context: TurnContext):
        conversation_id = turn_context.activity.conversation.id
        user_text = (turn_context.activity.text or "").strip()

        if not user_text:
            return

        history = self._histories.setdefault(conversation_id, [])
        history.append({"role": "user", "text": user_text})

        reply = await self._gemini.generate_reply(history)

        history.append({"role": "model", "text": reply})
        self._trim_history(conversation_id)

        await turn_context.send_activity(reply)

    def _trim_history(self, conversation_id: str):
        """Keep only the last HISTORY_LIMIT turns for context."""
        history = self._histories[conversation_id]
        if len(history) > Config.HISTORY_LIMIT:
            self._histories[conversation_id] = history[-Config.HISTORY_LIMIT :]
