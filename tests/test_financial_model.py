"""
Stage 5 tests — original principal, outstanding, interest base, rebuild, Adjustment.
"""

from __future__ import annotations

import pytest

import database as db
from src.services.historical_rebuild_service import HistoricalRebuildService


def test_principal_not_mutated_on_repayment(seeded_temp_db):
    path, summary = seeded_temp_db
    lid = summary["loan_ids"]["anita"]
    loan = db.get_loan(lid)
    assert loan["principal"] == 50000.0
    assert loan["original_principal"] == 50000.0
    assert loan["outstanding_principal"] == 40000.0


def test_interest_uses_outstanding_not_original(seeded_temp_db):
    _path, summary = seeded_temp_db
    loan = db.get_loan(summary["loan_ids"]["anita"])
    # 40000 * 2.5% = 1000
    assert db.expected_monthly_interest(loan) == 1000.0


def test_closed_loan_retains_original_principal(seeded_temp_db):
    _path, summary = seeded_temp_db
    loan = db.get_loan(summary["loan_ids"]["vikram_closed"])
    assert loan["status"] == "Closed"
    assert loan["original_principal"] == 30000.0
    assert loan["outstanding_principal"] == 0.0
    assert loan["principal"] == 30000.0


def test_adjustment_rejected(seeded_temp_db):
    _path, summary = seeded_temp_db
    bid = summary["borrowers_by_name"]["Prem Singh"]
    lid = summary["loan_ids"]["prem"]
    with pytest.raises(ValueError, match="Adjustment"):
        db.add_transaction(bid, lid, "Adjustment", 100.0, "2024-09-01", "nope")


def test_principal_received_cannot_exceed_outstanding(seeded_temp_db):
    _path, summary = seeded_temp_db
    bid = summary["borrowers_by_name"]["Sneha Kapoor"]
    lid = summary["loan_ids"]["sneha"]
    with pytest.raises(ValueError, match="exceeds outstanding"):
        db.add_transaction(bid, lid, "Principal Received", 999999.0, "2024-09-01")


def test_repair_restores_mutated_legacy_principal(temp_db_path, monkeypatch):
    """Simulate legacy mutated principal then repair."""
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Legacy User", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 5, "2024-01-01")
    # Force legacy mutation directly
    conn = db.get_connection()
    conn.execute("UPDATE loans SET principal=70000 WHERE loan_id=?", (lid,))
    conn.execute(
        """INSERT INTO transactions (borrower_id, loan_id, txn_type, amount, txn_date, notes)
           VALUES (?,?,?,?,?,?)""",
        (bid, lid, "Principal Received", 30000.0, "2024-02-01", "legacy"),
    )
    conn.commit()
    conn.close()

    conn = db.get_connection()
    raw = conn.execute("SELECT principal FROM loans WHERE loan_id=?", (lid,)).fetchone()["principal"]
    conn.close()
    assert raw == 70000.0

    updated = db.repair_loan_principals(temp_db_path)
    assert updated >= 1
    loan = db.get_loan(lid)
    assert loan["principal"] == 100000.0
    assert loan["outstanding_principal"] == 70000.0


def test_rebuild_service_no_outstanding_column_error(seeded_temp_db):
    path, _summary = seeded_temp_db
    result = HistoricalRebuildService(path).rebuild_all()
    assert result["errors"] == 0


def test_update_loan_syncs_loan_given(seeded_temp_db):
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["sneha"]
    loan = db.get_loan(lid)
    db.update_loan(lid, 80000.0, loan["interest_rate"], loan["due_day"], loan["start_date"], "Active")
    updated = db.get_loan(lid)
    assert updated["principal"] == 80000.0
    assert updated["original_principal"] == 80000.0
    txns = [t for t in db.get_transactions_for_borrower(summary["borrowers_by_name"]["Sneha Kapoor"])
            if t["loan_id"] == lid and t["txn_type"] == "Loan Given"]
    assert len(txns) == 1
    assert txns[0]["amount"] == 80000.0


def test_update_loan_rejects_principal_below_repaid(seeded_temp_db):
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["anita"]
    loan = db.get_loan(lid)
    with pytest.raises(ValueError, match="cannot be less"):
        db.update_loan(lid, 5000.0, loan["interest_rate"], loan["due_day"],
                       loan["start_date"], "Active")


def test_dashboard_uses_outstanding(seeded_temp_db):
    _path, summary = seeded_temp_db
    data = db.get_dashboard_summary()
    # Prem 100k + Anita 40k + Sneha 75k + RS 100k+200k + RV 80k + Rashid 60k + Pammi 40k + Karan 100k+150k
    # Vikram closed excluded
    expected = 100000 + 40000 + 75000 + 100000 + 200000 + 80000 + 60000 + 40000 + 100000 + 150000
    assert data["total_principal"] == expected
