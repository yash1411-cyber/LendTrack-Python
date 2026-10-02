"""
Historical Rebuild Service - Recalculate all metrics after import
Production-ready recalculation of outstanding principal, pending interest, etc.
"""

import sqlite3
from datetime import datetime, date as date_class
from typing import Dict

class HistoricalRebuildService:
    """Recalculate all financial metrics after importing historical transactions"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def rebuild_all(self) -> Dict[str, int]:
        """
        Full recalculation after import
        Returns: {'recalculated': count, 'errors': count}
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Get all loans
            loans = c.execute("SELECT * FROM loans WHERE status='Active'").fetchall()
            
            recalculated = 0
            errors = 0
            
            for loan_row in loans:
                try:
                    self._rebuild_loan(c, loan_row, conn)
                    recalculated += 1
                except Exception as e:
                    print(f"Error rebuilding loan {loan_row[1]}: {e}")
                    errors += 1
            
            conn.commit()
            conn.close()
            
            return {'recalculated': recalculated, 'errors': errors}
        
        except Exception as e:
            print(f"Error in rebuild_all: {e}")
            return {'recalculated': 0, 'errors': 1}
    
    def _rebuild_loan(self, cursor, loan_row, conn):
        """Rebuild a single loan's outstanding principal"""
        
        loan_id = loan_row[1]  # loan_id
        original_principal = loan_row[3]  # principal
        
        # Calculate principal received for this loan
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE loan_id=? AND txn_type='Principal Received'
        """, (loan_id,))
        
        principal_received = cursor.fetchone()[0]
        
        # Outstanding = Original - Received
        outstanding = max(0, original_principal - principal_received)
        
        # Update the loan
        cursor.execute("""
            UPDATE loans SET outstanding_principal=? WHERE loan_id=?
        """, (outstanding, loan_id))
    
    def get_pending_interest(self, cursor, loan_row) -> float:
        """Calculate pending interest for a loan"""
        
        loan_id = loan_row[1]
        principal = loan_row[3]
        interest_rate = loan_row[4]
        start_date = loan_row[6]
        
        # Parse start date
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
        except:
            return 0
        
        today = date_class.today()
        
        # Calculate months elapsed
        months_elapsed = (today.year - start.year) * 12 + (today.month - start.month)
        if today.day < loan_row[5]:  # due_day
            months_elapsed -= 1
        
        months_elapsed = max(0, months_elapsed)
        
        # Expected interest = months * (principal * rate / 100)
        monthly_interest = (principal * interest_rate) / 100
        total_expected = monthly_interest * months_elapsed
        
        # Total received
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE loan_id=? AND txn_type='Interest Received'
        """, (loan_id,))
        
        total_received = cursor.fetchone()[0]
        
        # Pending = Expected - Received
        pending = max(0, total_expected - total_received)
        
        return pending