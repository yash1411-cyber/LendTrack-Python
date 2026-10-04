"""Cycle-accurate interest ledger — temporary DBs only."""

from __future__ import annotations

from datetime import date

import pytest

import database as db
from src.services import interest_ledger_service as ils


class FrozenDate(date):
    _today = date(2024, 2, 25)

    @classmethod
    def today(cls):
        return cls._today


def _freeze(monkeypatch, today: date):
    FrozenDate._today = today
    monkeypatch.setattr(ils, "date", FrozenDate)
    monkeypatch.setattr(db, "date", FrozenDate)


def _setup(temp_db_path, monkeypatch, today, principal=100000.0, rate=2.0, due=25, start="2024-01-25"):
    _freeze(monkeypatch, today)
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Cycle Borrower", "", "")
    lid = db.add_loan(bid, principal, rate, due, start)
    return bid, lid


def _cycle_map(lid):
    return {c["cycle_due_date"]: c for c in ils.list_cycles(lid)}


def test_a_basic_monthly_accrual(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 2, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 2, 25))
    cycles = ils.list_cycles(lid)
    assert len(cycles) == 1
    assert cycles[0]["cycle_due_date"] == "2024-02-25"
    assert cycles[0]["opening_outstanding"] == 100000.0
    assert cycles[0]["expected"] == 2000.0
    assert cycles[0]["pending"] == 2000.0
    loan = db.get_loan(lid)
    assert db.compute_pending_interest(loan, as_of=date(2024, 2, 25)) == 2000.0
    assert db.expected_monthly_interest(loan) == 2000.0


def test_b_principal_repayment_does_not_reprice_history(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 2, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 2, 25))
    db.add_transaction(bid, lid, "Principal Received", 30000.0, "2024-02-25")
    ils.sync_loan_interest(lid, as_of=date(2024, 3, 25))
    cycles = _cycle_map(lid)
    assert cycles["2024-02-25"]["expected"] == 2000.0
    assert cycles["2024-03-25"]["opening_outstanding"] == 70000.0
    assert cycles["2024-03-25"]["expected"] == 1400.0


def test_c_multiple_principal_payments(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 2, 25))
    db.add_transactions_batch([
        {
            "borrower_id": bid, "loan_id": lid, "txn_type": "Principal Received",
            "amount": 20000.0, "txn_date": "2024-02-20",
        },
        {
            "borrower_id": bid, "loan_id": lid, "txn_type": "Principal Received",
            "amount": 10000.0, "txn_date": "2024-03-10",
        },
    ])
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 25))
    cycles = _cycle_map(lid)
    # Feb cycle start 25-Jan: no PR yet on/before 25-Jan
    assert cycles["2024-02-25"]["opening_outstanding"] == 100000.0
    # Mar cycle start 25-Feb: PR 20k on 20-Feb <= 25-Feb
    assert cycles["2024-03-25"]["opening_outstanding"] == 80000.0
    # Apr cycle start 25-Mar: both PR
    assert cycles["2024-04-25"]["opening_outstanding"] == 70000.0


def test_d_full_interest_payment(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 2, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 2, 25))
    db.add_transaction(bid, lid, "Interest Received", 2000.0, "2024-02-25")
    loan = db.get_loan(lid)
    assert db.compute_pending_interest(loan, as_of=date(2024, 2, 25)) == 0.0
    assert loan["principal"] == 100000.0
    assert loan["outstanding_principal"] == 100000.0


def test_e_partial_interest_payment(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 2, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 2, 25))
    db.add_transaction(bid, lid, "Interest Received", 1000.0, "2024-02-25")
    loan = db.get_loan(lid)
    assert db.compute_pending_interest(loan, as_of=date(2024, 2, 25)) == 1000.0


