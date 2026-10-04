"""
Stage 9 — assisted similar-name matching for Excel import.

Similarity only produces confirmation candidates. Never auto-assigns.
"""

from __future__ import annotations

import database as db
from src.services.duplicate_checker import DuplicateChecker
from src.services.import_classify import (
    POSSIBLE_NAME_MATCH_REASON,
    apply_review_resolution,
    classify_import_rows,
    review_dialog_was_cancelled,
)
from src.services.loan_matcher import LoanMatcher
from src.services.name_similarity import (
    names_are_similar,
    names_equal_normalized,
    normalize_person_name,
)


def _row(name: str, due_day: int = 10, amount: float = 5000.0, date: str = "2024-09-01"):
    return {
        "date": date,
        "borrower_name": name,
        "due_day": due_day,
        "txn_type": "Principal Received",
        "amount": amount,
        "payment_mode": "UPI",
        "notes": "",
        "row_num": 2,
    }


def _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=True, two_loans=False):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    b_gupta = db.add_borrower("Yash Gupta", "", "")
    l_gupta = db.add_loan(b_gupta, 100000.0, 3.0, 10, "2026-01-05")
    extra = {}
    if two_loans:
        extra["l_gupta_2"] = db.add_loan(b_gupta, 50000.0, 2.5, 20, "2026-08-10")
    if two_borrowers:
        b_sharma = db.add_borrower("Yash Sharma", "", "")
        extra["b_sharma"] = b_sharma
        extra["l_sharma"] = db.add_loan(b_sharma, 50000.0, 2.0, 15, "2026-03-12")
    return {
        "b_gupta": b_gupta,
        "l_gupta": l_gupta,
        **extra,
    }


def test_normalize_case_and_whitespace():
    assert normalize_person_name(" Yash   Gupta ") == "yash gupta"
    assert names_equal_normalized("Yash Gupta", "yash gupta")
    assert names_equal_normalized("Yash, Gupta", "Yash Gupta")


def test_similarity_rules():
    assert names_are_similar("Yash", "Yash Gupta")
    assert names_are_similar("Yash Gupta", "Gupta Yash")
    assert names_are_similar("Pam", "Pammi")
    assert not names_are_similar("Yash Gupta", "Yash Gupta")  # exact is not "similar"
    assert not names_are_similar("Completely Unrelated Name", "Yash Gupta")
    assert not names_are_similar("ab", "Yash Gupta")


def test_partial_first_name_is_review_not_auto(temp_db_path, monkeypatch):
    ids = _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=False)
    matcher = LoanMatcher(temp_db_path)
    dup = DuplicateChecker(temp_db_path)
    result = classify_import_rows([_row("Yash")], matcher, dup)
    assert result["matched_txns"] == []
    assert result["error_txns"] == []
    assert len(result["review_txns"]) == 1
    review = result["review_txns"][0]
    assert review["reason"] == POSSIBLE_NAME_MATCH_REASON
    assert [c["loan_id"] for c in review["candidates"]] == [ids["l_gupta"]]
    assert review["candidates"][0]["borrower_name"] == "Yash Gupta"


def test_normalized_exact_name_still_deterministic(temp_db_path, monkeypatch):
    ids = _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=False)
    matcher = LoanMatcher(temp_db_path)
    loan, _c, status = matcher.match_by_borrower_due_day("  yash   gupta ", 10)
    assert status == "exact_match"
    assert loan["loan_id"] == ids["l_gupta"]

    dup = DuplicateChecker(temp_db_path)
    result = classify_import_rows([_row("yash gupta", due_day=10)], matcher, dup)
    assert len(result["matched_txns"]) == 1
    assert result["matched_txns"][0]["loan"]["loan_id"] == ids["l_gupta"]
    assert result["review_txns"] == []


