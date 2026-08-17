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
from app.services.leads import create_or_update_loan_lead, update_guest_lead


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


def _guest_account_block(session: Any) -> str | None:
    if getattr(session, "is_guest", False):
        return _ok(
            {
                "error": "guest_restricted",
                "message": "Guest users cannot access account, balance, or personal loan records. Share only KMPL products, policies, and eligibility from the knowledge base.",
            }
        )
    return None


@tool
def verify_customer_kyc(
    verification_method: Literal["aadhaar_last4", "pin_code", "phone_last4"],
    value: str,
) -> str:
    """Verify logged-in customer identity once per call before sharing confidential account data."""
    session, err = _session_or_error()
    if err:
        return err
    blocked = _guest_account_block(session)
    if blocked:
        return blocked
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
    blocked = _guest_account_block(session)
    if blocked:
        return blocked
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
    blocked = _guest_account_block(session)
    if blocked:
        return blocked
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
    blocked = _guest_account_block(session)
    if blocked:
        return blocked
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


@tool
def log_guest_interest(interested_in: str, question_or_need: str, notes: str = "") -> str:
    """Save what a guest visitor asked about so a human agent can follow up. Use after they share an interest or question."""
    session, err = _session_or_error()
    if err:
        return err
    if not session.is_guest:
        return _ok({"ok": True, "message": "Logged-in customers are not stored as guest leads."})
    session.add_topic(interested_in[:80])
    session.add_request(question_or_need[:120])
    update_guest_lead(
        session.lead_id,
        interested_in=interested_in[:200],
        follow_up_notes=notes or question_or_need,
        status="interested",
    )
    return _ok({"ok": True, "lead_id": session.lead_id, "saved": interested_in})


@tool
def submit_loan_enquiry(
    product_interest: str = "",
    city: str = "",
    employment_type: Literal["", "salaried", "self_employed"] = "",
    monthly_income_inr: str = "",
    vehicle_make_model: str = "",
    loan_amount_inr: str = "",
    tenure_months: str = "",
    existing_car_owner: str = "",
    notes: str = "",
    phone: str = "",
    email: str = "",
) -> str:
    """Save loan/product enquiry details for a guest. Call after each useful detail so a human can process the application later. Ask one missing field at a time."""
    session, err = _session_or_error()
    if err:
        return err
    if not session.is_guest:
        return _ok({"error": "logged_in_customer", "message": "Use the customer account tools for logged-in users."})

    if city:
        session.city = city
    details = {
        "product_interest": product_interest,
        "city": city or session.city,
        "employment_type": employment_type,
        "monthly_income_inr": monthly_income_inr,
        "vehicle_make_model": vehicle_make_model,
        "loan_amount_inr": loan_amount_inr,
        "tenure_months": tenure_months,
        "existing_car_owner": existing_car_owner,
        "notes": notes,
        "phone": phone,
        "email": email,
    }
    session.add_topic("loan_enquiry")
    if product_interest:
        session.add_request(f"loan:{product_interest}")
    lead_id = create_or_update_loan_lead(session, details)
    missing = [
        name
        for name, value in {
            "product_interest": details["product_interest"] or None,
            "city": details["city"] or None,
            "employment_type": details["employment_type"] or None,
            "monthly_income_inr": details["monthly_income_inr"] or None,
            "vehicle_make_model": details["vehicle_make_model"] or None,
            "loan_amount_inr": details["loan_amount_inr"] or None,
            "tenure_months": details["tenure_months"] or None,
        }.items()
        if not value
    ]
    return _ok(
        {
            "ok": True,
            "loan_lead_id": lead_id,
            "saved": {k: v for k, v in details.items() if v},
            "still_needed": missing,
            "message": "Ask the next missing field only. Do not promise approval.",
        }
    )


CUSTOMER_TOOLS = [
    verify_customer_kyc,
    get_my_account_summary,
    get_my_recent_transactions,
    send_my_document_email,
    search_company_knowledge,
    log_guest_interest,
    submit_loan_enquiry,
]

ACCOUNT_TOOL_NAMES = {
    "verify_customer_kyc",
    "get_my_account_summary",
    "get_my_recent_transactions",
    "send_my_document_email",
}

GUEST_TOOL_NAMES = {
    "log_guest_interest",
    "submit_loan_enquiry",
    "search_company_knowledge",
}
