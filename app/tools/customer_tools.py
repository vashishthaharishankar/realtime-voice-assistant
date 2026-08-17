"""Session-aware tools for logged-in customers."""

from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.tools import tool

from app.call_context import get_session_token
from app.services.call_session import get_session
from app.services.email_service import send_document_email
from app.services.knowledge import search_knowledge
from app.services.kyc import require_kyc, verify_kyc
from app.services.csv_store import get_loans_for_customer, get_transactions_for_customer


def _ok(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _session_or_error() -> tuple[Any, str | None]:
    token = get_session_token()
    if not token:
        return None, _ok({"error": "not_logged_in", "message": "Customer session missing."})
    session = get_session(token)
    if not session:
        return None, _ok({"error": "session_expired", "message": "Session expired. Please log in again."})
    return session, None


@tool
def verify_customer_kyc(
    verification_method: Literal["aadhaar_last4", "pin_code", "phone_last4"],
    value: str,
) -> str:
    """Verify logged-in customer identity once per call before sharing confidential account data."""
    session, err = _session_or_error()
    if err:
        return err
    session.add_request(f"kyc_attempt_{verification_method}")
    result = verify_kyc(session, verification_method, value)
    if result.get("verified"):
        session.add_topic("kyc_verification")
    return _ok(result)


@tool
def get_my_account_summary() -> str:
    """Get outstanding balance and EMI summary for the logged-in customer. Requires KYC verification."""
    session, err = _session_or_error()
    if err:
        return err
    blocked = require_kyc(session)
    if blocked:
        return _ok(blocked)

    loans = get_loans_for_customer(session.customer_id)
    if not loans:
        return _ok({"message": "No active loan account found for this customer."})

    loan = loans[0]
    session.add_topic("account_balance")
    session.add_request("account_summary")
    return _ok(
        {
            "customer_name": session.customer_name,
            "loan_account_number": loan["loan_account_number"],
            "product_type": loan["product_type"],
            "vehicle": loan["vehicle_model"],
            "outstanding_balance_inr": loan["outstanding_balance_inr"],
            "principal_outstanding_inr": loan["principal_outstanding_inr"],
            "emi_inr": loan["emi_inr"],
            "interest_rate_percent": loan["interest_rate_percent"],
            "next_emi_date": loan["next_emi_date"],
            "status": loan["status"],
        }
    )


@tool
def get_my_recent_transactions() -> str:
    """Get last 3 loan account transactions for logged-in customer. Requires KYC verification."""
    session, err = _session_or_error()
    if err:
        return err
    blocked = require_kyc(session)
    if blocked:
        return _ok(blocked)

    txns = get_transactions_for_customer(session.customer_id, limit=3)
    session.add_topic("transactions")
    session.add_request("recent_transactions")
    return _ok(
        {
            "customer_name": session.customer_name,
            "transaction_count": len(txns),
            "transactions": [
                {
                    "date": t["txn_date"],
                    "type": t["txn_type"],
                    "description": t["description"],
                    "amount_inr": t["amount_inr"],
                    "balance_after_inr": t["balance_after_inr"],
                    "mode": t["mode"],
                }
                for t in txns
            ],
        }
    )


@tool
def send_my_document_email(
    document_type: Literal[
        "account_statement",
        "interest_certificate",
        "loan_certificate",
        "noc_certificate",
    ],
) -> str:
    """Email a PDF document to the logged-in customer's registered email. Requires KYC verification."""
    session, err = _session_or_error()
    if err:
        return err
    blocked = require_kyc(session)
    if blocked:
        return _ok(blocked)

    session.add_request(f"email_{document_type}")
    session.add_topic("document_email")
    result = send_document_email(
        session.customer_id,
        session.customer_name,
        session.customer_email,
        document_type,
    )
    if not result.get("sent"):
        session.add_error(result.get("error", "email_failed"))
    return _ok(result)


@tool
def search_company_knowledge(query: str) -> str:
    """Search Kotak Prime knowledge base (policies, products, charges). Use only returned excerpts."""
    session, err = _session_or_error()
    if err:
        return err
    session.add_topic("knowledge_query")
    session.add_request(f"knowledge: {query[:80]}")
    return _ok(search_knowledge(query))


CUSTOMER_TOOLS = [
    verify_customer_kyc,
    get_my_account_summary,
    get_my_recent_transactions,
    send_my_document_email,
    search_company_knowledge,
]
