"""Thread-local session token for tool execution."""

from __future__ import annotations

from contextvars import ContextVar

_session_token: ContextVar[str | None] = ContextVar("session_token", default=None)


def set_session_token(token: str | None) -> None:
    _session_token.set(token)


def get_session_token() -> str | None:
    return _session_token.get()
