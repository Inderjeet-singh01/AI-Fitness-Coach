from collections import defaultdict, deque
from typing import Dict, List, Deque


class SessionMemoryStore:
    """Small in-memory conversation store for the current prototype."""

    _store: Dict[str, Deque[Dict[str, str]]] = defaultdict(lambda: deque(maxlen=12))

    @classmethod
    def get_history(cls, session_id: str) -> List[Dict[str, str]]:
        if not session_id:
            return []
        return list(cls._store[session_id])

    @classmethod
    def append_message(cls, session_id: str, role: str, content: str) -> None:
        if not session_id or not content:
            return
        cls._store[session_id].append({"role": role, "content": content})

    @classmethod
    def clear_session(cls, session_id: str) -> None:
        if session_id in cls._store:
            del cls._store[session_id]


def format_chat_history(chat_history: List[Dict[str, str]], max_messages: int = 6, max_chars: int = 3500) -> str:
    """Return a compact recent history to keep every LLM request bounded."""
    if not chat_history:
        return "No previous conversation history."

    recent = chat_history[-max_messages:]
    lines = []
    total = 0
    for message in recent:
        role = message.get("role", "user").capitalize()
        content = message.get("content", "").strip()
        if not content:
            continue
        remaining = max_chars - total
        if remaining <= 0:
            break
        content = content[:remaining]
        lines.append(f"{role}: {content}")
        total += len(content) + len(role) + 2

    return "\n".join(lines) if lines else "No previous conversation history."
