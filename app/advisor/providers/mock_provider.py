from app.advisor.providers.base import LLMProvider, LLMResponse, SourceContext


class MockLLMProvider(LLMProvider):
    def answer_question(
        self,
        question: str,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:
        if not sources:
            return LLMResponse(
                answer="I do not have enough retrieved evidence to answer this question.",
                confidence="low",
                limitations=["No relevant source chunks were retrieved."],
            )

        return LLMResponse(
            answer=(
                "Based on the retrieved sources, the main issues are governance, "
                f"security, and operational risk. {sources[0].label}"
            ),
            confidence="medium",
            limitations=["Mock provider response for local development; no LLM generation was performed."],
        )
