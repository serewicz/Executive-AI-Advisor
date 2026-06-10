from app.advisor.providers.base import (
    BoardMemoResponse,
    LLMError,
    LLMProvider,
    LLMResponse,
    SourceContext,
    TechnologyDiligenceDraftResponse,
)
from app.advisor.providers.openai_provider import _json_payload, _normalize_confidence, _normalize_list
from app.advisor.text import normalize_text_field
from app.core.config import settings


class AnthropicChatProvider(LLMProvider):
    provider_name = "anthropic"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4000,
        api_key_override: str | None = None,
        model_override: str | None = None,
    ) -> str:
        api_key = api_key_override or settings.anthropic_api_key
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic.")

        try:
            from anthropic import Anthropic, AnthropicError
        except ImportError as exc:
            raise LLMError("anthropic package is required when LLM_PROVIDER=anthropic.") from exc

        client = Anthropic(api_key=api_key)
        try:
            response = client.messages.create(
                model=model_override or settings.anthropic_chat_model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AnthropicError as exc:
            raise LLMError(f"Anthropic chat request failed: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"Anthropic generation failed: {exc}") from exc

        text_parts = [
            getattr(block, "text", "")
            for block in response.content
            if getattr(block, "type", "") == "text"
        ]
        content = "".join(text_parts).strip()
        if not content:
            raise LLMError("Anthropic chat response did not include content.")
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
            "Anthropic chat response was not valid JSON.",
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
            "Anthropic board summary response was not valid JSON.",
        )
        memo = payload.get("memo", payload)
        if not isinstance(memo, dict):
            raise LLMError("Anthropic board summary response did not include a memo object.")
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
            "Anthropic technology diligence report response was not valid JSON.",
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
