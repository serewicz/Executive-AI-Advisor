from functools import lru_cache

from app.advisor.providers.base import LLMError, LLMProvider
from app.advisor.providers.mock_provider import MockLLMProvider
from app.advisor.providers.openai_provider import OpenAIChatProvider
from app.core.config import settings


@lru_cache
def get_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower().strip()
    if provider == "mock":
        return MockLLMProvider()
    if provider == "openai":
        return OpenAIChatProvider()

    raise LLMError(f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. Use 'mock' or 'openai'.")
