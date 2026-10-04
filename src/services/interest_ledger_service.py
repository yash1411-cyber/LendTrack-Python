"""
Cycle-accurate monthly interest ledger.

Historical cycles are persisted and never repriced.
Pending interest is the sum of unpaid completed cycles.
Expected monthly interest remains a forecast (current outstanding × current rate).
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import List, Optional, Sequence

import database as db

LEDGER_REQUIRED_COLUMNS = (
    "loan_id",
    "cycle_due_date",
    "opening_outstanding",
    "rate",
    "expected",
    "received",
    "pending",
)

NEW_LEDGER_SQL = """
CREATE TABLE IF NOT EXISTS interest_ledger (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id              TEXT NOT NULL REFERENCES loans(loan_id),
    cycle_due_date       TEXT NOT NULL,
    opening_outstanding  REAL NOT NULL,
    rate                 REAL NOT NULL,
    expected             REAL NOT NULL,
    received             REAL NOT NULL DEFAULT 0,
    pending              REAL NOT NULL DEFAULT 0,
    updated_at           TEXT DEFAULT (datetime('now')),
    UNIQUE(loan_id, cycle_due_date)
);
"""

ALLOCATIONS_SQL = """
CREATE TABLE IF NOT EXISTS interest_allocations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id     INTEGER NOT NULL REFERENCES transactions(id),
    ledger_id  INTEGER NOT NULL REFERENCES interest_ledger(id),
    amount     REAL NOT NULL
);
"""


def _parse_iso(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def clamp_due_date(year: int, month: int, due_day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(int(due_day), last))


def add_one_month_due(current: date, due_day: int) -> date:
    year, month = current.year, current.month + 1
    if month > 12:
        year += 1
        month = 1
    return clamp_due_date(year, month, due_day)


def first_due_after(start: date, due_day: int) -> date:
    """First due date strictly after the loan start date."""
    candidate = clamp_due_date(start.year, start.month, due_day)
    if candidate > start:
        return candidate
    return add_one_month_due(candidate, due_day)


def ensure_interest_schema(conn) -> None:
    """Upgrade the unused cycle_month ledger to cycle-accurate columns if needed."""
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(interest_ledger)").fetchall()
    }
    if cols and not set(LEDGER_REQUIRED_COLUMNS).issubset(cols):
        count = conn.execute("SELECT COUNT(*) AS c FROM interest_ledger").fetchone()["c"]
        if count:
            raise RuntimeError(
                "interest_ledger has legacy rows that cannot be mapped to "
                "cycle_due_date / opening_outstanding / rate. Manual review required."
            )
        conn.execute("DROP TABLE interest_ledger")
        cols = set()
    if not cols:
        conn.executescript(NEW_LEDGER_SQL)
    conn.executescript(ALLOCATIONS_SQL)


def _loan_start(loan: dict) -> date:
    raw = loan.get("start_date") or loan.get("created_at") or str(date.today())
    try:
        return _parse_iso(raw)
    except ValueError:
        return date.today()


def _original_principal(conn, loan: dict) -> float:
    return float(db.get_original_principal(loan["loan_id"], loan, conn))


def _principal_received_on_or_before(conn, loan_id: str, as_of: date) -> float:
    row = conn.execute(
        """SELECT COALESCE(SUM(amount), 0) AS total FROM transactions
           WHERE loan_id=? AND txn_type='Principal Received' AND txn_date<=?""",
        (loan_id, as_of.isoformat()),
    ).fetchone()
    return float(row["total"])


def opening_outstanding(conn, loan: dict, cycle_start: date) -> float:
    original = _original_principal(conn, loan)
    received = _principal_received_on_or_before(conn, loan["loan_id"], cycle_start)
    return max(0.0, round(original - received, 2))


def generate_completed_cycles(loan_id: str, as_of: Optional[date] = None, conn=None) -> int:
    """
    Persist completed cycles through as_of (inclusive). Idempotent.
    Existing cycles are never overwritten.
    """
    as_of = as_of or date.today()
    own = conn is None
    if own:
        conn = db.get_connection()
    created = 0
    try:
        ensure_interest_schema(conn)
        loan_row = conn.execute("SELECT * FROM loans WHERE loan_id=?", (loan_id,)).fetchone()
        if not loan_row:
            return 0
        loan = dict(loan_row)
        due_day = int(loan["due_day"])
        start = _loan_start(loan)
        last = conn.execute(
            """SELECT cycle_due_date FROM interest_ledger
               WHERE loan_id=? ORDER BY cycle_due_date DESC LIMIT 1""",
            (loan_id,),
        ).fetchone()
        if last:
            cursor = add_one_month_due(_parse_iso(last["cycle_due_date"]), due_day)
            prev_due = _parse_iso(last["cycle_due_date"])
        else:
            cursor = first_due_after(start, due_day)
            prev_due = start

        while cursor <= as_of:
            exists = conn.execute(
                "SELECT id FROM interest_ledger WHERE loan_id=? AND cycle_due_date=?",
                (loan_id, cursor.isoformat()),
            ).fetchone()
            if not exists:
                opening = opening_outstanding(conn, loan, prev_due)
                rate = float(loan["interest_rate"])
                expected = round(opening * rate / 100.0, 2)
                conn.execute(
                    """INSERT INTO interest_ledger
                       (loan_id, cycle_due_date, opening_outstanding, rate,
                        expected, received, pending)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        loan_id,
                        cursor.isoformat(),
                        opening,
                        rate,
                        expected,
                        0.0,
                        expected,
                    ),
                )
                created += 1
            prev_due = cursor
            cursor = add_one_month_due(cursor, due_day)
        if own:
            conn.commit()
        return created
    except Exception:
        if own:
            conn.rollback()
        raise
    finally:
        if own:
            conn.close()


