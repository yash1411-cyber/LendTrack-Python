"""
Ambiguous Match Dialog - Resolve multiple loan matches interactively.

Stage 7: requires an explicit Select or Skip — never silent assignment.
"""

from __future__ import annotations

from typing import Optional, Tuple

import customtkinter as ctk
from tkinter import messagebox

BG = "#0F1117"
CARD = "#1E2435"
CARD2 = "#252B3B"
ACCENT = "#4F8EF7"
GREEN = "#34C77B"
AMBER = "#F5A623"
TEXT = "#E8EBF2"
MUTED = "#7A849E"
BORDER = "#2C3347"


class AmbiguousMatchDialog(ctk.CTkToplevel):
    """Dialog for resolving ambiguous loan matches."""

    def __init__(
        self,
        parent,
        borrower_name: str,
        candidates: list,
        txn_data: dict,
        due_day: Optional[int] = None,
        reason: str = "",
    ):
        super().__init__(parent)
        self.title("Multiple Loans Found - Select One")
        self.geometry("720x520")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.grab_set()
        self.lift()
        self.focus_force()

        self.borrower_name = borrower_name
        self.due_day = due_day
        self.candidates = candidates
        self.txn_data = txn_data
        self.reason = reason or "Multiple loans match this row"
        self.selected_loan: Optional[dict] = None
        self.skip = False

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        if self.due_day is not None:
            title = f"Multiple loans for {self.borrower_name} (Due Day {self.due_day})"
        else:
            title = f"Multiple loans for {self.borrower_name}"

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))

        ctk.CTkLabel(
            self,
            text=self.reason,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=AMBER,
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        info_frame = ctk.CTkFrame(
            self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=8
        )
        info_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10), ipady=8)

        info_text = (
            f"Date: {self.txn_data.get('date')} | "
            f"Type: {self.txn_data.get('txn_type')} | "
            f"Amount: ₹{float(self.txn_data.get('amount') or 0):,.0f}"
        )
        ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=MUTED,
        ).pack(anchor="w", padx=12, pady=4)

        ctk.CTkLabel(
            self,
            text="Select the correct loan (required — no automatic choice):",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=TEXT,
        ).grid(row=3, column=0, sticky="nw", padx=20, pady=(0, 6))

        candidates_frame = ctk.CTkScrollableFrame(
            self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=8
        )
        candidates_frame.grid(row=4, column=0, sticky="nsew", padx=20, pady=8)
        self.grid_rowconfigure(4, weight=1)

        self.selected_var = ctk.StringVar(value="0" if self.candidates else "")

        for idx, candidate in enumerate(self.candidates):
            self._create_candidate_button(candidates_frame, idx, candidate)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, sticky="ew", padx=20, pady=20)
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            btn_frame,
            text="Skip This Row",
            width=120,
            height=36,
            fg_color=AMBER,
            hover_color="#E8962C",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._skip,
        ).grid(row=0, column=0, padx=8)

        ctk.CTkButton(
            btn_frame,
            text="Select & Continue",
            width=160,
            height=36,
            fg_color=GREEN,
            hover_color="#27A060",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._confirm,
        ).grid(row=0, column=2, padx=8)

    def _create_candidate_button(self, parent, idx: int, candidate: dict):
        row = ctk.CTkFrame(
            parent, fg_color=CARD2, border_width=2, border_color=BORDER, corner_radius=8
        )
        row.pack(fill="x", pady=6, padx=2)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkRadioButton(
            row,
            text="",
            variable=self.selected_var,
            value=str(idx),
            fg_color=ACCENT,
            hover_color=ACCENT,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=10)

        info_frame = ctk.CTkFrame(row, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", padx=10, pady=8)
        info_frame.grid_columnconfigure(1, weight=1)

        status = candidate.get("status", "")
        status_bit = f" | {status}" if status else ""
        ctk.CTkLabel(
            info_frame,
            text=f"{candidate.get('loan_id', '?')} | Start: {candidate.get('start_date', '')}{status_bit}",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        original = float(
            candidate.get("original_principal", candidate.get("principal", 0)) or 0
        )
        outstanding = float(
            candidate.get(
                "outstanding_principal",
                candidate.get("principal", 0),
            )
            or 0
        )
        rate = float(candidate.get("interest_rate", 0) or 0)
        expected = candidate.get("expected_interest")
        if expected is None:
            expected = (outstanding * rate) / 100

        ctk.CTkLabel(
            info_frame,
            text=f"Original: ₹{original:,.0f}",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=MUTED,
        ).grid(row=1, column=0, sticky="w", pady=2)

        ctk.CTkLabel(
            info_frame,
            text=f"Outstanding: ₹{outstanding:,.0f}",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=MUTED,
        ).grid(row=1, column=1, sticky="e")

        ctk.CTkLabel(
            info_frame,
            text=f"Interest Rate: {rate}% | Expected: ₹{float(expected):,.0f}/mo",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=GREEN,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)

        display = candidate.get("display_name")
        if display:
            ctk.CTkLabel(
                info_frame,
                text=display,
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=MUTED,
            ).grid(row=3, column=0, columnspan=2, sticky="w")

    def _confirm(self):
        try:
            idx = int(self.selected_var.get())
            self.selected_loan = self.candidates[idx]
            self.skip = False
            self.destroy()
        except (ValueError, IndexError, TypeError):
            messagebox.showerror("Error", "Please select a loan")

    def _skip(self):
        self.skip = True
        self.selected_loan = None
        self.destroy()

    def get_result(self) -> Tuple[Optional[dict], bool]:
        """Return (selected_loan, skip_flag)."""
        return self.selected_loan, self.skip
