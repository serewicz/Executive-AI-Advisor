from abc import ABC, abstractmethod

from app.core.config import settings


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        pass

    @abstractmethod
    def embedding_dimension(self) -> int:
        pass


def fit_embedding_dimensions(embedding: list[float]) -> list[float]:
    target_dimensions = settings.embedding_dimensions
    if len(embedding) == target_dimensions:
        return embedding
    if len(embedding) > target_dimensions:
        return embedding[:target_dimensions]

    return embedding + [0.0] * (target_dimensions - len(embedding))
