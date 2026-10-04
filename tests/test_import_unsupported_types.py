"""Unsupported Excel types are Can't import before matching or write."""

from __future__ import annotations

import database as db
from src.services.duplicate_checker import DuplicateChecker
from src.services.import_classify import (
    classify_import_rows,
    unsupported_import_type_reason,
    write_batch_from_matched,
)
from src.services.loan_matcher import LoanMatcher


class _TrackingMatcher(LoanMatcher):
    def __init__(self, db_path: str):
        super().__init__(db_path)
        self.match_calls = 0

    def match_by_display_name(self, *args, **kwargs):
        self.match_calls += 1
        return super().match_by_display_name(*args, **kwargs)

    def match_by_borrower_due_day(self, *args, **kwargs):
        self.match_calls += 1
        return super().match_by_borrower_due_day(*args, **kwargs)

    def match_by_borrower_due_day_interest(self, *args, **kwargs):
        self.match_calls += 1
        return super().match_by_borrower_due_day_interest(*args, **kwargs)

    def find_similar_name_loans(self, *args, **kwargs):
        self.match_calls += 1
        return super().find_similar_name_loans(*args, **kwargs)


def _row(name, txn_type, due_day=25, amount=3000.0, date="2024-09-01"):
    return {
        "date": date,
        "borrower_name": name,
        "due_day": due_day,
        "txn_type": txn_type,
        "amount": amount,
        "payment_mode": "Cash",
        "notes": "",
        "row_num": 2,
    }


def test_loan_given_cant_import_without_matching(seeded_temp_db):
    path, _summary = seeded_temp_db
    matcher = _TrackingMatcher(path)
    before = len(db.get_all_transactions_raw())
    result = classify_import_rows(
        [_row("Prem Singh", "Loan Given")], matcher, DuplicateChecker(path)
    )
    assert matcher.match_calls == 0
    assert result["matched_txns"] == []
    assert result["review_txns"] == []
    assert result["duplicate_txns"] == []
    assert len(result["error_txns"]) == 1
    assert result["error_txns"][0]["error"] == "Unsupported transaction type: Loan Given"
    assert result["error_txns"][0]["txn"]["txn_type"] == "Loan Given"
    assert len(db.get_all_transactions_raw()) == before


def test_adjustment_cant_import_without_matching(seeded_temp_db):
    path, _summary = seeded_temp_db
    matcher = _TrackingMatcher(path)
    result = classify_import_rows(
        [_row("Prem Singh", "Adjustment")], matcher, DuplicateChecker(path)
    )
    assert matcher.match_calls == 0
    assert result["matched_txns"] == []
    assert result["error_txns"][0]["error"] == "Unsupported transaction type: Adjustment"
    assert result["error_txns"][0]["txn"]["txn_type"] == "Adjustment"


def test_unknown_type_cant_import(seeded_temp_db):
    path, _summary = seeded_temp_db
    matcher = _TrackingMatcher(path)
    result = classify_import_rows(
        [_row("Prem Singh", "Something Else")], matcher, DuplicateChecker(path)
    )
    assert matcher.match_calls == 0
    assert result["error_txns"][0]["error"] == "Unsupported transaction type: Something Else"


def test_mixed_file_valid_rows_write_unsupported_skipped(seeded_temp_db):
    path, summary = seeded_temp_db
    matcher = _TrackingMatcher(path)
    rows = [
        _row("Prem Singh", "Interest Received", amount=111.0, date="2024-09-02"),
        _row("Sneha Kapoor", "Principal Received", due_day=7, amount=500.0, date="2024-09-03"),
        _row("Prem Singh", "Loan Given", amount=100000.0, date="2024-09-04"),
        _row("Prem Singh", "Adjustment", amount=50.0, date="2024-09-05"),
        _row("Prem Singh", "Something Else", amount=9.0, date="2024-09-06"),
        _row("Anita Desai", "Interest Received", due_day=10, amount=125.0, date="2024-09-07"),
    ]
    before = len(db.get_all_transactions_raw())
    result = classify_import_rows(rows, matcher, DuplicateChecker(path))
    assert len(result["matched_txns"]) == 3
    assert len(result["error_txns"]) == 3
    assert result["review_txns"] == []
    errors = {e["txn"]["txn_type"]: e["error"] for e in result["error_txns"]}
    assert "Loan Given" in errors
    assert "Adjustment" in errors
    assert "Something Else" in errors
    for item in result["matched_txns"]:
        assert item["txn"]["txn_type"] in ("Interest Received", "Principal Received")

    batch = write_batch_from_matched(result["matched_txns"])
    assert all(b["txn_type"] in ("Interest Received", "Principal Received") for b in batch)
    written = db.add_transactions_batch(batch)
    assert written == 3
    after = db.get_all_transactions_raw()
    assert len(after) == before + 3
    new_txns = [t for t in after if t["txn_date"] >= "2024-09-02"]
    assert len(new_txns) == 3
    assert {t["txn_type"] for t in new_txns} <= {
        "Interest Received",
        "Principal Received",
    }


