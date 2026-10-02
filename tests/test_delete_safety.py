"""
Stage 6 tests — safe borrower / loan / transaction deletion.
"""

from __future__ import annotations

import pytest

import database as db


def test_delete_borrower_blocked_when_loans_exist(seeded_temp_db):
    _path, summary = seeded_temp_db
    bid = summary["borrowers_by_name"]["Prem Singh"]
    with pytest.raises(ValueError, match="Cannot delete borrower"):
        db.delete_borrower(bid)
    assert db.get_borrower(bid) is not None


def test_delete_borrower_allowed_when_empty(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Empty Person", "", "")
    db.delete_borrower(bid)
    assert db.get_borrower(bid) is None


def test_delete_loan_blocked_when_transactions_exist(seeded_temp_db):
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["prem"]
    with pytest.raises(ValueError, match="Cannot delete loan"):
        db.delete_loan(lid)
    assert db.get_loan(lid) is not None
    # History intact
    assert any(
        t["loan_id"] == lid
        for t in db.get_transactions_for_borrower(summary["borrowers_by_name"]["Prem Singh"])
    )


def test_close_loan_preserves_history(seeded_temp_db):
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["sneha"]
    bid = summary["borrowers_by_name"]["Sneha Kapoor"]
    before = len(db.get_transactions_for_borrower(bid))
    db.close_loan(lid)
    loan = db.get_loan(lid)
    assert loan["status"] == "Closed"
    assert len(db.get_transactions_for_borrower(bid)) == before
    assert loan["original_principal"] == 75000.0


def test_delete_loan_given_blocked(seeded_temp_db):
    _path, summary = seeded_temp_db
    bid = summary["borrowers_by_name"]["Prem Singh"]
    lid = summary["loan_ids"]["prem"]
    lg = next(
        t for t in db.get_transactions_for_borrower(bid)
        if t["loan_id"] == lid and t["txn_type"] == "Loan Given"
    )
    with pytest.raises(ValueError, match="Loan Given"):
        db.delete_transaction(lg["id"])
    assert db.get_loan(lid)["original_principal"] == 100000.0


def test_delete_principal_received_restores_outstanding(seeded_temp_db):
    _path, summary = seeded_temp_db
    bid = summary["borrowers_by_name"]["Anita Desai"]
    lid = summary["loan_ids"]["anita"]
    loan_before = db.get_loan(lid)
    assert loan_before["outstanding_principal"] == 40000.0

    pr = next(
        t for t in db.get_transactions_for_borrower(bid)
        if t["loan_id"] == lid and t["txn_type"] == "Principal Received"
    )
    deleted = db.delete_transaction(pr["id"])
    assert deleted["txn_type"] == "Principal Received"

    loan_after = db.get_loan(lid)
    assert loan_after["principal"] == 50000.0
    assert loan_after["outstanding_principal"] == 50000.0


def test_delete_interest_received_allowed(seeded_temp_db):
    _path, summary = seeded_temp_db
    bid = summary["borrowers_by_name"]["Prem Singh"]
    lid = summary["loan_ids"]["prem"]
    interest = next(
        t for t in db.get_transactions_for_borrower(bid)
        if t["loan_id"] == lid and t["txn_type"] == "Interest Received"
    )
    before = db.get_interest_received_for_loan(lid)
    db.delete_transaction(interest["id"])
    after = db.get_interest_received_for_loan(lid)
    assert after == before - interest["amount"]
