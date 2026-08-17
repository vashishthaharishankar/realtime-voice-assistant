"""Support ticket logging to CSV."""

from __future__ import annotations

import csv
import secrets
from datetime import datetime, timezone
from pathlib import Path

from app.services.call_session import CallSession

ROOT = Path(__file__).resolve().parent.parent.parent
TICKETS_PATH = ROOT / "database" / "support_tickets.csv"

HEADERS = [
    "ticket_id",
    "customer_id",
    "customer_name",
    "customer_email",
    "customer_mobile",
    "call_started_at",
    "call_ended_at",
    "duration_seconds",
    "topics_discussed",
    "requests_made",
    "kyc_verified",
    "resolved",
    "errors",
    "agent_notes",
    "created_at",
]


def _ensure_header() -> None:
    if not TICKETS_PATH.exists() or TICKETS_PATH.stat().st_size == 0:
        TICKETS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TICKETS_PATH.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=HEADERS)
            writer.writeheader()


def log_support_ticket(session: CallSession, resolved: bool = False) -> str:
    _ensure_header()
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(session.call_started_at, tz=timezone.utc)
    duration = int(now.timestamp() - session.call_started_at)
    ticket_id = f"TKT-{now.strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

    transcript_summary = " | ".join(
        f"{t['role']}: {t['text']}" for t in session.transcript[-20:]
    )

    row = {
        "ticket_id": ticket_id,
        "customer_id": session.customer_id,
        "customer_name": session.customer_name,
        "customer_email": session.customer_email,
        "customer_mobile": session.customer_mobile,
        "call_started_at": started.isoformat(),
        "call_ended_at": now.isoformat(),
        "duration_seconds": str(duration),
        "topics_discussed": "; ".join(session.topics),
        "requests_made": "; ".join(session.requests),
        "kyc_verified": "yes" if session.kyc_verified else "no",
        "resolved": "yes" if resolved else "no",
        "errors": "; ".join(session.errors),
        "agent_notes": transcript_summary[:2000],
        "created_at": now.isoformat(),
    }

    with TICKETS_PATH.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADERS)
        writer.writerow(row)

    return ticket_id
