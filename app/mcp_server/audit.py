"""Audit records for MCP calls.

Every tool call, resource read, and prompt request produces one ``AuditRecord``.
Free text (``query``, ``question``, ``meeting_focus``) is stored as a SHA-256
hash plus length unless ``MCP_AUDIT_STORE_TEXT=true``, so the audit table does
not become a second copy of sensitive questions.

Recording fails closed. ``CallGuard`` withholds a result it could not audit.
A caller may re-call a tool with ``accept_unaudited=true``; if the database
write fails again, the override is recorded in ``FallbackAuditFile`` (an
append-only JSON Lines file) before the result is returned. The rationale is in
ADR 0001.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import json
import logging
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
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


MIN_HASH_KEY_LENGTH = 32


class AuditHashKeyError(ValueError):
    """MCP_AUDIT_HASH_KEY is missing where required, or too short."""


def resolve_hash_key(configured: str | None, *, required: bool) -> bytes:
    """Return the HMAC key for free-text audit hashes.

    With no key configured and ``required`` false (stdio, loopback HTTP), a random key is
    generated for this process. Hashes then match only within one process lifetime.
    """
    if configured:
        if len(configured) < MIN_HASH_KEY_LENGTH:
            raise AuditHashKeyError(f"MCP_AUDIT_HASH_KEY must be at least {MIN_HASH_KEY_LENGTH} characters.")
        return configured.encode("utf-8")
    if required:
        raise AuditHashKeyError(
            "MCP_AUDIT_HASH_KEY is required for HTTP on a non-loopback host. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    logger.warning(
        "MCP_AUDIT_HASH_KEY is not set. Using a random key for this process; free-text audit hashes "
        "will not match across restarts."
    )
    return secrets.token_bytes(32)


def hash_text(value: str, key: bytes) -> str:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def redact_arguments(arguments: dict[str, Any], store_text: bool, hash_key: bytes | None = None) -> dict[str, Any]:
    if not store_text and not hash_key:
        raise AuditHashKeyError("A hash key is required unless free text is stored.")
    redacted: dict[str, Any] = {}
    for key, value in arguments.items():
        if value is None:
            continue
        if key in FREE_TEXT_ARGUMENTS and isinstance(value, str) and not store_text:
            redacted[key] = {"hmac_sha256": hash_text(value, hash_key), "length": len(value)}
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


class AuditWriteError(RuntimeError):
    """The audit record could not be written. The cause is chained, never sent to clients."""


class LoggingAuditSink:
    """Wraps a sink. Emits a structured log line for every record, then writes to the inner sink.

    Any failure in the inner sink is raised as ``AuditWriteError`` so ``CallGuard``
    can withhold the result (fail closed).
    """

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
        except Exception as exc:  # noqa: BLE001 - any sink failure means the call is not audited
            logger.error(
                "Audit write failed. correlation_id=%s error_class=%s", record.correlation_id, type(exc).__name__
            )
            raise AuditWriteError("audit write failed") from exc


class FallbackAuditFile:
    """Append-only JSON Lines file used when the audit table cannot be written.

    One line per event. Lines are written with O_APPEND and fsync so a crash
    after ``append`` returns does not lose the line. The file holds the same
    redacted fields as the table plus an ``event`` name:

    - ``audit_refused``: the call was blocked because the table write failed.
    - ``unaudited_override``: the caller accepted an unaudited result.

    Operators reconcile this file into ``mcp_audit_events`` after an outage
    (see docs/runbooks/mcp-operations.md). The application never truncates it.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append(self, event: str, record: AuditRecord, db_error_class: str | None) -> None:
        payload = {key: value for key, value in asdict(record).items()}
        payload.update(
            {
                "event": event,
                "logged_at": datetime.now(UTC).isoformat(),
                "audit_db_error_class": db_error_class,
            }
        )
        line = json.dumps(payload, default=str, sort_keys=True) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
