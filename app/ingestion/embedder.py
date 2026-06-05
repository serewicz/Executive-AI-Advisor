import re
from abc import ABC, abstractmethod

from openai import OpenAI, OpenAIError

from app.core.config import settings


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not settings.openai_api_key:
            raise EmbeddingError("OPENAI_API_KEY is required to generate OpenAI embeddings.")

        client = OpenAI(api_key=settings.openai_api_key)
        embeddings: list[list[float]] = []

        try:
            for batch in _batched(texts, batch_size=50):
                response = client.embeddings.create(
                    model=settings.embedding_model,
                    input=batch,
                )
                batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
                embeddings.extend([_fit_embedding_dimensions(embedding) for embedding in batch_embeddings])
        except OpenAIError as exc:
            raise EmbeddingError(f"OpenAI embedding request failed: {exc}") from exc
        except Exception as exc:
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc

        return embeddings


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self._model = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            model = self._get_model()
            embeddings = model.encode(
                texts,
                batch_size=50,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return [_fit_embedding_dimensions(embedding.tolist()) for embedding in embeddings]
        except Exception as exc:
            raise EmbeddingError(f"Local embedding generation failed: {exc}") from exc

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingError(
                    "sentence-transformers is required when EMBEDDING_PROVIDER=local."
                ) from exc

            self._model = SentenceTransformer(settings.local_embedding_model)

        return self._model


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


def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.embedding_provider.lower().strip()
    if provider == "openai":
        return OpenAIEmbeddingProvider()
    if provider == "local":
        return SentenceTransformerEmbeddingProvider()

    raise EmbeddingError(
        f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'. Use 'openai' or 'local'."
    )


def _batched(items: list[str], batch_size: int):
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _fit_embedding_dimensions(embedding: list[float]) -> list[float]:
    target_dimensions = settings.embedding_dimensions
    if len(embedding) == target_dimensions:
        return embedding
    if len(embedding) > target_dimensions:
        return embedding[:target_dimensions]

    return embedding + [0.0] * (target_dimensions - len(embedding))
