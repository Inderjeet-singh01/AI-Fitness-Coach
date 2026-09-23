from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "AI Fitness & Nutrition Assistant"
    API_V1_STR: str = "/api/v1"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_ROUTER_MODEL: str = "openai/gpt-oss-20b"

    # Hard output caps keep latency, TPM usage and cost predictable.
    MAX_OUTPUT_TOKENS: int = 700
    # The router model (gpt-oss) spends part of this budget on hidden
    # reasoning tokens before emitting visible content. The planner's output
    # grew from a one-line {"selected_tools": [...]} to a full plan (goal +
    # success_criteria + a task per capability), so 180 was no longer enough
    # headroom and could return empty content on larger plans.
    ROUTER_MAX_OUTPUT_TOKENS: int = 700
    GENERAL_MAX_OUTPUT_TOKENS: int = 450
    GYM_MAX_OUTPUT_TOKENS: int = 450

    TEMPERATURE: float = 0.2
    SERPER_API_KEY: str = ""
    GEOAPIFY_API_KEY: str = ""

    # Termination protection for the plan -> execute -> evaluate -> replan
    # loop (a single chat turn may pass through the executor multiple times
    # across replans, so this is a hard cap across the whole turn, not per
    # plan). MAX_REPLANS bounds how many times the evaluator may send the
    # loop back through the replanner before it stops and reports honestly.
    MAX_REPLANS: int = 3
    MAX_EXECUTION_STEPS: int = 20

    # Per-task retry policy: a task that fails (execution error, empty/
    # truncated output, or evaluation) is retried at most this many times per
    # turn, and never again once it fails for the same reason twice.
    MAX_TASK_RETRIES: int = 2

    # Per-turn LLM budget. When either is reached the turn stops cleanly and
    # reports what was completed instead of silently draining the quota.
    MAX_LLM_CALLS_PER_TURN: int = 20
    MAX_LLM_TOKENS_PER_TURN: int = 30000

    # Groq SDK retries per call on 429/5xx (it honours retry-after). Once
    # exhausted the turn stops with status "rate_limited"; it never replans.
    LLM_MAX_RETRIES: int = 2

    # gpt-oss reasoning effort ("low" | "medium" | "high"; "" = provider
    # default). Hidden reasoning tokens count against max_tokens, so "low"
    # leaves room for the visible answer instead of returning empty content.
    REASONING_EFFORT: str = "low"


settings = Settings()
