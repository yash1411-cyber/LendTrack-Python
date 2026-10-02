"""
Loan Matcher - Match transactions to loans using multiple strategies.

Stage 3 rules:
- Match Active and Closed loans (historical imports)
- Display names use original principal (Loan Given), not mutated outstanding
- Structured display-name compare requires date + principal + due day
- Never auto-assign on interest amount alone (ambiguous → review)
- Candidate info exposes derived outstanding (no schema column required)
"""

from typing import Dict, Tuple, Optional, List
from datetime import datetime

import database as db


class LoanMatcher:
    """Match transactions to loans using multiple strategies"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.loans_cache = {}           # borrower_name -> [loan dicts]
        self.borrower_loans_cache = {}  # (borrower_name, due_day) -> [loan dicts]
        self._load_all_loans()

    def _load_all_loans(self):
        """Load Active and Closed loans into memory for matching."""
        try:
            conn = db.get_connection(self.db_path)
            c = conn.cursor()

            rows = c.execute("""
                SELECT l.*, b.name as borrower_name, b.borrower_id
                FROM loans l
                JOIN borrowers b ON l.borrower_id = b.borrower_id
            """).fetchall()

            loan_given = {
                r["loan_id"]: r["total"]
                for r in c.execute("""
                    SELECT loan_id, COALESCE(SUM(amount), 0) AS total
                    FROM transactions
                    WHERE txn_type = 'Loan Given'
                    GROUP BY loan_id
                """).fetchall()
            }
            principal_received = {
                r["loan_id"]: r["total"]
                for r in c.execute("""
                    SELECT loan_id, COALESCE(SUM(amount), 0) AS total
                    FROM transactions
                    WHERE txn_type = 'Principal Received'
                    GROUP BY loan_id
                """).fetchall()
            }

            self.loans_cache = {}
            self.borrower_loans_cache = {}

            for row in rows:
                loan_dict = dict(row)
                lid = loan_dict["loan_id"]
                original = float(loan_given.get(lid, loan_dict["principal"]))
                received = float(principal_received.get(lid, 0))
                outstanding = max(0.0, original - received)

                loan_dict["original_principal"] = original
                loan_dict["outstanding_principal"] = outstanding
                loan_dict["display_name"] = self._generate_display_name(loan_dict)

                borrower = loan_dict["borrower_name"]
                self.loans_cache.setdefault(borrower, []).append(loan_dict)

                key = (borrower, loan_dict["due_day"])
                self.borrower_loans_cache.setdefault(key, []).append(loan_dict)

            conn.close()
        except Exception as e:
            print(f"Error loading loans: {e}")

    def _generate_display_name(self, loan: Dict) -> str:
        """Stable display name based on start date, original principal, and due day."""
        start_date = loan.get("start_date") or ""
        principal = loan.get("original_principal", loan["principal"])
        due_day = loan["due_day"]

        try:
            date_obj = datetime.strptime(str(start_date)[:10], "%Y-%m-%d")
            date_str = date_obj.strftime("%d-%b-%y")
        except Exception:
            date_str = str(start_date)

        return f"{date_str} | ₹{principal:,.0f} | Due {due_day}"

    # ══════════════════════════════════════════════════════════════
    # OLD FORMAT MATCHING (Loan Display Name)
    # ══════════════════════════════════════════════════════════════

    def match_by_display_name(self, borrower_name: str, loan_display: str) -> Tuple[Optional[Dict], str]:
        """
        Match using Loan Display Name.
        Returns: (loan_dict, status_message) where status is 'matched' or an error/ambiguous string.
        """
        borrower_name = borrower_name.strip()
        loan_display = loan_display.strip()

        if borrower_name not in self.loans_cache:
            return None, f"Borrower '{borrower_name}' not found"

        loans = self.loans_cache[borrower_name]

        exact = [l for l in loans if l["display_name"].lower() == loan_display.lower()]
        if len(exact) == 1:
            return exact[0], "matched"
        if len(exact) > 1:
            return None, f"Ambiguous: {len(exact)} loans match"

        structured = [l for l in loans if self._display_names_match(l["display_name"], loan_display)]
        if len(structured) == 1:
            return structured[0], "matched"
        if len(structured) > 1:
            return None, f"Ambiguous: {len(structured)} loans match"

        available = [l["display_name"] for l in loans]
        return None, f"No loan found for '{loan_display}'. Available: {', '.join(available)}"

    def _display_names_match(self, stored: str, provided: str) -> bool:
        """
        Structured equality: start-date segment + principal + due day must all match.
        (Does not ignore the date — avoids wrong matches among same due day/principal.)
        """
        if stored.lower() == provided.lower():
            return True

        stored_parts = self._parse_display_parts(stored)
        provided_parts = self._parse_display_parts(provided)
        if not stored_parts or not provided_parts:
            return False

        return (
            stored_parts["date"] == provided_parts["date"]
            and stored_parts["principal"] == provided_parts["principal"]
            and stored_parts["due"] == provided_parts["due"]
        )

    def _parse_display_parts(self, display: str) -> Optional[Dict[str, str]]:
        parts = [p.strip() for p in display.split("|")]
        if len(parts) < 3:
            return None
        return {
            "date": parts[0].lower(),
            "principal": parts[1].lower().replace(" ", ""),
            "due": parts[2].lower().replace(" ", ""),
        }

    # ══════════════════════════════════════════════════════════════
    # NEW FORMAT MATCHING (Borrower Name + Due Day)
    # ══════════════════════════════════════════════════════════════

    def match_by_borrower_due_day(
        self, borrower_name: str, due_day: int
    ) -> Tuple[Optional[Dict], List[Dict], str]:
        """
        STEP 1: Match by borrower name + due day (Active or Closed).
        Returns: (matched_loan, candidate_loans, status)
        Status: 'exact_match', 'ambiguous', 'not_found'
        """
        borrower_name = borrower_name.strip()
        key = (borrower_name, due_day)

        if key not in self.borrower_loans_cache:
            return None, [], f"No loan found for {borrower_name} (Due Day {due_day})"

        candidates = self.borrower_loans_cache[key]

        if len(candidates) == 1:
            return candidates[0], candidates, "exact_match"

        return None, candidates, "ambiguous"

    def match_by_borrower_due_day_interest(
        self, borrower_name: str, due_day: int, amount: float, txn_type: str
    ) -> Tuple[Optional[Dict], str]:
        """
        STEP 2 (safe): Do NOT auto-assign based on interest amount.

        Interest amounts often collide across loans; silent assignment is unsafe.
        Always leave ambiguous cases for manual review (Stage 7 UI).
        """
        borrower_name = borrower_name.strip()
        key = (borrower_name, due_day)
        candidates = self.borrower_loans_cache.get(key, [])
        if not candidates:
            return None, "No candidates"
        # Intentionally never return 'matched_by_interest'
        return None, f"Still ambiguous: {len(candidates)} loans match"

    def get_candidate_info(self, candidates: List[Dict]) -> List[Dict]:
        """Format candidate loans for display in review dialog."""
        info = []
        for c in candidates:
            original = float(c.get("original_principal", c["principal"]))
            outstanding = float(c.get("outstanding_principal", c["principal"]))
            # Expected monthly interest on outstanding principal (README model)
            expected = (outstanding * float(c["interest_rate"])) / 100
            info.append({
                "loan_id": c["loan_id"],
                "start_date": c["start_date"],
                "principal": original,
                "interest_rate": c["interest_rate"],
                "expected_interest": expected,
                "outstanding_principal": outstanding,
                "status": c.get("status", "Active"),
                "display_name": c.get("display_name", ""),
            })
        return info

    def get_all_loans(self) -> Dict:
        """Return all loans in cache"""
        return self.loans_cache

    def get_borrower_due_days(self) -> List[Tuple[str, int]]:
        """Get all unique (borrower_name, due_day) pairs for template"""
        return list(self.borrower_loans_cache.keys())