def test_f_oldest_first_allocation(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 4, 25))
    db.add_transactions_batch([
        {
            "borrower_id": bid, "loan_id": lid, "txn_type": "Principal Received",
            "amount": 30000.0, "txn_date": "2024-02-25",
        },
        {
            "borrower_id": bid, "loan_id": lid, "txn_type": "Principal Received",
            "amount": 20000.0, "txn_date": "2024-03-20",
        },
    ])
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 25))
    db.add_transaction(bid, lid, "Interest Received", 3000.0, "2024-04-25")
    cycles = _cycle_map(lid)
    assert cycles["2024-02-25"]["pending"] == 0.0
    assert cycles["2024-02-25"]["received"] == 2000.0
    assert cycles["2024-03-25"]["expected"] == 1400.0
    assert cycles["2024-03-25"]["received"] == 1000.0
    assert cycles["2024-03-25"]["pending"] == 400.0
    assert cycles["2024-04-25"]["expected"] == 1000.0
    assert cycles["2024-04-25"]["pending"] == 1000.0
    loan = db.get_loan(lid)
    assert db.compute_pending_interest(loan, as_of=date(2024, 4, 25)) == 1400.0


def test_g_late_interest_payment_stays_on_february(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 4, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 25))
    db.add_transaction(bid, lid, "Interest Received", 2000.0, "2024-04-20")
    cycles = _cycle_map(lid)
    assert cycles["2024-02-25"]["pending"] == 0.0
    assert cycles["2024-03-25"]["pending"] == 2000.0


def test_h_no_compounding(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 3, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 3, 25))
    cycles = _cycle_map(lid)
    assert cycles["2024-03-25"]["opening_outstanding"] == 100000.0
    assert cycles["2024-03-25"]["expected"] == 2000.0


def test_i_closed_loan_keeps_history_zero_future_when_paid_off(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 3, 25), principal=30000.0, rate=5.0)
    ils.sync_loan_interest(lid, as_of=date(2024, 2, 25))
    db.add_transaction(bid, lid, "Principal Received", 30000.0, "2024-03-01")
    db.close_loan(lid)
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 25))
    cycles = _cycle_map(lid)
    assert "2024-02-25" in cycles
    assert cycles["2024-02-25"]["expected"] == 1500.0
    assert cycles["2024-03-25"]["opening_outstanding"] == 30000.0
    assert cycles["2024-04-25"]["opening_outstanding"] == 0.0
    assert cycles["2024-04-25"]["expected"] == 0.0
    loan = db.get_loan(lid)
    assert db.compute_pending_interest(loan, as_of=date(2024, 4, 25)) == 3000.0
    assert db.expected_monthly_interest(loan) == 0.0


def test_j_reopen_does_not_duplicate_cycles(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 3, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 3, 25))
    before = [c["cycle_due_date"] for c in ils.list_cycles(lid)]
    db.close_loan(lid)
    db.reopen_loan(lid)
    ils.sync_loan_interest(lid, as_of=date(2024, 3, 25))
    after = [c["cycle_due_date"] for c in ils.list_cycles(lid)]
    assert after == before
    assert len(after) == len(set(after))


def test_k_rate_change_future_only(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 2, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 2, 25))
    db.update_loan(lid, 100000.0, 2.5, 25, "2024-01-25", "Active")
    ils.sync_loan_interest(lid, as_of=date(2024, 3, 25))
    cycles = _cycle_map(lid)
    assert cycles["2024-02-25"]["rate"] == 2.0
    assert cycles["2024-02-25"]["expected"] == 2000.0
    assert cycles["2024-03-25"]["rate"] == 2.5
    assert cycles["2024-03-25"]["expected"] == 2500.0


def test_l_due_day_change_future_only(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 2, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 2, 25))
    db.update_loan(lid, 100000.0, 2.0, 10, "2024-01-25", "Active")
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 10))
    dates = [c["cycle_due_date"] for c in ils.list_cycles(lid)]
    assert "2024-02-25" in dates
    assert "2024-03-10" in dates
    assert "2024-04-10" in dates
    assert "2024-03-25" not in dates


