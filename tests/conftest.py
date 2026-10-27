"""Shared test setup."""

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _fallback_audit_file_in_tmp(tmp_path, monkeypatch):
    """Keep the fail-closed audit fallback file (ADR 0001) out of the working tree during tests."""
    monkeypatch.setattr(settings, "mcp_audit_fallback_file", tmp_path / "mcp_audit_fallback.jsonl")
