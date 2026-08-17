"""Customer login against CSV credentials."""

from __future__ import annotations

from typing import Any

from app.services.call_session import create_guest_session, create_session
from app.services.csv_store import customer_public_profile, find_customer_by_login
from app.services.leads import create_guest_lead


def authenticate(login: str, password: str) -> dict[str, Any]:
    customer = find_customer_by_login(login)
    if not customer:
        return {"success": False, "error": "No account found for this email or mobile number."}
    if customer["password"] != password:
        return {"success": False, "error": "Incorrect password."}
    if customer.get("account_status", "").lower() != "active":
        return {"success": False, "error": "Account is not active. Contact Kotak Prime support."}

    session = create_session(customer["customer_id"])
    if not session:
        return {"success": False, "error": "Unable to start session."}

    return {
        "success": True,
        "session_token": session.token,
        "customer": customer_public_profile(customer),
    }


def authenticate_guest(full_name: str, email: str = "", phone: str = "") -> dict[str, Any]:
    name = (full_name or "").strip()
    email = (email or "").strip().lower()
    phone = (phone or "").strip()
    if not name:
        return {"success": False, "error": "Please enter your name."}
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not email and len(digits) < 10:
        return {"success": False, "error": "Enter a valid email or a 10-digit mobile number."}
    if email and "@" not in email:
        return {"success": False, "error": "Enter a valid email address."}

    session = create_guest_session(name, email, phone)
    session.lead_id = create_guest_lead(name, email, phone)
    return {
        "success": True,
        "session_token": session.token,
        "customer": {
            "customer_id": session.customer_id,
            "full_name": session.customer_name,
            "email": session.customer_email,
            "registered_mobile": session.customer_mobile,
            "city": "",
            "customer_type": "guest",
            "is_guest": True,
        },
    }
