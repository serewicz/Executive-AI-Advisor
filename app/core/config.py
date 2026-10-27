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
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    openai_chat_model: str = Field(default="gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_chat_model: str = Field(default="claude-3-5-sonnet-latest", alias="ANTHROPIC_CHAT_MODEL")
    xai_api_key: str | None = Field(default=None, alias="XAI_API_KEY")
    xai_chat_model: str = Field(default="grok-4.3", alias="XAI_CHAT_MODEL")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=4000, alias="LLM_MAX_TOKENS")
    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    local_embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="LOCAL_EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    max_embedding_chunks_per_request: int = Field(default=200, alias="MAX_EMBEDDING_CHUNKS_PER_REQUEST")
    max_embedding_text_chars: int = Field(default=12000, alias="MAX_EMBEDDING_TEXT_CHARS")
    max_search_query_chars: int = Field(default=2000, alias="MAX_SEARCH_QUERY_CHARS")

    # MCP server (see docs/adr/0001-mcp-hardening-and-audit-log.md)
    mcp_auth_tokens: str | None = Field(default=None, alias="MCP_AUTH_TOKENS")
    mcp_allow_insecure_bind: bool = Field(default=False, alias="MCP_ALLOW_INSECURE_BIND")
    mcp_model_policy_file: Path = Field(default=Path("config/models.yaml"), alias="MCP_MODEL_POLICY_FILE")
    mcp_rate_limit_read_per_minute: int = Field(default=60, ge=1, alias="MCP_RATE_LIMIT_READ_PER_MINUTE")
    mcp_rate_limit_llm_per_minute: int = Field(default=10, ge=1, alias="MCP_RATE_LIMIT_LLM_PER_MINUTE")
    mcp_rate_limit_llm_per_day: int = Field(default=200, ge=1, alias="MCP_RATE_LIMIT_LLM_PER_DAY")
    mcp_audit_store_text: bool = Field(default=False, alias="MCP_AUDIT_STORE_TEXT")
    # HMAC key for free-text audit hashes. Required for HTTP on a non-loopback host.
    mcp_audit_hash_key: str | None = Field(default=None, alias="MCP_AUDIT_HASH_KEY")
    # Fail-closed audit (ADR 0001). false = no override; an unaudited call always fails.
    mcp_audit_allow_unaudited_override: bool = Field(default=True, alias="MCP_AUDIT_ALLOW_UNAUDITED_OVERRIDE")
    # After an audit write failure, refuse model tools for this many seconds before calling the
    # provider, unless the caller passes accept_unaudited. 0 turns the breaker off.
    mcp_audit_breaker_seconds: int = Field(default=30, ge=0, alias="MCP_AUDIT_BREAKER_SECONDS")
    mcp_audit_fallback_file: Path = Field(
        default=Path("data/audit/mcp_audit_fallback.jsonl"), alias="MCP_AUDIT_FALLBACK_FILE"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
