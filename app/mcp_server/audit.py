"""Audit records for MCP calls.

Every tool call, resource read, and prompt request produces one ``AuditRecord``.
Free text (``query``, ``question``, ``meeting_focus``) is stored as a SHA-256
hash plus length unless ``MCP_AUDIT_STORE_TEXT=true``, so the audit table does
not become a second copy of sensitive questions.

Recording fails open: if the write fails, the call still returns and the
failure is logged at ERROR with the correlation ID. The rationale is in ADR 0001.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger("eaia.mcp.audit")

FREE_TEXT_ARGUMENTS = frozenset({"query", "question", "meeting_focus"})


@dataclass
class AuditRecord:
    correlation_id: UUID
    client_id: str
    transport: str
    kind: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    document_set_id: UUID | None = None
    outcome: str = "ok"
    error_class: str | None = None
    duration_ms: int = 0
    provider: str | None = None
    model: str | None = None
    request_id: UUID | None = None
    detail: str | None = None


class AuditSink(Protocol):
    def write(self, record: AuditRecord) -> None: ...


def redact_arguments(arguments: dict[str, Any], store_text: bool) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in arguments.items():
        if value is None:
            continue
        if key in FREE_TEXT_ARGUMENTS and isinstance(value, str) and not store_text:
            redacted[key] = {"sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(), "length": len(value)}
        elif isinstance(value, (str, int, float, bool)):
            redacted[key] = value
        else:
            redacted[key] = str(value)
    return redacted


class MemoryAuditSink:
    """Keeps records in a list. For tests and local experiments."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def write(self, record: AuditRecord) -> None:
        self.records.append(record)


class DatabaseAuditSink:
    """Writes each record in its own short transaction, separate from the tool's session."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def write(self, record: AuditRecord) -> None:
        from app.models.audit import MCPAuditEvent

        session = self._session_factory()
        try:
            session.add(MCPAuditEvent(**asdict(record)))
            session.commit()
        finally:
            session.close()


class FailOpenAuditSink:
    """Wraps a sink. Emits a structured log line for every record and never raises."""

    def __init__(self, inner: AuditSink) -> None:
        self._inner = inner

    def write(self, record: AuditRecord) -> None:
        logger.info(
            json.dumps(
                {
                    "event": "mcp_call",
                    "correlation_id": str(record.correlation_id),
                    "client_id": record.client_id,
                    "kind": record.kind,
                    "name": record.name,
                    "outcome": record.outcome,
                    "duration_ms": record.duration_ms,
                }
            )
        )
        try:
            self._inner.write(record)
        except Exception:  # noqa: BLE001 - audit failure must not change the tool result
            logger.exception("Audit write failed. correlation_id=%s", record.correlation_id)
