"""
Stage 1 tests — canonical database path and shared connections.
"""

from __future__ import annotations

import inspect
import os

import database as db
from src.services.duplicate_checker import DuplicateChecker
from src.services.loan_matcher import LoanMatcher


def test_ui_transactions_uses_db_path_not_parent_relative():
    """Import/template entry points must reference db.DB_PATH, not ../lendtrack.db."""
    import ui_transactions

    source = inspect.getsource(ui_transactions)
    assert '..", "lendtrack.db"' not in source
    assert "os.path.join(os.path.dirname" not in source or "lendtrack.db" not in source
    assert "db.DB_PATH" in source


def test_no_parent_lendtrack_path_in_repo_python():
    """No application Python source should still point at parent-folder lendtrack.db."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    offenders = []
    needle = 'os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lendtrack.db")'
    app_dirs = [
        root,
        os.path.join(root, "src"),
    ]
    for base in app_dirs:
        for dirpath, dirnames, filenames in os.walk(base):
            # Do not recurse into tests/venv/git from root walk
            dirnames[:] = [
                d for d in dirnames
                if d not in (".venv", "__pycache__", ".git", "tests", "scripts")
            ]
            if os.path.basename(dirpath) in ("tests", "scripts"):
                continue
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                if needle in text:
                    offenders.append(path)
    assert offenders == [], f"Parent-relative lendtrack.db still present in: {offenders}"


def test_get_connection_enables_foreign_keys(initialized_temp_db):
    conn = db.get_connection(initialized_temp_db)
    try:
        enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert enabled == 1
    finally:
        conn.close()


def test_get_connection_default_uses_module_db_path(monkeypatch, tmp_path):
    path = str(tmp_path / "canonical.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    db.initialize_db()
    conn = db.get_connection()
    try:
        # sqlite exposes the file path via PRAGMA database_list
        rows = conn.execute("PRAGMA database_list").fetchall()
        main = [r for r in rows if r[1] == "main"][0]
        assert os.path.normpath(main[2]) == os.path.normpath(path)
    finally:
        conn.close()


def test_matcher_reads_canonical_seeded_db(seeded_temp_db):
    path, summary = seeded_temp_db
    matcher = LoanMatcher(path)
    # Prem Singh active loan must be visible via canonical path
    assert "Prem Singh" in matcher.loans_cache
    assert any(l["loan_id"] == summary["loan_ids"]["prem"] for l in matcher.loans_cache["Prem Singh"])


def test_duplicate_checker_reads_canonical_seeded_db(seeded_temp_db):
    path, summary = seeded_temp_db
    checker = DuplicateChecker(path)
    # Seeded Prem interest on 2024-02-15 / 3000 should be detected as duplicate key
    txn = {
        "date": "2024-02-15",
        "txn_type": "Interest Received",
        "amount": 3000.0,
    }
    assert checker.check_duplicate(txn, summary["loan_ids"]["prem"]) is True
