"""
Stage 3 tests — safe, deterministic loan matching rules.
"""

from __future__ import annotations

from src.services.loan_matcher import LoanMatcher


def test_exact_unambiguous_match(seeded_temp_db):
    path, summary = seeded_temp_db
    matcher = LoanMatcher(path)
    loan, candidates, status = matcher.match_by_borrower_due_day("Prem Singh", 25)
    assert status == "exact_match"
    assert loan["loan_id"] == summary["loan_ids"]["prem"]
    assert len(candidates) == 1


def test_ambiguous_same_borrower_same_due_day(seeded_temp_db):
    path, _summary = seeded_temp_db
    matcher = LoanMatcher(path)
    loan, candidates, status = matcher.match_by_borrower_due_day("Rahul Sharma", 5)
    assert status == "ambiguous"
    assert loan is None
    assert len(candidates) == 2


def test_closed_loan_is_matchable(seeded_temp_db):
    path, summary = seeded_temp_db
    matcher = LoanMatcher(path)
    loan, candidates, status = matcher.match_by_borrower_due_day("Vikram Mehta", 1)
    assert status == "exact_match"
    assert loan["loan_id"] == summary["loan_ids"]["vikram_closed"]
    assert loan["status"] == "Closed"
    assert len(candidates) == 1


def test_interest_auto_match_does_not_silently_assign(seeded_temp_db):
    """Karan has two loans with identical expected interest (₹3000)."""
    path, _summary = seeded_temp_db
    matcher = LoanMatcher(path)
    loan, candidates, status = matcher.match_by_borrower_due_day("Karan Joshi", 8)
    assert status == "ambiguous"
    assert len(candidates) == 2

    picked, step2 = matcher.match_by_borrower_due_day_interest(
        "Karan Joshi", 8, 3000.0, "Interest Received"
    )
    assert picked is None
    assert step2.startswith("Still ambiguous")
    assert "matched_by_interest" not in step2


def test_display_name_uses_original_principal_after_repayment(seeded_temp_db):
    """Anita had 50k original; after 10k principal received outstanding is 40k."""
    path, summary = seeded_temp_db
    matcher = LoanMatcher(path)
    anita_loans = matcher.loans_cache["Anita Desai"]
    assert len(anita_loans) == 1
    loan = anita_loans[0]
    assert loan["loan_id"] == summary["loan_ids"]["anita"]
    assert loan["original_principal"] == 50000.0
    assert loan["outstanding_principal"] == 40000.0
    # Stable identity string still shows original principal
    assert "₹50,000" in loan["display_name"]
    assert "Due 10" in loan["display_name"]

    matched, status = matcher.match_by_display_name(
        "Anita Desai", loan["display_name"]
    )
    assert status == "matched"
    assert matched["loan_id"] == loan["loan_id"]

    # Excel string with original principal (fixture style) also matches
    matched2, status2 = matcher.match_by_display_name(
        "Anita Desai", "01-Mar-24 | ₹50,000 | Due 10"
    )
    assert status2 == "matched"
    assert matched2["loan_id"] == loan["loan_id"]


def test_display_name_partial_requires_date(seeded_temp_db):
    """Principal+due without matching date must not silently match."""
    path, summary = seeded_temp_db
    matcher = LoanMatcher(path)
    # Rahul Sharma L004: 15-Jan-24 | ₹100,000 | Due 5
    # Wrong date, same principal+due as one loan — must not match via loose partial
    loan, status = matcher.match_by_display_name(
        "Rahul Sharma", "01-Jan-99 | ₹100,000 | Due 5"
    )
    assert loan is None
    assert "No loan found" in status or "Ambiguous" in status


def test_unmatched_borrower_and_due_day(seeded_temp_db):
    path, _summary = seeded_temp_db
    matcher = LoanMatcher(path)

    loan, status = matcher.match_by_display_name("Nobody Exists", "01-Jan-24 | ₹1 | Due 1")
    assert loan is None
    assert "not found" in status.lower()

    loan2, cands, status2 = matcher.match_by_borrower_due_day("Prem Singh", 31)
    assert loan2 is None
    assert status2 == "not_found" or "No loan found" in status2
    assert cands == []


def test_get_candidate_info_has_derived_outstanding(seeded_temp_db):
    path, _summary = seeded_temp_db
    matcher = LoanMatcher(path)
    _loan, candidates, status = matcher.match_by_borrower_due_day("Rahul Sharma", 5)
    assert status == "ambiguous"
    info = matcher.get_candidate_info(candidates)
    assert len(info) == 2
    for row in info:
        assert "outstanding_principal" in row
        assert isinstance(row["outstanding_principal"], (int, float))
        assert "principal" in row
        assert "expected_interest" in row
        # Must not KeyError — values are derived, not missing schema columns
        assert row["outstanding_principal"] >= 0
