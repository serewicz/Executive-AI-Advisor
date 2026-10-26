"""Errors that are safe to show to API and MCP clients.

Service code raises domain exceptions. Adapters (the MCP server today) convert
them to a ``PublicError`` before anything leaves the process. Only
``public_message`` is sent to the client; the original exception stays in the
server log under the same correlation ID.
"""

from __future__ import annotations

from uuid import UUID


class PublicError(Exception):
    """Base class. ``public_message`` must never contain upstream text."""

    category = "internal"

    def __init__(self, public_message: str, correlation_id: UUID | None = None) -> None:
        super().__init__(public_message)
        self.public_message = public_message
        self.correlation_id = correlation_id

    def client_text(self) -> str:
        if self.correlation_id is None:
            return self.public_message
        return f"{self.public_message} Reference: {self.correlation_id}"


class NotFound(PublicError):
    category = "not_found"


class InvalidInput(PublicError):
    category = "invalid_input"


class Denied(PublicError):
    category = "denied"


class RateLimited(PublicError):
    category = "rate_limited"

    def __init__(self, retry_after_seconds: int, correlation_id: UUID | None = None) -> None:
        super().__init__(f"Rate limit exceeded. Retry after {retry_after_seconds} seconds.", correlation_id)
        self.retry_after_seconds = retry_after_seconds


class ProviderUnavailable(PublicError):
    category = "provider_unavailable"


class Internal(PublicError):
    category = "internal"
