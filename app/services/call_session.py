"""In-memory voice call session state."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.csv_store import customer_public_profile, find_customer_by_id


@dataclass
class CallSession:
    token: str
    customer_id: str
    customer_name: str
    customer_email: str
    customer_mobile: str
    kyc_verified: bool = False
    kyc_method: str = ""
    call_started_at: float = field(default_factory=time.time)
    topics: list[str] = field(default_factory=list)
    requests: list[str] = field(default_factory=list)
    transcript: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    resolved: bool = False

    def add_topic(self, topic: str) -> None:
        t = topic.strip()
        if t and t not in self.topics:
            self.topics.append(t)

    def add_request(self, request: str) -> None:
        r = request.strip()
        if r and r not in self.requests:
            self.requests.append(r)

    def add_transcript(self, role: str, text: str) -> None:
        if text.strip():
            self.transcript.append({"role": role, "text": text.strip()})

    def add_error(self, error: str) -> None:
        if error.strip():
            self.errors.append(error.strip())


_sessions: dict[str, CallSession] = {}


def create_session(customer_id: str) -> CallSession | None:
    customer = find_customer_by_id(customer_id)
    if not customer:
        return None
    token = secrets.token_urlsafe(32)
    session = CallSession(
        token=token,
        customer_id=customer["customer_id"],
        customer_name=customer["full_name"],
        customer_email=customer["email"],
        customer_mobile=customer["registered_mobile"],
    )
    _sessions[token] = session
    return session


def get_session(token: str) -> CallSession | None:
    return _sessions.get(token)


def end_session(token: str) -> CallSession | None:
    return _sessions.pop(token, None)


def reset_call_state(session: CallSession) -> None:
    """Clear per-call data but keep the logged-in session alive."""
    session.kyc_verified = False
    session.kyc_method = ""
    session.call_started_at = time.time()
    session.topics = []
    session.requests = []
    session.transcript = []
    session.errors = []
    session.resolved = False


def begin_voice_call(token: str) -> CallSession | None:
    """Prepare an existing login session for a new voice call."""
    session = get_session(token)
    if not session:
        return None
    reset_call_state(session)
    session.add_topic("voice_call_started")
    return session


def session_customer_context(token: str) -> dict[str, Any] | None:
    session = get_session(token)
    if not session:
        return None
    customer = find_customer_by_id(session.customer_id)
    if not customer:
        return None
    profile = customer_public_profile(customer)
    profile["kyc_verified_this_call"] = session.kyc_verified
    return profile
