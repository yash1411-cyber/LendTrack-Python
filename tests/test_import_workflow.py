"""
Stage 4 tests — import classification, duplicates, honest status.
"""

from __future__ import annotations

import os

from src.services.duplicate_checker import DuplicateChecker
from src.services.excel_import_service import ExcelImportService
from src.services.import_classify import classify_import_rows, build_import_status
from src.services.loan_matcher import LoanMatcher

FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests",
    "fixtures",
    "excel",
)


def _classify_fixture(seeded_temp_db, filename: str):
    path, summary = seeded_temp_db
    xlsx = os.path.join(FIXTURE_DIR, filename)
    svc = ExcelImportService()
    rows, ok = svc.read_excel(xlsx)
    assert ok, svc.get_errors()
    matcher = LoanMatcher(path)
    dup = DuplicateChecker(path)
    result = classify_import_rows(rows, matcher, dup)
    return result, summary, rows


def test_valid_import_classifies_as_matched(seeded_temp_db):
    result, summary, _rows = _classify_fixture(seeded_temp_db, "01_valid_import.xlsx")
    assert len(result["matched_txns"]) == 1
    assert result["matched_txns"][0]["loan"]["loan_id"] == summary["loan_ids"]["prem"]
    assert result["duplicate_txns"] == []
    assert result["error_txns"] == []


def test_database_duplicate_detected(seeded_temp_db):
    result, _summary, _rows = _classify_fixture(
        seeded_temp_db, "02_duplicate_existing.xlsx"
    )
    assert len(result["duplicate_txns"]) == 1
    assert result["duplicate_txns"][0]["reason"] == "database"
    assert result["matched_txns"] == []


def test_within_file_duplicates_detected(seeded_temp_db):
    result, _summary, rows = _classify_fixture(
        seeded_temp_db, "03_duplicate_within_file.xlsx"
    )
    assert len(rows) == 2
    assert len(result["matched_txns"]) == 1
    assert len(result["duplicate_txns"]) == 1
    assert result["duplicate_txns"][0]["reason"] == "within_file"


def test_ambiguous_goes_to_review_not_matched(seeded_temp_db):
    result, _summary, _rows = _classify_fixture(
        seeded_temp_db, "04_ambiguous_match.xlsx"
    )
    assert len(result["review_txns"]) == 1
    assert result["matched_txns"] == []
    assert len(result["review_txns"][0]["candidates"]) >= 2


def test_closed_loan_historical_matches(seeded_temp_db):
    result, summary, _rows = _classify_fixture(
        seeded_temp_db, "05_closed_loan_historical.xlsx"
    )
    # May be duplicate of seeded interest OR matched — either is valid classification;
    # must not be an error / unmatched.
    assert result["error_txns"] == []
    combined = result["matched_txns"] + result["duplicate_txns"]
    assert len(combined) == 1
    loan_id = combined[0]["loan"]["loan_id"]
    assert loan_id == summary["loan_ids"]["vikram_closed"]


def test_unmatched_goes_to_errors(seeded_temp_db):
    result, _summary, rows = _classify_fixture(seeded_temp_db, "06_unmatched.xlsx")
    assert len(rows) == 2
    assert len(result["error_txns"]) == 2
    assert result["matched_txns"] == []


def test_mixed_batch_counts(seeded_temp_db):
    result, _summary, rows = _classify_fixture(seeded_temp_db, "07_mixed_batch.xlsx")
    assert len(rows) == 3
    assert len(result["matched_txns"]) == 1  # valid Prem
    assert len(result["duplicate_txns"]) == 1  # dup of seed
    assert len(result["error_txns"]) == 1  # Ghost Borrower
    assert result["review_txns"] == []


def test_build_import_status_honest():
    assert build_import_status(0, 5, 5, 0, 0, 0, "boom")["status"] == "rolled_back"
    assert "SUCCESSFUL" not in build_import_status(0, 5, 5, 0, 0, 0, "boom")["headline"]

    ok = build_import_status(2, 0, 2, 1, 0, 1)
    assert ok["status"] == "success"
    assert "review" in ok["detail"].lower()

    review_only = build_import_status(0, 0, 0, 0, 0, 3)
    assert review_only["status"] == "review_only"
    assert "SUCCESSFUL" not in review_only["headline"]

    nothing = build_import_status(0, 0, 0, 2, 1, 0)
    assert nothing["status"] == "nothing_imported"
    assert "SUCCESSFUL" not in nothing["headline"]


def test_excel_service_resets_errors_between_reads(seeded_temp_db):
    _path, _summary = seeded_temp_db
    svc = ExcelImportService()
    bad = os.path.join(FIXTURE_DIR, "06_unmatched.xlsx")
    # Force a missing-sheet style failure via nonexistent file
    rows, ok = svc.read_excel(os.path.join(FIXTURE_DIR, "does_not_exist.xlsx"))
    assert ok is False
    assert svc.get_errors()
    first_err_count = len(svc.get_errors())

    rows2, ok2 = svc.read_excel(os.path.join(FIXTURE_DIR, "01_valid_import.xlsx"))
    assert ok2 is True
    # Errors from previous read must not linger
    assert svc.get_errors() == [] or len(svc.get_errors()) < first_err_count
    assert len(rows2) == 1


def test_duplicate_checker_returns_all_db_ids(seeded_temp_db):
    path, summary = seeded_temp_db
    dup = DuplicateChecker(path)
    txn = {
        "date": "2024-02-15",
        "txn_type": "Interest Received",
        "amount": 3000.0,
    }
    ids = dup.get_duplicate_ids(txn, summary["loan_ids"]["prem"])
    assert len(ids) >= 1
    assert dup.classify_duplicate(txn, summary["loan_ids"]["prem"]) == "database"
