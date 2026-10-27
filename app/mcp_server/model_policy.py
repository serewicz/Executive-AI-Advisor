"""Model allowlist for MCP callers.

Reads ``config/models.yaml`` (path from ``MCP_MODEL_POLICY_FILE``). When the file
does not exist, each provider allows only the model configured in its
environment variable, which matches behavior before the allowlist existed for
callers that do not override the model.

File format (see config/models.example.yaml and
docs/runbooks/updating-model-list.md)::

    as_of: "2026-10-25"          # date someone last checked the list
    providers:
      openai:
        models:
          - id: gpt-6-luna
            notes: Low-cost default.
      local:
        base_url: http://127.0.0.1:11434/v1   # must match LOCAL_LLM_BASE_URL
        models:
          - id: llama3.2:3b

The older ``allowed_models: [id, ...]`` form is still accepted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.config import Settings

KNOWN_PROVIDERS = ("mock", "openai", "anthropic", "grok", "local")


class ModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=120)
    notes: str | None = None


class ProviderPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    models: list[ModelEntry] = Field(default_factory=list)
    allowed_models: list[str] = Field(default_factory=list)  # older form, still accepted
    base_url: str | None = None  # local provider only; pins the endpoint
    notes: str | None = None

    @model_validator(mode="after")
    def _has_models(self) -> "ProviderPolicy":
        if not self.models and not self.allowed_models:
            raise ValueError("each provider needs at least one entry under models")
        return self

    def model_ids(self) -> list[str]:
        return [entry.id for entry in self.models] + list(self.allowed_models)


class ModelPolicyFile(BaseModel):
    model_config = ConfigDict(extra="allow")  # ADR 0002 adds routes and fallback sections.
    as_of: str | None = None
    providers: dict[str, ProviderPolicy]


class ModelPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class ModelPolicy:
    allowed: dict[str, frozenset[str]] = field(default_factory=dict)
    source: str = "environment"
    as_of: str | None = None

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
            "local": frozenset({settings.local_llm_model}),
        },
        source="environment",
    )


_UNPINNED = (
    "LOCAL_LLM_BASE_URL is set but {where}. Add a local block with base_url equal to "
    "LOCAL_LLM_BASE_URL to config/models.yaml, or unset LOCAL_LLM_BASE_URL. "
    "See docs/runbooks/updating-model-list.md."
)


def load_model_policy(settings: Settings, path: Path | None = None) -> ModelPolicy:
    path = path or settings.mcp_model_policy_file
    base_url_set = "local_llm_base_url" in settings.model_fields_set
    if not path.exists():
        if base_url_set:
            raise ModelPolicyError(_UNPINNED.format(where=f"{path} does not exist"))
        return policy_from_settings(settings)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        parsed = ModelPolicyFile.model_validate(raw)
    except (yaml.YAMLError, ValidationError) as exc:
        raise ModelPolicyError(f"Invalid model policy file {path}: {exc}") from exc
    unknown = sorted(set(parsed.providers) - set(KNOWN_PROVIDERS))
    if unknown:
        raise ModelPolicyError(f"Unknown providers in {path}: {', '.join(unknown)}")
    local = parsed.providers.get("local")
    if base_url_set and (local is None or local.base_url is None):
        raise ModelPolicyError(_UNPINNED.format(where=f"{path} has no providers.local.base_url"))
    if local is not None and local.base_url is not None:
        if local.base_url.rstrip("/") != settings.local_llm_base_url.rstrip("/"):
            raise ModelPolicyError(
                f"{path}: providers.local.base_url does not match LOCAL_LLM_BASE_URL. "
                "Update one so they agree; the file pins the approved endpoint."
            )
    return ModelPolicy(
        allowed={name: frozenset(p.model_ids()) for name, p in parsed.providers.items()},
        source=str(path),
        as_of=parsed.as_of,
    )


def env_default_gaps(policy: ModelPolicy, settings: Settings) -> list[str]:
    """Providers whose environment default model is not in the allowlist.

    Calls that omit llm_model use that default, so each gap means such calls are denied.
    """
    defaults = policy_from_settings(settings).allowed
    gaps = []
    for provider, models in sorted(policy.allowed.items()):
        default = next(iter(defaults.get(provider, frozenset())), None)
        if default is not None and default not in models:
            gaps.append(f"{provider}: default model {default!r} is not listed")
    return gaps


def main(argv: list[str] | None = None) -> int:
    """Validate a model policy file: ``python -m app.mcp_server.model_policy [path]``."""
    import sys

    from app.core.config import settings as current

    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else current.mcp_model_policy_file
    if not path.exists():
        print(f"{path} not found. The server would use the environment defaults only.")
        return 1
    try:
        policy = load_model_policy(current, path)
    except ModelPolicyError as exc:
        print(f"INVALID: {exc}")
        return 1
    print(f"OK: {path} (as_of {policy.as_of or 'not set'})")
    for provider, models in policy.describe().items():
        print(f"  {provider}: {', '.join(models)}")
    for gap in env_default_gaps(policy, current):
        print(f"WARNING: {gap}. Calls that omit llm_model for this provider will be denied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
