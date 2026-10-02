"""
Duplicate Checker - Detect duplicate transactions in DB and within an import batch.
"""

from typing import List, Dict, Optional, Tuple

import database as db


def duplicate_key(txn: Dict, loan_id: str) -> Tuple:
    """Canonical key: date + loan + type + amount (amount as float)."""
    return (
        txn["date"],
        loan_id,
        txn["txn_type"],
        float(txn["amount"]),
    )


class DuplicateChecker:
    """Detect duplicate transactions against the database and within the current file."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.existing_txns: Dict[Tuple, List[int]] = {}
        self._batch_seen: set = set()
        self._load_existing_transactions()

    def _load_existing_transactions(self):
        """Load all existing transactions from database (all IDs per key)."""
        try:
            conn = db.get_connection(self.db_path)
            rows = conn.execute("""
                SELECT id, borrower_id, loan_id, txn_type, amount, txn_date
                FROM transactions
                ORDER BY txn_date DESC, id DESC
            """).fetchall()

            self.existing_txns = {}
            for row in rows:
                key = (
                    row["txn_date"],
                    row["loan_id"],
                    row["txn_type"],
                    float(row["amount"]),
                )
                self.existing_txns.setdefault(key, []).append(row["id"])

            conn.close()
        except Exception as e:
            print(f"Error loading transactions: {e}")

    def reset_batch(self):
        """Clear in-file / in-batch seen keys (call at start of each classification pass)."""
        self._batch_seen.clear()

    def classify_duplicate(self, txn: Dict, loan_id: str) -> Optional[str]:
        """
        Return:
          'database'    — already in DB
          'within_file' — already seen earlier in this import file/batch
          None          — not a duplicate
        """
        key = duplicate_key(txn, loan_id)
        if key in self.existing_txns:
            return "database"
        if key in self._batch_seen:
            return "within_file"
        return None

    def remember(self, txn: Dict, loan_id: str) -> None:
        """Mark a row as seen so later identical rows in the same file are duplicates."""
        self._batch_seen.add(duplicate_key(txn, loan_id))

    def check_duplicate(self, txn: Dict, loan_id: str) -> bool:
        """True if DB or within-file duplicate."""
        return self.classify_duplicate(txn, loan_id) is not None

    def get_duplicate_ids(self, txn: Dict, loan_id: str) -> List[int]:
        """Return all DB transaction IDs matching the key (empty if none)."""
        key = duplicate_key(txn, loan_id)
        return list(self.existing_txns.get(key, []))
