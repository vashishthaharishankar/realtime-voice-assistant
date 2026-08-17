"""LangChain tools backed by Kotak Prime Loans mock data."""

from __future__ import annotations

import json
import math
from typing import Any, Literal

from langchain_core.tools import tool

from app.tools import (
    APPLICATIONS,
    BRANCHES,
    CONTACT,
    DOCUMENTS,
    ELIGIBILITY,
    FEES_AND_CHARGES,
    PRODUCTS,
    SCHEMES,
)


def _ok(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


@tool
def list_loan_products() -> str:
    """List all Kotak Mahindra Prime loan products and short summaries."""
    items = [
        {
            "id": p["id"],
            "name": p["name"],
            "summary": p["summary"],
            "funding": p.get("funding"),
        }
        for p in PRODUCTS.values()
    ]
    return _ok({"products": items, "provider": CONTACT["company"]})


@tool
def get_product_details(
    product_id: Literal["new_car", "used_car", "refinance", "cash_against_car"],
) -> str:
    """Get detailed features for a Kotak Prime loan product."""
    product = PRODUCTS.get(product_id)
    if not product:
        return _ok({"error": f"Unknown product_id: {product_id}"})
    return _ok(product)


@tool
def get_scheme_details(
    scheme_id: Literal["margin_money", "step_up", "balloon", "advance_emi"],
) -> str:
    """Get details of a new-car financing scheme (Margin Money, Step Up, Balloon, Advance EMI)."""
    scheme = SCHEMES.get(scheme_id)
    if not scheme:
        return _ok({"error": f"Unknown scheme_id: {scheme_id}"})
    return _ok(scheme)


@tool
def compare_schemes() -> str:
    """Compare all new-car financing schemes side by side."""
    return _ok({"schemes": list(SCHEMES.values())})


@tool
def check_eligibility(
    customer_type: Literal["salaried", "self_employed"],
    age: int,
    monthly_income_inr: float | None = None,
    business_years: float | None = None,
    tenure_months: int = 60,
) -> str:
    """Check basic eligibility for a Kotak Prime car loan using mock policy rules."""
    rules = ELIGIBILITY.get(customer_type)
    if not rules:
        return _ok({"eligible": False, "reason": "Unsupported customer type"})

    reasons: list[str] = []
    age_at_maturity = age + (tenure_months // 12)

    if age < rules["min_age"]:
        reasons.append(f"Minimum applicant age is {rules['min_age']}")
    if age_at_maturity > rules["max_age_at_maturity"]:
        reasons.append(
            f"Age at maturity ({age_at_maturity}) exceeds max "
            f"{rules['max_age_at_maturity']} for {customer_type}"
        )

    if customer_type == "salaried":
        income = monthly_income_inr or 0
        if income < rules["min_monthly_income_inr"]:
            reasons.append(
                f"Minimum monthly income is Rs. {rules['min_monthly_income_inr']:,}"
            )
    else:
        years = business_years or 0
        if years < rules["min_business_years"]:
            reasons.append(
                f"Minimum business vintage is {rules['min_business_years']} year(s)"
            )

    eligible = len(reasons) == 0
    return _ok(
        {
            "eligible": eligible,
            "customer_type": customer_type,
            "age": age,
            "age_at_maturity": age_at_maturity,
            "reasons": reasons or ["Meets basic mock eligibility checks"],
            "policy": rules,
            "disclaimer": "Final credit decision is at sole discretion of KMPL.",
        }
    )


@tool
def get_required_documents(
    customer_type: Literal["salaried", "self_employed"] = "salaried",
    product_id: Literal["new_car", "used_car", "refinance", "cash_against_car"] = "new_car",
) -> str:
    """List documents required for a customer type and product."""
    docs = list(DOCUMENTS.get(customer_type, []))
    if product_id in {"used_car", "refinance", "cash_against_car"}:
        extra = [
            "RC copy",
            "Insurance copy",
            "Valuation form from authorized agency",
        ]
        for item in extra:
            if item not in docs:
                docs.append(item)
    return _ok(
        {
            "customer_type": customer_type,
            "product_id": product_id,
            "documents": docs,
        }
    )


@tool
def estimate_emi(
    loan_amount: float,
    annual_interest_rate: float = 10.5,
    tenure_months: int = 60,
) -> str:
    """Estimate EMI for a car loan using a standard reducing-balance formula (illustrative)."""
    if loan_amount <= 0 or tenure_months <= 0:
        return _ok({"error": "loan_amount and tenure_months must be positive"})

    monthly_rate = annual_interest_rate / 12 / 100
    if monthly_rate == 0:
        emi = loan_amount / tenure_months
    else:
        factor = (1 + monthly_rate) ** tenure_months
        emi = loan_amount * monthly_rate * factor / (factor - 1)

    total_payment = emi * tenure_months
    interest = total_payment - loan_amount

    return _ok(
        {
            "loan_amount": round(loan_amount, 2),
            "annual_interest_rate_percent": annual_interest_rate,
            "tenure_months": tenure_months,
            "estimated_emi": round(emi, 2),
            "total_payment": round(total_payment, 2),
            "total_interest": round(interest, 2),
            "note": (
                "Illustrative estimate only. Actual Kotak Prime rates depend on "
                "profile, product, and credit assessment."
            ),
        }
    )


@tool
def get_fees_and_charges() -> str:
    """Get fees, charges, and interest-rate guidance for Kotak Prime car loans."""
    return _ok(FEES_AND_CHARGES)


@tool
def track_application(prospect_number: str = "", mobile_number: str = "") -> str:
    """Track a mock loan application by prospect number (e.g. KMPL1001) or mobile."""
    key = (prospect_number or "").strip().upper()
    if key and key in APPLICATIONS:
        return _ok({"found": True, "application": APPLICATIONS[key]})

    # Mobile lookup is intentionally mock / not indexed
    if mobile_number.strip():
        return _ok(
            {
                "found": False,
                "message": (
                    f"No mock application linked to mobile {mobile_number}. "
                    "Try prospect numbers KMPL1001, KMPL1002, or KMPL1003."
                ),
            }
        )

    return _ok(
        {
            "found": False,
            "message": "Provide a prospect number. Demo IDs: KMPL1001, KMPL1002, KMPL1003.",
            "how_to_track": CONTACT["track_application"],
        }
    )


@tool
def get_contact_and_branches(city: str = "") -> str:
    """Get Kotak Prime contact details and service points; optionally filter by city."""
    city_q = city.strip().lower()
    branches = BRANCHES
    if city_q:
        branches = [b for b in BRANCHES if city_q in b["city"].lower()]
    return _ok(
        {
            "contact": CONTACT,
            "branches": branches or BRANCHES,
            "apply_options": [
                "Request a callback on primeloans.kotak.com",
                CONTACT["apply_sms"],
                "Visit a service point / dealership partner",
            ],
        }
    )


@tool
def recommend_product(
    goal: Literal[
        "buy_new_car",
        "buy_used_car",
        "refinance_existing",
        "cash_from_owned_car",
    ],
    budget_inr: float | None = None,
) -> str:
    """Recommend a Kotak Prime product based on customer goal and optional budget."""
    mapping = {
        "buy_new_car": "new_car",
        "buy_used_car": "used_car",
        "refinance_existing": "refinance",
        "cash_from_owned_car": "cash_against_car",
    }
    product = PRODUCTS[mapping[goal]]
    suggestion: dict[str, Any] = {
        "recommended_product": product,
        "suggested_next_steps": [
            "Confirm eligibility",
            "Share required documents",
            "Request callback or apply via SMS 5676788",
        ],
    }
    if budget_inr and goal == "buy_new_car":
        suggestion["funding_hint"] = (
            f"For a vehicle around Rs. {budget_inr:,.0f}, new-car finance may cover "
            "up to 100% for eligible models (subject to credit)."
        )
    if budget_inr and goal == "buy_used_car":
        suggestion["funding_hint"] = (
            f"Used-car funding is typically up to 90% of value "
            f"(~Rs. {math.floor(budget_inr * 0.9):,} illustrative)."
        )
    return _ok(suggestion)


_PUBLIC_TOOLS = [
    list_loan_products,
    get_product_details,
    get_scheme_details,
    compare_schemes,
    check_eligibility,
    get_required_documents,
    estimate_emi,
    get_fees_and_charges,
    track_application,
    get_contact_and_branches,
    recommend_product,
]


def _all_tools() -> list:
    from app.tools.customer_tools import CUSTOMER_TOOLS

    return _PUBLIC_TOOLS + CUSTOMER_TOOLS


ALL_TOOLS = _all_tools()
TOOL_BY_NAME = {t.name: t for t in ALL_TOOLS}


def realtime_tool_schemas() -> list[dict[str, Any]]:
    """Convert LangChain tools to OpenAI Realtime function schemas."""
    schemas: list[dict[str, Any]] = []
    for tool_obj in ALL_TOOLS:
        schema = tool_obj.args_schema.model_json_schema()
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        # Remove title-only noise from nested schemas if present
        clean_props: dict[str, Any] = {}
        for key, value in properties.items():
            prop = {k: v for k, v in value.items() if k != "title"}
            clean_props[key] = prop
        schemas.append(
            {
                "type": "function",
                "name": tool_obj.name,
                "description": tool_obj.description,
                "parameters": {
                    "type": "object",
                    "properties": clean_props,
                    "required": required,
                    "additionalProperties": False,
                },
            }
        )
    return schemas
