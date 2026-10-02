"""
Generate deterministic Excel import fixtures under tests/fixtures/excel/.

Uses the application's expected sheet/column conventions.
Does NOT modify import logic.

Run from repo root:
  python scripts/generate_excel_fixtures.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openpyxl import Workbook

FIXTURE_DIR = os.path.join(ROOT, "tests", "fixtures", "excel")

NEW_HEADERS = [
    "Date", "Borrower Name", "Due Day", "Transaction Type",
    "Amount", "Payment Mode", "Notes",
]
OLD_HEADERS = [
    "Date", "Borrower Name", "Loan Display Name", "Transaction Type",
    "Amount", "Payment Mode", "Notes",
]


def _write(path: str, headers: list, rows: list) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Daily Transactions"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)
    print(f"Wrote {path}")


def generate_all() -> None:
    os.makedirs(FIXTURE_DIR, exist_ok=True)

    # 1) Valid import — Prem Singh due day 25 (exact match against seed)
    _write(
        os.path.join(FIXTURE_DIR, "01_valid_import.xlsx"),
        NEW_HEADERS,
        [
            ["15/08/2024", "Prem Singh", 25, "Interest Received", 3000, "Cash", "valid fixture"],
        ],
    )

    # 2) Duplicate of an existing seeded txn (Prem interest 3000 on 2024-02-15)
    _write(
        os.path.join(FIXTURE_DIR, "02_duplicate_existing.xlsx"),
        NEW_HEADERS,
        [
            ["15/02/2024", "Prem Singh", 25, "Interest Received", 3000, "Cash", "dup of seed"],
        ],
    )

    # 3) Duplicate rows within the same file
    _write(
        os.path.join(FIXTURE_DIR, "03_duplicate_within_file.xlsx"),
        NEW_HEADERS,
        [
            ["01/09/2024", "Prem Singh", 25, "Interest Received", 3000, "Cash", "row A"],
            ["01/09/2024", "Prem Singh", 25, "Interest Received", 3000, "Cash", "row B identical"],
        ],
    )

    # 4) Ambiguous match — Rahul Sharma due day 5 (two loans in seed)
    _write(
        os.path.join(FIXTURE_DIR, "04_ambiguous_match.xlsx"),
        NEW_HEADERS,
        [
            ["10/09/2024", "Rahul Sharma", 5, "Interest Received", 2500, "UPI", "ambiguous amount"],
        ],
    )

    # 5) Closed-loan historical — Vikram Mehta due day 1 (loan Closed in seed)
    _write(
        os.path.join(FIXTURE_DIR, "05_closed_loan_historical.xlsx"),
        NEW_HEADERS,
        [
            ["01/08/2023", "Vikram Mehta", 1, "Interest Received", 900, "Cash", "closed historical"],
        ],
    )

    # 6) Unmatched borrower / unmatched loan
    _write(
        os.path.join(FIXTURE_DIR, "06_unmatched.xlsx"),
        NEW_HEADERS,
        [
            ["01/09/2024", "Nobody Exists", 25, "Interest Received", 1000, "Cash", "unmatched borrower"],
            ["01/09/2024", "Prem Singh", 31, "Interest Received", 1000, "Cash", "unmatched due day"],
        ],
    )

    # 7) Mixed valid + duplicate + unmatched
    _write(
        os.path.join(FIXTURE_DIR, "07_mixed_batch.xlsx"),
        NEW_HEADERS,
        [
            ["20/08/2024", "Prem Singh", 25, "Interest Received", 3000, "Cash", "valid"],
            ["15/02/2024", "Prem Singh", 25, "Interest Received", 3000, "Cash", "dup of seed"],
            ["01/09/2024", "Ghost Borrower", 5, "Interest Received", 500, "Cash", "unmatched"],
        ],
    )

    # 8) Mid-import failure candidate — includes Adjustment + invalid amount row
    # (import logic currently accepts Adjustment at parse; Stage 2+ may fail later)
    _write(
        os.path.join(FIXTURE_DIR, "08_mid_import_failure.xlsx"),
        NEW_HEADERS,
        [
            ["21/08/2024", "Prem Singh", 25, "Interest Received", 3000, "Cash", "ok first"],
            ["22/08/2024", "Prem Singh", 25, "Adjustment", 100, "Cash", "adjustment row"],
            ["23/08/2024", "Sneha Kapoor", 7, "Interest Received", 2250, "Online", "ok later"],
        ],
    )

    # Bonus: old display-name format.
    # Anita start_date is 2024-03-01; original principal 50000 remains in display_name
    # even after partial repayment reduced outstanding to 40000.
    _write(
        os.path.join(FIXTURE_DIR, "09_old_display_name.xlsx"),
        OLD_HEADERS,
        [
            [
                "15/03/2024",
                "Anita Desai",
                "01-Mar-24 | ₹50,000 | Due 10",
                "Interest Received",
                1250,
                "Cash",
                "old display name using original principal",
            ],
            [
                "15/05/2024",
                "Anita Desai",
                "01-Mar-24 | ₹40,000 | Due 10",
                "Interest Received",
                1000,
                "Cash",
                "display name using outstanding (must not silently match)",
            ],
        ],
    )

    print(f"All fixtures written under {FIXTURE_DIR}")


if __name__ == "__main__":
    generate_all()
