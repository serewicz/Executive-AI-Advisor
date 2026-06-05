import re

from openai import OpenAI, OpenAIError

from app.core.config import settings


class EmbeddingError(RuntimeError):
    pass


def embed_texts(texts: list[str]) -> list[list[float]]:
    normalized_texts = [_normalize_whitespace(text) for text in texts]

    if not normalized_texts:
        raise EmbeddingError("At least one non-empty text is required for embedding.")
    if any(not text for text in normalized_texts):
        raise EmbeddingError("Embedding input cannot contain empty text.")
    if not settings.openai_api_key:
        raise EmbeddingError("OPENAI_API_KEY is required to generate embeddings.")

    client = OpenAI(api_key=settings.openai_api_key)
    embeddings: list[list[float]] = []

    try:
        for batch in _batched(normalized_texts, batch_size=50):
            response = client.embeddings.create(
                model=settings.embedding_model,
                input=batch,
            )
            embeddings.extend([item.embedding for item in sorted(response.data, key=lambda item: item.index)])
    except OpenAIError as exc:
        raise EmbeddingError(f"OpenAI embedding request failed: {exc}") from exc
    except Exception as exc:
        raise EmbeddingError(f"Embedding generation failed: {exc}") from exc

    return embeddings


def _batched(items: list[str], batch_size: int):
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
