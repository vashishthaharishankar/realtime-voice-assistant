"""KYC verification for confidential account information."""

from __future__ import annotations

from typing import Any, Literal

from app.services.call_session import CallSession
from app.services.csv_store import find_customer_by_id

VerificationMethod = Literal["aadhaar_last4", "pin_code", "phone_last4"]


def verify_kyc(
    session: CallSession,
    method: VerificationMethod,
    value: str,
) -> dict[str, Any]:
    if session.kyc_verified:
        return {
            "verified": True,
            "message": "Customer already verified for this call.",
            "method": session.kyc_method,
        }

    customer = find_customer_by_id(session.customer_id)
    if not customer:
        return {"verified": False, "error": "Customer record not found."}

    cleaned = value.strip().replace(" ", "")
    expected: str | None = None
    label = ""

    if method == "aadhaar_last4":
        expected = customer["aadhaar_last4"]
        label = "last 4 digits of Aadhaar"
        if len(cleaned) != 4 or not cleaned.isdigit():
            return {"verified": False, "error": "Provide exactly 4 digits of Aadhaar."}
    elif method == "pin_code":
        expected = customer["pin_code"]
        label = "6-digit PIN code"
        if len(cleaned) != 6 or not cleaned.isdigit():
            return {"verified": False, "error": "Provide exactly 6 digits of registered PIN code."}
    elif method == "phone_last4":
        digits = "".join(ch for ch in customer["registered_mobile"] if ch.isdigit())
        expected = digits[-4:]
        label = "last 4 digits of registered mobile"
        if len(cleaned) != 4 or not cleaned.isdigit():
            return {"verified": False, "error": "Provide exactly 4 digits of registered mobile."}
    else:
        return {"verified": False, "error": "Unsupported verification method."}

    if cleaned != expected:
        return {
            "verified": False,
            "error": f"Verification failed. {label} did not match our records.",
            "hint": "Try PIN code or last 4 digits of registered mobile if Aadhaar is unavailable.",
        }

    session.kyc_verified = True
    session.kyc_method = method
    session.add_request(f"kyc_verified_via_{method}")
    return {
        "verified": True,
        "message": "Identity verified successfully for this call.",
        "method": method,
    }


def require_kyc(session: CallSession) -> dict[str, Any] | None:
    if session.kyc_verified:
        return None
    return {
        "error": "kyc_required",
        "message": (
            "Verify the customer once per call before sharing balance, transactions, "
            "or sending confidential documents. Ask for last 4 digits of Aadhaar first; "
            "if unavailable, 6-digit registered PIN code; else last 4 digits of registered mobile."
        ),
    }
