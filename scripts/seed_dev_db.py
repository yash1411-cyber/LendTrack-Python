"""
seed_dev_db.py — Create a deterministic SYNTHETIC development database.

WARNING:
  This script REPLACES the SQLite file at database.DB_PATH.
  It is intended ONLY for the isolated development laptop.
  It NEVER uses or copies production financial data.

Usage (from repo root, with .venv active):
  python scripts/seed_dev_db.py
"""

from __future__ import annotations

import os
import sys

# Ensure project root is on sys.path when run as a script
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import database as db


# Fixed dates — never use "today" so re-seeds stay deterministic
D_START_A = "2024-01-15"
D_START_B = "2024-03-01"
D_START_C = "2024-06-10"
D_START_D = "2023-08-20"
D_START_E = "2024-02-05"
D_START_F = "2024-04-12"
D_START_G = "2024-05-01"
D_START_CLOSED = "2023-05-01"

D_TXN_OLD = "2023-06-15"
D_TXN_MID = "2024-02-20"
D_TXN_LATE = "2024-07-05"
D_TXN_INTEREST_1 = "2024-02-15"
D_TXN_INTEREST_2 = "2024-03-15"
D_TXN_PRINCIPAL_PARTIAL = "2024-04-01"
D_TXN_CLOSED_INT = "2023-07-01"
D_TXN_CLOSED_PRI = "2023-12-01"


def _banner(msg: str) -> None:
    print("=" * 72)
    print(msg)
    print("=" * 72)


def reset_database() -> str:
    """Delete existing DB at DB_PATH (if any) and recreate empty schema."""
    path = db.DB_PATH
    if os.path.exists(path):
        print(f"[DESTRUCTIVE] Removing existing database: {path}")
        os.remove(path)
    else:
        print(f"[INFO] No existing database at {path}")
    db.initialize_db()
    print(f"[INFO] Schema initialized at {path}")
    return path


