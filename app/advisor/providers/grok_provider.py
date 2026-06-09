from openai import OpenAI, OpenAIError

from app.advisor.providers.base import LLMError
from app.advisor.providers.openai_provider import OpenAIChatProvider
from app.core.config import settings


class GrokChatProvider(OpenAIChatProvider):
    provider_name = "grok"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4000,
        api_key_override: str | None = None,
        model_override: str | None = None,
    ) -> str:
        api_key = api_key_override or settings.xai_api_key
        if not api_key:
            raise LLMError("XAI_API_KEY is required when LLM_PROVIDER=grok.")

        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        try:
            response = client.chat.completions.create(
                model=model_override or settings.xai_chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except OpenAIError as exc:
            raise LLMError(f"xAI/Grok chat request failed: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"xAI/Grok generation failed: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMError("xAI/Grok chat response did not include content.")
        return content
