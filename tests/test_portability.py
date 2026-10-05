"""
Portability checks for launcher, build script, and setup docs.
Does not exercise accounting or import semantics.
"""

from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name: str) -> str:
    path = os.path.join(ROOT, name)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def test_launcher_and_setup_files_exist():
    for name in (
        "README.md",
        "requirements.txt",
        "LendTrack.bat",
        "build.bat",
        "main.py",
        "database.py",
    ):
        path = os.path.join(ROOT, name)
        assert os.path.isfile(path), f"Missing {name}"


def test_lendtrack_bat_has_no_machine_specific_paths():
    text = _read("LendTrack.bat")
    lowered = text.lower()
    assert "cd /d \"%~dp0\"" in lowered or "cd /d \"%~dp0\"" in text
    assert ".venv" in text
    assert "py -3.11" in text
    assert r"D:\LT" not in text
    assert r"C:\Users" not in text
    assert "OneDrive" not in text
    assert "%LOCALAPPDATA%" not in text


def test_build_bat_discovers_customtkinter_from_active_python():
    text = _read("build.bat")
    assert r"%LOCALAPPDATA%" not in text
    assert "Python311" not in text
    assert r"D:\LT" not in text
    assert r"C:\Users" not in text
    assert "customtkinter.__file__" in text
    assert "--add-data \"%CTK_DIR%;customtkinter\"" in text
    assert "import PyInstaller" in text
    assert "import customtkinter" in text
    assert re.search(r"ERROR:.*customtkinter", text)
    assert re.search(r"ERROR:.*PyInstaller", text)
    assert "main.py" in text


def test_readme_covers_fresh_windows_setup():
    text = _read("README.md")
    lowered = text.lower()
    assert "python 3.11" in lowered
    assert ".venv" in text
    assert "tkinter" in lowered
    assert "pandas" in lowered
    assert "pytest" in lowered
    assert "LendTrack.bat" in text
    assert "lendtrack.db" in lowered
    assert "does not" in lowered and "seed" in lowered
    assert "development-only" in lowered
    assert "seed_dev_db.py" in text
    assert "pip install -r requirements.txt" in text
    assert "outstanding" in lowered
    # Frozen EXE DB may document LOCALAPPDATA\\LendTrack; never hardcode site-packages.
    assert "Python311\\site-packages\\customtkinter" not in text
    assert "Programs\\Python\\Python311" not in text
    assert "LendTrack\\lendtrack.db" in text or "LendTrack/lendtrack.db" in text