def test_multiple_similar_borrowers_no_auto_select(temp_db_path, monkeypatch):
    ids = _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=True)
    matcher = LoanMatcher(temp_db_path)
    dup = DuplicateChecker(temp_db_path)
    result = classify_import_rows([_row("Yash")], matcher, dup)
    assert result["matched_txns"] == []
    cands = result["review_txns"][0]["candidates"]
    loan_ids = {c["loan_id"] for c in cands}
    names = {c["borrower_name"] for c in cands}
    assert loan_ids == {ids["l_gupta"], ids["l_sharma"]}
    assert names == {"Yash Gupta", "Yash Sharma"}


def test_multiple_loans_same_borrower_are_separate(temp_db_path, monkeypatch):
    ids = _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=False, two_loans=True)
    matcher = LoanMatcher(temp_db_path)
    cands = matcher.find_similar_name_loans("Yash")
    assert [c["loan_id"] for c in cands] == sorted([ids["l_gupta"], ids["l_gupta_2"]])
    dup = DuplicateChecker(temp_db_path)
    result = classify_import_rows([_row("Yash")], matcher, dup)
    assert len(result["review_txns"][0]["candidates"]) == 2


def test_unrelated_name_has_no_fuzzy_candidate(temp_db_path, monkeypatch):
    _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=False)
    matcher = LoanMatcher(temp_db_path)
    dup = DuplicateChecker(temp_db_path)
    result = classify_import_rows([_row("Completely Unrelated Name")], matcher, dup)
    assert result["review_txns"] == []
    assert result["matched_txns"] == []
    assert len(result["error_txns"]) == 1


def test_known_borrower_wrong_due_day_does_not_fuzzy(seeded_temp_db):
    """Prem Singh due 31 stays unmatched — do not suggest Prem's other due day."""
    path, _summary = seeded_temp_db
    matcher = LoanMatcher(path)
    dup = DuplicateChecker(path)
    result = classify_import_rows([_row("Prem Singh", due_day=31)], matcher, dup)
    assert result["review_txns"] == []
    assert result["matched_txns"] == []
    assert len(result["error_txns"]) == 1


def test_pammi_partial_is_review(seeded_temp_db):
    path, summary = seeded_temp_db
    matcher = LoanMatcher(path)
    dup = DuplicateChecker(path)
    result = classify_import_rows([_row("Pam", due_day=20, amount=100.0)], matcher, dup)
    assert result["matched_txns"] == []
    cands = result["review_txns"][0]["candidates"]
    assert any(c["loan_id"] == summary["loan_ids"]["pammi"] for c in cands)


def test_closed_loan_is_similar_name_candidate(seeded_temp_db):
    path, summary = seeded_temp_db
    matcher = LoanMatcher(path)
    cands = matcher.find_similar_name_loans("Vikram")
    assert any(c["loan_id"] == summary["loan_ids"]["vikram_closed"] for c in cands)
    assert any(c.get("status") == "Closed" for c in cands)


def test_reopened_loan_still_similar_candidate(temp_db_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", temp_db_path)
    db.initialize_db()
    bid = db.add_borrower("Yash Gupta", "", "")
    lid = db.add_loan(bid, 100000.0, 3.0, 10, "2026-01-05")
    db.add_transaction(bid, lid, "Interest Received", 3000.0, "2026-02-05")
    db.close_loan(lid)
    db.reopen_loan(lid)
    matcher = LoanMatcher(temp_db_path)
    cands = matcher.find_similar_name_loans("Yash")
    assert len(cands) == 1
    assert cands[0]["loan_id"] == lid
    assert cands[0]["status"] == "Active"
    loan, _c, status = matcher.match_by_borrower_due_day("Yash Gupta", 10)
    assert status == "exact_match"
    assert loan["loan_id"] == lid


def test_select_assigns_chosen_loan_only(temp_db_path, monkeypatch):
    ids = _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=True)
    matcher = LoanMatcher(temp_db_path)
    dup = DuplicateChecker(temp_db_path)
    result = classify_import_rows([_row("Yash")], matcher, dup)
    review = result["review_txns"][0]
    chosen = next(c for c in review["candidates"] if c["loan_id"] == ids["l_gupta"])
    matched, duplicates, skipped = [], [], []
    outcome = apply_review_resolution(
        review, chosen, False, dup, matched, duplicates, skipped
    )
    assert outcome == "matched"
    assert matched[0]["loan"]["loan_id"] == ids["l_gupta"]
    assert skipped == []


