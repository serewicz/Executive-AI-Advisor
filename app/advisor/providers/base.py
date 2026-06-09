from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMResponse:
    answer: str
    confidence: str
    limitations: list[str]


@dataclass(frozen=True)
class BoardMemoResponse:
    executive_summary: str
    key_risks: list[str]
    evidence: list[str]
    board_questions: list[str]
    recommended_actions: list[str]
    limitations: list[str]
    confidence: str


@dataclass(frozen=True)
class TechnologyDiligenceDraftResponse:
    executive_summary: str
    top_5_risks: list[str]
    management_questions: list[str]
    board_discussion_points: list[str]
    recommended_actions: list[str]
    limitations: list[str]
    confidence: str


@dataclass(frozen=True)
class SourceContext:
    label: str
    content: str
    document_title: str
    page_start: int
    page_end: int


class LLMProvider(ABC):
    @abstractmethod
    def answer_question(
        self,
        question: str,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:
        pass

    @abstractmethod
    def generate_board_summary(
        self,
        summary_type: str,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
    ) -> BoardMemoResponse:
        pass

    @abstractmethod
    def generate_technology_diligence_report(
        self,
        sources: list[SourceContext],
        system_prompt: str,
        user_prompt: str,
    ) -> TechnologyDiligenceDraftResponse:
        pass
