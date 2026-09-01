from typing import Optional

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

    return ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=model,
        temperature=final_temp,
        max_tokens=max_tokens,
        max_retries=2,
    )
