"""Guest enquiry and loan-application lead storage."""

from __future__ import annotations

import csv
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.call_session import CallSession

ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_DIR = ROOT / "database"
NEW_LEADS_PATH = DATABASE_DIR / "new_leads.csv"
LOAN_LEADS_PATH = DATABASE_DIR / "loan_lead.csv"

_lock = threading.Lock()

NEW_LEAD_HEADERS = [
    "lead_id",
    "full_name",
    "email",
    "phone",
    "status",
    "source",
    "interested_in",
    "topics_discussed",
    "questions_asked",
    "conversation_summary",
    "follow_up_notes",
    "created_at",
    "updated_at",
]

LOAN_LEAD_HEADERS = [
    "lead_id",
    "guest_lead_id",
    "full_name",
    "email",
    "phone",
    "city",
    "employment_type",
    "monthly_income_inr",
    "product_interest",
    "vehicle_make_model",
    "loan_amount_inr",
    "tenure_months",
    "existing_car_owner",
    "notes",
    "status",
    "created_at",
    "updated_at",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_file(path: Path, headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", encoding="utf-8", newline="") as fh:
            csv.DictWriter(fh, fieldnames=headers).writeheader()


def _read_rows(path: Path, headers: list[str]) -> list[dict[str, str]]:
    _ensure_file(path, headers)
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


def _upsert(path: Path, headers: list[str], key: str, row: dict[str, str]) -> None:
    with _lock:
        rows = _read_rows(path, headers)
        found = False
        for i, existing in enumerate(rows):
            if existing.get(key) == row.get(key):
                merged = {**existing, **{k: v for k, v in row.items() if v not in (None, "")}}
                rows[i] = {h: merged.get(h, "") for h in headers}
                found = True
                break
        if not found:
            rows.append({h: row.get(h, "") for h in headers})
        _write_rows(path, headers, rows)


def create_guest_lead(full_name: str, email: str, phone: str) -> str:
    lead_id = f"LEAD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
    stamp = _now()
    _upsert(
        NEW_LEADS_PATH,
        NEW_LEAD_HEADERS,
        "lead_id",
        {
            "lead_id": lead_id,
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "status": "new",
            "source": "guest_login",
            "interested_in": "",
            "topics_discussed": "",
            "questions_asked": "",
            "conversation_summary": "",
            "follow_up_notes": "Guest signed in on Kotak Assist. Awaiting conversation.",
            "created_at": stamp,
            "updated_at": stamp,
        },
    )
    return lead_id


def update_guest_lead(lead_id: str, **fields: Any) -> None:
    if not lead_id:
        return
    payload = {k: str(v) for k, v in fields.items() if v is not None}
    payload["lead_id"] = lead_id
    payload["updated_at"] = _now()
    if "status" not in payload:
        payload["status"] = "contacted"
    _upsert(NEW_LEADS_PATH, NEW_LEAD_HEADERS, "lead_id", payload)


def update_guest_lead_from_session(session: CallSession) -> None:
    if not session.is_guest or not session.lead_id:
        return
    questions = [t["text"] for t in session.transcript if t.get("role") == "user" and t.get("text")]
    summary = " | ".join(f"{t['role']}: {t['text']}" for t in session.transcript[-30:])
    update_guest_lead(
        session.lead_id,
        topics_discussed="; ".join(session.topics),
        questions_asked=" || ".join(questions)[:3000],
        conversation_summary=summary[:4000],
        follow_up_notes=(
            "Voice conversation captured. Human agent can use topics, questions, "
            "and summary to follow up and convert this lead."
        ),
        status="conversed" if session.transcript else "new",
    )


def create_or_update_loan_lead(session: CallSession, details: dict[str, Any]) -> str:
    stamp = _now()
    lead_id = session.loan_lead_id or (
        f"LOAN-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
    )
    session.loan_lead_id = lead_id
    row = {
        "lead_id": lead_id,
        "guest_lead_id": session.lead_id,
        "full_name": details.get("full_name") or session.customer_name,
        "email": details.get("email") or session.customer_email,
        "phone": details.get("phone") or session.customer_mobile,
        "city": details.get("city") or session.city,
        "employment_type": details.get("employment_type") or "",
        "monthly_income_inr": details.get("monthly_income_inr") or "",
        "product_interest": details.get("product_interest") or "",
        "vehicle_make_model": details.get("vehicle_make_model") or "",
        "loan_amount_inr": details.get("loan_amount_inr") or "",
        "tenure_months": details.get("tenure_months") or "",
        "existing_car_owner": details.get("existing_car_owner") or "",
        "notes": details.get("notes") or "",
        "status": "open",
        "updated_at": stamp,
    }
    existing = None
    with _lock:
        rows = _read_rows(LOAN_LEADS_PATH, LOAN_LEAD_HEADERS)
        for item in rows:
            if item.get("lead_id") == lead_id:
                existing = item
                break
    if existing:
        merged_notes = existing.get("notes", "")
        extra = (details.get("notes") or "").strip()
        if extra and extra not in merged_notes:
            merged_notes = f"{merged_notes} | {extra}".strip(" |")
        row = {**existing, **{k: v for k, v in row.items() if v not in (None, "")}}
        row["notes"] = merged_notes
        row["created_at"] = existing.get("created_at") or stamp
    else:
        row["created_at"] = stamp
    _upsert(LOAN_LEADS_PATH, LOAN_LEAD_HEADERS, "lead_id", row)
    update_guest_lead(
        session.lead_id,
        interested_in=row.get("product_interest") or "loan_enquiry",
        status="loan_enquiry",
        follow_up_notes="Loan enquiry captured in loan_lead.csv for human follow-up.",
    )
    return lead_id
