"""
database.py - SQLite database layer for LendTrack
Handles all DB creation, queries, and business logic calculations.
"""

import sqlite3
import os
from datetime import date, datetime, timedelta
from typing import Optional

# Database file lives next to the executable / script
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lendtrack.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Return a connection with row_factory set for dict-like access.

    Uses DB_PATH by default. Callers (including import services) may pass an
    explicit path; foreign_keys are always enabled so all access is consistent.
    """
    path = DB_PATH if db_path is None else db_path
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ──────────────────────────────────────────────
# SCHEMA CREATION
# ──────────────────────────────────────────────

def initialize_db():
    """Create all tables on first run if they do not exist, then repair principals."""
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS borrowers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id TEXT UNIQUE NOT NULL,   -- B001, B002 …
            name        TEXT NOT NULL,
            phone       TEXT,
            notes       TEXT,
            created_at  TEXT DEFAULT (date('now'))
        );

        CREATE TABLE IF NOT EXISTS loans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id         TEXT UNIQUE NOT NULL,  -- L001, L002 …
            borrower_id     TEXT NOT NULL REFERENCES borrowers(borrower_id),
            principal       REAL NOT NULL,          -- ORIGINAL principal (not reduced by repayments)
            interest_rate   REAL NOT NULL,   -- monthly % e.g. 3.0
            due_day         INTEGER NOT NULL CHECK(due_day BETWEEN 1 AND 31),
            start_date      TEXT,
            status          TEXT DEFAULT 'Active',  -- Active / Closed
            created_at      TEXT DEFAULT (date('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id     TEXT NOT NULL REFERENCES borrowers(borrower_id),
            loan_id         TEXT REFERENCES loans(loan_id),
            txn_type        TEXT NOT NULL,  -- Interest Received / Principal Received / Loan Given
            amount          REAL NOT NULL,
            txn_date        TEXT NOT NULL,
            notes           TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        -- Ledger that tracks cumulative pending interest per loan
        CREATE TABLE IF NOT EXISTS interest_ledger (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id         TEXT NOT NULL REFERENCES loans(loan_id),
            cycle_month     TEXT NOT NULL,   -- YYYY-MM for the billing cycle
            expected        REAL NOT NULL,   -- interest expected that cycle
            received        REAL NOT NULL DEFAULT 0,
            pending         REAL NOT NULL DEFAULT 0,
            updated_at      TEXT DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    from src.services.interest_ledger_service import ensure_interest_schema, reconcile_all_loans
    ensure_interest_schema(conn)
    conn.commit()
    conn.close()
    # Ensure loans.principal reflects original (Loan Given), not a legacy mutated balance
    repair_loan_principals()
    reconcile_all_loans()


# ──────────────────────────────────────────────
# ID GENERATORS
# ──────────────────────────────────────────────

def next_borrower_id() -> str:
    conn = get_connection()
    row = conn.execute("SELECT borrower_id FROM borrowers ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if row is None:
        return "B001"
    num = int(row["borrower_id"][1:]) + 1
    return f"B{num:03d}"


def next_loan_id() -> str:
    conn = get_connection()
    row = conn.execute("SELECT loan_id FROM loans ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if row is None:
        return "L001"
    num = int(row["loan_id"][1:]) + 1
    return f"L{num:03d}"


# ──────────────────────────────────────────────
# BORROWER CRUD
# ──────────────────────────────────────────────

def add_borrower(name: str, phone: str = "", notes: str = "") -> str:
    bid = next_borrower_id()
    conn = get_connection()
    conn.execute(
        "INSERT INTO borrowers (borrower_id, name, phone, notes) VALUES (?,?,?,?)",
        (bid, name.strip(), phone.strip(), notes.strip())
    )
    conn.commit()
    conn.close()
    return bid


def update_borrower(borrower_id: str, name: str, phone: str, notes: str):
    conn = get_connection()
    conn.execute(
        "UPDATE borrowers SET name=?, phone=?, notes=? WHERE borrower_id=?",
        (name.strip(), phone.strip(), notes.strip(), borrower_id)
    )
    conn.commit()
    conn.close()


def delete_borrower(borrower_id: str):
    """
    Delete a borrower only when they have no loans and no transactions.
    Preserves financial history — does not cascade.
    """
    conn = get_connection()
    try:
        loan_count = conn.execute(
            "SELECT COUNT(*) AS c FROM loans WHERE borrower_id=?", (borrower_id,)
        ).fetchone()["c"]
        txn_count = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE borrower_id=?", (borrower_id,)
        ).fetchone()["c"]
        if loan_count or txn_count:
            raise ValueError(
                f"Cannot delete borrower {borrower_id}: "
                f"{loan_count} loan(s) and {txn_count} transaction(s) still exist. "
                "Close related loans and keep history, or remove child records first."
            )
        conn.execute("DELETE FROM borrowers WHERE borrower_id=?", (borrower_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_all_borrowers(search: str = "") -> list:
    conn = get_connection()
    if search:
        rows = conn.execute(
            "SELECT * FROM borrowers WHERE name LIKE ? OR borrower_id LIKE ? ORDER BY id",
            (f"%{search}%", f"%{search}%")
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM borrowers ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_borrower(borrower_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM borrowers WHERE borrower_id=?", (borrower_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ──────────────────────────────────────────────
# LOAN CRUD
# ──────────────────────────────────────────────

def add_loan(borrower_id: str, principal: float, interest_rate: float,
             due_day: int, start_date: str = "") -> str:
    lid = next_loan_id()
    conn = get_connection()
    conn.execute(
        """INSERT INTO loans (loan_id, borrower_id, principal, interest_rate, due_day, start_date)
           VALUES (?,?,?,?,?,?)""",
        (lid, borrower_id, principal, interest_rate, due_day, start_date)
    )
    # Also record a Loan Given transaction
    conn.execute(
        """INSERT INTO transactions (borrower_id, loan_id, txn_type, amount, txn_date)
           VALUES (?,?,?,?,?)""",
        (borrower_id, lid, "Loan Given", principal, start_date or str(date.today()))
    )
    conn.commit()
    conn.close()
    return lid


def update_loan(loan_id: str, principal: float, interest_rate: float,
                due_day: int, start_date: str, status: str):
    """
    Update loan fields. `principal` is the ORIGINAL principal.

    Syncs the single foundational Loan Given row (amount + txn_date) to match.
    NEVER inserts an additional Loan Given when one already exists — editing a
    loan must not create a new disbursement transaction.
    """
    conn = get_connection()
    try:
        loan_row = conn.execute(
            "SELECT borrower_id, principal FROM loans WHERE loan_id=?", (loan_id,)
        ).fetchone()
        if not loan_row:
            raise ValueError(f"Loan {loan_id} not found")

        principal = float(principal)
        received = _txn_sum(conn, loan_id, "Principal Received")
        if principal + 1e-9 < received:
            raise ValueError(
                f"Original principal ({principal}) cannot be less than "
                f"principal already repaid ({received})."
            )
        conn.execute(
            """UPDATE loans SET principal=?, interest_rate=?, due_day=?, start_date=?, status=?
               WHERE loan_id=?""",
            (principal, interest_rate, due_day, start_date, status, loan_id)
        )
        _sync_foundational_loan_given(
            conn,
            loan_id=loan_id,
            borrower_id=loan_row["borrower_id"],
            principal=principal,
            start_date=start_date or "",
        )
        from src.services.interest_ledger_service import sync_loan_interest
        sync_loan_interest(loan_id, conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _sync_foundational_loan_given(
    conn: sqlite3.Connection,
    loan_id: str,
    borrower_id: str,
    principal: float,
    start_date: str,
) -> None:
    """
    Ensure exactly one foundational Loan Given exists and matches principal.

    - If one or more exist: update the earliest row; remove any extras.
    - If none exist (legacy): insert exactly one.
    Editing must never leave multiple Loan Given rows for the same loan.
    """
    rows = conn.execute(
        """SELECT id FROM transactions
           WHERE loan_id=? AND txn_type='Loan Given'
           ORDER BY id ASC""",
        (loan_id,),
    ).fetchall()
    txn_date = start_date or str(date.today())

    if not rows:
        conn.execute(
            """INSERT INTO transactions
               (borrower_id, loan_id, txn_type, amount, txn_date, notes)
               VALUES (?,?,?,?,?,?)""",
            (borrower_id, loan_id, "Loan Given", principal, txn_date, ""),
        )
        return

    foundational_id = rows[0]["id"]
    conn.execute(
        "UPDATE transactions SET amount=?, txn_date=? WHERE id=?",
        (principal, txn_date, foundational_id),
    )
    if len(rows) > 1:
        extra_ids = [r["id"] for r in rows[1:]]
        conn.executemany(
            "DELETE FROM transactions WHERE id=?",
            [(eid,) for eid in extra_ids],
        )


def close_loan(loan_id: str):
    """
    Mark a loan Closed without deleting transactions or changing identity fields.

    Principal, due day, start date, and Loan Given are left untouched so the
    loan remains matchable for historical imports after close/reopen.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT loan_id FROM loans WHERE loan_id=?", (loan_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Loan {loan_id} not found")
        conn.execute(
            "UPDATE loans SET status=? WHERE loan_id=?",
            ("Closed", loan_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reopen_loan(loan_id: str):
    """
    Reopen a Closed loan by setting status=Active only.

    Does not create a new loan or Loan Given, and does not alter principal,
    due day, or start date (matching identity is preserved).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT loan_id, status FROM loans WHERE loan_id=?", (loan_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Loan {loan_id} not found")
        conn.execute(
            "UPDATE loans SET status=? WHERE loan_id=?",
            ("Active", loan_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_loan(loan_id: str):
    """
    Delete a loan only when it has no transactions.
    Loans with history must be Closed instead so imported/manual history is kept.
    """
    conn = get_connection()
    try:
        txn_count = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE loan_id=?", (loan_id,)
        ).fetchone()["c"]
        if txn_count:
            raise ValueError(
                f"Cannot delete loan {loan_id}: {txn_count} transaction(s) exist. "
                "Close the loan instead to preserve history."
            )
        conn.execute("DELETE FROM interest_allocations WHERE ledger_id IN (SELECT id FROM interest_ledger WHERE loan_id=?)", (loan_id,))
        conn.execute("DELETE FROM interest_ledger WHERE loan_id=?", (loan_id,))
        conn.execute("DELETE FROM loans WHERE loan_id=?", (loan_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_loans_for_borrower(borrower_id: str) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM loans WHERE borrower_id=? ORDER BY id",
            (borrower_id,)
        ).fetchall()
        return [enrich_loan(dict(r), conn) for r in rows]
    finally:
        conn.close()


def get_all_loans(status_filter: str = "") -> list:
    conn = get_connection()
    try:
        if status_filter:
            rows = conn.execute(
                """SELECT l.*, b.name as borrower_name FROM loans l
                   JOIN borrowers b ON l.borrower_id = b.borrower_id
                   WHERE l.status=? ORDER BY l.id""",
                (status_filter,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT l.*, b.name as borrower_name FROM loans l
                   JOIN borrowers b ON l.borrower_id = b.borrower_id
                   ORDER BY l.id"""
            ).fetchall()
        return [enrich_loan(dict(r), conn) for r in rows]
    finally:
        conn.close()


def get_loan(loan_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT l.*, b.name as borrower_name FROM loans l
               JOIN borrowers b ON l.borrower_id = b.borrower_id
               WHERE l.loan_id=?""",
            (loan_id,)
        ).fetchone()
        return enrich_loan(dict(row), conn) if row else None
    finally:
        conn.close()


# ──────────────────────────────────────────────
# PRINCIPAL / OUTSTANDING (Stage 5)
# ──────────────────────────────────────────────

SUPPORTED_TXN_TYPES = {
    "Interest Received",
    "Principal Received",
    "Loan Given",
}


def _txn_sum(conn: sqlite3.Connection, loan_id: str, txn_type: str) -> float:
    row = conn.execute(
        """SELECT COALESCE(SUM(amount), 0) AS total FROM transactions
           WHERE loan_id=? AND txn_type=?""",
        (loan_id, txn_type)
    ).fetchone()
    return float(row["total"])


def _foundational_loan_given_amount(
    conn: sqlite3.Connection, loan_id: str
) -> Optional[float]:
    """Amount of the earliest Loan Given for a loan, or None if missing."""
    row = conn.execute(
        """SELECT amount FROM transactions
           WHERE loan_id=? AND txn_type='Loan Given'
           ORDER BY id ASC LIMIT 1""",
        (loan_id,),
    ).fetchone()
    return float(row["amount"]) if row else None


def get_original_principal(loan_id: str, loan_row: dict = None,
                           conn: sqlite3.Connection = None) -> float:
    """
    Original principal for a loan (Stage 5).

    Canonical source is loans.principal. The foundational (earliest) Loan Given
    is a fallback for legacy rows — never SUM multiple Loan Given rows.
    """
    own = conn is None
    if own:
        conn = get_connection()
    try:
        if loan_row is not None and loan_row.get("principal") is not None:
            return float(loan_row["principal"])
        row = conn.execute(
            "SELECT principal FROM loans WHERE loan_id=?", (loan_id,)
        ).fetchone()
        if row is not None and row["principal"] is not None:
            return float(row["principal"])
        given = _foundational_loan_given_amount(conn, loan_id)
        return given if given is not None else 0.0
    finally:
        if own:
            conn.close()


def get_outstanding_principal(loan_id: str, loan_row: dict = None,
                              conn: sqlite3.Connection = None) -> float:
    """Outstanding = original principal − Principal Received (never below 0)."""
    own = conn is None
    if own:
        conn = get_connection()
    try:
        original = get_original_principal(loan_id, loan_row, conn)
        received = _txn_sum(conn, loan_id, "Principal Received")
        return max(0.0, round(original - received, 2))
    finally:
        if own:
            conn.close()


def enrich_loan(loan: dict, conn: sqlite3.Connection = None) -> dict:
    """Attach original_principal and outstanding_principal to a loan dict."""
    out = dict(loan)
    lid = out["loan_id"]
    out["original_principal"] = get_original_principal(lid, out, conn)
    out["outstanding_principal"] = get_outstanding_principal(lid, out, conn)
    return out


def repair_loan_principals(db_path: str = None) -> int:
    """
    Set loans.principal from the foundational (earliest) Loan Given amount.

    Repairs DBs previously mutated by Principal Received updates.
    Does NOT sum multiple Loan Given rows (that would inflate principal).
    Returns number of rows updated.
    """
    conn = get_connection(db_path)
    try:
        updated = 0
        for loan in conn.execute("SELECT loan_id, principal FROM loans").fetchall():
            lid = loan["loan_id"]
            given = _foundational_loan_given_amount(conn, lid)
            if given is not None and abs(float(loan["principal"]) - given) > 1e-9:
                conn.execute(
                    "UPDATE loans SET principal=? WHERE loan_id=?",
                    (given, lid)
                )
                updated += 1
        conn.commit()
        return updated
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ──────────────────────────────────────────────
# TRANSACTION CRUD
# ──────────────────────────────────────────────

def _compose_notes(notes: str = "", payment_mode: str = None) -> str:
    """Merge optional payment_mode into notes (no schema column for payment_mode)."""
    text = (notes or "").strip()
    if payment_mode:
        mode = str(payment_mode).strip()
        if mode and mode.lower() != "nan":
            tag = f"[Payment: {mode}]"
            if tag not in text:
                text = f"{text} {tag}".strip() if text else tag
    return text


def _apply_transaction(conn: sqlite3.Connection, borrower_id: str, loan_id: str,
                       txn_type: str, amount: float, txn_date: str,
                       notes: str = "", payment_mode: str = None) -> None:
    """
    Insert one transaction on an open connection.
    Does not commit — caller owns the transaction boundary.

    loans.principal is NEVER mutated here. Outstanding is derived from transactions.
    Adjustment is rejected (unsupported).
    """
    if txn_type == "Adjustment":
        raise ValueError(
            "Adjustment transactions are not supported. "
            "Use Principal Received or Interest Received."
        )
    if txn_type not in SUPPORTED_TXN_TYPES:
        raise ValueError(
            f"Unsupported transaction type: {txn_type}. "
            f"Must be one of: {', '.join(sorted(SUPPORTED_TXN_TYPES))}"
        )
    if amount is None or float(amount) <= 0:
        raise ValueError(f"Amount must be positive, got: {amount}")
    amount = float(amount)

    if txn_type == "Loan Given":
        if not loan_id:
            raise ValueError("Loan Given requires a loan_id.")
        existing = conn.execute(
            """SELECT COUNT(*) AS c FROM transactions
               WHERE loan_id=? AND txn_type='Loan Given'""",
            (loan_id,),
        ).fetchone()["c"]
        if existing:
            raise ValueError(
                "Loan Given already exists for this loan. "
                "Editing a loan must not create another Loan Given. "
                "Change original principal via Edit Loan if needed."
            )

    if txn_type == "Principal Received" and loan_id:
        outstanding = get_outstanding_principal(loan_id, conn=conn)
        if amount - outstanding > 1e-9:
            raise ValueError(
                f"Principal Received ({amount}) exceeds outstanding ({outstanding}) "
                f"for loan {loan_id}."
            )

    composed = _compose_notes(notes, payment_mode)
    cur = conn.execute(
        """INSERT INTO transactions (borrower_id, loan_id, txn_type, amount, txn_date, notes)
           VALUES (?,?,?,?,?,?)""",
        (borrower_id, loan_id, txn_type, amount, txn_date, composed)
    )
    return cur.lastrowid


def add_transaction(borrower_id: str, loan_id: str, txn_type: str,
                    amount: float, txn_date: str, notes: str = "",
                    payment_mode: str = None):
    """
    Add a single transaction and commit.

    payment_mode is accepted for Excel-import compatibility and stored in notes
    (no separate DB column). Manual UI callers may omit it.
    """
    conn = get_connection()
    try:
        _apply_transaction(
            conn, borrower_id, loan_id, txn_type, amount, txn_date, notes, payment_mode
        )
        if loan_id:
            from src.services.interest_ledger_service import sync_loan_interest
            sync_loan_interest(loan_id, conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_transactions_batch(transactions: list) -> int:
    """
    Insert many transactions atomically on DB_PATH.

    Each item is a dict with keys:
      borrower_id, loan_id, txn_type, amount, txn_date
      optional: notes, payment_mode

    On any failure the entire batch is rolled back and the exception is re-raised.
    Returns the number of transactions committed.
    """
    if not transactions:
        return 0

    conn = get_connection()
    try:
        for item in transactions:
            _apply_transaction(
                conn,
                borrower_id=item["borrower_id"],
                loan_id=item.get("loan_id"),
                txn_type=item["txn_type"],
                amount=item["amount"],
                txn_date=item["txn_date"],
                notes=item.get("notes", ""),
                payment_mode=item.get("payment_mode"),
            )
        loan_ids = {item.get("loan_id") for item in transactions if item.get("loan_id")}
        from src.services.interest_ledger_service import sync_loan_interest
        for lid in loan_ids:
            sync_loan_interest(lid, conn=conn)
        conn.commit()
        return len(transactions)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_all_transactions(limit: int = 200) -> list:
    conn = get_connection()
    rows = conn.execute(
        """SELECT t.*, b.name as borrower_name FROM transactions t
           JOIN borrowers b ON t.borrower_id = b.borrower_id
           ORDER BY t.txn_date DESC, t.id DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_transactions_for_borrower(borrower_id: str) -> list:
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM transactions WHERE borrower_id=?
           ORDER BY txn_date DESC, id DESC""",
        (borrower_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_transaction(txn_id: int) -> dict:
    """
    Delete a non-foundational transaction.

    - Loan Given cannot be deleted while the loan exists (preserves original principal).
    - Interest / Principal Received may be deleted; outstanding and interest
      recalculate from remaining transactions (Stage 5 model).

    Returns the deleted transaction dict.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id=?", (txn_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Transaction {txn_id} not found")
        txn = dict(row)

        if txn["txn_type"] == "Loan Given":
            raise ValueError(
                "Cannot delete Loan Given transactions. "
                "They define the loan's original principal. "
                "Close the loan to retain history instead."
            )

        if txn["txn_type"] == "Interest Received":
            from src.services.interest_ledger_service import reverse_interest_allocations
            reverse_interest_allocations(conn, txn_id)

        conn.execute("DELETE FROM transactions WHERE id=?", (txn_id,))
        conn.commit()
        return txn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ──────────────────────────────────────────────
# INTEREST CALCULATION ENGINE
# ──────────────────────────────────────────────

def expected_monthly_interest(loan: dict) -> float:
    """
    Monthly interest = outstanding principal × rate / 100.
    No compounding. Outstanding is derived from transactions.
    """
    outstanding = loan.get("outstanding_principal")
    if outstanding is None:
        outstanding = get_outstanding_principal(loan["loan_id"], loan)
    return round(float(outstanding) * float(loan["interest_rate"]) / 100, 2)


def get_interest_received_for_loan(loan_id: str,
                                    from_date: str = None,
                                    to_date: str = None) -> float:
    """Sum all 'Interest Received' transactions for a loan in a date range."""
    conn = get_connection()
    if from_date and to_date:
        row = conn.execute(
            """SELECT COALESCE(SUM(amount),0) as total FROM transactions
               WHERE loan_id=? AND txn_type='Interest Received'
               AND txn_date BETWEEN ? AND ?""",
            (loan_id, from_date, to_date)
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT COALESCE(SUM(amount),0) as total FROM transactions
               WHERE loan_id=? AND txn_type='Interest Received'""",
            (loan_id,)
        ).fetchone()
    conn.close()
    return row["total"]


def compute_pending_interest(loan: dict, as_of=None) -> float:
    """
    Pending interest = sum of unpaid completed historical cycles.
    Not an estimate from current outstanding × elapsed months.
    """
    from src.services.interest_ledger_service import (
        pending_interest_total,
        sync_loan_interest,
    )

    lid = loan["loan_id"]
    conn = get_connection()
    try:
        sync_loan_interest(lid, as_of=as_of, conn=conn)
        total = pending_interest_total(lid, conn=conn)
        conn.commit()
        return total
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ──────────────────────────────────────────────
# DASHBOARD SUMMARY
# ──────────────────────────────────────────────

def get_dashboard_summary() -> dict:
    conn = get_connection()
    today = str(date.today())
    month_start = date.today().replace(day=1).isoformat()

    active_rows = conn.execute(
        "SELECT * FROM loans WHERE status='Active'"
    ).fetchall()
    active_loans = [enrich_loan(dict(l), conn) for l in active_rows]

    total_principal = sum(l["outstanding_principal"] for l in active_loans)

    total_expected_interest = sum(
        expected_monthly_interest(l) for l in active_loans
    )

    # Interest received this month
    interest_this_month = conn.execute(
        """SELECT COALESCE(SUM(amount),0) as v FROM transactions
           WHERE txn_type='Interest Received' AND txn_date >= ?""",
        (month_start,)
    ).fetchone()["v"]

    # Principal received this month
    principal_this_month = conn.execute(
        """SELECT COALESCE(SUM(amount),0) as v FROM transactions
           WHERE txn_type='Principal Received' AND txn_date >= ?""",
        (month_start,)
    ).fetchone()["v"]

    conn.close()

    total_overdue = sum(
        compute_pending_interest(l) for l in active_loans
    )

    today_day = date.today().day
    due_today = [l for l in active_loans if l["due_day"] == today_day]
    for l in due_today:
        b = get_borrower(l["borrower_id"])
        l["borrower_name"] = b["name"] if b else l["borrower_id"]

    return {
        "total_principal": total_principal,
        "expected_monthly_interest": round(total_expected_interest, 2),
        "interest_this_month": round(interest_this_month, 2),
        "principal_this_month": round(principal_this_month, 2),
        "total_overdue_interest": round(total_overdue, 2),
        "due_today": due_today,
    }


# ──────────────────────────────────────────────
# REPORTS
# ──────────────────────────────────────────────

def get_report_data() -> list:
    """Return per-borrower summary rows for the Reports screen."""
    borrowers = get_all_borrowers()
    report = []
    for b in borrowers:
        loans = get_loans_for_borrower(b["borrower_id"])
        if not loans:
            continue
        total_principal_given = sum(
            t["amount"] for t in get_transactions_for_borrower(b["borrower_id"])
            if t["txn_type"] == "Loan Given"
        )
        total_principal_returned = sum(
            t["amount"] for t in get_transactions_for_borrower(b["borrower_id"])
            if t["txn_type"] == "Principal Received"
        )
        outstanding_principal = sum(
            l["outstanding_principal"] for l in loans if l["status"] == "Active"
        )
        expected_interest = sum(
            expected_monthly_interest(l) for l in loans if l["status"] == "Active"
        )
        interest_received = sum(
            get_interest_received_for_loan(l["loan_id"]) for l in loans
        )
        pending_interest = sum(
            compute_pending_interest(l) for l in loans
        )
        report.append({
            "borrower_id": b["borrower_id"],
            "name": b["name"],
            "phone": b["phone"] or "",
            "total_principal_given": round(total_principal_given, 2),
            "principal_returned": round(total_principal_returned, 2),
            "outstanding_principal": round(outstanding_principal, 2),
            "expected_monthly_interest": round(expected_interest, 2),
            "interest_received": round(interest_received, 2),
            "pending_interest": round(pending_interest, 2),
        })
    return report

# ──────────────────────────────────────────────────────────────
# IMPORT HELPERS
# ──────────────────────────────────────────────────────────────

def get_loan_by_borrower_and_dates(borrower_id: str, principal: float, due_day: int, start_date: str):
    """Find loan by borrower, principal, due day, and start date"""
    conn = get_connection()
    try:
        # Match by borrower, principal, and due day
        loan = conn.execute(
            """SELECT * FROM loans 
               WHERE borrower_id=? AND principal=? AND due_day=? AND start_date=?""",
            (borrower_id, principal, due_day, start_date)
        ).fetchone()
        
        conn.close()
        return dict(loan) if loan else None
    except Exception as e:
        conn.close()
        raise e

def get_all_transactions_raw():
    """Get all transactions for duplicate checking"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY txn_date DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
