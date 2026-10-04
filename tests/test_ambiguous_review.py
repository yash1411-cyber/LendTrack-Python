"""
Stage 7 tests — explicit ambiguous match resolution (no silent assignment).
"""

from __future__ import annotations

from src.services.duplicate_checker import DuplicateChecker
from src.services.import_classify import (
    classify_import_rows,
    apply_review_resolution,
    build_import_status,
)
from src.services.loan_matcher import LoanMatcher
from src.ui.ambiguous_match_dialog import AmbiguousMatchDialog


def test_ambiguous_match_dialog_imports():
    assert AmbiguousMatchDialog is not None
    assert callable(AmbiguousMatchDialog.get_result)


def test_apply_review_select_adds_matched(seeded_temp_db):
    path, summary = seeded_temp_db
    matcher = LoanMatcher(path)
    dup = DuplicateChecker(path)
    classified = classify_import_rows(
        [{
            "date": "2024-09-10",
            "borrower_name": "Rahul Sharma",
            "due_day": 5,
            "txn_type": "Interest Received",
            "amount": 2500.0,
            "payment_mode": "UPI",
            "notes": "",
            "row_num": 2,
        }],
        matcher,
        dup,
    )
    assert len(classified["review_txns"]) == 1
    review = classified["review_txns"][0]
    chosen = next(
        c for c in review["candidates"]
        if c["loan_id"] == summary["loan_ids"]["rahul_sharma_1"]
    )

    matched, duplicates, skipped = [], [], []
    outcome = apply_review_resolution(
        review, chosen, False, dup, matched, duplicates, skipped
    )
    assert outcome == "matched"
    assert len(matched) == 1
    assert matched[0]["loan"]["loan_id"] == summary["loan_ids"]["rahul_sharma_1"]
    assert skipped == []
    assert duplicates == []


def test_apply_review_skip(seeded_temp_db):
    path, _summary = seeded_temp_db
    matcher = LoanMatcher(path)
    dup = DuplicateChecker(path)
    classified = classify_import_rows(
        [{
            "date": "2024-09-10",
            "borrower_name": "Rahul Sharma",
            "due_day": 5,
            "txn_type": "Interest Received",
            "amount": 2500.0,
            "payment_mode": "Cash",
            "notes": "",
            "row_num": 2,
        }],
        matcher,
        dup,
    )
    review = classified["review_txns"][0]
    matched, duplicates, skipped = [], [], []
    outcome = apply_review_resolution(
        review, None, True, dup, matched, duplicates, skipped
    )
    assert outcome == "skipped"
    assert matched == []
    assert len(skipped) == 1


def test_apply_review_rejects_loan_not_in_candidates(seeded_temp_db):
    path, summary = seeded_temp_db
    matcher = LoanMatcher(path)
    dup = DuplicateChecker(path)
    classified = classify_import_rows(
        [{
            "date": "2024-09-10",
            "borrower_name": "Rahul Sharma",
            "due_day": 5,
            "txn_type": "Interest Received",
            "amount": 2500.0,
            "payment_mode": "Cash",
            "notes": "",
            "row_num": 2,
        }],
        matcher,
        dup,
    )
    review = classified["review_txns"][0]
    # Prem's loan is not a candidate for Rahul Sharma due day 5
    wrong = {"loan_id": summary["loan_ids"]["prem"], "borrower_id": "B005"}
    matched, duplicates, skipped = [], [], []
    outcome = apply_review_resolution(
        review, wrong, False, dup, matched, duplicates, skipped
    )
    assert outcome == "invalid"
    assert matched == []


def test_apply_review_duplicate_after_select(seeded_temp_db):
    path, summary = seeded_temp_db
    matcher = LoanMatcher(path)
    dup = DuplicateChecker(path)
    # Seed already has Rahul Sharma interest on L004 for 2024-02-20 amount 3000
    classified = classify_import_rows(
        [{
            "date": "2024-02-20",
            "borrower_name": "Rahul Sharma",
            "due_day": 5,
            "txn_type": "Interest Received",
            "amount": 3000.0,
            "payment_mode": "Cash",
            "notes": "",
            "row_num": 2,
        }],
        matcher,
        dup,
    )
    assert len(classified["review_txns"]) == 1
    review = classified["review_txns"][0]
    chosen = next(
        c for c in review["candidates"]
        if c["loan_id"] == summary["loan_ids"]["rahul_sharma_1"]
    )
    matched, duplicates, skipped = [], [], []
    outcome = apply_review_resolution(
        review, chosen, False, dup, matched, duplicates, skipped
    )
    assert outcome == "duplicate"
    assert duplicates[0]["reason"] == "database"
    assert matched == []


def test_status_accounts_for_skipped_review():
    status = build_import_status(
        imported=0,
        failed=0,
        matched_count=0,
        duplicate_count=0,
        error_count=0,
        review_count=0,
        skipped_review_count=2,
    )
    assert status["status"] == "nothing_imported"
    assert "skipped" in status["detail"].lower()