def test_m_due_day_31_february(temp_db_path, monkeypatch):
    bid, lid = _setup(
        temp_db_path, monkeypatch, date(2024, 4, 30), due=31, start="2024-01-31"
    )
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 30))
    dates = [c["cycle_due_date"] for c in ils.list_cycles(lid)]
    assert dates[0] == "2024-02-29"
    assert dates[1] == "2024-03-31"
    assert dates[2] == "2024-04-30"


def test_n_idempotent_generation(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 4, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 25))
    first = ils.list_cycles(lid)
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 25))
    ils.generate_completed_cycles(lid, as_of=date(2024, 4, 25))
    second = ils.list_cycles(lid)
    assert [(c["cycle_due_date"], c["expected"], c["pending"]) for c in first] == [
        (c["cycle_due_date"], c["expected"], c["pending"]) for c in second
    ]


def test_o_delete_interest_reverses_allocation(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 2, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 2, 25))
    db.add_transaction(bid, lid, "Interest Received", 2000.0, "2024-02-25")
    txns = db.get_transactions_for_borrower(bid)
    ir = next(t for t in txns if t["txn_type"] == "Interest Received")
    db.delete_transaction(ir["id"])
    loan = db.get_loan(lid)
    assert db.compute_pending_interest(loan, as_of=date(2024, 2, 25)) == 2000.0
    assert loan["principal"] == 100000.0
    assert loan["outstanding_principal"] == 100000.0
    assert _cycle_map(lid)["2024-02-25"]["expected"] == 2000.0


def test_p_delete_principal_does_not_reprice_history(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 4, 25))
    db.add_transaction(bid, lid, "Principal Received", 30000.0, "2024-03-10")
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 25))
    feb = _cycle_map(lid)["2024-02-25"]["expected"]
    apr = _cycle_map(lid)["2024-04-25"]["expected"]
    txns = db.get_transactions_for_borrower(bid)
    pr = next(t for t in txns if t["txn_type"] == "Principal Received")
    db.delete_transaction(pr["id"])
    cycles = _cycle_map(lid)
    assert cycles["2024-02-25"]["expected"] == feb
    assert cycles["2024-04-25"]["expected"] == apr
    assert cycles["2024-04-25"]["opening_outstanding"] == 70000.0


def test_q_pending_is_sum_of_unpaid_cycles(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 4, 25))
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 25))
    loan = db.get_loan(lid)
    pending = db.compute_pending_interest(loan, as_of=date(2024, 4, 25))
    assert pending == sum(c["pending"] for c in ils.list_cycles(lid))
    assert pending == 6000.0


def test_r_expected_monthly_separate_from_pending(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 4, 25))
    db.add_transaction(bid, lid, "Principal Received", 30000.0, "2024-03-10")
    ils.sync_loan_interest(lid, as_of=date(2024, 4, 25))
    loan = db.get_loan(lid)
    assert db.expected_monthly_interest(loan) == 1400.0
    pending = db.compute_pending_interest(loan, as_of=date(2024, 4, 25))
    assert pending != 1400.0
    assert pending == sum(c["pending"] for c in ils.list_cycles(lid))


def test_reconstruct_allocates_existing_interest_once(temp_db_path, monkeypatch):
    bid, lid = _setup(temp_db_path, monkeypatch, date(2024, 2, 25))
    db.add_transaction(bid, lid, "Interest Received", 2000.0, "2024-02-25")
    ils.reconcile_all_loans(as_of=date(2024, 2, 25))
    ils.reconcile_all_loans(as_of=date(2024, 2, 25))
    cycles = _cycle_map(lid)
    assert cycles["2024-02-25"]["received"] == 2000.0
    assert cycles["2024-02-25"]["pending"] == 0.0
    conn = db.get_connection()
    n = conn.execute("SELECT COUNT(*) AS c FROM interest_allocations").fetchone()["c"]
    conn.close()
    assert n == 1
