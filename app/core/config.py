from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Executive AI Advisor"
    app_env: str = "development"
    app_debug: bool = True

    database_url: str = Field(
        default="postgresql+psycopg://executive_ai:change_me_in_local_development@localhost:5432/executive_ai_advisor",
        alias="DATABASE_URL",
    )
    upload_dir: Path = Field(default=Path("data/uploads"), alias="UPLOAD_DIR")
    max_upload_mb: int = Field(default=25, alias="MAX_UPLOAD_MB")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    local_embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="LOCAL_EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    max_embedding_chunks_per_request: int = Field(default=200, alias="MAX_EMBEDDING_CHUNKS_PER_REQUEST")
    max_embedding_text_chars: int = Field(default=12000, alias="MAX_EMBEDDING_TEXT_CHARS")
    max_search_query_chars: int = Field(default=2000, alias="MAX_SEARCH_QUERY_CHARS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
