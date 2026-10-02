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
    """Create all tables on first run if they do not exist."""
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
            principal       REAL NOT NULL,
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
    conn.close()


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
    conn = get_connection()
    conn.execute("DELETE FROM borrowers WHERE borrower_id=?", (borrower_id,))
    conn.commit()
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
    conn = get_connection()
    conn.execute(
        """UPDATE loans SET principal=?, interest_rate=?, due_day=?, start_date=?, status=?
           WHERE loan_id=?""",
        (principal, interest_rate, due_day, start_date, status, loan_id)
    )
    conn.commit()
    conn.close()


def delete_loan(loan_id: str):
    conn = get_connection()
    try:
        # First, delete all transactions for this loan
        conn.execute("DELETE FROM transactions WHERE loan_id=?", (loan_id,))
        
        # Then delete the loan itself
        conn.execute("DELETE FROM loans WHERE loan_id=?", (loan_id,))
        
        conn.commit()
        print(f"Loan {loan_id} deleted successfully")
    except Exception as e:
        conn.rollback()
        print(f"Error deleting loan: {e}")
        raise
    finally:
        conn.close()


def get_loans_for_borrower(borrower_id: str) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM loans WHERE borrower_id=? ORDER BY id",
        (borrower_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_loans(status_filter: str = "") -> list:
    conn = get_connection()
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
    conn.close()
    return [dict(r) for r in rows]


def get_loan(loan_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        """SELECT l.*, b.name as borrower_name FROM loans l
           JOIN borrowers b ON l.borrower_id = b.borrower_id
           WHERE l.loan_id=?""",
        (loan_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


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
    Insert one transaction (and principal side-effect) on an open connection.
    Does not commit — caller owns the transaction boundary.
    """
    if amount is None or float(amount) <= 0:
        raise ValueError(f"Amount must be positive, got: {amount}")
    amount = float(amount)
    composed = _compose_notes(notes, payment_mode)
    conn.execute(
        """INSERT INTO transactions (borrower_id, loan_id, txn_type, amount, txn_date, notes)
           VALUES (?,?,?,?,?,?)""",
        (borrower_id, loan_id, txn_type, amount, txn_date, composed)
    )
    if txn_type == "Principal Received" and loan_id:
        conn.execute(
            "UPDATE loans SET principal = MAX(0, principal - ?) WHERE loan_id=?",
            (amount, loan_id)
        )


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


def delete_transaction(txn_id: int):
    """Delete a transaction. Note: does not reverse principal changes."""
    conn = get_connection()
    conn.execute("DELETE FROM transactions WHERE id=?", (txn_id,))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# INTEREST CALCULATION ENGINE
# ──────────────────────────────────────────────

def expected_monthly_interest(loan: dict) -> float:
    """Simple monthly interest = principal × rate / 100. No compounding."""
    return round(loan["principal"] * loan["interest_rate"] / 100, 2)


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


def compute_pending_interest(loan: dict) -> float:
    """
    Pending interest = accumulated expected interest - total interest received.
    Interest is calculated monthly from start_date (or first txn date).
    Does NOT compound: interest only on principal.
    """
    start_str = loan.get("start_date") or loan.get("created_at", str(date.today()))
    try:
        start = date.fromisoformat(start_str[:10])
    except Exception:
        start = date.today()

    today = date.today()
    # Count full months elapsed since start
    months_elapsed = (today.year - start.year) * 12 + (today.month - start.month)
    if today.day < loan.get("due_day", 1):
        months_elapsed -= 1
    months_elapsed = max(0, months_elapsed)

    total_expected = round(expected_monthly_interest(loan) * months_elapsed, 2)
    total_received = get_interest_received_for_loan(loan["loan_id"])
    pending = round(max(0.0, total_expected - total_received), 2)
    return pending


# ──────────────────────────────────────────────
# DASHBOARD SUMMARY
# ──────────────────────────────────────────────

def get_dashboard_summary() -> dict:
    conn = get_connection()
    today = str(date.today())
    month_start = date.today().replace(day=1).isoformat()

    # Total outstanding principal
    total_principal = conn.execute(
        "SELECT COALESCE(SUM(principal),0) as v FROM loans WHERE status='Active'"
    ).fetchone()["v"]

    # Expected monthly interest across all active loans
    active_loans = conn.execute(
        "SELECT * FROM loans WHERE status='Active'"
    ).fetchall()
    total_expected_interest = sum(
        expected_monthly_interest(dict(l)) for l in active_loans
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

    # Total pending interest (computed per loan)
    total_overdue = sum(
        compute_pending_interest(dict(l)) for l in active_loans
    )

    # Borrowers with due today
    today_day = date.today().day
    due_today = [
        dict(l) for l in active_loans
        if l["due_day"] == today_day
    ]
    # Enrich with borrower names
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
        outstanding_principal = sum(l["principal"] for l in loans if l["status"] == "Active")
        expected_interest = sum(
            expected_monthly_interest(l) for l in loans if l["status"] == "Active"
        )
        interest_received = sum(
            get_interest_received_for_loan(l["loan_id"]) for l in loans
        )
        pending_interest = sum(
            compute_pending_interest(l) for l in loans if l["status"] == "Active"
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
