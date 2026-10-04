"""
Ambiguous Match Dialog - Resolve multiple loan matches interactively.

Stage 7: requires an explicit Select or Skip — never silent assignment.
"""

from __future__ import annotations

from typing import Optional, Tuple

import customtkinter as ctk
from src.ui.theme import (
    BG, CARD, CARD2, TEXT, MUTED, BORDER, ACCENT, GREEN, AMBER,
    font_section, font_body_bold, font_meta, font_overline, font_meta_bold,
    RADIUS_CARD, S8, S12, S16,
    fmt_inr, secondary_button, success_button, notify, clamp_dialog_size, place_dialog,
)


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
        possible_name_match: bool = False,
    ):
        super().__init__(parent)
        self.possible_name_match = possible_name_match or (
            "Possible match" in (reason or "")
        )
        if self.possible_name_match:
            self.title("Possible Match Found — Confirm")
        else:
            self.title("Multiple possible matches")
        self.geometry(clamp_dialog_size(680, 480, parent))
        self.minsize(560, 400)
        self.resizable(True, True)
        self.configure(fg_color=BG)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._skip)
        self.bind("<Escape>", lambda _e: self._skip())
        place_dialog(self, parent)

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
        self.grid_rowconfigure(4, weight=1)

        if self.possible_name_match:
            title = "Possible match — please confirm"
        elif self.due_day is not None:
            title = f"Multiple possible matches for {self.borrower_name}"
        else:
            title = f"Multiple possible matches for {self.borrower_name}"

        ctk.CTkLabel(
            self,
            text=title,
            font=font_section(),
            text_color=TEXT,
            wraplength=600,
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=S16, pady=(S16, 4))

        explain = (
            "Multiple possible matches were found. Select the correct loan "
            "or skip this row. Closing this window skips the row — it does "
            "not choose a match."
        )
        if self.possible_name_match:
            explain = (
                f"Excel name: {self.borrower_name}. "
                "No exact match was found. Confirm a possible existing loan "
                "or skip this row. Closing this window skips the row."
            )
        ctk.CTkLabel(
            self,
            text=explain,
            font=font_meta(),
            text_color=AMBER,
            wraplength=600,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=S16, pady=(0, S8))

        info_frame = ctk.CTkFrame(
            self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=RADIUS_CARD
        )
        info_frame.grid(row=2, column=0, sticky="ew", padx=S16, pady=(0, 10), ipady=S8)

        info_text = (
            f"Date: {self.txn_data.get('date')}  |  "
            f"Type: {self.txn_data.get('txn_type')}  |  "
            f"Amount: {fmt_inr(self.txn_data.get('amount') or 0)}"
        )
        if self.due_day is not None:
            info_text += f"  |  Due day: {self.due_day}"
        ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=font_meta(),
            text_color=MUTED,
            wraplength=600,
            justify="left",
        ).pack(anchor="w", padx=S12, pady=4)

        ctk.CTkLabel(
            self,
            text="No loan is selected yet. Choose one, or skip this row.",
            font=font_body_bold(),
            text_color=TEXT,
        ).grid(row=3, column=0, sticky="nw", padx=S16, pady=(0, 6))

        candidates_frame = ctk.CTkScrollableFrame(
            self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=RADIUS_CARD
        )
        candidates_frame.grid(row=4, column=0, sticky="nsew", padx=S16, pady=S8)

        self.selected_var = ctk.StringVar(value="")

        if not self.candidates:
            ctk.CTkLabel(
                candidates_frame,
                text="No existing loans were suggested for this row.",
                font=font_meta(),
                text_color=MUTED,
            ).pack(anchor="w", padx=S8, pady=S8)
        else:
            for idx, candidate in enumerate(self.candidates):
                self._create_candidate_button(candidates_frame, idx, candidate)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, sticky="ew", padx=S16, pady=S16)
        btn_frame.grid_columnconfigure(1, weight=1)

        secondary_button(btn_frame, "Skip This Row", self._skip, width=140).grid(
            row=0, column=0, padx=S8
        )
        success_button(btn_frame, "Select", self._confirm, width=140).grid(
            row=0, column=2, padx=S8
        )

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

        name = candidate.get("borrower_name") or ""
        bid = candidate.get("borrower_id") or ""
        lid = candidate.get("loan_id") or "?"
        header = lid
        if name:
            header = f"{name}  •  {lid}"
        if bid:
            header = f"{header}  •  {bid}"
        phone = candidate.get("phone") or candidate.get("borrower_phone") or ""
        if phone:
            header = f"{header}  •  {phone}"

        ctk.CTkLabel(
            info_frame,
            text=header,
            font=font_meta_bold(),
            text_color=TEXT,
            wraplength=520,
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        bits = []
        status = candidate.get("status")
        if status:
            bits.append(str(status))
        due = candidate.get("due_day")
        if due not in (None, ""):
            bits.append(f"Due day {due}")
        start = candidate.get("start_date")
        if start:
            bits.append(f"Start {start}")
        if bits:
            ctk.CTkLabel(
                info_frame,
                text="  |  ".join(bits),
                font=font_overline(),
                text_color=MUTED,
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        original = candidate.get("original_principal", candidate.get("principal"))
        outstanding = candidate.get("outstanding_principal", candidate.get("principal"))
        ctk.CTkLabel(
            info_frame,
            text=f"Original Principal: {fmt_inr(original)}",
            font=font_overline(),
            text_color=MUTED,
        ).grid(row=2, column=0, sticky="w", pady=2)
        ctk.CTkLabel(
            info_frame,
            text=f"Outstanding: {fmt_inr(outstanding)}",
            font=font_overline(),
            text_color=MUTED,
        ).grid(row=2, column=1, sticky="e")

        rate = candidate.get("interest_rate")
        expected = candidate.get("expected_interest")
        extra = []
        if rate not in (None, ""):
            extra.append(f"Monthly Interest Rate: {rate}%")
        if expected is not None:
            extra.append(f"Expected: {fmt_inr(expected)}/mo")
        if extra:
            ctk.CTkLabel(
                info_frame,
                text="  |  ".join(extra),
                font=font_overline(),
                text_color=GREEN,
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=2)

        display = candidate.get("display_name")
        if display:
            ctk.CTkLabel(
                info_frame,
                text=display,
                font=font_overline(),
                text_color=MUTED,
                wraplength=520,
                justify="left",
                anchor="w",
            ).grid(row=4, column=0, columnspan=2, sticky="w")

    def _confirm(self):
        raw = (self.selected_var.get() or "").strip()
        if raw == "":
            notify(
                self,
                "Select a loan",
                "No loan is selected. Choose a match, or skip this row.",
                tone="error",
            )
            return
        try:
            idx = int(raw)
            self.selected_loan = self.candidates[idx]
            self.skip = False
            self.destroy()
        except (ValueError, IndexError, TypeError):
            notify(
                self,
                "Select a loan",
                "No loan is selected. Choose a match, or skip this row.",
                tone="error",
            )

    def _skip(self):
        self.skip = True
        self.selected_loan = None
        self.destroy()

    def get_result(self) -> Tuple[Optional[dict], bool]:
        """Return (selected_loan, skip_flag)."""
        return self.selected_loan, self.skip
