"""
Stage 8 — cross-cutting regression suite for Stages 1–7.

No product code changes. Uses synthetic seed + Excel fixtures only.
"""

from __future__ import annotations

import os

import pytest

import database as db
from src.services.duplicate_checker import DuplicateChecker
from src.services.excel_import_service import ExcelImportService
from src.services.historical_rebuild_service import HistoricalRebuildService
from src.services.import_classify import (
    apply_review_resolution,
    build_import_status,
    classify_import_rows,
)
from src.services.loan_matcher import LoanMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(ROOT, "tests", "fixtures", "excel")


def _classify(seeded_temp_db, filename: str):
    path, summary = seeded_temp_db
    xlsx = os.path.join(FIXTURE_DIR, filename)
    svc = ExcelImportService()
    rows, ok = svc.read_excel(xlsx)
    assert ok, svc.get_errors()
    matcher = LoanMatcher(path)
    dup = DuplicateChecker(path)
    result = classify_import_rows(rows, matcher, dup)
    return result, summary, rows, path


def _txn_count(loan_id: str | None = None) -> int:
    conn = db.get_connection()
    try:
        if loan_id:
            return conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE loan_id=?", (loan_id,)
            ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    finally:
        conn.close()


def _borrower_count() -> int:
    return len(db.get_all_borrowers())


def _loan_count() -> int:
    return len(db.get_all_loans())


# ── Matching matrix (Stage 3 + 4 fixtures) ───────────────────────────────────

@pytest.mark.parametrize(
    "filename,expect",
    [
        ("01_valid_import.xlsx", {"matched": 1, "review": 0, "dup": 0, "error": 0}),
        ("02_duplicate_existing.xlsx", {"matched": 0, "review": 0, "dup": 1, "error": 0}),
        ("03_duplicate_within_file.xlsx", {"matched": 1, "review": 0, "dup": 1, "error": 0}),
        ("04_ambiguous_match.xlsx", {"matched": 0, "review": 1, "dup": 0, "error": 0}),
        ("06_unmatched.xlsx", {"matched": 0, "review": 0, "dup": 0, "error": 2}),
        ("07_mixed_batch.xlsx", {"matched": 1, "review": 0, "dup": 1, "error": 1}),
    ],
)
def test_matching_matrix_fixture_counts(seeded_temp_db, filename, expect):
    result, _summary, rows, _path = _classify(seeded_temp_db, filename)
    assert len(result["matched_txns"]) == expect["matched"]
    assert len(result["review_txns"]) == expect["review"]
    assert len(result["duplicate_txns"]) == expect["dup"]
    assert len(result["error_txns"]) == expect["error"]
    # Sanity: every parsed row accounted for
    accounted = (
        len(result["matched_txns"])
        + len(result["review_txns"])
        + len(result["duplicate_txns"])
        + len(result["error_txns"])
    )
    assert accounted == len(rows)


def test_matching_matrix_closed_loan_not_error(seeded_temp_db):
    result, summary, _rows, _path = _classify(
        seeded_temp_db, "05_closed_loan_historical.xlsx"
    )
    assert result["error_txns"] == []
    assert result["review_txns"] == []
    combined = result["matched_txns"] + result["duplicate_txns"]
    assert len(combined) == 1
    assert combined[0]["loan"]["loan_id"] == summary["loan_ids"]["vikram_closed"]


def test_matching_matrix_karan_similar_interest_stays_review(seeded_temp_db):
    path, _summary = seeded_temp_db
    matcher = LoanMatcher(path)
    dup = DuplicateChecker(path)
    rows = [{
        "date": "2024-09-01",
        "borrower_name": "Karan Joshi",
        "due_day": 8,
        "txn_type": "Interest Received",
        "amount": 3000.0,
        "payment_mode": "Cash",
        "notes": "same expected interest both loans",
        "row_num": 2,
    }]
    result = classify_import_rows(rows, matcher, dup)
    assert len(result["review_txns"]) == 1
    assert result["matched_txns"] == []
    assert len(result["review_txns"][0]["candidates"]) == 2


