"""
Loan Matcher - Match transactions to loans using multiple strategies
Supports old format (Loan Display Name) and new format (Borrower Name + Due Day)
With smart 3-step matching and ambiguity detection
"""

from typing import Dict, Tuple, Optional, List
import sqlite3
from datetime import datetime

class LoanMatcher:
    """Match transactions to loans using multiple strategies"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.loans_cache = {}
        self.borrower_loans_cache = {}
        self._load_all_loans()
    
    def _load_all_loans(self):
        """Load all loans into memory for fast matching"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            rows = c.execute("""
                SELECT l.*, b.name as borrower_name, b.borrower_id
                FROM loans l
                JOIN borrowers b ON l.borrower_id = b.borrower_id
                WHERE l.status = 'Active'
            """).fetchall()
            
            # Build caches
            for row in rows:
                loan_dict = dict(row)
                loan_dict['display_name'] = self._generate_display_name(loan_dict)
                
                # Cache by display name (for old format)
                borrower = loan_dict['borrower_name']
                if borrower not in self.loans_cache:
                    self.loans_cache[borrower] = []
                self.loans_cache[borrower].append(loan_dict)
                
                # Cache by borrower + due_day (for new format)
                key = (borrower, loan_dict['due_day'])
                if key not in self.borrower_loans_cache:
                    self.borrower_loans_cache[key] = []
                self.borrower_loans_cache[key].append(loan_dict)
            
            conn.close()
        except Exception as e:
            print(f"Error loading loans: {e}")
    
    def _generate_display_name(self, loan: Dict) -> str:
        """Generate loan display name from loan fields"""
        start_date = loan['start_date']
        principal = loan['principal']
        due_day = loan['due_day']
        
        try:
            date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            date_str = date_obj.strftime('%d-%b-%y')
        except:
            date_str = start_date
        
        return f"{date_str} | ₹{principal:,.0f} | Due {due_day}"
    
    # ══════════════════════════════════════════════════════════════
    # OLD FORMAT MATCHING (Loan Display Name)
    # ══════════════════════════════════════════════════════════════
    
    def match_by_display_name(self, borrower_name: str, loan_display: str) -> Tuple[Optional[Dict], str]:
        """
        Match transaction using old format (Loan Display Name)
        Returns: (loan_dict, status_message)
        """
        borrower_name = borrower_name.strip()
        loan_display = loan_display.strip()
        
        if borrower_name not in self.loans_cache:
            return None, f"Borrower '{borrower_name}' not found"
        
        loans = self.loans_cache[borrower_name]
        
        # Try exact match
        for loan in loans:
            if loan['display_name'].lower() == loan_display.lower():
                return loan, 'matched'
        
        # Try partial match
        matching_loans = [l for l in loans if self._display_names_match(l['display_name'], loan_display)]
        
        if len(matching_loans) == 0:
            available = [l['display_name'] for l in loans]
            return None, f"No loan found for '{loan_display}'. Available: {', '.join(available)}"
        
        if len(matching_loans) == 1:
            return matching_loans[0], 'matched'
        
        return None, f"Ambiguous: {len(matching_loans)} loans match"
    
    def _display_names_match(self, stored: str, provided: str) -> bool:
        """Check if two display names are similar enough"""
        stored_lower = stored.lower()
        provided_lower = provided.lower()
        
        if stored_lower == provided_lower:
            return True
        
        try:
            stored_parts = stored.split('|')
            provided_parts = provided.split('|')
            
            if len(stored_parts) >= 3 and len(provided_parts) >= 3:
                stored_principal = stored_parts[1].strip()
                provided_principal = provided_parts[1].strip()
                stored_due = stored_parts[2].strip()
                provided_due = provided_parts[2].strip()
                
                principal_match = stored_principal.lower() == provided_principal.lower()
                due_match = stored_due.lower() == provided_due.lower()
                
                return principal_match and due_match
        except:
            pass
        
        return False
    
    # ══════════════════════════════════════════════════════════════
    # NEW FORMAT MATCHING (Borrower Name + Due Day) - 3 STEP STRATEGY
    # ══════════════════════════════════════════════════════════════
    
    def match_by_borrower_due_day(self, borrower_name: str, due_day: int) -> Tuple[Optional[Dict], List[Dict], str]:
        """
        STEP 1: Match by borrower name + due day
        Returns: (matched_loan, candidate_loans, status)
        Status: 'exact_match', 'ambiguous', 'not_found'
        """
        borrower_name = borrower_name.strip()
        key = (borrower_name, due_day)
        
        if key not in self.borrower_loans_cache:
            return None, [], f"No active loan for {borrower_name} (Due Day {due_day})"
        
        candidates = self.borrower_loans_cache[key]
        
        if len(candidates) == 1:
            return candidates[0], candidates, 'exact_match'
        
        # Multiple candidates - go to step 2
        return None, candidates, 'ambiguous'
    
    def match_by_borrower_due_day_interest(self, borrower_name: str, due_day: int, 
                                          amount: float, txn_type: str) -> Tuple[Optional[Dict], str]:
        """
        STEP 2: Try to disambiguate using transaction amount
        If txn_type is 'Interest Received' and amount matches expected monthly interest,
        auto-select that loan
        """
        borrower_name = borrower_name.strip()
        key = (borrower_name, due_day)
        
        if key not in self.borrower_loans_cache:
            return None, "No candidates"
        
        candidates = self.borrower_loans_cache[key]
        
        # Only try interest matching if it's an interest transaction
        if txn_type == 'Interest Received':
            matching_by_interest = []
            
            for loan in candidates:
                expected_interest = (loan['principal'] * loan['interest_rate']) / 100
                # Allow 5% tolerance
                if abs(expected_interest - amount) <= expected_interest * 0.05:
                    matching_by_interest.append(loan)
            
            if len(matching_by_interest) == 1:
                return matching_by_interest[0], 'matched_by_interest'
        
        # Couldn't disambiguate
        return None, f"Still ambiguous: {len(candidates)} loans match"
    
    def get_candidate_info(self, candidates: List[Dict]) -> List[Dict]:
        """Format candidate loans for display in review dialog"""
        return [{
            'loan_id': c['loan_id'],
            'start_date': c['start_date'],
            'principal': c['principal'],
            'interest_rate': c['interest_rate'],
            'expected_interest': (c['principal'] * c['interest_rate']) / 100,
            'outstanding_principal': c['outstanding_principal'],
        } for c in candidates]
    
    def get_all_loans(self) -> Dict:
        """Return all loans in cache"""
        return self.loans_cache
    
    def get_borrower_due_days(self) -> List[Tuple[str, int]]:
        """Get all unique (borrower_name, due_day) pairs for template"""
        return list(self.borrower_loans_cache.keys())