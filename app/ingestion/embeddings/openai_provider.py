from openai import OpenAI, OpenAIError

from app.core.config import settings
from app.ingestion.embeddings.base import EmbeddingError, EmbeddingProvider, fit_embedding_dimensions


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not settings.openai_api_key:
            raise EmbeddingError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai.")

        client = OpenAI(api_key=settings.openai_api_key)
        embeddings: list[list[float]] = []

        try:
            for batch in _batched(texts, batch_size=50):
                response = client.embeddings.create(
                    model=settings.openai_embedding_model,
                    input=batch,
                )
                batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
                embeddings.extend([fit_embedding_dimensions(embedding) for embedding in batch_embeddings])
        except OpenAIError as exc:
            raise EmbeddingError(f"OpenAI embedding request failed: {exc}") from exc
        except Exception as exc:
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc

        return embeddings

    def embedding_dimension(self) -> int:
        return settings.embedding_dimensions


def _batched(items: list[str], batch_size: int):
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]