def test_unsupported_loan_given_does_not_open_ambiguous_review(seeded_temp_db):
    path, _summary = seeded_temp_db
    matcher = _TrackingMatcher(path)
    # Rahul Sharma has two loans on due day 5
    result = classify_import_rows(
        [_row("Rahul Sharma", "Loan Given", due_day=5, amount=100000.0)],
        matcher,
        DuplicateChecker(path),
    )
    assert matcher.match_calls == 0
    assert result["review_txns"] == []
    assert len(result["error_txns"]) == 1
    assert "Unsupported transaction type: Loan Given" in result["error_txns"][0]["error"]


def test_no_silent_type_conversion(seeded_temp_db):
    path, _summary = seeded_temp_db
    result = classify_import_rows(
        [
            _row("Prem Singh", "Loan Given"),
            _row("Prem Singh", "Adjustment"),
        ],
        LoanMatcher(path),
        DuplicateChecker(path),
    )
    types = [e["txn"]["txn_type"] for e in result["error_txns"]]
    assert types == ["Loan Given", "Adjustment"]
    assert result["matched_txns"] == []


def test_write_batch_defense_drops_unsupported_even_if_matched(seeded_temp_db):
    _path, summary = seeded_temp_db
    lid = summary["loan_ids"]["prem"]
    bid = summary["borrowers_by_name"]["Prem Singh"]
    fake_matched = [
        {
            "txn": {
                "date": "2024-09-10",
                "txn_type": "Loan Given",
                "amount": 1.0,
                "notes": "",
                "payment_mode": "Cash",
            },
            "loan": {"borrower_id": bid, "loan_id": lid},
        },
        {
            "txn": {
                "date": "2024-09-11",
                "txn_type": "Interest Received",
                "amount": 100.0,
                "notes": "",
                "payment_mode": "Cash",
            },
            "loan": {"borrower_id": bid, "loan_id": lid},
        },
    ]
    batch = write_batch_from_matched(fake_matched)
    assert len(batch) == 1
    assert batch[0]["txn_type"] == "Interest Received"


def test_parser_reads_legacy_and_unknown_types(tmp_path):
    import openpyxl
    from src.services.excel_import_service import ExcelImportService

    path = tmp_path / "legacy_types.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Daily Transactions"
    ws.append(["Date", "Borrower Name", "Due Day", "Transaction Type", "Amount", "Payment Mode", "Notes"])
    ws.append(["2024-09-01", "Prem Singh", 25, "Loan Given", 100000, "Cash", ""])
    ws.append(["2024-09-02", "Prem Singh", 25, "Adjustment", 10, "Cash", ""])
    ws.append(["2024-09-03", "Prem Singh", 25, "Something Else", 10, "Cash", ""])
    ws.append(["2024-09-04", "Prem Singh", 25, "Interest Received", 3000, "Cash", ""])
    wb.save(path)
    rows, ok = ExcelImportService().read_excel(str(path))
    assert ok is True
    assert [r["txn_type"] for r in rows] == [
        "Loan Given",
        "Adjustment",
        "Something Else",
        "Interest Received",
    ]


def test_unsupported_reason_helper():
    assert unsupported_import_type_reason("Interest Received") is None
    assert unsupported_import_type_reason("Principal Received") is None
    assert unsupported_import_type_reason("Loan Given") == "Unsupported transaction type: Loan Given"
    assert unsupported_import_type_reason("Adjustment") == "Unsupported transaction type: Adjustment"
    assert unsupported_import_type_reason("  ") == "Unsupported transaction type: (blank)"