def pending_interest_total(loan_id: str, conn=None) -> float:
    own = conn is None
    if own:
        conn = db.get_connection()
    try:
        row = conn.execute(
            """SELECT COALESCE(SUM(pending), 0) AS total FROM interest_ledger
               WHERE loan_id=?""",
            (loan_id,),
        ).fetchone()
        return round(float(row["total"]), 2)
    finally:
        if own:
            conn.close()


def list_cycles(loan_id: str, conn=None) -> List[dict]:
    own = conn is None
    if own:
        conn = db.get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM interest_ledger
               WHERE loan_id=? ORDER BY cycle_due_date ASC, id ASC""",
            (loan_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own:
            conn.close()


def allocate_interest_payment(conn, txn_id: int, loan_id: str, amount: float) -> float:
    """Oldest-first. Returns unallocated remainder (overpayment). Does not invent prepaid cycles."""
    remaining = round(float(amount), 2)
    rows = conn.execute(
        """SELECT id, pending FROM interest_ledger
           WHERE loan_id=? AND pending > 1e-9
           ORDER BY cycle_due_date ASC, id ASC""",
        (loan_id,),
    ).fetchall()
    for row in rows:
        if remaining <= 1e-9:
            break
        apply = round(min(remaining, float(row["pending"])), 2)
        if apply <= 0:
            continue
        conn.execute(
            """UPDATE interest_ledger
               SET received = received + ?, pending = pending - ?,
                   updated_at = datetime('now')
               WHERE id=?""",
            (apply, apply, row["id"]),
        )
        conn.execute(
            "INSERT INTO interest_allocations (txn_id, ledger_id, amount) VALUES (?,?,?)",
            (txn_id, row["id"], apply),
        )
        remaining = round(remaining - apply, 2)
    return max(0.0, remaining)


def reverse_interest_allocations(conn, txn_id: int) -> None:
    allocs = conn.execute(
        "SELECT ledger_id, amount FROM interest_allocations WHERE txn_id=?",
        (txn_id,),
    ).fetchall()
    for alloc in allocs:
        conn.execute(
            """UPDATE interest_ledger
               SET received = received - ?, pending = pending + ?,
                   updated_at = datetime('now')
               WHERE id=?""",
            (float(alloc["amount"]), float(alloc["amount"]), alloc["ledger_id"]),
        )
    conn.execute("DELETE FROM interest_allocations WHERE txn_id=?", (txn_id,))


def unallocated_interest_txns(conn, loan_id: str) -> Sequence:
    return conn.execute(
        """SELECT t.id, t.amount, t.txn_date FROM transactions t
           WHERE t.loan_id=? AND t.txn_type='Interest Received'
             AND NOT EXISTS (
                 SELECT 1 FROM interest_allocations a WHERE a.txn_id = t.id
             )
           ORDER BY t.txn_date ASC, t.id ASC""",
        (loan_id,),
    ).fetchall()


def settle_unallocated_interest(conn, loan_id: str) -> None:
    for txn in unallocated_interest_txns(conn, loan_id):
        allocate_interest_payment(conn, txn["id"], loan_id, float(txn["amount"]))


def sync_loan_interest(loan_id: str, as_of: Optional[date] = None, conn=None) -> None:
    own = conn is None
    if own:
        conn = db.get_connection()
    try:
        generate_completed_cycles(loan_id, as_of=as_of, conn=conn)
        settle_unallocated_interest(conn, loan_id)
        if own:
            conn.commit()
    except Exception:
        if own:
            conn.rollback()
        raise
    finally:
        if own:
            conn.close()


def reconcile_all_loans(as_of: Optional[date] = None, conn=None) -> None:
    """
    Rebuild missing completed cycles from transactions.

    Reconstructable: cycle dates from start_date + current due_day, opening
    outstanding from Principal Received dates, Interest Received allocation
    oldest-first.

    Not reconstructable: historical rates or due days from before a loan edit.
    Those loans use the rate/due_day stored on the loan row for any cycle that
    does not already exist.
    """
    own = conn is None
    if own:
        conn = db.get_connection()
    try:
        ensure_interest_schema(conn)
        ids = [r["loan_id"] for r in conn.execute("SELECT loan_id FROM loans").fetchall()]
        for loan_id in ids:
            generate_completed_cycles(loan_id, as_of=as_of, conn=conn)
            settle_unallocated_interest(conn, loan_id)
        if own:
            conn.commit()
    except Exception:
        if own:
            conn.rollback()
        raise
    finally:
        if own:
            conn.close()
