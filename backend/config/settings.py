from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "AI Fitness & Nutrition Assistant"
    API_V1_STR: str = "/api/v1"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_ROUTER_MODEL: str = "openai/gpt-oss-20b"

    # Hard output caps keep latency, TPM usage and cost predictable.
    MAX_OUTPUT_TOKENS: int = 700
    ROUTER_MAX_OUTPUT_TOKENS: int = 180
    GENERAL_MAX_OUTPUT_TOKENS: int = 450
    GYM_MAX_OUTPUT_TOKENS: int = 450

    TEMPERATURE: float = 0.2
    SERPER_API_KEY: str = ""
    GEOAPIFY_API_KEY: str = ""


settings = Settings()
