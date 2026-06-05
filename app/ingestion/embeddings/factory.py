from functools import lru_cache

from app.core.config import settings
from app.ingestion.embeddings.base import EmbeddingError, EmbeddingProvider
from app.ingestion.embeddings.local import LocalEmbeddingProvider
from app.ingestion.embeddings.openai_provider import OpenAIEmbeddingProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.embedding_provider.lower().strip()
    if provider == "local":
        return LocalEmbeddingProvider()
    if provider == "openai":
        return OpenAIEmbeddingProvider()

    raise EmbeddingError(
        f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'. Use 'openai' or 'local'."
    )
