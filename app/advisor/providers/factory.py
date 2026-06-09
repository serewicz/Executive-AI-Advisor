from functools import lru_cache

from app.advisor.providers.base import LLMError, LLMProvider
from app.advisor.providers.anthropic_provider import AnthropicChatProvider
from app.advisor.providers.grok_provider import GrokChatProvider
from app.advisor.providers.mock_provider import MockLLMProvider
from app.advisor.providers.openai_provider import OpenAIChatProvider
from app.core.config import settings


@lru_cache
def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    provider = (provider_name or settings.llm_provider or "mock").lower().strip()
    if provider == "mock":
        return MockLLMProvider()
    if provider == "openai":
        return OpenAIChatProvider()
    if provider == "anthropic":
        return AnthropicChatProvider()
    if provider == "grok":
        return GrokChatProvider()

    raise LLMError(f"Unsupported LLM provider '{provider}'. Use 'mock', 'openai', 'anthropic', or 'grok'.")