def test_matching_matrix_old_display_name_fixture(seeded_temp_db):
    """
    Original-principal display name matches; outstanding-in-name does not
    silently assign (goes to error).
    """
    result, summary, rows, _path = _classify(seeded_temp_db, "09_old_display_name.xlsx")
    assert len(rows) == 2
    lid = summary["loan_ids"]["anita"]

    # Row with ₹50,000 (original) — matched or duplicate of seeded interest
    resolved = result["matched_txns"] + result["duplicate_txns"]
    assert len(resolved) == 1
    assert resolved[0]["loan"]["loan_id"] == lid

    # Row with ₹40,000 (outstanding) — must not silently match
    assert len(result["error_txns"]) == 1
    assert result["review_txns"] == []
    assert _borrower_count() == summary["expected_borrower_count"]
    assert _loan_count() == summary["expected_loan_count"]


# ── Atomic import + financial integrity (Stages 2 + 5) ───────────────────────

def test_e2e_valid_import_writes_without_mutating_principal(seeded_temp_db):
    result, summary, _rows, path = _classify(seeded_temp_db, "01_valid_import.xlsx")
    lid = summary["loan_ids"]["prem"]
    before_principal = db.get_loan(lid)["principal"]
    before_out = db.get_loan(lid)["outstanding_principal"]
    before_count = _txn_count(lid)

    batch = [{
        "borrower_id": item["loan"]["borrower_id"],
        "loan_id": item["loan"]["loan_id"],
        "txn_type": item["txn"]["txn_type"],
        "amount": item["txn"]["amount"],
        "txn_date": item["txn"]["date"],
        "notes": item["txn"].get("notes", ""),
        "payment_mode": item["txn"].get("payment_mode"),
    } for item in result["matched_txns"]]

    imported = db.add_transactions_batch(batch)
    assert imported == 1
    assert _txn_count(lid) == before_count + 1

    loan = db.get_loan(lid)
    assert loan["principal"] == before_principal
    assert loan["original_principal"] == before_principal
    assert loan["outstanding_principal"] == before_out  # interest only

    rebuild = HistoricalRebuildService(path).rebuild_all()
    assert rebuild["errors"] == 0
    assert db.get_loan(lid)["principal"] == before_principal


def test_e2e_batch_rollback_leaves_balances_intact(seeded_temp_db):
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["prem"]
    bid = summary["borrowers_by_name"]["Prem Singh"]
    before_count = _txn_count()
    before_loan = db.get_loan(lid)

    batch = [
        {
            "borrower_id": bid,
            "loan_id": lid,
            "txn_type": "Interest Received",
            "amount": 3000.0,
            "txn_date": "2024-10-01",
            "notes": "ok",
            "payment_mode": "Cash",
        },
        {
            "borrower_id": bid,
            "loan_id": lid,
            "txn_type": "Adjustment",
            "amount": 50.0,
            "txn_date": "2024-10-02",
            "notes": "should fail whole batch",
            "payment_mode": "Cash",
        },
    ]
    with pytest.raises(ValueError):
        db.add_transactions_batch(batch)

    assert _txn_count() == before_count
    after = db.get_loan(lid)
    assert after["principal"] == before_loan["principal"]
    assert after["outstanding_principal"] == before_loan["outstanding_principal"]


def test_e2e_principal_received_import_then_delete_roundtrip(seeded_temp_db):
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["sneha"]
    bid = summary["borrowers_by_name"]["Sneha Kapoor"]
    assert db.get_loan(lid)["outstanding_principal"] == 75000.0

    imported = db.add_transactions_batch([{
        "borrower_id": bid,
        "loan_id": lid,
        "txn_type": "Principal Received",
        "amount": 15000.0,
        "txn_date": "2024-09-15",
        "notes": "stage8 repayment",
        "payment_mode": "UPI",
    }])
    assert imported == 1
    loan = db.get_loan(lid)
    assert loan["principal"] == 75000.0
    assert loan["original_principal"] == 75000.0
    assert loan["outstanding_principal"] == 60000.0
    assert db.expected_monthly_interest(loan) == 1800.0  # 60000 * 3%

    pr = next(
        t for t in db.get_transactions_for_borrower(bid)
        if t["loan_id"] == lid
        and t["txn_type"] == "Principal Received"
        and t["txn_date"] == "2024-09-15"
    )
    db.delete_transaction(pr["id"])
    restored = db.get_loan(lid)
    assert restored["outstanding_principal"] == 75000.0
    assert restored["principal"] == 75000.0


