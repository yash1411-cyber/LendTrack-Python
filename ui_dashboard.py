"""
ui_dashboard.py - Dashboard screen with summary cards and due-today list.
"""

import customtkinter as ctk
from datetime import date
import database as db
from src.ui.theme import (
    BG, CARD, CARD2, TEXT, MUTED, BORDER, ACCENT, GREEN, AMBER, RED,
    font_section, font_body, font_meta, font_table, CONTENT_PAD,
    S8, S12, S16, S24, RADIUS_CARD, BTN_HEIGHT_COMPACT, ROW_PY,
    fmt_inr, metric_card, table_header, table_cell, bind_row_hover,
    primary_button,
)

TXN_COLORS = {
    "Interest Received": GREEN,
    "Principal Received": ACCENT,
    "Loan Given": AMBER,
}


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, on_navigate=None, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._on_navigate = on_navigate
        self._build_ui()

    def refresh(self):
        data = db.get_dashboard_summary()
        loans = db.get_all_loans()
        self._update_empty_banner(loans)
        self._update_support_counts(loans)
        self._update_cards(data)
        self._update_due_table(data["due_today"])
        self._update_recent(db.get_all_transactions(limit=8))

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        self._scroll = scroll

        meta = ctk.CTkFrame(scroll, fg_color="transparent")
        meta.grid(row=0, column=0, sticky="ew", padx=CONTENT_PAD, pady=(S16, 0))
        self._support_lbl = ctk.CTkLabel(
            meta, text="", font=font_meta(), text_color=MUTED
        )
        self._support_lbl.pack(side="left")
        ctk.CTkLabel(
            meta,
            text=date.today().strftime("%A, %d %B %Y"),
            font=font_body(),
            text_color=MUTED,
        ).pack(side="right")

        self._empty_banner = ctk.CTkFrame(
            scroll, fg_color=CARD, corner_radius=RADIUS_CARD,
            border_width=1, border_color=BORDER,
        )
        self._empty_banner.grid(row=1, column=0, sticky="ew", padx=CONTENT_PAD, pady=(S12, 0))
        ctk.CTkLabel(
            self._empty_banner,
            text="No loans yet",
            font=font_section(),
            text_color=TEXT,
        ).pack(anchor="w", padx=S16, pady=(S12, 4))
        ctk.CTkLabel(
            self._empty_banner,
            text="Create your first loan to start tracking outstanding principal and interest.",
            font=font_body(),
            text_color=MUTED,
            wraplength=640,
            justify="left",
        ).pack(anchor="w", padx=S16, pady=(0, S12))

        cards = ctk.CTkFrame(scroll, fg_color="transparent")
        cards.grid(row=2, column=0, sticky="ew", padx=S16, pady=S16)
        cards.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._card_labels = {}

        outstanding, out_val = metric_card(
            cards,
            "Total Outstanding",
            value_color=ACCENT,
            prominent=True,
            caption="Outstanding principal on active loans",
        )
        outstanding.grid(row=0, column=0, columnspan=2, padx=S8, pady=S8, sticky="nsew")
        self._card_labels["total_principal"] = out_val

        expected, exp_val = metric_card(
            cards, "Expected Interest / Month", value_color=GREEN
        )
        expected.grid(row=0, column=2, padx=S8, pady=S8, sticky="nsew")
        self._card_labels["expected_monthly_interest"] = exp_val

        overdue, ov_val = metric_card(
            cards, "Overdue Interest", value_color=RED
        )
        overdue.grid(row=0, column=3, padx=S8, pady=S8, sticky="nsew")
        self._card_labels["total_overdue_interest"] = ov_val

        interest, int_val = metric_card(
            cards, "Interest Received — This Month", value_color=GREEN
        )
        interest.grid(row=1, column=0, columnspan=2, padx=S8, pady=S8, sticky="nsew")
        self._card_labels["interest_this_month"] = int_val

        principal, prin_val = metric_card(
            cards, "Principal Received — This Month", value_color=AMBER
        )
        principal.grid(row=1, column=2, columnspan=2, padx=S8, pady=S8, sticky="nsew")
        self._card_labels["principal_this_month"] = prin_val

        self._due_table = self._section(
            scroll, 3, "Due today",
            "Loans whose due day is today. Outstanding is the amount still owed.",
        )
        due_cols = [
            "Loan ID", "Borrower", "Outstanding", "Rate", "Expected Monthly Interest", ""
        ]
        for ci, col in enumerate(due_cols):
            self._due_table.grid_columnconfigure(ci, weight=1 if ci < 5 else 0)
            table_header(self._due_table, col).grid(
                row=0, column=ci, padx=S12, pady=10, sticky="w"
            )
        self._due_row_widgets = []

        self._recent_table = self._section(
            scroll, 4, "Recent activity",
            "Latest recorded transactions.",
        )
        recent_cols = ["Date", "Borrower", "Type", "Amount"]
        for ci, col in enumerate(recent_cols):
            self._recent_table.grid_columnconfigure(ci, weight=1)
            table_header(self._recent_table, col).grid(
                row=0, column=ci, padx=S12, pady=10, sticky="w"
            )
        self._recent_row_widgets = []

        self.refresh()

    def _section(self, parent, row, title, subtitle):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=row, column=0, sticky="ew", padx=CONTENT_PAD, pady=(0, S16))
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text=title, font=font_section(), text_color=TEXT).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(wrap, text=subtitle, font=font_meta(), text_color=MUTED).grid(
            row=1, column=0, sticky="w", pady=(0, S8)
        )
        body = ctk.CTkFrame(
            wrap, fg_color=CARD, corner_radius=RADIUS_CARD,
            border_width=1, border_color=BORDER,
        )
        body.grid(row=2, column=0, sticky="ew")
        return body

    def _update_empty_banner(self, loans: list):
        if loans:
            self._empty_banner.grid_remove()
        else:
            self._empty_banner.grid()

    def _update_support_counts(self, loans: list):
        if not loans:
            self._support_lbl.configure(text="")
            return
        active = sum(1 for l in loans if l.get("status") == "Active")
        closed = sum(1 for l in loans if l.get("status") == "Closed")
        self._support_lbl.configure(
            text=f"{active} active loan{'s' if active != 1 else ''}  ·  "
                 f"{closed} closed"
        )

    def _update_cards(self, data: dict):
        key_map = {
            "total_principal": data["total_principal"],
            "expected_monthly_interest": data["expected_monthly_interest"],
            "interest_this_month": data["interest_this_month"],
            "principal_this_month": data["principal_this_month"],
            "total_overdue_interest": data["total_overdue_interest"],
        }
        for key, val in key_map.items():
            if key in self._card_labels:
                self._card_labels[key].configure(text=fmt_inr(val))

    def _clear_rows(self, widgets: list):
        for w in widgets:
            w.destroy()
        widgets.clear()

    def _empty_row(self, table, widgets, text, columns):
        lbl = ctk.CTkLabel(table, text=text, font=font_body(), text_color=MUTED)
        lbl.grid(row=1, column=0, columnspan=columns, pady=S24)
        widgets.append(lbl)

    def _update_due_table(self, due_today: list):
        self._clear_rows(self._due_row_widgets)
        if not due_today:
            self._empty_row(
                self._due_table, self._due_row_widgets,
                "No payments due today.", 6,
            )
            return

        for ri, loan in enumerate(due_today, start=1):
            row_color = CARD if ri % 2 == 0 else CARD2
            row_frame = ctk.CTkFrame(self._due_table, fg_color=row_color, corner_radius=0)
            row_frame.grid(row=ri, column=0, columnspan=6, sticky="ew")
            for ci in range(6):
                row_frame.grid_columnconfigure(ci, weight=1 if ci < 5 else 0)
            bind_row_hover(row_frame, row_color)
            self._due_row_widgets.append(row_frame)

            exp = db.expected_monthly_interest(loan)
            pending = db.compute_pending_interest(loan)
            overdue_note = f"  (+{fmt_inr(pending)} overdue)" if pending > 0 else ""

            vals = [
                loan["loan_id"],
                loan.get("borrower_name", loan["borrower_id"]),
                fmt_inr(loan.get("outstanding_principal", loan["principal"])),
                f"{loan['interest_rate']}%",
                f"{fmt_inr(exp)}{overdue_note}",
            ]
            colors = [TEXT, TEXT, TEXT, TEXT, AMBER if pending > 0 else GREEN]
            for ci, (v, col) in enumerate(zip(vals, colors)):
                table_cell(
                    row_frame, v, col,
                    row=0, column=ci, padx=S12, pady=ROW_PY, sticky="w",
                    wraplength=160 if ci == 1 else 180 if ci == 4 else 0,
                )
            primary_button(
                row_frame,
                "Record Payment",
                self._go_record_payment,
                width=132,
                height=BTN_HEIGHT_COMPACT,
                font=font_table(),
            ).grid(row=0, column=5, padx=S8, pady=4, sticky="e")

    def _go_record_payment(self):
        if self._on_navigate:
            self._on_navigate("Transactions")

    def _update_recent(self, txns: list):
        self._clear_rows(self._recent_row_widgets)
        if not txns:
            self._empty_row(
                self._recent_table, self._recent_row_widgets,
                "No transactions recorded yet.", 4,
            )
            return

        for ri, t in enumerate(txns, start=1):
            row_color = CARD if ri % 2 == 0 else CARD2
            row_frame = ctk.CTkFrame(
                self._recent_table, fg_color=row_color, corner_radius=0
            )
            row_frame.grid(row=ri, column=0, columnspan=4, sticky="ew")
            for ci in range(4):
                row_frame.grid_columnconfigure(ci, weight=1)
            bind_row_hover(row_frame, row_color)
            self._recent_row_widgets.append(row_frame)

            txn_type = t.get("txn_type") or ""
            type_color = TXN_COLORS.get(txn_type, TEXT)
            vals = [
                t.get("txn_date") or "—",
                t.get("borrower_name") or "—",
                txn_type or "—",
                fmt_inr(t.get("amount")),
            ]
            colors = [MUTED, TEXT, type_color, type_color]
            for ci, (v, col) in enumerate(zip(vals, colors)):
                table_cell(
                    row_frame, v, col,
                    row=0, column=ci, padx=S12, pady=ROW_PY, sticky="w",
                    wraplength=180 if ci in (1, 2) else 0,
                )
