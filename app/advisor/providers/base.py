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
