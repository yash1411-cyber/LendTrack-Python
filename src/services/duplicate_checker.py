"""
Duplicate Checker - Detect duplicate transactions
Production-ready duplicate detection logic
"""

from typing import List, Dict, Set
import sqlite3

class DuplicateChecker:
    """Detect duplicate transactions in database"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.existing_txns = {}
        self._load_existing_transactions()
    
    def _load_existing_transactions(self):
        """Load all existing transactions from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            rows = c.execute("""
                SELECT id, borrower_id, loan_id, txn_type, amount, txn_date
                FROM transactions
                ORDER BY txn_date DESC
            """).fetchall()
            
            # Build unique key: (date, loan_id, type, amount)
            for row in rows:
                key = (row[5], row[2], row[3], row[4])  # date, loan_id, type, amount
                self.existing_txns[key] = row[0]  # transaction id
            
            conn.close()
        except Exception as e:
            print(f"Error loading transactions: {e}")
    
    def check_duplicate(self, txn: Dict, loan_id: str) -> bool:
        """
        Check if transaction is duplicate
        Duplicate if: date + loan + type + amount match
        """
        key = (txn['date'], loan_id, txn['txn_type'], txn['amount'])
        return key in self.existing_txns
    
    def get_duplicate_ids(self, txn: Dict, loan_id: str) -> List[int]:
        """Get IDs of duplicate transactions"""
        key = (txn['date'], loan_id, txn['txn_type'], txn['amount'])
        if key in self.existing_txns:
            return [self.existing_txns[key]]
        return []