import json

from openai import OpenAI, OpenAIError

from app.advisor.providers.base import (
    BoardMemoResponse,
    LLMError,
    LLMProvider,
    LLMResponse,
    SourceContext,
    TechnologyDiligenceDraftResponse,
)
from app.advisor.text import normalize_text_field
from app.core.config import settings


class OpenAIChatProvider(LLMProvider):
    provider_name = "openai"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4000,
        api_key_override: str | None = None,
        model_override: str | None = None,
    ) -> str:
        api_key = api_key_override or settings.openai_api_key
        if not api_key:
            raise LLMError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")

        client = OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=model_override or settings.openai_chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except OpenAIError as exc:
            raise LLMError(f"OpenAI chat request failed: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"LLM generation failed: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMError("OpenAI chat response did not include content.")
        return content

    def answer_question(
        self,
        question: str,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
        api_key_override: str | None = None,
        model_override: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        payload = _json_payload(
            self.generate(system_prompt, user_prompt, temperature, max_tokens, api_key_override, model_override),
            "OpenAI chat response was not valid JSON.",
        )
        return LLMResponse(
            answer=normalize_text_field(payload.get("answer", "")),
            confidence=_normalize_confidence(payload.get("confidence")),
            limitations=_normalize_list(payload.get("limitations")),
        )

    def generate_board_summary(
        self,
        summary_type: str,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
        api_key_override: str | None = None,
        model_override: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4000,
    ) -> BoardMemoResponse:
        payload = _json_payload(
            self.generate(system_prompt, user_prompt, temperature, max_tokens, api_key_override, model_override),
            "OpenAI board summary response was not valid JSON.",
        )
        memo = payload.get("memo", payload)
        if not isinstance(memo, dict):
            raise LLMError("OpenAI board summary response did not include a memo object.")

        return BoardMemoResponse(
            executive_summary=normalize_text_field(memo.get("executive_summary", "")),
            key_risks=_normalize_list(memo.get("key_risks")),
            evidence=_normalize_list(memo.get("evidence")),
            board_questions=_normalize_list(memo.get("board_questions")),
            recommended_actions=_normalize_list(memo.get("recommended_actions")),
            limitations=_normalize_list(memo.get("limitations")),
            confidence=_normalize_confidence(memo.get("confidence", payload.get("confidence"))),
        )

    def generate_technology_diligence_report(
        self,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
        api_key_override: str | None = None,
        model_override: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4000,
    ) -> TechnologyDiligenceDraftResponse:
        payload = _json_payload(
            self.generate(system_prompt, user_prompt, temperature, max_tokens, api_key_override, model_override),
            "OpenAI technology diligence report response was not valid JSON.",
        )
        return TechnologyDiligenceDraftResponse(
            executive_summary=normalize_text_field(payload.get("executive_summary", "")),
            top_5_risks=_normalize_list(payload.get("top_5_risks")),
            management_questions=_normalize_list(payload.get("management_questions")),
            board_discussion_points=_normalize_list(payload.get("board_discussion_points")),
            recommended_actions=_normalize_list(payload.get("recommended_actions")),
            limitations=_normalize_list(payload.get("limitations")),
            confidence=_normalize_confidence(payload.get("confidence")),
        )


def _json_payload(content: str, error_message: str) -> dict:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(error_message) from exc
    if not isinstance(payload, dict):
        raise LLMError(error_message)
    return payload


def _normalize_confidence(value) -> str:
    confidence = str(value or "low").lower().strip()
    if confidence in {"high", "medium", "low"}:
        return confidence
    return "low"


def _normalize_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_text_field(item) for item in value if normalize_text_field(item)]
    normalized = normalize_text_field(value)
    return [normalized] if normalized else []
