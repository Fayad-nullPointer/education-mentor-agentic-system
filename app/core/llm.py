from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_llm() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
        temperature=0,
    )


@lru_cache(maxsize=1)
def get_agent_llm() -> ChatGoogleGenerativeAI:
    """Model tuned for tool-calling agent loops.

    Gemini 2.5 Flash is a *thinking* model. Under a large system prompt (such as
    the deepagents harness), reasoning tokens can consume the entire response
    budget and the model returns an empty message with ``finish_reason=STOP`` —
    no text and no tool call. Disabling thinking (``thinking_budget=0``) keeps
    the budget for the actual response, which the orchestrator/executor loops
    need to emit tool calls reliably.
    """
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
        temperature=0,
        thinking_budget=0,
    )
