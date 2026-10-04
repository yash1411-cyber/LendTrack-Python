"""Stage D UX: borrower placeholder, global search, reports notify."""

from __future__ import annotations

import inspect

import customtkinter as ctk
import pytest

from ui_transactions import SELECT_BORROWER, SELECT_LOAN, TransactionsFrame


def _root():
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.withdraw()
    return root


def test_transactions_do_not_auto_select_first_borrower(seeded_temp_db):
    root = _root()
    frame = TransactionsFrame(root)
    root.update()
    assert frame._borrower_var.get() == SELECT_BORROWER
    assert frame._selected_borrower_id() is None
    assert frame._loan_var.get() == SELECT_LOAN
    assert str(frame._loan_dd.cget("state")).lower() in ("disabled", "disable")
    values = list(frame._borrower_dd.cget("values"))
    assert values[0] == SELECT_BORROWER
    assert values[1] != SELECT_BORROWER
    root.destroy()


def test_transactions_borrower_then_loan_and_switch(seeded_temp_db):
    path, summary = seeded_temp_db
    root = _root()
    frame = TransactionsFrame(root)
    root.update()
    prem = f"{summary['borrowers_by_name']['Prem Singh']} – Prem Singh"
    anita = f"{summary['borrowers_by_name']['Anita Desai']} – Anita Desai"
    frame._borrower_var.set(prem)
    frame._on_borrower_change(prem)
    root.update()
    assert frame._selected_borrower_id() == summary["borrowers_by_name"]["Prem Singh"]
    assert str(frame._loan_dd.cget("state")).lower() in ("normal", "enabled")
    assert frame._loan_var.get() == SELECT_LOAN
    loan_values = list(frame._loan_dd.cget("values"))
    assert SELECT_LOAN in loan_values
    prem_loan = next(v for v in loan_values if v != SELECT_LOAN)
    frame._loan_var.set(prem_loan)
    frame._on_loan_change(prem_loan)
    root.update()
    assert frame._selected_loan() is not None
    assert frame._selected_loan()["loan_id"] == summary["loan_ids"]["prem"]

    frame._borrower_var.set(anita)
    frame._on_borrower_change(anita)
    root.update()
    assert frame._loan_var.get() == SELECT_LOAN
    anita_ids = {ln.get("loan_id") for ln in frame._loan_map.values()}
    assert summary["loan_ids"]["anita"] in anita_ids
    assert summary["loan_ids"]["prem"] not in anita_ids

    frame.refresh()
    root.update()
    assert frame._borrower_var.get() == anita
    root.destroy()


def test_global_search_does_not_navigate_on_keystroke(initialized_temp_db):
    import database as db

    db.add_borrower("Rahul Sharma", "", "")
    db.add_borrower("Prem Singh", "", "")
    from main import LendTrackApp

    app = LendTrackApp()
    app.withdraw()
    app.update()
    assert app._current_screen == "Dashboard"
    app._search.insert(0, "Rah")
    app._on_global_search()
    app.update()
    assert app._current_screen == "Dashboard"
    assert "Borrowers" not in app._screens

    app._navigate("Borrowers")
    app.update()
    assert app._current_screen == "Borrowers"
    b_screen = app._screens["Borrowers"]
    assert b_screen._search.get() == "Rah"
    app._search.delete(0, "end")
    app._on_global_search()
    app.update()
    assert app._current_screen == "Borrowers"
    assert b_screen._search.get() == ""
    app.destroy()


def test_global_search_source_does_not_force_borrowers_navigation():
    import main as main_mod

    src = inspect.getsource(main_mod.LendTrackApp._on_global_search)
    assert "_navigate" not in src
    assert "Borrowers" not in src


def test_reports_export_uses_notify_not_messagebox(initialized_temp_db, tmp_path, monkeypatch):
    import ui_reports

    assert "messagebox" not in inspect.getsource(ui_reports)
    seen = []

    def fake_notify(parent, title, body, tone="info", geometry="440x240"):
        seen.append({"title": title, "body": body, "tone": tone})

    monkeypatch.setattr(ui_reports, "notify", fake_notify)
    root = _root()
    frame = ui_reports.ReportsFrame(root)
    frame._report_data = []
    frame._export_excel()
    assert seen and seen[-1]["tone"] == "info"

    monkeypatch.setattr(
        ui_reports.filedialog,
        "asksaveasfilename",
        lambda **_k: str(tmp_path / "report.xlsx"),
    )
    frame._report_data = [
        {
            "borrower_id": "B001",
            "name": "Test",
            "phone": "",
            "total_principal_given": 1,
            "principal_returned": 0,
            "outstanding_principal": 1,
            "expected_monthly_interest": 0,
            "interest_received": 0,
            "pending_interest": 0,
        }
    ]
    seen.clear()
    frame._export_excel()
    assert seen and seen[-1]["tone"] == "success"
    assert (tmp_path / "report.xlsx").is_file()
    root.destroy()


@pytest.mark.parametrize("geom", ["1280x780", "1024x640"])
def test_stage_d_layouts_keep_placeholder(seeded_temp_db, geom):
    from main import LendTrackApp

    app = LendTrackApp()
    app.geometry(geom)
    app.update()
    app._navigate("Transactions")
    app.update()
    frame = app._screens["Transactions"]
    assert frame._borrower_var.get() == SELECT_BORROWER
    assert frame._loan_var.get() == SELECT_LOAN
    app.destroy()
