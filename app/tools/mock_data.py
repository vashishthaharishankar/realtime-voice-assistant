"""Mock knowledge base sourced from Kotak Mahindra Prime Loans (primeloans.kotak.com)."""

from __future__ import annotations

PRODUCTS = {
    "new_car": {
        "id": "new_car",
        "name": "New Car Finance",
        "provider": "Kotak Mahindra Prime Limited (KMPL)",
        "summary": (
            "Finance for new passenger cars and multi-utility vehicles from "
            "leading manufacturers, including select imported cars."
        ),
        "funding": "Up to 100% of on-road / invoice value for eligible models",
        "min_loan_amount": 75000,
        "tenure_months": {"min": 12, "max": 84},
        "processing_time": "Within 48 hours of complete documentation",
        "prepayment": "Allowed anytime after 6 months; small prepayment fee applies",
        "schemes": [
            "margin_money",
            "step_up",
            "balloon",
            "advance_emi",
        ],
        "notes": [
            "Credit at the sole discretion of KMPL",
            "Loans subject to RBI guidelines and complete documentation",
        ],
    },
    "used_car": {
        "id": "used_car",
        "name": "Used Car Finance",
        "provider": "Kotak Mahindra Prime Limited (KMPL)",
        "summary": (
            "Finance for existing passenger cars with funding up to 90% "
            "and flexible tenure options."
        ),
        "funding": "Up to 90% of car value",
        "min_loan_amount": 100000,
        "tenure_months": {"min": 12, "max": 84},
        "processing_time": "Up to 72 hours upon completing documentation",
        "variants": [
            {
                "id": "pre_approved",
                "name": "Pre-approved loan",
                "loan_amount": "Up to Rs. 1.5 Lacs",
                "highlights": ["Minimum documentation"],
            },
            {
                "id": "preferred_segment",
                "name": "Preferred segment loan",
                "loan_amount": "Rs. 1.5 – 15 Lacs",
                "highlights": [
                    "Hassle-free processing",
                    "Funding up to 90%",
                    "Tenure up to 84 months",
                ],
            },
            {
                "id": "approve_your_own",
                "name": "Approve your own loan",
                "loan_amount": "Up to 2x annual salary",
                "highlights": [
                    "For salaried employees",
                    "EMI up to 40% of net salary",
                ],
            },
        ],
        "notes": [
            "Also available: loan takeover / refinance and cash against car",
        ],
    },
    "refinance": {
        "id": "refinance",
        "name": "Car Loan Takeover / Refinance",
        "provider": "Kotak Mahindra Prime Limited (KMPL)",
        "summary": (
            "Take over an existing car loan. When KMPL funding is higher than "
            "the foreclosure amount, customers can generate cash."
        ),
        "funding": "Can exceed 100% relative to foreclosure in eligible cases",
        "highlights": [
            "Take over from select financiers",
            "Top-up based on repayment track record",
            "Clear title required in customer favour",
        ],
    },
    "cash_against_car": {
        "id": "cash_against_car",
        "name": "Cash Against Car",
        "provider": "Kotak Mahindra Prime Limited (KMPL)",
        "summary": (
            "Pledge an existing lien-free car to generate cash. "
            "KMPL marks lien on the vehicle."
        ),
        "eligibility_notes": [
            "Car must have clear title in customer favour",
            "Vehicle free of lien / hypothecation",
        ],
    },
}

SCHEMES = {
    "margin_money": {
        "id": "margin_money",
        "name": "Margin Money Scheme",
        "product": "new_car",
        "description": (
            "Finance up to 100% of invoice value for certain models. "
            "Customer pays margin money to dealer or to KMPL."
        ),
        "best_for": "Customers who want maximum funding on eligible models",
        "repayment": "12–84 months EMIs",
    },
    "step_up": {
        "id": "step_up",
        "name": "Step Up Scheme",
        "product": "new_car",
        "description": (
            "EMI increases every year, six months, or quarter based on need. "
            "Start with lower EMIs early in the tenure."
        ),
        "best_for": "Customers expecting income growth; luxury car buyers",
        "repayment": "Stepped EMIs over chosen tenure",
    },
    "balloon": {
        "id": "balloon",
        "name": "Low EMI / Balloon Scheme",
        "product": "new_car",
        "description": (
            "10%–25% of car cost paid as last EMI (balloon). "
            "Reduced EMIs during the tenure."
        ),
        "best_for": (
            "Customers planning to dispose of the vehicle at tenure end "
            "and wanting affordable EMIs meanwhile"
        ),
        "repayment": "Lower EMIs + balloon final payment",
    },
    "advance_emi": {
        "id": "advance_emi",
        "name": "Advance EMI Scheme",
        "product": "new_car",
        "description": (
            "Pay a few monthly instalments upfront; remaining balance "
            "via regular EMIs. Helps repay faster."
        ),
        "best_for": "Customers who can pay advance instalments",
        "repayment": "Advance EMIs + remaining EMIs",
    },
}

