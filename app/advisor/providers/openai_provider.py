import json

from openai import OpenAI, OpenAIError

from app.advisor.providers.base import BoardMemoResponse, LLMError, LLMProvider, LLMResponse, SourceContext
from app.core.config import settings


class OpenAIChatProvider(LLMProvider):
    def answer_question(
        self,
        question: str,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")

        client = OpenAI(api_key=settings.openai_api_key)

        try:
            response = client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except OpenAIError as exc:
            raise LLMError(f"OpenAI chat request failed: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"LLM generation failed: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMError("OpenAI chat response did not include content.")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError("OpenAI chat response was not valid JSON.") from exc

        return LLMResponse(
            answer=str(payload.get("answer", "")).strip(),
            confidence=_normalize_confidence(payload.get("confidence")),
            limitations=[
                str(limitation).strip()
                for limitation in payload.get("limitations", [])
                if str(limitation).strip()
            ],
        )

    def generate_board_summary(
        self,
        summary_type: str,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
    ) -> BoardMemoResponse:
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")

        client = OpenAI(api_key=settings.openai_api_key)

        try:
            response = client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except OpenAIError as exc:
            raise LLMError(f"OpenAI board summary request failed: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"Board summary generation failed: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMError("OpenAI board summary response did not include content.")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError("OpenAI board summary response was not valid JSON.") from exc

        memo = payload.get("memo", payload)
        if not isinstance(memo, dict):
            raise LLMError("OpenAI board summary response did not include a memo object.")

        return BoardMemoResponse(
            executive_summary=str(memo.get("executive_summary", "")).strip(),
            key_risks=_normalize_list(memo.get("key_risks")),
            evidence=_normalize_list(memo.get("evidence")),
            board_questions=_normalize_list(memo.get("board_questions")),
            recommended_actions=_normalize_list(memo.get("recommended_actions")),
            limitations=_normalize_list(memo.get("limitations")),
            confidence=_normalize_confidence(memo.get("confidence", payload.get("confidence"))),
        )


def _normalize_confidence(value) -> str:
    confidence = str(value or "low").lower().strip()
    if confidence in {"high", "medium", "low"}:
        return confidence
    return "low"


def _normalize_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    normalized = str(value).strip()
    return [normalized] if normalized else []
