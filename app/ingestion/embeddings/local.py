from app.core.config import settings
from app.ingestion.embeddings.base import EmbeddingError, EmbeddingProvider, fit_embedding_dimensions


class LocalEmbeddingProvider(EmbeddingProvider):
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
            return [fit_embedding_dimensions(embedding.tolist()) for embedding in embeddings]
        except Exception as exc:
            raise EmbeddingError(f"Local embedding generation failed: {exc}") from exc

    def embedding_dimension(self) -> int:
        return settings.embedding_dimensions

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
