"""
ui_dashboard.py - Dashboard screen with summary cards and due-today list.
"""

import customtkinter as ctk
from datetime import date
import database as db


# ── Colour tokens (shared palette) ─────────────────────────────────────────
BG       = "#0F1117"
SIDEBAR  = "#161B27"
CARD     = "#1E2435"
CARD2    = "#252B3B"
ACCENT   = "#4F8EF7"
GREEN    = "#34C77B"
AMBER    = "#F5A623"
RED      = "#E85D5D"
TEXT     = "#E8EBF2"
MUTED    = "#7A849E"
BORDER   = "#2C3347"


def _fmt(val: float) -> str:
    """Format a number as Indian-style currency string."""
    return f"₹{val:,.0f}"


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._build_ui()

    # ── public ──────────────────────────────────────────────────────────────
    def refresh(self):
        """Reload data from DB and update all widgets."""
        data = db.get_dashboard_summary()
        self._update_cards(data)
        self._update_due_table(data["due_today"])

    # ── private ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 0))
        ctk.CTkLabel(hdr, text="Dashboard",
                     font=ctk.CTkFont("Segoe UI", 24, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(hdr,
                     text=date.today().strftime("%A, %d %B %Y"),
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=MUTED).pack(side="right", pady=(4, 0))

        # ── Cards row ──────────────────────────────────────────────────────
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=20)
        cards_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        card_defs = [
            ("total_principal",         "Total Principal",       ACCENT, "🏦"),
            ("expected_monthly_interest","Expected Interest/Mo",  GREEN,  "📈"),
            ("interest_this_month",     "Interest Received",     GREEN,  "✅"),
            ("principal_this_month",    "Principal Received",    AMBER,  "💰"),
            ("total_overdue_interest",  "Overdue Interest",      RED,    "⚠️"),
        ]
        self._card_labels = {}
        for col, (key, title, color, icon) in enumerate(card_defs):
            card = ctk.CTkFrame(cards_frame, fg_color=CARD,
                                corner_radius=14,
                                border_width=1, border_color=BORDER)
            card.grid(row=0, column=col, padx=8, pady=4, sticky="ew")
            card.grid_columnconfigure(0, weight=1)

            # Icon + title row
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 4))
            ctk.CTkLabel(top, text=icon,
                         font=ctk.CTkFont("Segoe UI", 18),
                         text_color=color).pack(side="left")
            ctk.CTkLabel(top, text=title,
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color=MUTED).pack(side="left", padx=6)

            # Value
            val_lbl = ctk.CTkLabel(card, text="₹0",
                                   font=ctk.CTkFont("Segoe UI", 22, "bold"),
                                   text_color=color)
            val_lbl.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 14))
            self._card_labels[key] = val_lbl

        # ── Due Today section ──────────────────────────────────────────────
        sec = ctk.CTkFrame(self, fg_color="transparent")
        sec.grid(row=2, column=0, sticky="nsew", padx=28, pady=(0, 20))
        sec.grid_columnconfigure(0, weight=1)
        sec.grid_rowconfigure(1, weight=1)

        hdr2 = ctk.CTkFrame(sec, fg_color="transparent")
        hdr2.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(hdr2, text="🔔  Payments Due Today",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=TEXT).pack(side="left")

        # Table container
        tbl_frame = ctk.CTkScrollableFrame(sec, fg_color=CARD,
                                           corner_radius=14,
                                           border_width=1,
                                           border_color=BORDER)
        tbl_frame.grid(row=1, column=0, sticky="nsew")
        tbl_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self._due_table = tbl_frame

        # Column headers
        cols = ["Loan ID", "Borrower", "Principal", "Interest Rate", "Expected Interest"]
        for ci, col in enumerate(cols):
            ctk.CTkLabel(tbl_frame, text=col,
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=MUTED).grid(row=0, column=ci,
                                                padx=12, pady=8, sticky="w")

        self._due_rows_start = 1  # track dynamic rows
        self._due_row_widgets = []
        self.refresh()

    def _update_cards(self, data: dict):
        key_map = {
            "total_principal":          data["total_principal"],
            "expected_monthly_interest":data["expected_monthly_interest"],
            "interest_this_month":      data["interest_this_month"],
            "principal_this_month":     data["principal_this_month"],
            "total_overdue_interest":   data["total_overdue_interest"],
        }
        for key, val in key_map.items():
            if key in self._card_labels:
                self._card_labels[key].configure(text=_fmt(val))

    def _update_due_table(self, due_today: list):
        # Clear previous rows
        for w in self._due_row_widgets:
            w.destroy()
        self._due_row_widgets.clear()

        if not due_today:
            lbl = ctk.CTkLabel(self._due_table,
                               text="No payments due today 🎉",
                               font=ctk.CTkFont("Segoe UI", 13),
                               text_color=MUTED)
            lbl.grid(row=1, column=0, columnspan=5, pady=24)
            self._due_row_widgets.append(lbl)
            return

        for ri, loan in enumerate(due_today, start=1):
            row_color = CARD if ri % 2 == 0 else CARD2
            row_frame = ctk.CTkFrame(self._due_table, fg_color=row_color,
                                     corner_radius=0)
            row_frame.grid(row=ri, column=0, columnspan=5, sticky="ew")
            row_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
            self._due_row_widgets.append(row_frame)

            exp = db.expected_monthly_interest(loan)
            pending = db.compute_pending_interest(loan)
            pending_txt = f" (+₹{pending:,.0f} overdue)" if pending > 0 else ""

            vals = [
                loan["loan_id"],
                loan.get("borrower_name", loan["borrower_id"]),
                _fmt(loan["principal"]),
                f"{loan['interest_rate']}%",
                f"{_fmt(exp)}{pending_txt}",
            ]
            colors = [TEXT, TEXT, TEXT, TEXT, AMBER if pending > 0 else GREEN]
            for ci, (v, col) in enumerate(zip(vals, colors)):
                ctk.CTkLabel(row_frame, text=v,
                             font=ctk.CTkFont("Segoe UI", 12),
                             text_color=col).grid(row=0, column=ci,
                                                  padx=12, pady=8, sticky="w")
