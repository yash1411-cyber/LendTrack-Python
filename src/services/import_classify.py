"""
Import row classification — match, duplicate, review, or error.

Extracted for Stage 4 so workflow rules are unit-testable without the GUI.
Does not create borrowers/loans. Does not open AmbiguousMatchDialog (Stage 7).
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional

from src.services.duplicate_checker import DuplicateChecker
from src.services.loan_matcher import LoanMatcher

POSSIBLE_NAME_MATCH_REASON = "Possible match — please confirm"


def review_dialog_was_cancelled(selected_loan, skipped: bool) -> bool:
    """Stage 7/9: closing the dialog without Select or Skip cancels the import."""
    return (not skipped) and selected_loan is None


def classify_import_rows(
    transactions: List[Dict],
    loan_matcher: LoanMatcher,
    duplicate_checker: DuplicateChecker,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Classify parsed Excel rows into matched / review / duplicate / error buckets.

    Review rows are NOT imported (manual resolution is Stage 7).
    """
    matched_txns: List[Dict] = []
    review_txns: List[Dict] = []
    error_txns: List[Dict] = []
    duplicate_txns: List[Dict] = []

    duplicate_checker.reset_batch()

    for txn in transactions:
        matched_loan = None
        error_msg = None
        needs_review = False
        review_candidates: List[Dict] = []
        review_reason = ""

        try:
            if "loan_display" in txn:
                loan, status = loan_matcher.match_by_display_name(
                    txn["borrower_name"], txn["loan_display"]
                )
                if status == "matched":
                    matched_loan = loan
                elif isinstance(status, str) and status.startswith("Ambiguous"):
                    needs_review = True
                    review_candidates = list(
                        loan_matcher.loans_for_canonical_borrower(txn["borrower_name"])
                    )
                    review_reason = status
                else:
                    similar = _assisted_name_candidates(loan_matcher, txn["borrower_name"], status)
                    if similar:
                        needs_review = True
                        review_candidates = similar
                        review_reason = POSSIBLE_NAME_MATCH_REASON
                    else:
                        error_msg = status

            elif "due_day" in txn:
                loan, candidates, step1_status = loan_matcher.match_by_borrower_due_day(
                    txn["borrower_name"], txn["due_day"]
                )
                if step1_status == "exact_match":
                    matched_loan = loan
                elif step1_status == "ambiguous":
                    # Stage 3: interest auto-match never assigns — always review
                    _loan, _step2 = loan_matcher.match_by_borrower_due_day_interest(
                        txn["borrower_name"],
                        txn["due_day"],
                        txn["amount"],
                        txn["txn_type"],
                    )
                    needs_review = True
                    review_candidates = candidates
                    review_reason = "Multiple loans share borrower + due day"
                else:
                    similar = _assisted_name_candidates(
                        loan_matcher, txn["borrower_name"], step1_status
                    )
                    if similar:
                        needs_review = True
                        review_candidates = similar
                        review_reason = POSSIBLE_NAME_MATCH_REASON
                    else:
                        error_msg = step1_status
            else:
                error_msg = "Row missing Loan Display Name and Due Day"

            if needs_review:
                review_txns.append({
                    "txn": txn,
                    "candidates": review_candidates,
                    "reason": review_reason,
                })
                continue

            if matched_loan:
                dup_kind = duplicate_checker.classify_duplicate(
                    txn, matched_loan["loan_id"]
                )
                if dup_kind:
                    duplicate_txns.append({
                        "txn": txn,
                        "loan": matched_loan,
                        "reason": dup_kind,
                    })
                else:
                    matched_txns.append({
                        "txn": txn,
                        "loan": matched_loan,
                    })
                    duplicate_checker.remember(txn, matched_loan["loan_id"])
            elif error_msg:
                error_txns.append({
                    "txn": txn,
                    "error": error_msg,
                })

        except Exception as e:
            error_txns.append({
                "txn": txn,
                "error": str(e),
            })

    return {
        "matched_txns": matched_txns,
        "review_txns": review_txns,
        "duplicate_txns": duplicate_txns,
        "error_txns": error_txns,
    }


