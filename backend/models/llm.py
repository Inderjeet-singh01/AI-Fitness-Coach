from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, Optional

from langchain_groq import ChatGroq

from config.settings import settings


def get_llm(temperature: Optional[float] = None, *, purpose: str = "generation") -> ChatGroq:
    """Return a shared, cost-controlled Groq chat model configuration."""
    final_temp = temperature if temperature is not None else settings.TEMPERATURE

    if purpose == "router":
        model = settings.GROQ_ROUTER_MODEL
        max_tokens = settings.ROUTER_MAX_OUTPUT_TOKENS
    elif purpose == "general":
        model = settings.GROQ_ROUTER_MODEL
        max_tokens = settings.GENERAL_MAX_OUTPUT_TOKENS
    elif purpose == "gym":
        model = settings.GROQ_ROUTER_MODEL
        max_tokens = settings.GYM_MAX_OUTPUT_TOKENS
    else:
        model = settings.GROQ_MODEL
        max_tokens = settings.MAX_OUTPUT_TOKENS

    # langchain-groq 0.2.x predates gpt-oss, so reasoning_effort is sent as a
    # raw request field. Only gpt-oss models accept it.
    model_kwargs: Dict[str, Any] = {}
    if settings.REASONING_EFFORT and model.startswith("openai/gpt-oss"):
        model_kwargs["extra_body"] = {"reasoning_effort": settings.REASONING_EFFORT}

    return ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=model,
        temperature=final_temp,
        max_tokens=max_tokens,
        max_retries=settings.LLM_MAX_RETRIES,
        model_kwargs=model_kwargs,
    )


# --- Per-turn LLM accounting -------------------------------------------------

class TurnHalted(Exception):
    """Base for conditions that must stop the whole turn, not fail a task."""
    kind = "halted"


class LLMRateLimited(TurnHalted):
    """Groq returned 429 and the SDK's retries (retry-after aware) ran out."""
    kind = "rate_limited"


class LLMBudgetExceeded(TurnHalted):
    """The per-turn LLM call/token budget is spent."""
    kind = "budget_exhausted"


def _is_rate_limit(exc: Exception) -> bool:
    try:
        import groq
        if isinstance(exc, groq.RateLimitError):
            return True
    except ImportError:  # pragma: no cover
        pass
    text = str(exc).lower()
    return "error code: 429" in text or "rate_limit" in text or "tokens per minute" in text


class LLMMeter:
    """Counts LLM calls/tokens for the current turn and remembers how the
    most recent call finished, so a worker can reject truncated output."""

    def __init__(self, calls: int = 0, tokens: int = 0):
        self.calls = calls
        self.tokens = tokens
        self.calls_in_node = 0
        self.last_finish_reason: Optional[str] = None

    def check_budget(self) -> None:
        if self.calls >= settings.MAX_LLM_CALLS_PER_TURN:
            raise LLMBudgetExceeded(f"per-turn LLM call limit ({settings.MAX_LLM_CALLS_PER_TURN}) reached")
        if self.tokens >= settings.MAX_LLM_TOKENS_PER_TURN:
            raise LLMBudgetExceeded(f"per-turn LLM token limit ({settings.MAX_LLM_TOKENS_PER_TURN}) reached")

    def record(self, response: Any, inputs: Any) -> None:
        self.calls += 1
        self.calls_in_node += 1
        metadata = getattr(response, "response_metadata", None) or {}
        self.last_finish_reason = metadata.get("finish_reason")
        usage = getattr(response, "usage_metadata", None) or {}
        total = usage.get("total_tokens") or (metadata.get("token_usage") or {}).get("total_tokens")
        if not total:
            # Streaming responses may carry no usage; estimate (~4 chars/token).
            total = (len(str(inputs)) + len(str(getattr(response, "content", "") or ""))) // 4
        self.tokens += int(total)

    def state_update(self) -> Dict[str, int]:
        return {"llm_calls": self.calls, "llm_tokens": self.tokens}


_current_meter: ContextVar[Optional[LLMMeter]] = ContextVar("llm_meter", default=None)


@contextmanager
def llm_meter(state: Dict[str, Any], reset: bool = False) -> Iterator[LLMMeter]:
    """Activate a meter for one graph node, seeded from this turn's counters."""
    meter = LLMMeter(0, 0) if reset else LLMMeter(state.get("llm_calls") or 0, state.get("llm_tokens") or 0)
    token = _current_meter.set(meter)
    try:
        yield meter
    finally:
        _current_meter.reset(token)


def call_llm(runnable: Any, inputs: Dict[str, Any]) -> Any:
    """Invoke an LLM chain under the turn budget.

    Raises LLMBudgetExceeded before the call when the budget is spent and
    LLMRateLimited when Groq still answers 429 after the SDK's retries, so
    callers can stop the turn instead of treating it as a task failure.
    """
    meter = _current_meter.get()
    if meter is not None:
        meter.check_budget()
    try:
        response = runnable.invoke(inputs)
    except Exception as exc:
        if _is_rate_limit(exc):
            raise LLMRateLimited(str(exc)[:300]) from exc
        raise
    if meter is not None:
        meter.record(response, inputs)
    return response


def last_finish_reason() -> Optional[str]:
    meter = _current_meter.get()
    return meter.last_finish_reason if meter else None


def calls_in_current_node() -> int:
    meter = _current_meter.get()
    return meter.calls_in_node if meter else 0
