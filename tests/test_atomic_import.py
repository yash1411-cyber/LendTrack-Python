"""
Stage 2 tests — atomic import writes and transaction API contract.
"""

from __future__ import annotations

import pytest

import database as db


def _count_txns(loan_id: str = None) -> int:
    conn = db.get_connection()
    try:
        if loan_id:
            return conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE loan_id=?", (loan_id,)
            ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    finally:
        conn.close()


def test_add_transaction_accepts_payment_mode(seeded_temp_db):
    """payment_mode kwarg must not raise; value is folded into notes."""
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["prem"]
    bid = summary["borrowers_by_name"]["Prem Singh"]
    before = _count_txns(lid)

    db.add_transaction(
        borrower_id=bid,
        loan_id=lid,
        txn_type="Interest Received",
        amount=3000.0,
        txn_date="2024-08-15",
        notes="stage2 test",
        payment_mode="UPI",
    )

    assert _count_txns(lid) == before + 1
    rows = [
        t for t in db.get_transactions_for_borrower(bid)
        if t["txn_date"] == "2024-08-15" and t["loan_id"] == lid
    ]
    assert len(rows) == 1
    assert "[Payment: UPI]" in (rows[0]["notes"] or "")


def test_import_write_without_payment_mode_kw_crash(seeded_temp_db):
    """Mirrors Excel import kwargs that previously caused TypeError."""
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["sneha"]
    bid = summary["borrowers_by_name"]["Sneha Kapoor"]
    before = _count_txns()

    # Exact keyword pattern used by ImportDialog (pre-Stage-2 crash)
    db.add_transaction(
        borrower_id=bid,
        loan_id=lid,
        txn_type="Interest Received",
        amount=2250.0,
        payment_mode="Cash",
        txn_date="2024-08-21",
        notes="import-style call",
    )
    assert _count_txns() == before + 1


def test_import_commit_all_on_success(seeded_temp_db):
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["prem"]
    bid = summary["borrowers_by_name"]["Prem Singh"]
    before = _count_txns()

    batch = [
        {
            "borrower_id": bid,
            "loan_id": lid,
            "txn_type": "Interest Received",
            "amount": 3000.0,
            "txn_date": "2024-09-01",
            "notes": "batch 1",
            "payment_mode": "Cash",
        },
        {
            "borrower_id": bid,
            "loan_id": lid,
            "txn_type": "Interest Received",
            "amount": 3000.0,
            "txn_date": "2024-10-01",
            "notes": "batch 2",
            "payment_mode": "Online",
        },
    ]
    n = db.add_transactions_batch(batch)
    assert n == 2
    assert _count_txns() == before + 2


def test_import_rollback_on_mid_failure(seeded_temp_db):
    """If any row fails, no rows from the batch are persisted."""
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["prem"]
    bid = summary["borrowers_by_name"]["Prem Singh"]
    before = _count_txns()
    before_prem = _count_txns(lid)

    batch = [
        {
            "borrower_id": bid,
            "loan_id": lid,
            "txn_type": "Interest Received",
            "amount": 3000.0,
            "txn_date": "2024-11-01",
            "notes": "ok first",
            "payment_mode": "Cash",
        },
        {
            "borrower_id": bid,
            "loan_id": lid,
            "txn_type": "Interest Received",
            "amount": -50.0,  # invalid — triggers ValueError mid-batch
            "txn_date": "2024-11-02",
            "notes": "bad amount",
            "payment_mode": "Cash",
        },
        {
            "borrower_id": bid,
            "loan_id": lid,
            "txn_type": "Interest Received",
            "amount": 3000.0,
            "txn_date": "2024-11-03",
            "notes": "would be third",
            "payment_mode": "Cash",
        },
    ]

    with pytest.raises(ValueError):
        db.add_transactions_batch(batch)

    assert _count_txns() == before
    assert _count_txns(lid) == before_prem


def test_manual_add_transaction_without_payment_mode_still_works(seeded_temp_db):
    """UI path without payment_mode must keep working."""
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["pammi"]
    bid = summary["borrowers_by_name"]["Pammi"]
    before = _count_txns(lid)
    db.add_transaction(bid, lid, "Interest Received", 1000.0, "2024-08-01", "manual")
    assert _count_txns(lid) == before + 1
