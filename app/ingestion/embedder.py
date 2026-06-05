import re

from app.core.config import settings
from app.ingestion.embeddings import EmbeddingError
from app.ingestion.embeddings.factory import get_embedding_provider


def embed_texts(texts: list[str]) -> list[list[float]]:
    normalized_texts = [_normalize_whitespace(text) for text in texts]

    if not normalized_texts:
        raise EmbeddingError("At least one non-empty text is required for embedding.")
    if any(not text for text in normalized_texts):
        raise EmbeddingError("Embedding input cannot contain empty text.")
    if any(len(text) > settings.max_embedding_text_chars for text in normalized_texts):
        raise EmbeddingError(
            f"Embedding input exceeds the {settings.max_embedding_text_chars} character limit."
        )
    return get_embedding_provider().embed_texts(normalized_texts)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
