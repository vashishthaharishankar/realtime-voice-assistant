"""Load Kotak Prime mock data from CSV files."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_DIR = ROOT / "database"


def _read_csv(name: str) -> list[dict[str, str]]:
    path = DATABASE_DIR / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@lru_cache
def get_customers() -> list[dict[str, str]]:
    return _read_csv("customers.csv")


@lru_cache
def get_loans() -> list[dict[str, str]]:
    return _read_csv("loans.csv")


@lru_cache
def get_transactions() -> list[dict[str, str]]:
    return _read_csv("transactions.csv")


def find_customer_by_id(customer_id: str) -> dict[str, str] | None:
    cid = customer_id.strip().upper()
    for row in get_customers():
        if row["customer_id"].upper() == cid:
            return dict(row)
    return None


def find_customer_by_login(login: str) -> dict[str, str] | None:
    login = login.strip().lower()
    for row in get_customers():
        if row["email"].lower() == login or row["registered_mobile"] == login:
            return dict(row)
    return None


def get_loans_for_customer(customer_id: str) -> list[dict[str, str]]:
    cid = customer_id.strip().upper()
    return [dict(r) for r in get_loans() if r["customer_id"].upper() == cid]


def get_transactions_for_customer(customer_id: str, limit: int = 10) -> list[dict[str, str]]:
    cid = customer_id.strip().upper()
    rows = [dict(r) for r in get_transactions() if r["customer_id"].upper() == cid]
    rows.sort(key=lambda r: r["txn_date"], reverse=True)
    return rows[:limit]


def customer_public_profile(customer: dict[str, str]) -> dict[str, Any]:
    return {
        "customer_id": customer["customer_id"],
        "full_name": customer["full_name"],
        "email": customer["email"],
        "registered_mobile": customer["registered_mobile"],
        "city": customer["city"],
        "customer_type": customer["customer_type"],
    }
