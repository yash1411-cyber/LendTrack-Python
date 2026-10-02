"""
Regression tests for:
  Bug 1 — loan edit must never duplicate Loan Given / inflate principal
  Bug 2 — close → reopen same loan must remain matchable for Excel import
"""

from __future__ import annotations

import pytest

import database as db
from src.services.duplicate_checker import DuplicateChecker
from src.services.import_classify import classify_import_rows
from src.services.loan_matcher import LoanMatcher


def _loan_given_rows(loan_id: str):
    conn = db.get_connection()
    try:
        return conn.execute(
            """SELECT id, amount, txn_date FROM transactions
               WHERE loan_id=? AND txn_type='Loan Given'
               ORDER BY id ASC""",
            (loan_id,),
        ).fetchall()
    finally:
        conn.close()


def _assert_single_loan_given(loan_id: str, amount: float = 100000.0):
    rows = _loan_given_rows(loan_id)
    assert len(rows) == 1
    assert float(rows[0]["amount"]) == amount
    loan = db.get_loan(loan_id)
    assert loan["principal"] == amount
    assert loan["original_principal"] == amount
    assert loan["outstanding_principal"] == amount


def test_new_loan_creates_exactly_one_loan_given(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Edit User", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 5, "2024-01-15")
    _assert_single_loan_given(lid, 100000.0)


def test_edit_roi_does_not_duplicate_loan_given(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Edit User", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 5, "2024-01-15")

    db.update_loan(lid, 100000.0, 3.5, 5, "2024-01-15", "Active")
    _assert_single_loan_given(lid, 100000.0)
    assert db.get_loan(lid)["interest_rate"] == 3.5


def test_edit_due_day_preserves_financials(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Edit User", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 5, "2024-01-15")

    db.update_loan(lid, 100000.0, 3.0, 12, "2024-01-15", "Active")
    _assert_single_loan_given(lid, 100000.0)
    assert db.get_loan(lid)["due_day"] == 12


def test_edit_start_date_preserves_financials_and_one_loan_given(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Edit User", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 5, "2024-01-15")

    db.update_loan(lid, 100000.0, 3.0, 5, "2024-02-01", "Active")
    _assert_single_loan_given(lid, 100000.0)
    loan = db.get_loan(lid)
    assert loan["start_date"] == "2024-02-01"
    # Foundational Loan Given date stays aligned with start_date identity
    assert _loan_given_rows(lid)[0]["txn_date"] == "2024-02-01"


def test_repeated_edits_never_inflate_principal(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Edit User", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 5, "2024-01-15")

    for i in range(8):
        db.update_loan(lid, 100000.0, 3.0 + (i * 0.1), 5, "2024-01-15", "Active")

    _assert_single_loan_given(lid, 100000.0)
    assert len(_loan_given_rows(lid)) == 1


def test_manual_loan_given_transaction_rejected_when_one_exists(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Edit User", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 5, "2024-01-15")
    with pytest.raises(ValueError, match="Loan Given already exists"):
        db.add_transaction(bid, lid, "Loan Given", 100000.0, "2024-03-01", "dup")
    _assert_single_loan_given(lid, 100000.0)


def test_update_collapses_preexisting_duplicate_loan_givens(temp_db_path, monkeypatch):
    """If legacy data already has extra Loan Givens, edit must not keep inflating."""
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Edit User", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 5, "2024-01-15")
    # Simulate legacy duplicate bypassing API
    conn = db.get_connection()
    conn.execute(
        """INSERT INTO transactions (borrower_id, loan_id, txn_type, amount, txn_date, notes)
           VALUES (?,?,?,?,?,?)""",
        (bid, lid, "Loan Given", 100000.0, "2024-03-01", "legacy dup"),
    )
    conn.commit()
    conn.close()
    assert len(_loan_given_rows(lid)) == 2

    db.update_loan(lid, 100000.0, 3.25, 5, "2024-01-15", "Active")
    _assert_single_loan_given(lid, 100000.0)


def test_legitimate_principal_increase_updates_single_loan_given(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Edit User", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 5, "2024-01-15")
    db.update_loan(lid, 125000.0, 3.0, 5, "2024-01-15", "Active")
    _assert_single_loan_given(lid, 125000.0)


def test_close_reopen_same_loan_matchable_by_due_day(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Reopen User", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 25, "2024-01-15")
    db.add_transaction(bid, lid, "Interest Received", 3000.0, "2024-02-15")

    db.close_loan(lid)
    assert db.get_loan(lid)["status"] == "Closed"
    assert len(_loan_given_rows(lid)) == 1

    db.reopen_loan(lid)
    loan = db.get_loan(lid)
    assert loan["status"] == "Active"
    assert loan["start_date"] == "2024-01-15"
    assert loan["due_day"] == 25
    assert loan["original_principal"] == 100000.0
    assert len(_loan_given_rows(lid)) == 1
    assert len(db.get_loans_for_borrower(bid)) == 1  # same loan, not a new one

    matcher = LoanMatcher(temp_db_path)
    matched, cands, status = matcher.match_by_borrower_due_day("Reopen User", 25)
    assert status == "exact_match"
    assert matched["loan_id"] == lid
    assert len(cands) == 1

    dup = DuplicateChecker(temp_db_path)
    result = classify_import_rows(
        [{
            "date": "2024-08-15",
            "borrower_name": "Reopen User",
            "due_day": 25,
            "txn_type": "Interest Received",
            "amount": 3000.0,
            "payment_mode": "Cash",
            "notes": "after reopen",
            "row_num": 2,
        }],
        matcher,
        dup,
    )
    assert len(result["matched_txns"]) == 1
    assert result["matched_txns"][0]["loan"]["loan_id"] == lid
    assert result["error_txns"] == []


def test_close_reopen_matchable_by_display_name(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Display User", "", "")
    lid = db.add_loan(bid, 60000.0, 3.0, 15, "2024-03-01")
    db.add_transaction(bid, lid, "Interest Received", 1800.0, "2024-04-01")

    matcher_before = LoanMatcher(temp_db_path)
    display = matcher_before.loans_cache["Display User"][0]["display_name"]

    db.close_loan(lid)
    db.reopen_loan(lid)

    matcher = LoanMatcher(temp_db_path)
    matched, status = matcher.match_by_display_name("Display User", display)
    assert status == "matched"
    assert matched["loan_id"] == lid
    assert db.get_loan(lid)["start_date"] == "2024-03-01"
    assert len(_loan_given_rows(lid)) == 1


def test_reopen_via_update_status_preserves_match_identity(temp_db_path, monkeypatch):
    """Edit-dialog style reopen (status Active) must keep start/due/principal."""
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Status User", "", "")
    lid = db.add_loan(bid, 80000.0, 2.5, 10, "2024-04-12")
    db.close_loan(lid)
    loan = db.get_loan(lid)
    db.update_loan(
        lid,
        loan["original_principal"],
        loan["interest_rate"],
        loan["due_day"],
        loan["start_date"],
        "Active",
    )
    assert db.get_loan(lid)["start_date"] == "2024-04-12"
    matcher = LoanMatcher(temp_db_path)
    matched, _c, status = matcher.match_by_borrower_due_day("Status User", 10)
    assert status == "exact_match"
    assert matched["loan_id"] == lid
