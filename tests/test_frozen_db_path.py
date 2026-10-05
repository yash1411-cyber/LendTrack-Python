"""
P1-2 — source vs frozen database path resolution.

Uses temporary LOCALAPPDATA only. Does not touch the workspace lendtrack.db
or the user's real AppData database.
"""

from __future__ import annotations

import os
import sys

import database as db


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DB = os.path.join(ROOT, "lendtrack.db")


def test_source_mode_resolves_repo_relative(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    path = db.get_database_path()
    assert os.path.normpath(path) == os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(db.__file__)), "lendtrack.db")
    )
    assert path.endswith("lendtrack.db")
    assert os.path.normpath(path) == os.path.normpath(SOURCE_DB) or os.path.basename(
        os.path.dirname(path)
    ) == os.path.basename(ROOT)


def test_frozen_mode_uses_localappdata_lendtrack(monkeypatch, tmp_path):
    fake_local = tmp_path / "LocalAppData"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    path = db.get_database_path()
    expected = os.path.join(str(fake_local), "LendTrack", "lendtrack.db")
    assert os.path.normpath(path) == os.path.normpath(expected)
    assert os.path.isdir(os.path.join(str(fake_local), "LendTrack"))


def test_frozen_mode_creates_lendtrack_directory(monkeypatch, tmp_path):
    fake_local = tmp_path / "LocalMissing"
    assert not fake_local.exists()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    path = db.get_database_path()
    app_dir = os.path.dirname(path)
    assert os.path.isdir(app_dir)
    assert os.path.basename(app_dir) == "LendTrack"


def test_frozen_mode_does_not_use_source_repo_db(monkeypatch, tmp_path):
    fake_local = tmp_path / "LocalAppData"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    path = db.get_database_path()
    assert os.path.normpath(path) != os.path.normpath(SOURCE_DB)
    assert "LendTrack" in path
    assert os.path.dirname(os.path.abspath(db.__file__)) not in os.path.normpath(path)


def test_frozen_mode_keeps_existing_db_file(monkeypatch, tmp_path):
    fake_local = tmp_path / "LocalAppData"
    app_dir = fake_local / "LendTrack"
    app_dir.mkdir(parents=True)
    existing = app_dir / "lendtrack.db"
    marker = b"existing-frozen-db-bytes"
    existing.write_bytes(marker)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    path = db.get_database_path()
    assert os.path.normpath(path) == os.path.normpath(str(existing))
    assert existing.read_bytes() == marker


def test_frozen_mode_localappdata_fallback_to_home(monkeypatch, tmp_path):
    """If LOCALAPPDATA is unset, fall back to ~/AppData/Local/LendTrack."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    # expanduser("~") on Windows uses USERPROFILE; ensure it points at tmp home
    monkeypatch.setattr(os.path, "expanduser", lambda _p: str(home))

    path = db.get_database_path()
    expected = os.path.join(str(home), "AppData", "Local", "LendTrack", "lendtrack.db")
    assert os.path.normpath(path) == os.path.normpath(expected)
    assert os.path.isdir(os.path.dirname(path))


def test_module_db_path_is_source_mode_in_tests():
    """Pytest runs unfrozen; DB_PATH must remain the repo-relative source path."""
    assert not getattr(sys, "frozen", False)
    assert os.path.normpath(db.DB_PATH) == os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(db.__file__)), "lendtrack.db")
    )