ELIGIBILITY = {
    "salaried": {
        "customer_type": "salaried",
        "min_age": 21,
        "max_age_at_maturity": 60,
        "min_monthly_income_inr": 15000,
        "residency": "All Indian residents (used car); individuals 21–58/60 for new car profiles",
        "notes": [
            "Guarantor generally not required",
            "Guarantor may be needed if income/age does not meet criteria",
        ],
    },
    "self_employed": {
        "customer_type": "self_employed",
        "min_age": 21,
        "max_age_at_maturity": 65,
        "min_business_years": 1,
        "notes": [
            "Also eligible: partnership firms, LLPs, Pvt/Public Ltd companies, HUFs, Trusts",
        ],
    },
}

DOCUMENTS = {
    "salaried": [
        "KMPL application form",
        "Latest salary slip with statutory deductions",
        "Form 16 / IT returns",
        "Proof of residence (electricity/telephone bill, passport, voter ID, lease/rent agreement, property docs)",
        "Signature verification / KYC (PAN, passport, DL, voter ID, banker verification)",
        "Photograph (signed)",
        "For used car: RC copy, insurance copy, authorized valuation form",
    ],
    "self_employed": [
        "KMPL application form",
        "P&L and Balance Sheet for last 2 years (CA certified)",
        "Income Tax Returns for last 2 years",
        "Proof of residence",
        "Signature / KYC documents",
        "Photograph (signed)",
        "Partnership deed / trust deed / letter of authority if applicable",
        "For companies: MOA and board resolution",
        "For used car: RC, insurance, valuation form",
    ],
}

FEES_AND_CHARGES = {
    "processing_fee": "Up to ~3% of loan amount (non-refundable; illustrative mock)",
    "other_charges": [
        "RTO charges, NACH, RCU, CERSAI as applicable at actuals",
        "Stamp duty as applicable",
        "Prepayment fee on outstanding after 6 months",
    ],
    "interest_rates": (
        "Attractive rates depending on applicant profile, product segment, "
        "tenure, and KMPL interest gradation. Exact rate is credit-decision based."
    ),
    "disclaimer": (
        "Offers from Kotak Mahindra Prime Ltd, subsidiary of Kotak Mahindra Bank Ltd. "
        "Sanction/disbursement at sole discretion of KMPL. T&C apply."
    ),
}

CONTACT = {
    "company": "Kotak Mahindra Prime Limited",
    "address": "27BKC, C 27, G Block, Bandra Kurla Complex, Bandra (E), Mumbai - 400 051",
    "apply_sms": "SMS to 5676788",
    "website": "https://primeloans.kotak.com",
    "bank_car_loan_page": "https://www.kotak.bank.in/en/personal-banking/loans/car-loan.html",
    "track_application": "Track via Mobile Number or Prospect Number on primeloans.kotak.com",
}

# Mock application tracker
APPLICATIONS = {
    "KMPL1001": {
        "prospect_number": "KMPL1001",
        "customer_name": "Rahul Sharma",
        "product": "new_car",
        "vehicle": "Hyundai Creta SX",
        "loan_amount": 1250000,
        "status": "Under credit review",
        "last_updated": "2026-08-09",
        "next_step": "Share latest salary slip and Form 16",
    },
    "KMPL1002": {
        "prospect_number": "KMPL1002",
        "customer_name": "Priya Nair",
        "product": "used_car",
        "vehicle": "Maruti Swift VXI 2021",
        "loan_amount": 450000,
        "status": "Documents pending",
        "last_updated": "2026-08-08",
        "next_step": "Upload RC, insurance, and valuation report",
    },
    "KMPL1003": {
        "prospect_number": "KMPL1003",
        "customer_name": "Amit Patel",
        "product": "refinance",
        "vehicle": "Tata Nexon XZ+",
        "loan_amount": 380000,
        "status": "Approved – pending disbursement",
        "last_updated": "2026-08-10",
        "next_step": "Complete agreement signing",
    },
}

BRANCHES = [
    {"city": "Mumbai", "area": "Bandra Kurla Complex", "phone": "+91-22-XXXX-1001"},
    {"city": "Delhi", "area": "Connaught Place", "phone": "+91-11-XXXX-2002"},
    {"city": "Bengaluru", "area": "Koramangala", "phone": "+91-80-XXXX-3003"},
    {"city": "Chennai", "area": "T Nagar", "phone": "+91-44-XXXX-4004"},
    {"city": "Pune", "area": "Baner", "phone": "+91-20-XXXX-5005"},
    {"city": "Hyderabad", "area": "Banjara Hills", "phone": "+91-40-XXXX-6006"},
]
