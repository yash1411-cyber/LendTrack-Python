"""
Stage 0 smoke tests — environment, schema, seed determinism.
No product bug-fix assertions.
"""

from __future__ import annotations

import os
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_venv_imports():
    """Important project modules import successfully."""
    import database
    import main  # noqa: F401 — ensures CustomTkinter app module loads
    import ui_dashboard
    import ui_borrowers
    import ui_loans
    import ui_transactions
    import ui_reports
    from src.services import excel_import_service
    from src.services import loan_matcher
    from src.services import duplicate_checker
    from src.services import historical_rebuild_service
    from src.ui import import_dialog

    assert database.DB_PATH.endswith("lendtrack.db")
    assert excel_import_service.ExcelImportService is not None
    assert loan_matcher.LoanMatcher is not None
    assert duplicate_checker.DuplicateChecker is not None
    assert historical_rebuild_service.HistoricalRebuildService is not None
    assert import_dialog.ImportDialog is not None
    assert ui_dashboard.DashboardFrame is not None
    assert ui_borrowers.BorrowersFrame is not None
    assert ui_loans.LoansFrame is not None
    assert ui_transactions.TransactionsFrame is not None
    assert ui_reports.ReportsFrame is not None

    # ambiguous_match_dialog.py currently fails to import due to a pre-existing
    # missing `Tuple` annotation import (product bug for Stage 7). Stage 0 only
    # verifies the file is present — do not "fix" that bug here.
    amb_path = os.path.join(ROOT, "src", "ui", "ambiguous_match_dialog.py")
    assert os.path.isfile(amb_path)


def test_initialize_db_creates_tables(initialized_temp_db):
    """Schema creates the four expected tables on a temp DB."""
    conn = sqlite3.connect(initialized_temp_db)
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    }
    conn.close()
    assert "borrowers" in names
    assert "loans" in names
    assert "transactions" in names
    assert "interest_ledger" in names


def test_seed_is_deterministic(temp_db_path, monkeypatch):
    """Seeding twice on a fresh temp DB yields the same IDs and counts."""
    import database as db
    from scripts.seed_dev_db import reset_database, seed_all

    monkeypatch.setattr(db, "DB_PATH", temp_db_path)

    reset_database()
    first = seed_all()

    assert first["expected_first_borrower_id"] == "B001"
    assert first["expected_first_loan_id"] == "L001"
    assert first["borrower_ids"][0] == "B001"
    assert first["loan_ids"]["prem"] == "L001"
    assert len(first["borrower_ids"]) == first["expected_borrower_count"]
    assert len(first["loan_ids"]) == first["expected_loan_count"]

    # Closed Vikram loan must be present and Closed
    closed = db.get_loan(first["expected_closed_loan_id"])
    assert closed is not None
    assert closed["status"] == "Closed"
    assert closed["borrower_name"] == "Vikram Mehta"

    # Re-seed from scratch — same IDs
    reset_database()
    second = seed_all()
    assert second["borrower_ids"] == first["borrower_ids"]
    assert second["loan_ids"] == first["loan_ids"]
    assert second["expected_closed_loan_id"] == first["expected_closed_loan_id"]

    # Named borrowers exist
    names = {row["name"] for row in db.get_all_borrowers()}
    for required in ("Rahul Sharma", "Rahul Verma", "Rashid", "Pammi", "Prem Singh"):
        assert required in names


def test_excel_fixtures_exist():
    """Committed Excel fixtures are present for later stages."""
    fixture_dir = os.path.join(ROOT, "tests", "fixtures", "excel")
    required = [
        "01_valid_import.xlsx",
        "02_duplicate_existing.xlsx",
        "03_duplicate_within_file.xlsx",
        "04_ambiguous_match.xlsx",
        "05_closed_loan_historical.xlsx",
        "06_unmatched.xlsx",
        "07_mixed_batch.xlsx",
        "08_mid_import_failure.xlsx",
        "09_old_display_name.xlsx",
    ]
    for name in required:
        path = os.path.join(fixture_dir, name)
        assert os.path.isfile(path), f"Missing fixture: {path}"
