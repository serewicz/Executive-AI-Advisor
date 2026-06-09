from app.advisor.providers.base import (
    BoardMemoResponse,
    LLMProvider,
    LLMResponse,
    SourceContext,
    TechnologyDiligenceDraftResponse,
)


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

    def generate_board_summary(
        self,
        summary_type: str,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
    ) -> BoardMemoResponse:
        if not sources:
            return BoardMemoResponse(
                executive_summary="There is not enough retrieved evidence to prepare a board summary.",
                key_risks=[],
                evidence=[],
                board_questions=[],
                recommended_actions=[],
                limitations=["No source chunks were available for board summary generation."],
                confidence="low",
            )

        first_label = sources[0].label
        return BoardMemoResponse(
            executive_summary=(
                "The retrieved materials indicate governance, security, and operational risk themes "
                f"that warrant board attention. {first_label}"
            ),
            key_risks=[
                f"Governance and execution risk should be reviewed with management. {first_label}",
                f"Security and operational resilience controls may require further validation. {first_label}",
            ],
            evidence=[
                f"The retrieved source set includes document evidence tied to {summary_type}. {first_label}",
            ],
            board_questions=[
                f"What controls, owners, and timelines address the risks identified in {first_label}?",
            ],
            recommended_actions=[
                f"Ask management to map the cited risks to accountable owners and near-term milestones. {first_label}",
            ],
            limitations=["Mock provider response for local development; no LLM generation was performed."],
            confidence="medium",
        )

    def generate_technology_diligence_report(
        self,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
    ) -> TechnologyDiligenceDraftResponse:
        if not sources:
            return TechnologyDiligenceDraftResponse(
                executive_summary="There is not enough retrieved evidence to prepare a technology due diligence report.",
                top_5_risks=[],
                management_questions=[],
                board_discussion_points=[],
                recommended_actions=[],
                limitations=["No source chunks were available for report generation."],
                confidence="low",
            )

        first_label = sources[0].label
        return TechnologyDiligenceDraftResponse(
            executive_summary=(
                "The retrieved diligence materials indicate technology governance, security, operational, "
                f"and scalability themes that require management validation. {first_label}"
            ),
            top_5_risks=[
                f"Validate the highest-rated security, architecture, and key-person risks with management. {first_label}",
            ],
            management_questions=[
                f"What owners, evidence, and remediation dates support the cited diligence risks in {first_label}?",
            ],
            board_discussion_points=[
                f"Confirm whether management has the mandate and capacity to address cited technology risks. {first_label}",
            ],
            recommended_actions=[
                f"Map cited technology risks to accountable owners, dates, and board-visible operating metrics. {first_label}",
            ],
            limitations=["Mock provider response for local development; no LLM generation was performed."],
            confidence="medium",
        )
