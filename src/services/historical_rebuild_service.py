"""
Historical Rebuild Service - Restore original principals after import.

Stage 5: outstanding is derived from transactions (not stored).
Rebuild repairs loans.principal from Loan Given totals if a legacy DB
had mutated principal values.
"""

from typing import Dict

import database as db


class HistoricalRebuildService:
    """Recalculate / repair financial principal fields after importing history."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def rebuild_all(self) -> Dict[str, int]:
        """
        Repair original principals from Loan Given transactions.
        Outstanding is not written to the DB — it is computed live.

        Returns: {'recalculated': count, 'errors': count}
        """
        try:
            updated = db.repair_loan_principals(self.db_path)
            return {"recalculated": updated, "errors": 0}
        except Exception as e:
            print(f"Error in rebuild_all: {e}")
            return {"recalculated": 0, "errors": 1}
