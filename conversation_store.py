"""Conversation history storage.

The store keeps the last N turns per conversation so Gemini has context.
It exposes an **async** interface so a persistent backend (Azure Cosmos DB,
Blob, Redis, ...) can be dropped in later without changing ``bot.py`` —
just implement ``ConversationStore`` and pass it to ``CivicSpaceBot``.

Current default: ``InMemoryConversationStore`` (process memory). Fine for a
single instance; history is lost on restart and not shared across instances.
"""

from abc import ABC, abstractmethod
from typing import Dict, List

from config import Config


class ConversationStore(ABC):
    """Interface for storing per-conversation chat history."""

    @abstractmethod
    async def get_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Return turns (oldest first) as ``{"role", "text"}`` dicts."""

    @abstractmethod
    async def add_turn(self, conversation_id: str, role: str, text: str) -> None:
        """Append one turn and trim to the configured limit."""


class InMemoryConversationStore(ConversationStore):
    """Keeps the last ``history_limit`` turns per conversation in memory."""

    def __init__(self, history_limit: int = Config.HISTORY_LIMIT):
        self._history_limit = history_limit
        self._histories: Dict[str, List[Dict[str, str]]] = {}

    async def get_history(self, conversation_id: str) -> List[Dict[str, str]]:
        return list(self._histories.get(conversation_id, []))

    async def add_turn(self, conversation_id: str, role: str, text: str) -> None:
        history = self._histories.setdefault(conversation_id, [])
        history.append({"role": role, "text": text})
        if len(history) > self._history_limit:
            self._histories[conversation_id] = history[-self._history_limit :]
