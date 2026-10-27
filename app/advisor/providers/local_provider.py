"""Local model through an OpenAI-compatible endpoint.

Ollama, the llama.cpp server, and vLLM expose ``/v1/chat/completions`` in the
OpenAI wire format, so this provider reuses ``OpenAIChatProvider`` and changes
only the endpoint, key, and default model. The model must support JSON output
(``response_format={"type": "json_object"}``); small models that ignore it
fail with ``LLMError`` and the caller sees "The model provider request failed."

Routing between providers and fallback rules are out of scope here (issue #24).
See docs/runbooks/updating-model-list.md for setup.
"""

from openai import OpenAI

from app.advisor.providers.openai_provider import OpenAIChatProvider
from app.core.config import settings


class LocalChatProvider(OpenAIChatProvider):
    provider_name = "local"
    display_name = "Local model"

    def _client(self, api_key_override: str | None) -> OpenAI:
        # Local servers usually ignore the key, but the OpenAI client requires a value.
        return OpenAI(api_key=settings.local_llm_api_key or "not-needed", base_url=settings.local_llm_base_url)

    def _default_model(self) -> str:
        return settings.local_llm_model
