"""
Pytest fixtures for LendTrack Stage 0.

Isolates tests onto temporary SQLite files by monkeypatching database.DB_PATH.
Does not alter application business logic.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def temp_db_path(tmp_path, monkeypatch):
    """Point database.DB_PATH at a fresh temp file for the duration of a test."""
    import database as db

    path = tmp_path / "lendtrack_test.db"
    monkeypatch.setattr(db, "DB_PATH", str(path))
    return str(path)


@pytest.fixture
def initialized_temp_db(temp_db_path):
    """Temp DB with schema created via database.initialize_db()."""
    import database as db

    db.initialize_db()
    return temp_db_path


@pytest.fixture
def seeded_temp_db(temp_db_path):
    """Temp DB fully seeded with synthetic Stage 0 data."""
    from scripts.seed_dev_db import reset_database, seed_all

    reset_database()
    summary = seed_all()
    return temp_db_path, summary