# ── Delete safety regressions (Stage 6) ──────────────────────────────────────

def test_delete_safety_cannot_wipe_history_via_loan_or_borrower(seeded_temp_db):
    _path, summary = seeded_temp_db
    bid = summary["borrowers_by_name"]["Anita Desai"]
    lid = summary["loan_ids"]["anita"]
    before_txns = len(db.get_transactions_for_borrower(bid))

    with pytest.raises(ValueError):
        db.delete_loan(lid)
    with pytest.raises(ValueError):
        db.delete_borrower(bid)

    assert db.get_loan(lid) is not None
    assert db.get_borrower(bid) is not None
    assert len(db.get_transactions_for_borrower(bid)) == before_txns


def test_close_loan_alternative_keeps_matchable_history(seeded_temp_db):
    path, summary = seeded_temp_db
    lid = summary["loan_ids"]["pammi"]
    bid = summary["borrowers_by_name"]["Pammi"]
    db.close_loan(lid)
    assert db.get_loan(lid)["status"] == "Closed"

    matcher = LoanMatcher(path)
    loan, _cands, status = matcher.match_by_borrower_due_day("Pammi", 20)
    assert status == "exact_match"
    assert loan["loan_id"] == lid
    assert len(db.get_transactions_for_borrower(bid)) >= 1  # Loan Given remains


# ── Ambiguous resolution → write (Stage 7 + 2) ───────────────────────────────

def test_ambiguous_select_then_import_no_silent_loan_create(seeded_temp_db):
    result, summary, _rows, path = _classify(seeded_temp_db, "04_ambiguous_match.xlsx")
    assert len(result["review_txns"]) == 1
    review = result["review_txns"][0]
    chosen = next(
        c for c in review["candidates"]
        if c["loan_id"] == summary["loan_ids"]["rahul_sharma_2"]
    )

    borrowers_before = _borrower_count()
    loans_before = _loan_count()
    matched, duplicates, skipped = [], [], []
    outcome = apply_review_resolution(
        review, chosen, False, DuplicateChecker(path), matched, duplicates, skipped
    )
    assert outcome == "matched"
    assert len(matched) == 1

    imported = db.add_transactions_batch([{
        "borrower_id": matched[0]["loan"]["borrower_id"],
        "loan_id": matched[0]["loan"]["loan_id"],
        "txn_type": matched[0]["txn"]["txn_type"],
        "amount": matched[0]["txn"]["amount"],
        "txn_date": matched[0]["txn"]["date"],
        "notes": matched[0]["txn"].get("notes", ""),
        "payment_mode": matched[0]["txn"].get("payment_mode"),
    }])
    assert imported == 1
    assert _borrower_count() == borrowers_before
    assert _loan_count() == loans_before

    # Preference went to loan 2 explicitly — not silent assign to loan 1
    bid = summary["borrowers_by_name"]["Rahul Sharma"]
    saved = [
        t for t in db.get_transactions_for_borrower(bid)
        if t["txn_date"] == matched[0]["txn"]["date"]
        and t["amount"] == matched[0]["txn"]["amount"]
    ]
    assert len(saved) == 1
    assert saved[0]["loan_id"] == summary["loan_ids"]["rahul_sharma_2"]


