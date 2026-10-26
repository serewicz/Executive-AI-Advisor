"""Model allowlist for MCP callers.

Reads ``config/models.yaml`` (path from ``MCP_MODEL_POLICY_FILE``). When the file
does not exist, each provider allows only the model configured in its
environment variable, which matches behavior before the allowlist existed for
callers that do not override the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import Settings

KNOWN_PROVIDERS = ("mock", "openai", "anthropic", "grok")


class ProviderPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_models: list[str] = Field(min_length=1)


class ModelPolicyFile(BaseModel):
    model_config = ConfigDict(extra="allow")  # ADR 0002 adds routes and fallback sections.
    providers: dict[str, ProviderPolicy]


class ModelPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class ModelPolicy:
    allowed: dict[str, frozenset[str]] = field(default_factory=dict)
    source: str = "environment"

    def is_allowed(self, provider: str, model: str | None) -> bool:
        provider = provider.lower().strip()
        if provider not in self.allowed:
            return False
        return model is None or model in self.allowed[provider]

    def describe(self) -> dict[str, list[str]]:
        return {provider: sorted(models) for provider, models in self.allowed.items()}


def policy_from_settings(settings: Settings) -> ModelPolicy:
    return ModelPolicy(
        allowed={
            "mock": frozenset({"mock"}),
            "openai": frozenset({settings.openai_chat_model}),
            "anthropic": frozenset({settings.anthropic_chat_model}),
            "grok": frozenset({settings.xai_chat_model}),
        },
        source="environment",
    )


def load_model_policy(settings: Settings, path: Path | None = None) -> ModelPolicy:
    path = path or settings.mcp_model_policy_file
    if not path.exists():
        return policy_from_settings(settings)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        parsed = ModelPolicyFile.model_validate(raw)
    except (yaml.YAMLError, ValidationError) as exc:
        raise ModelPolicyError(f"Invalid model policy file {path}: {exc}") from exc
    unknown = sorted(set(parsed.providers) - set(KNOWN_PROVIDERS))
    if unknown:
        raise ModelPolicyError(f"Unknown providers in {path}: {', '.join(unknown)}")
    return ModelPolicy(
        allowed={name: frozenset(p.allowed_models) for name, p in parsed.providers.items()},
        source=str(path),
    )
