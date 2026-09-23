from typing import Dict, List


def format_chat_history(chat_history: List[Dict[str, str]], max_messages: int = 6, max_chars: int = 3500) -> str:
    """Return a compact recent history to keep every LLM request bounded.

    `chat_history` is the runtime `messages` list from LangGraph checkpointed
    state (list of {"role": ..., "content": ...} dicts) for the current
    session/thread. Runtime persistence itself is handled by the graph's
    checkpointer, not by this module.
    """
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
