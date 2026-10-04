"""
Compact calendar popup for user-editable date fields.

Presentation only. Writes YYYY-MM-DD into an existing entry. Does not
touch the database or accounting.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime

import customtkinter as ctk

from src.ui.theme import (
    BG, CARD, CARD2, TEXT, MUTED, BORDER, ACCENT, HOVER, NAV_ACTIVE,
    font_body, font_body_bold, font_overline, font_table,
    RADIUS_CONTROL, S8, S12, S16,
    secondary_button, setup_dialog, place_dialog,
)

ISO_FMT = "%Y-%m-%d"
WEEKDAYS = ("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")


def format_iso_date(value: date) -> str:
    return value.strftime(ISO_FMT)


def parse_entry_date(text: str, fallback: date | None = None) -> date:
    """Parse YYYY-MM-DD for calendar navigation only. Does not rewrite the field."""
    raw = (text or "").strip()[:10]
    try:
        return datetime.strptime(raw, ISO_FMT).date()
    except ValueError:
        return fallback if fallback is not None else date.today()


def set_entry_iso(entry, iso: str) -> None:
    """Replace the entry contents with an ISO date. Does not validate accounting."""
    entry.delete(0, "end")
    entry.insert(0, iso)


def attach_date_picker(parent, entry, button_parent=None) -> ctk.CTkButton:
    """Add a compact Pick button that opens the calendar for `entry`."""
    host = button_parent or parent

    def _open():
        initial = parse_entry_date(entry.get(), fallback=date.today())
        DatePickerDialog(
            parent,
            initial=initial,
            on_select=lambda iso: set_entry_iso(entry, iso),
        )

    btn = secondary_button(
        host,
        "Pick",
        _open,
        width=52,
        height=36,
        font=font_table(),
    )
    btn.pack(side="right", padx=(S8, 0))
    return btn


class DatePickerDialog(ctk.CTkToplevel):
    """Month calendar. Selecting a day writes YYYY-MM-DD and closes."""

    def __init__(self, parent, initial: date, on_select=None):
        super().__init__(parent)
        self._on_select = on_select
        self._initial = initial
        self._view = date(initial.year, initial.month, 1)
        self._day_buttons: list[ctk.CTkButton] = []

        setup_dialog(self, "Select date", "300x360")
        self._build()
        place_dialog(self, parent)
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass
        self.bind("<Escape>", lambda _e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=0, column=0, sticky="ew", padx=S12, pady=(S12, S8))
        nav.grid_columnconfigure(1, weight=1)

        secondary_button(
            nav, "<", lambda: self._shift(-1), width=36, height=32, font=font_body_bold()
        ).grid(row=0, column=0, padx=(0, 4))
        self._month_lbl = ctk.CTkLabel(
            nav, text="", font=font_body_bold(), text_color=TEXT
        )
        self._month_lbl.grid(row=0, column=1, sticky="ew")
        secondary_button(
            nav, ">", lambda: self._shift(1), width=36, height=32, font=font_body_bold()
        ).grid(row=0, column=2, padx=(4, 0))

        days_hdr = ctk.CTkFrame(self, fg_color="transparent")
        days_hdr.grid(row=1, column=0, sticky="ew", padx=S12)
        for i, name in enumerate(WEEKDAYS):
            days_hdr.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(
                days_hdr, text=name, font=font_overline(), text_color=MUTED
            ).grid(row=0, column=i, padx=1, pady=2)

        self._grid = ctk.CTkFrame(self, fg_color="transparent")
        self._grid.grid(row=2, column=0, sticky="nsew", padx=S12, pady=(0, S8))
        for i in range(7):
            self._grid.grid_columnconfigure(i, weight=1)

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=3, column=0, sticky="ew", padx=S12, pady=(0, S12))
        secondary_button(bf, "Cancel", self._cancel, width=110).pack(side="left")

        self._render_month()

    def _shift(self, months: int) -> None:
        month = self._view.month + months
        year = self._view.year
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        self._view = date(year, month, 1)
        self._render_month()

    def _render_month(self) -> None:
        self._month_lbl.configure(text=self._view.strftime("%B %Y"))
        for btn in self._day_buttons:
            btn.destroy()
        self._day_buttons.clear()

        cal = calendar.Calendar(firstweekday=6)
        weeks = cal.monthdayscalendar(self._view.year, self._view.month)
        today = date.today()
        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                if day == 0:
                    spacer = ctk.CTkLabel(self._grid, text="", width=32, height=28)
                    spacer.grid(row=r, column=c, padx=1, pady=1)
                    self._day_buttons.append(spacer)
                    continue
                cell = date(self._view.year, self._view.month, day)
                fg = CARD2
                hover = NAV_ACTIVE
                if cell == today:
                    fg = NAV_ACTIVE
                if cell == self._initial:
                    fg = ACCENT
                    hover = HOVER
                btn = ctk.CTkButton(
                    self._grid,
                    text=str(day),
                    width=32,
                    height=28,
                    corner_radius=RADIUS_CONTROL,
                    fg_color=fg,
                    hover_color=hover,
                    text_color=TEXT,
                    font=font_body(),
                    command=lambda d=day: self._select_day(d),
                )
                btn.grid(row=r, column=c, padx=1, pady=1)
                self._day_buttons.append(btn)

    def _select_day(self, day: int) -> None:
        chosen = date(self._view.year, self._view.month, day)
        iso = format_iso_date(chosen)
        if self._on_select:
            self._on_select(iso)
        self.destroy()

    def _cancel(self, _e=None) -> None:
        try:
            self.destroy()
        except Exception:
            pass