def test_ambiguous_skip_imports_nothing_and_status_honest(seeded_temp_db):
    result, _summary, _rows, path = _classify(seeded_temp_db, "04_ambiguous_match.xlsx")
    review = result["review_txns"][0]
    matched, duplicates, skipped = [], [], []
    outcome = apply_review_resolution(
        review, None, True, DuplicateChecker(path), matched, duplicates, skipped
    )
    assert outcome == "skipped"
    assert matched == []
    assert len(skipped) == 1

    status = build_import_status(
        imported=0,
        failed=0,
        matched_count=0,
        duplicate_count=0,
        error_count=0,
        review_count=0,
        skipped_review_count=len(skipped),
    )
    assert status["status"] == "nothing_imported"
    assert "SUCCESSFUL" not in status["headline"]


def test_unmatched_never_creates_borrowers_or_loans(seeded_temp_db):
    result, _summary, _rows, _path = _classify(seeded_temp_db, "06_unmatched.xlsx")
    assert len(result["error_txns"]) == 2
    borrowers_before = _borrower_count()
    loans_before = _loan_count()
    txns_before = _txn_count()

    # Mimic wizard: only matched rows would be written; unmatched stay errors
    assert result["matched_txns"] == []
    assert _borrower_count() == borrowers_before
    assert _loan_count() == loans_before
    assert _txn_count() == txns_before


def test_closed_loan_new_interest_import_preserves_closed_status(seeded_temp_db):
    """Non-duplicate interest on closed Vikram should write without reopening."""
    result, summary, _rows, path = _classify(
        seeded_temp_db, "05_closed_loan_historical.xlsx"
    )
    lid = summary["loan_ids"]["vikram_closed"]
    # Prefer matched path; if fixture collides as duplicate, craft a fresh row
    if result["matched_txns"]:
        items = result["matched_txns"]
    else:
        items = [{
            "txn": {
                "date": "2023-09-01",
                "txn_type": "Interest Received",
                "amount": 500.0,
                "notes": "stage8 closed interest",
                "payment_mode": "Cash",
            },
            "loan": db.get_loan(lid),
        }]

    before = db.get_loan(lid)
    assert before["status"] == "Closed"
    assert before["original_principal"] == 30000.0

    imported = db.add_transactions_batch([{
        "borrower_id": items[0]["loan"]["borrower_id"],
        "loan_id": lid,
        "txn_type": items[0]["txn"]["txn_type"],
        "amount": items[0]["txn"]["amount"],
        "txn_date": items[0]["txn"]["date"],
        "notes": items[0]["txn"].get("notes", ""),
        "payment_mode": items[0]["txn"].get("payment_mode"),
    }])
    assert imported == 1
    after = db.get_loan(lid)
    assert after["status"] == "Closed"
    assert after["original_principal"] == 30000.0
    assert after["outstanding_principal"] == 0.0
    assert HistoricalRebuildService(path).rebuild_all()["errors"] == 0


# ── Canonical path / status honesty (Stages 1 + 4) ───────────────────────────

def test_import_services_share_seeded_canonical_path(seeded_temp_db):
    path, summary = seeded_temp_db
    assert path == db.DB_PATH
    matcher = LoanMatcher(path)
    dup = DuplicateChecker(path)
    assert any(
        l["loan_id"] == summary["loan_ids"]["prem"]
        for l in matcher.loans_cache.get("Prem Singh", [])
    )
    txn = {
        "date": "2024-02-15",
        "txn_type": "Interest Received",
        "amount": 3000.0,
    }
    assert dup.check_duplicate(txn, summary["loan_ids"]["prem"]) is True


def test_status_honesty_matrix():
    assert build_import_status(0, 3, 3, 0, 0, 0, "boom")["status"] == "rolled_back"
    assert build_import_status(0, 0, 0, 0, 0, 2)["status"] == "review_only"
    assert build_import_status(0, 0, 0, 0, 0, 0, skipped_review_count=1)["status"] == (
        "nothing_imported"
    )
    ok = build_import_status(2, 0, 2, 1, 0, 0)
    assert ok["status"] == "success"
    assert "SUCCESSFUL" in ok["headline"]
    mixed = build_import_status(0, 0, 0, 2, 1, 0)
    assert mixed["status"] == "nothing_imported"
    assert "SUCCESSFUL" not in mixed["headline"]
