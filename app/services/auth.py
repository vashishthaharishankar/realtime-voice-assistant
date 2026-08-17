"""Customer login against CSV credentials."""

from __future__ import annotations

from typing import Any

from app.services.call_session import create_session
from app.services.csv_store import customer_public_profile, find_customer_by_login


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