def _assisted_name_candidates(
    loan_matcher: LoanMatcher,
    borrower_name: str,
    not_found_status: str,  # retained for call-site clarity; lookup uses matcher cache
) -> List[Dict]:
    """
    After deterministic matching fails, offer similar-name loans for confirmation.

    If the Excel borrower is already a known name (exact/normalized) but the
    loan/due-day did not match, do NOT widen to other borrowers.
    """
    kind, _names = loan_matcher.canonical_borrower_names(borrower_name)
    if kind != "not_found":
        return []
    return loan_matcher.find_similar_name_loans(borrower_name)


def apply_review_resolution(
    review_item: Dict[str, Any],
    selected_loan: Optional[dict],
    skipped: bool,
    duplicate_checker: DuplicateChecker,
    matched_txns: List[Dict],
    duplicate_txns: List[Dict],
    skipped_review: List[Dict],
) -> str:
    """
    Apply an explicit user resolution for one ambiguous row.

    Returns: 'matched' | 'duplicate' | 'skipped' | 'invalid'

    Never silently assigns a loan — selected_loan must be provided unless skipped.
    """
    txn = review_item["txn"]
    if skipped or selected_loan is None:
        skipped_review.append({
            "txn": txn,
            "reason": review_item.get("reason", "skipped by user"),
        })
        return "skipped"

    # Guard: selected loan must be one of the candidates
    candidate_ids = {c.get("loan_id") for c in review_item.get("candidates") or []}
    if candidate_ids and selected_loan.get("loan_id") not in candidate_ids:
        return "invalid"

    dup_kind = duplicate_checker.classify_duplicate(txn, selected_loan["loan_id"])
    if dup_kind:
        duplicate_txns.append({
            "txn": txn,
            "loan": selected_loan,
            "reason": dup_kind,
        })
        return "duplicate"

    matched_txns.append({
        "txn": txn,
        "loan": selected_loan,
    })
    duplicate_checker.remember(txn, selected_loan["loan_id"])
    return "matched"


def build_import_status(
    imported: int,
    failed: int,
    matched_count: int,
    duplicate_count: int,
    error_count: int,
    review_count: int,
    error_message: str = "",
    skipped_review_count: int = 0,
) -> Dict[str, str]:
    """
    Honest status summary for the results step / tests.
    Never reports success when the batch rolled back or nothing was imported
    while problems remain.
    """
    if failed:
        return {
            "status": "rolled_back",
            "headline": "IMPORT ROLLED BACK (no rows saved)",
            "detail": error_message or "Batch failed",
        }
    if imported > 0:
        extra = []
        if skipped_review_count:
            extra.append(f"{skipped_review_count} ambiguous row(s) skipped by user")
        if review_count:
            extra.append(f"{review_count} review row(s) still unresolved")
        if duplicate_count:
            extra.append(f"{duplicate_count} duplicate(s) skipped")
        if error_count:
            extra.append(f"{error_count} error row(s) skipped")
        return {
            "status": "success",
            "headline": "IMPORT SUCCESSFUL",
            "detail": "; ".join(extra) if extra else "All matched rows imported",
        }
    # imported == 0, not failed
    if review_count and matched_count == 0 and not skipped_review_count:
        return {
            "status": "review_only",
            "headline": "NO ROWS IMPORTED — manual review required",
            "detail": f"{review_count} ambiguous row(s) were not imported",
        }
    if skipped_review_count and matched_count == 0:
        return {
            "status": "nothing_imported",
            "headline": "NO ROWS IMPORTED",
            "detail": (
                f"user skipped {skipped_review_count} ambiguous row(s); "
                f"duplicates={duplicate_count}, errors={error_count}"
            ),
        }
    if duplicate_count or error_count:
        return {
            "status": "nothing_imported",
            "headline": "NO ROWS IMPORTED",
            "detail": (
                f"duplicates={duplicate_count}, errors={error_count}, "
                f"review={review_count}, skipped_review={skipped_review_count}"
            ),
        }
    return {
        "status": "nothing_imported",
        "headline": "NO ROWS IMPORTED",
        "detail": "No matched transactions",
    }
