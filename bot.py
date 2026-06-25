"""CivicSpace bot: bridges Bot Framework activities to Gemini."""

import logging
from typing import List

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount

from conversation_store import ConversationStore, InMemoryConversationStore
from gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class CivicSpaceBot(ActivityHandler):
    """Replies to user messages using Gemini, keeping per-conversation history."""

    def __init__(self, gemini: GeminiClient, store: ConversationStore = None):
        self._gemini = gemini
        # Swap in a persistent ConversationStore here for multi-instance/durable
        # history; defaults to in-process memory.
        self._store = store or InMemoryConversationStore()

    async def on_members_added_activity(
        self, members_added: List[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "สวัสดีครับ ผมคือ CivicSpace Assistant"
                    "ถามได้เลยครับ ทั้งเรื่อง CivicSpace ประเด็นแอลกอฮอล์/ปัจจัยเสี่ยง "
                    "งานพื้นที่ หรือประเด็นอื่นๆที่ท่านสนใจ ผมจะพยายามช่วยตอบให้ครับ"
                )

    async def on_message_activity(self, turn_context: TurnContext):
        conversation_id = turn_context.activity.conversation.id
        user_text = (turn_context.activity.text or "").strip()

        if not user_text:
            return

        await self._store.add_turn(conversation_id, "user", user_text)
        history = await self._store.get_history(conversation_id)

        reply = await self._gemini.generate_reply(history)

        await self._store.add_turn(conversation_id, "model", reply)
        await turn_context.send_activity(reply)