def test_skip_does_not_import(temp_db_path, monkeypatch):
    _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=False)
    matcher = LoanMatcher(temp_db_path)
    dup = DuplicateChecker(temp_db_path)
    result = classify_import_rows([_row("Yash")], matcher, dup)
    matched, duplicates, skipped = [], [], []
    outcome = apply_review_resolution(
        result["review_txns"][0], None, True, dup, matched, duplicates, skipped
    )
    assert outcome == "skipped"
    assert matched == []
    assert len(skipped) == 1


def test_dialog_cancel_predicate_matches_stage7():
    assert review_dialog_was_cancelled(None, False) is True
    assert review_dialog_was_cancelled({"loan_id": "L001"}, False) is False
    assert review_dialog_was_cancelled(None, True) is False


def test_fuzzy_select_still_detects_duplicate(temp_db_path, monkeypatch):
    ids = _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=False)
    db.add_transaction(
        ids["b_gupta"], ids["l_gupta"], "Principal Received", 5000.0, "2024-09-01"
    )
    matcher = LoanMatcher(temp_db_path)
    dup = DuplicateChecker(temp_db_path)
    result = classify_import_rows([_row("Yash")], matcher, dup)
    chosen = result["review_txns"][0]["candidates"][0]
    matched, duplicates, skipped = [], [], []
    outcome = apply_review_resolution(
        result["review_txns"][0], chosen, False, dup, matched, duplicates, skipped
    )
    assert outcome == "duplicate"
    assert duplicates[0]["reason"] == "database"
    assert matched == []


def test_fuzzy_select_atomic_write_no_new_borrower(temp_db_path, monkeypatch):
    ids = _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=False)
    before_borrowers = len(db.get_all_borrowers())
    before_loans = len(db.get_all_loans())
    matcher = LoanMatcher(temp_db_path)
    dup = DuplicateChecker(temp_db_path)
    result = classify_import_rows([_row("Yash", amount=4000.0)], matcher, dup)
    chosen = result["review_txns"][0]["candidates"][0]
    matched, duplicates, skipped = [], [], []
    apply_review_resolution(
        result["review_txns"][0], chosen, False, dup, matched, duplicates, skipped
    )
    imported = db.add_transactions_batch([{
        "borrower_id": matched[0]["loan"]["borrower_id"],
        "loan_id": matched[0]["loan"]["loan_id"],
        "txn_type": matched[0]["txn"]["txn_type"],
        "amount": matched[0]["txn"]["amount"],
        "txn_date": matched[0]["txn"]["date"],
        "notes": "",
        "payment_mode": "UPI",
    }])
    assert imported == 1
    assert len(db.get_all_borrowers()) == before_borrowers
    assert len(db.get_all_loans()) == before_loans
    assert db.get_loan(ids["l_gupta"])["outstanding_principal"] == 96000.0


def test_classify_never_creates_borrower(temp_db_path, monkeypatch):
    _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=False)
    before = len(db.get_all_borrowers())
    matcher = LoanMatcher(temp_db_path)
    dup = DuplicateChecker(temp_db_path)
    classify_import_rows([_row("Yash"), _row("Nobody")], matcher, dup)
    assert len(db.get_all_borrowers()) == before


def test_candidate_info_uses_original_principal(temp_db_path, monkeypatch):
    ids = _seed_yash_pair(temp_db_path, monkeypatch, two_borrowers=False)
    db.add_transaction(
        ids["b_gupta"], ids["l_gupta"], "Principal Received", 25000.0, "2026-02-01"
    )
    matcher = LoanMatcher(temp_db_path)
    cands = matcher.find_similar_name_loans("Yash")
    info = matcher.get_candidate_info(cands)
    assert info[0]["original_principal"] == 100000.0
    assert info[0]["principal"] == 100000.0
    assert info[0]["outstanding_principal"] == 75000.0
    assert info[0]["borrower_name"] == "Yash Gupta"
