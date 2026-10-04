"""
Operator confirmation for scripts/seed_dev_db.py.

Never points at the workspace lendtrack.db.
"""

from __future__ import annotations

import os
import sqlite3

from scripts.seed_dev_db import confirm_destructive_seed, run_seed


WORKSPACE_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lendtrack.db",
)


def _workspace_db_fingerprint():
    if not os.path.isfile(WORKSPACE_DB):
        return None
    stat = os.stat(WORKSPACE_DB)
    return (stat.st_mtime_ns, stat.st_size)


def test_confirm_yes_allows_proceed():
    assert confirm_destructive_seed(r"C:\tmp\synthetic.db", input_fn=lambda _: "YES") is True


def test_confirm_no_rejects():
    assert confirm_destructive_seed(r"C:\tmp\synthetic.db", input_fn=lambda _: "NO") is False


def test_confirm_blank_rejects():
    assert confirm_destructive_seed(r"C:\tmp\synthetic.db", input_fn=lambda _: "") is False


def test_confirm_wrong_case_rejects():
    assert confirm_destructive_seed(r"C:\tmp\synthetic.db", input_fn=lambda _: "yes") is False


def test_run_seed_yes_uses_temp_db_only(temp_db_path, monkeypatch):
    before = _workspace_db_fingerprint()
    marker = temp_db_path + ".marker"
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write("keep")

    result = run_seed(input_fn=lambda _: "YES")
    assert result is not None
    assert result["expected_first_borrower_id"] == "B001"
    assert os.path.isfile(temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM borrowers").fetchone()[0]
    finally:
        conn.close()
    assert n == result["expected_borrower_count"]
    assert os.path.isfile(marker)
    assert _workspace_db_fingerprint() == before
    assert os.path.normpath(temp_db_path) != os.path.normpath(WORKSPACE_DB)


def test_run_seed_rejected_does_not_touch_db(temp_db_path):
    before = _workspace_db_fingerprint()
    payload = b"do-not-delete"
    with open(temp_db_path, "wb") as handle:
        handle.write(payload)
    mtime = os.stat(temp_db_path).st_mtime_ns

    for answer in ("NO", "", "yes"):
        result = run_seed(input_fn=lambda _p, a=answer: a)
        assert result is None
        with open(temp_db_path, "rb") as handle:
            assert handle.read() == payload
        assert os.stat(temp_db_path).st_mtime_ns == mtime

    assert _workspace_db_fingerprint() == before