def seed_all() -> dict:
    """
    Populate the DB at database.DB_PATH with deterministic synthetic data.
    Returns a summary dict useful for assertions.
    """
    # ── Borrowers (order => B001, B002, …) ─────────────────────────────────
    borrowers = [
        ("Rahul Sharma", "9000000001", "Synthetic – multi-loan same due day"),
        ("Rahul Verma", "9000000002", "Synthetic – similar name to Rahul Sharma"),
        ("Rashid", "9000000003", "Synthetic – ambiguous short name"),
        ("Pammi", "9000000004", "Synthetic – ambiguous short name"),
        ("Prem Singh", "9000000005", "Synthetic – clear exact-match borrower"),
        ("Anita Desai", "9000000006", "Synthetic – single active loan"),
        ("Vikram Mehta", "9000000007", "Synthetic – closed loan history"),
        ("Sneha Kapoor", "9000000008", "Synthetic – no-repayment loan"),
        ("Karan Joshi", "9000000009", "Synthetic – similar interest amounts"),
    ]

    borrower_ids = []
    for name, phone, notes in borrowers:
        bid = db.add_borrower(name, phone, notes)
        borrower_ids.append(bid)

    b = {name: bid for (name, _, _), bid in zip(borrowers, borrower_ids)}

    # ── Loans ──────────────────────────────────────────────────────────────
    # Prem Singh — single clear active loan (exact match)
    l_prem = db.add_loan(b["Prem Singh"], 100000.0, 3.0, 25, D_START_A)

    # Anita — active, interest only later
    l_anita = db.add_loan(b["Anita Desai"], 50000.0, 2.5, 10, D_START_B)

    # Sneha — active, no repayments beyond Loan Given
    l_sneha = db.add_loan(b["Sneha Kapoor"], 75000.0, 3.0, 7, D_START_C)

    # Rahul Sharma — TWO active loans, SAME due day (ambiguous match)
    l_rs_1 = db.add_loan(b["Rahul Sharma"], 100000.0, 3.0, 5, D_START_A)
    l_rs_2 = db.add_loan(b["Rahul Sharma"], 200000.0, 2.0, 5, D_START_E)

    # Rahul Verma — one active loan (similar name cases)
    l_rv = db.add_loan(b["Rahul Verma"], 80000.0, 3.0, 12, D_START_F)

    # Rashid / Pammi — one loan each (short-name identity fixtures)
    l_rashid = db.add_loan(b["Rashid"], 60000.0, 3.0, 15, D_START_B)
    l_pammi = db.add_loan(b["Pammi"], 40000.0, 2.5, 20, D_START_C)

    # Karan — two loans with similar monthly interest (100000*3%=3000, 150000*2%=3000)
    l_karan_a = db.add_loan(b["Karan Joshi"], 100000.0, 3.0, 8, D_START_G)
    l_karan_b = db.add_loan(b["Karan Joshi"], 150000.0, 2.0, 8, D_START_G)

    # Vikram — loan that will be fully repaid then Closed (historical)
    l_vikram = db.add_loan(b["Vikram Mehta"], 30000.0, 3.0, 1, D_START_CLOSED)

    # Loan used for display-name-after-repayment: Prem already has primary;
    # use Anita? Better: dedicated partial-repayment on Prem's loan via extra txn,
    # OR add second loan for Prem. Use Sneha? Use a dedicated loan on Anita with partial.
    # Create partial repayment on l_anita so principal mutates (display name changes).
    db.add_transaction(
        b["Anita Desai"], l_anita, "Interest Received", 1250.0, D_TXN_INTEREST_1, "synthetic interest"
    )
    db.add_transaction(
        b["Anita Desai"], l_anita, "Principal Received", 10000.0, D_TXN_PRINCIPAL_PARTIAL,
        "synthetic partial principal — mutates loans.principal for display-name drift"
    )

    # Prem — interest transactions (exact match interest import target)
    db.add_transaction(
        b["Prem Singh"], l_prem, "Interest Received", 3000.0, D_TXN_INTEREST_1, "synthetic"
    )
    db.add_transaction(
        b["Prem Singh"], l_prem, "Interest Received", 3000.0, D_TXN_INTEREST_2, "synthetic"
    )

    # Rahul Sharma — interest on first loan only
    db.add_transaction(
        b["Rahul Sharma"], l_rs_1, "Interest Received", 3000.0, D_TXN_MID, "synthetic"
    )

    # Vikram closed loan history: interest + full principal return, then Closed
    db.add_transaction(
        b["Vikram Mehta"], l_vikram, "Interest Received", 900.0, D_TXN_CLOSED_INT, "synthetic"
    )
    db.add_transaction(
        b["Vikram Mehta"], l_vikram, "Principal Received", 30000.0, D_TXN_CLOSED_PRI,
        "synthetic full repayment"
    )
    # After full principal received, loans.principal should be 0; mark Closed
    vloan = db.get_loan(l_vikram)
    db.update_loan(
        l_vikram,
        vloan["principal"],
        vloan["interest_rate"],
        vloan["due_day"],
        vloan["start_date"],
        "Closed",
    )

    # Older interest on Rashid
    db.add_transaction(
        b["Rashid"], l_rashid, "Interest Received", 1800.0, D_TXN_OLD, "synthetic old interest"
    )

    loan_ids = {
        "prem": l_prem,
        "anita": l_anita,
        "sneha": l_sneha,
        "rahul_sharma_1": l_rs_1,
        "rahul_sharma_2": l_rs_2,
        "rahul_verma": l_rv,
        "rashid": l_rashid,
        "pammi": l_pammi,
        "karan_a": l_karan_a,
        "karan_b": l_karan_b,
        "vikram_closed": l_vikram,
    }

    return {
        "borrower_ids": borrower_ids,
        "borrowers_by_name": b,
        "loan_ids": loan_ids,
        "expected_borrower_count": len(borrowers),
        "expected_loan_count": len(loan_ids),
        "expected_first_borrower_id": "B001",
        "expected_first_loan_id": "L001",
        "expected_closed_loan_id": l_vikram,
    }


def run_seed() -> dict:
    _banner("LendTrack Stage 0 — SYNTHETIC DEVELOPMENT DATA ONLY")
    print("This is NOT production data.")
    print("This script will DESTROY and recreate the database at DB_PATH.")
    print(f"DB_PATH = {db.DB_PATH}")
    print()
    reset_database()
    summary = seed_all()
    print()
    _banner("SEED COMPLETE (SYNTHETIC)")
    print(f"Borrowers : {summary['expected_borrower_count']} "
          f"({summary['expected_first_borrower_id']} …)")
    print(f"Loans     : {summary['expected_loan_count']} "
          f"({summary['expected_first_loan_id']} …)")
    print(f"Closed    : {summary['expected_closed_loan_id']}")
    for name, lid in summary["loan_ids"].items():
        print(f"  {name:20} -> {lid}")
    return summary


if __name__ == "__main__":
    run_seed()
