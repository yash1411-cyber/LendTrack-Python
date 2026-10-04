"""
ui_transactions.py - Daily transaction entry, history, and Excel import
"""

import customtkinter as ctk
from tkinter import filedialog
from datetime import date, datetime
from src.ui.import_dialog import ImportDialog
import database as db
from src.ui.theme import (
    BG, CARD, CARD2, TEXT, MUTED, BORDER, ACCENT, GREEN, AMBER, RED,
    font_section, font_body, font_meta, font_overline, font_table, CONTENT_PAD,
    S8, S12, S16, S32, RADIUS_CARD, RADIUS_CONTROL, BTN_HEIGHT_COMPACT, ROW_PY,
    fmt_inr, primary_button, secondary_button, success_button, danger_button,
    table_header, table_cell, bind_row_hover, confirm_action, notify, explain_error,
    ellipsize,
)
from src.ui.date_picker import attach_date_picker

TXN_TYPES = ["Interest Received", "Principal Received"]
TXN_COLORS = {
    "Interest Received": GREEN,
    "Principal Received": ACCENT,
    "Loan Given": AMBER,
}
TYPE_HELP = {
    "Interest Received": "Records an interest payment. Does not reduce principal.",
    "Principal Received": "Records principal repayment and reduces outstanding principal.",
}
TYPE_BLURB = {
    "Interest Received": "Payment toward interest",
    "Principal Received": "Payment toward the loan principal",
    "Loan Given": "Original loan amount — not a payment entry",
}
SELECT_LOAN = "Select a loan…"
SELECT_BORROWER = "Select a borrower…"
FILTER_ALL = "All"


class TransactionsFrame(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._loan_map = {}
        self._all_txns = []
        self._build_ui()

    def refresh(self):
        self._populate_borrower_options()
        self._load_table()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        entry_panel = ctk.CTkFrame(
            self, fg_color=CARD, corner_radius=RADIUS_CARD,
            border_width=1, border_color=BORDER,
        )
        entry_panel.grid(row=0, column=0, sticky="ew", padx=CONTENT_PAD, pady=(S16, S12))
        entry_panel.grid_columnconfigure((1, 3, 5, 7), weight=1)

        hdr_frame = ctk.CTkFrame(entry_panel, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, columnspan=8, sticky="ew", padx=S16, pady=(12, 4))
        hdr_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            hdr_frame, text="Record Payment",
            font=font_section(), text_color=TEXT,
        ).grid(row=0, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")
        primary_button(
            btn_frame, "Export Template", self._export_import_template, width=150
        ).pack(side="left", padx=4)
        success_button(
            btn_frame, "Import Excel", self._open_import_dialog, width=140
        ).pack(side="left", padx=4)

        ctk.CTkLabel(
            entry_panel, text="Borrower", font=font_table(), text_color=MUTED
        ).grid(row=1, column=0, padx=(S16, 4), pady=(6, 4), sticky="e")
        self._borrower_var = ctk.StringVar(value=SELECT_BORROWER)
        self._borrower_dd = ctk.CTkOptionMenu(
            entry_panel, values=[SELECT_BORROWER], variable=self._borrower_var,
            fg_color=BG, button_color=ACCENT, text_color=TEXT,
            height=36, width=220, command=self._on_borrower_change,
            corner_radius=RADIUS_CONTROL, dynamic_resizing=False,
        )
        self._borrower_dd.grid(row=1, column=1, padx=4, pady=(6, 4), sticky="ew")

        ctk.CTkLabel(
            entry_panel, text="Loan", font=font_table(), text_color=MUTED
        ).grid(row=1, column=2, padx=(S12, 4), pady=(6, 4), sticky="e")
        self._loan_var = ctk.StringVar(value=SELECT_LOAN)
        self._loan_dd = ctk.CTkOptionMenu(
            entry_panel, values=[SELECT_LOAN], variable=self._loan_var,
            fg_color=BG, button_color=ACCENT, text_color=TEXT,
            height=36, width=360, command=self._on_loan_change,
            corner_radius=RADIUS_CONTROL, dynamic_resizing=False,
        )
        self._loan_dd.grid(
            row=1, column=3, columnspan=5, padx=(4, S16), pady=(6, 4), sticky="ew"
        )

        summary = ctk.CTkFrame(
            entry_panel, fg_color=CARD2, corner_radius=RADIUS_CONTROL,
            border_width=1, border_color=BORDER,
        )
        summary.grid(
            row=2, column=0, columnspan=8, sticky="ew", padx=S16, pady=(4, 8)
        )
        for i in range(5):
            summary.grid_columnconfigure(i, weight=1)
        self._summary_labels = {}
        for col, key, title in [
            (0, "loan", "Selected Loan"),
            (1, "original", "Original Principal"),
            (2, "outstanding", "Outstanding"),
            (3, "rate", "Monthly Interest Rate"),
            (4, "expected", "Expected Monthly Interest"),
        ]:
            cell = ctk.CTkFrame(summary, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew", padx=S12, pady=S8)
            ctk.CTkLabel(cell, text=title, font=font_overline(), text_color=MUTED).pack(
                anchor="w"
            )
            val = ctk.CTkLabel(cell, text="—", font=font_body(), text_color=TEXT, anchor="w")
            val.pack(anchor="w")
            self._summary_labels[key] = val

        self._closed_lbl = ctk.CTkLabel(
            summary, text="", font=font_meta(), text_color=RED, justify="left",
            wraplength=720, anchor="w",
        )
        self._closed_lbl.grid(
            row=1, column=0, columnspan=5, sticky="w", padx=S12, pady=(0, S8)
        )

        ctk.CTkLabel(
            entry_panel, text="Type", font=font_table(), text_color=MUTED
        ).grid(row=3, column=0, padx=(S16, 4), pady=4, sticky="e")
        self._type_var = ctk.StringVar(value=TXN_TYPES[0])
        ctk.CTkOptionMenu(
            entry_panel, values=TXN_TYPES, variable=self._type_var,
            fg_color=BG, button_color=ACCENT, text_color=TEXT,
            height=36, width=180, command=self._on_type_change,
            corner_radius=RADIUS_CONTROL, dynamic_resizing=False,
        ).grid(row=3, column=1, padx=4, pady=4, sticky="ew")

        ctk.CTkLabel(
            entry_panel, text="Amount", font=font_table(), text_color=MUTED
        ).grid(row=3, column=2, padx=(S12, 4), pady=4, sticky="e")
        amt_wrap = ctk.CTkFrame(entry_panel, fg_color="transparent")
        amt_wrap.grid(row=3, column=3, padx=4, pady=4, sticky="ew")
        self._amount_entry = ctk.CTkEntry(
            amt_wrap, placeholder_text="Enter the amount received",
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            height=36, corner_radius=RADIUS_CONTROL,
        )
        self._amount_entry.pack(fill="x")

        ctk.CTkLabel(
            entry_panel, text="Payment Date", font=font_table(), text_color=MUTED
        ).grid(row=3, column=4, padx=(S12, 4), pady=4, sticky="e")
        date_wrap = ctk.CTkFrame(entry_panel, fg_color="transparent")
        date_wrap.grid(row=3, column=5, columnspan=3, padx=(4, S16), pady=4, sticky="ew")
        row = ctk.CTkFrame(date_wrap, fg_color="transparent")
        row.pack(fill="x")
        self._date_entry = ctk.CTkEntry(
            row, fg_color=BG, border_color=BORDER, text_color=TEXT,
            height=36, corner_radius=RADIUS_CONTROL,
        )
        self._date_entry.insert(0, str(date.today()))
        attach_date_picker(self, self._date_entry, button_parent=row)
        self._date_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            date_wrap, text="YYYY-MM-DD", font=font_overline(), text_color=MUTED
        ).pack(anchor="w")

        ctk.CTkLabel(
            entry_panel, text="Notes (optional)", font=font_table(), text_color=MUTED
        ).grid(row=4, column=0, padx=(S16, 4), pady=4, sticky="e")
        self._notes_entry = ctk.CTkEntry(
            entry_panel, placeholder_text="Optional note",
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            height=36, corner_radius=RADIUS_CONTROL,
        )
        self._notes_entry.grid(
            row=4, column=1, columnspan=7, padx=(4, S16), pady=4, sticky="ew"
        )

        help_row = ctk.CTkFrame(entry_panel, fg_color="transparent")
        help_row.grid(row=5, column=0, columnspan=8, sticky="ew", padx=S16, pady=(0, 4))
        help_row.grid_columnconfigure(0, weight=1)
        self._type_help = ctk.CTkLabel(
            help_row, text=TYPE_HELP[TXN_TYPES[0]],
            font=font_meta(), text_color=MUTED, anchor="w",
            wraplength=520, justify="left",
        )
        self._type_help.grid(row=0, column=0, sticky="w")
        self._record_btn = success_button(
            help_row, "Record Payment", self._save, width=160
        )
        self._record_btn.grid(row=0, column=1, sticky="e")

        self._hint_lbl = ctk.CTkLabel(
            entry_panel, text="Select a loan to continue.",
            text_color=MUTED, font=font_meta(), justify="left", anchor="w",
            wraplength=480,
        )
        self._hint_lbl.grid(
            row=6, column=0, columnspan=5, sticky="w", padx=S16, pady=(0, 8)
        )
        self._status_lbl = ctk.CTkLabel(
            entry_panel, text="", text_color=GREEN, font=font_meta(),
            justify="right", anchor="e", wraplength=280,
        )
        self._status_lbl.grid(
            row=6, column=5, columnspan=3, sticky="e", padx=(4, S16), pady=(0, 8)
        )

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=CONTENT_PAD, pady=(0, S16))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            content, text="Payment history", font=font_section(), text_color=TEXT
        ).grid(row=0, column=0, sticky="w", pady=(0, S8))

        filters = ctk.CTkFrame(content, fg_color="transparent")
        filters.grid(row=1, column=0, sticky="ew", pady=(0, S8))
        ctk.CTkLabel(filters, text="Borrower", font=font_table(), text_color=MUTED).pack(
            side="left", padx=(0, 6)
        )
        self._filter_borrower = ctk.StringVar(value=FILTER_ALL)
        self._filter_borrower_dd = ctk.CTkOptionMenu(
            filters, values=[FILTER_ALL], variable=self._filter_borrower,
            fg_color=CARD, button_color=ACCENT, text_color=TEXT,
            height=32, width=180, command=lambda _: self._render_table(),
            corner_radius=RADIUS_CONTROL, dynamic_resizing=False,
        )
        self._filter_borrower_dd.pack(side="left", padx=(0, S12))
        ctk.CTkLabel(filters, text="Type", font=font_table(), text_color=MUTED).pack(
            side="left", padx=(0, 6)
        )
        self._filter_type = ctk.StringVar(value=FILTER_ALL)
        ctk.CTkOptionMenu(
            filters,
            values=[FILTER_ALL, "Interest Received", "Principal Received", "Loan Given"],
            variable=self._filter_type,
            fg_color=CARD, button_color=ACCENT, text_color=TEXT,
            height=32, width=170, command=lambda _: self._render_table(),
            corner_radius=RADIUS_CONTROL, dynamic_resizing=False,
        ).pack(side="left", padx=(0, S12))
        self._filter_search_entry = ctk.CTkEntry(
            filters,
            placeholder_text="Search history…",
            width=180, height=32, fg_color=CARD, border_color=BORDER, text_color=TEXT,
            corner_radius=RADIUS_CONTROL,
        )
        self._filter_search_entry.pack(side="left", padx=(0, S12))
        self._filter_search_entry.bind("<KeyRelease>", lambda _e: self._render_table())
        secondary_button(
            filters, "Clear filters", self._clear_filters, width=120,
            height=BTN_HEIGHT_COMPACT, font=font_table(),
        ).pack(side="left")

        cols = ["Date", "Borrower", "Loan", "Type", "Amount", "Notes", "Action"]
        weights = [1, 2, 1, 2, 1, 2, 1]
        self._hist_weights = weights
        tbl = ctk.CTkScrollableFrame(
            content, fg_color=CARD, corner_radius=RADIUS_CARD,
            border_width=1, border_color=BORDER,
        )
        tbl.grid(row=2, column=0, sticky="nsew")
        for ci, w in enumerate(weights):
            tbl.grid_columnconfigure(ci, weight=w)
        self._tbl = tbl
        for ci, col in enumerate(cols):
            table_header(tbl, col).grid(
                row=0, column=ci, padx=S12, pady=10, sticky="w"
            )
        self._row_widgets = []
        self.refresh()

    def _loan_label(self, loan: dict) -> str:
        original = loan.get("original_principal", loan.get("principal"))
        outstanding = loan.get("outstanding_principal", loan.get("principal"))
        status = loan.get("status") or ""
        return (
            f"{loan['loan_id']}  —  Original {fmt_inr(original)}"
            f"  —  Outstanding {fmt_inr(outstanding)}  —  {status}"
        )

    def _selected_borrower_id(self):
        val = self._borrower_var.get()
        if not val or val in (SELECT_BORROWER, "—"):
            return None
        return val.split("–")[0].strip()

    def _selected_loan(self):
        label = self._loan_var.get()
        if not label or label in (SELECT_LOAN, "—"):
            return None
        loan = self._loan_map.get(label)
        if loan:
            return loan
        lid = label.split("—")[0].split()[0].strip()
        return next((l for l in self._loan_map.values() if l.get("loan_id") == lid), None)

    def _clear_loan_context(self):
        self._loan_map = {}
        self._loan_dd.configure(values=[SELECT_LOAN])
        self._loan_var.set(SELECT_LOAN)
        self._apply_selected_loan(None)

    def _populate_borrower_options(self):
        borrowers = db.get_all_borrowers()
        opts = [f"{b['borrower_id']} – {b['name']}" for b in borrowers]
        prev = self._borrower_var.get()
        prev_loan = self._loan_var.get()
        self._borrower_dd.configure(values=opts or [SELECT_BORROWER])
        if prev in opts:
            self._on_borrower_change(prev, keep_loan_label=prev_loan)
        elif opts:
            self._borrower_var.set(opts[0])
            self._on_borrower_change(opts[0])
        else:
            self._borrower_var.set(SELECT_BORROWER)
            self._clear_loan_context()

    def _on_borrower_change(self, val: str, keep_loan_label: str = None):
        if val in (SELECT_BORROWER, "—", None, ""):
            self._clear_loan_context()
            return
        bid = val.split("–")[0].strip()
        loans = db.get_loans_for_borrower(bid)
        self._loan_map = {}
        opts = [SELECT_LOAN]
        for loan in loans:
            label = self._loan_label(loan)
            self._loan_map[label] = loan
            opts.append(label)
        self._loan_dd.configure(values=opts)
        if keep_loan_label and keep_loan_label in self._loan_map:
            self._loan_var.set(keep_loan_label)
            self._apply_selected_loan(self._loan_map[keep_loan_label])
        elif keep_loan_label:
            keep_id = keep_loan_label.split("—")[0].split()[0].strip()
            match = next(
                (lbl for lbl, ln in self._loan_map.items() if ln.get("loan_id") == keep_id),
                None,
            )
            if match:
                self._loan_var.set(match)
                self._apply_selected_loan(self._loan_map[match])
                return
            self._loan_var.set(SELECT_LOAN)
            self._apply_selected_loan(None)
        else:
            self._loan_var.set(SELECT_LOAN)
            self._apply_selected_loan(None)

    def _on_loan_change(self, val: str):
        if val in (SELECT_LOAN, "—", None, ""):
            self._apply_selected_loan(None)
            return
        self._apply_selected_loan(self._loan_map.get(val) or self._selected_loan())

    def _apply_selected_loan(self, loan):
        if not loan:
            for key in self._summary_labels:
                self._summary_labels[key].configure(text="—", text_color=TEXT)
            self._closed_lbl.configure(text="")
            self._hint_lbl.configure(
                text="Select a loan to continue.", text_color=MUTED
            )
            self._record_btn.configure(state="normal")
            return

        original = loan.get("original_principal", loan.get("principal"))
        outstanding = loan.get("outstanding_principal", loan.get("principal"))
        rate = loan.get("interest_rate")
        expected = db.expected_monthly_interest(loan)
        status = loan.get("status") or ""
        self._summary_labels["loan"].configure(
            text=f"{loan.get('loan_id', '—')}  ({status})"
        )
        self._summary_labels["original"].configure(text=fmt_inr(original))
        self._summary_labels["outstanding"].configure(text=fmt_inr(outstanding), text_color=ACCENT)
        self._summary_labels["rate"].configure(text=f"{rate}%")
        self._summary_labels["expected"].configure(text=fmt_inr(expected), text_color=GREEN)

        if status == "Closed":
            self._closed_lbl.configure(
                text="Closed loan — this loan is closed and cannot receive a payment. "
                     "Reopen the loan first to record a payment."
            )
            self._hint_lbl.configure(text="", text_color=MUTED)
            self._record_btn.configure(state="disabled")
        else:
            self._closed_lbl.configure(text="")
            pending = db.compute_pending_interest(loan)
            hint = f"Current expected monthly interest: {fmt_inr(expected)}"
            if pending > 0:
                hint += f"  •  Overdue interest: {fmt_inr(pending)}"
            self._hint_lbl.configure(text=hint, text_color=AMBER)
            self._record_btn.configure(state="normal")

    def _on_type_change(self, val: str):
        self._type_help.configure(text=TYPE_HELP.get(val, ""))

    def _filtered_txns(self):
        rows = list(self._all_txns)
        bfilter = self._filter_borrower.get()
        if bfilter and bfilter != FILTER_ALL:
            rows = [t for t in rows if t.get("borrower_name") == bfilter]
        tfilter = self._filter_type.get()
        if tfilter and tfilter != FILTER_ALL:
            rows = [t for t in rows if t.get("txn_type") == tfilter]
        q = (self._filter_search_entry.get() if hasattr(self, "_filter_search_entry") else "").strip().lower()
        if q:
            rows = [
                t for t in rows
                if q in (t.get("borrower_name") or "").lower()
                or q in (t.get("txn_type") or "").lower()
                or q in (t.get("loan_id") or "").lower()
                or q in (t.get("notes") or "").lower()
                or q in (t.get("txn_date") or "").lower()
            ]
        return rows

    def _filters_active(self) -> bool:
        return (
            self._filter_borrower.get() != FILTER_ALL
            or self._filter_type.get() != FILTER_ALL
            or bool((self._filter_search_entry.get() if hasattr(self, "_filter_search_entry") else "").strip())
        )

    def _clear_filters(self):
        self._filter_borrower.set(FILTER_ALL)
        self._filter_type.set(FILTER_ALL)
        if hasattr(self, "_filter_search_entry"):
            self._filter_search_entry.delete(0, "end")
        self._render_table()

    def _load_table(self):
        self._all_txns = db.get_all_transactions()
        names = sorted({t.get("borrower_name") for t in self._all_txns if t.get("borrower_name")})
        current = self._filter_borrower.get()
        values = [FILTER_ALL] + names
        self._filter_borrower_dd.configure(values=values)
        if current not in values:
            self._filter_borrower.set(FILTER_ALL)
        self._render_table()

    def _render_table(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()

        txns = self._filtered_txns()
        if not txns:
            if self._filters_active():
                text = "No payments match your filters."
            elif not self._all_txns:
                text = "No payments recorded yet."
            else:
                text = "No payments match your filters."
            lbl = ctk.CTkLabel(
                self._tbl, text=text, text_color=MUTED, font=font_body(),
            )
            lbl.grid(row=1, column=0, columnspan=7, pady=S32)
            self._row_widgets.append(lbl)
            return

        for ri, t in enumerate(txns, start=1):
            bg = CARD if ri % 2 == 0 else CARD2
            rf = ctk.CTkFrame(self._tbl, fg_color=bg, corner_radius=0)
            rf.grid(row=ri, column=0, columnspan=7, sticky="ew")
            for ci in range(7):
                rf.grid_columnconfigure(ci, weight=self._hist_weights[ci])
            bind_row_hover(rf, bg)
            self._row_widgets.append(rf)

            txn_type = t.get("txn_type") or ""
            is_given = txn_type == "Loan Given"
            col = TXN_COLORS.get(txn_type, TEXT)
            type_text = txn_type
            blurb = TYPE_BLURB.get(txn_type)
            if blurb:
                type_text = f"{txn_type}\n{blurb}"
            vals = [
                t.get("txn_date") or "—",
                ellipsize(t.get("borrower_name") or "—", 22),
                t.get("loan_id") or "—",
                type_text,
                fmt_inr(t.get("amount")),
                ellipsize(
                    (t.get("notes") or "—") if not is_given else (
                        (t.get("notes") or "This is the original loan amount. It is not a payment entry.")
                    ),
                    28,
                ),
            ]
            colors = [MUTED, TEXT, MUTED, col, col, MUTED]
            for ci, (v, c) in enumerate(zip(vals, colors)):
                table_cell(
                    rf, v, c, row=0, column=ci, padx=S12, pady=ROW_PY, sticky="w",
                    wraplength=160 if ci in (1, 3, 5) else 0,
                )
            if is_given:
                table_cell(
                    rf, "—", MUTED, row=0, column=6, padx=S8, pady=ROW_PY, sticky="w"
                )
            else:
                danger_button(
                    rf, "Delete",
                    lambda tid=t["id"]: self._delete_txn(tid),
                    width=64, height=BTN_HEIGHT_COMPACT, font=font_table(),
                ).grid(row=0, column=6, padx=S8, pady=4)

    def _save(self):
        try:
            amount = float(self._amount_entry.get())
            if amount <= 0:
                raise ValueError
        except Exception:
            notify(
                self, "Payment could not be recorded.",
                "Enter a valid positive amount.",
                tone="error",
            )
            return

        bid = self._selected_borrower_id()
        if not bid:
            notify(
                self, "Payment could not be recorded.",
                "Select a borrower.",
                tone="error",
            )
            return
        loan = self._selected_loan()
        if not loan:
            notify(
                self, "Payment could not be recorded.",
                "Select a loan to continue.",
                tone="error",
            )
            return
        if loan.get("status") == "Closed":
            notify(
                self,
                "Payment could not be recorded.",
                "This loan is closed and cannot receive a payment.\n"
                "Reopen the loan first to record a payment.",
                tone="error",
            )
            return

        lid = loan.get("loan_id")
        txn_date = self._date_entry.get().strip() or str(date.today())
        notes = self._notes_entry.get().strip()
        txn_type = self._type_var.get()
        if txn_type not in TXN_TYPES:
            notify(
                self, "Payment could not be recorded.",
                "Select Interest Received or Principal Received.",
                tone="error",
            )
            return

        try:
            db.add_transaction(bid, lid, txn_type, amount, txn_date, notes)
        except ValueError as e:
            notify(
                self,
                "Payment could not be recorded.",
                explain_error(e),
                tone="error",
            )
            return

        updated = db.get_loan(lid) if lid else None
        outstanding = (
            updated.get("outstanding_principal", updated.get("principal"))
            if updated else None
        )
        if txn_type == "Principal Received" and outstanding is not None:
            self._status_lbl.configure(
                text=f"Principal payment recorded.\nRemaining outstanding: {fmt_inr(outstanding)}"
            )
        else:
            self._status_lbl.configure(text="Interest payment recorded.")

        self._amount_entry.delete(0, "end")
        self._notes_entry.delete(0, "end")
        keep_label = self._loan_var.get()
        self._on_borrower_change(self._borrower_var.get(), keep_loan_label=keep_label)
        self._load_table()

    def _delete_txn(self, tid: int):
        txn = next((t for t in self._all_txns if t.get("id") == tid), None)
        if txn and txn.get("txn_type") == "Loan Given":
            notify(
                self,
                "Payment could not be deleted.",
                "Loan Given is the original loan amount. It is not a payment "
                "and cannot be deleted.",
                tone="error",
            )
            return
        if txn:
            body = (
                f"Borrower: {txn.get('borrower_name')}\n"
                f"Type: {txn.get('txn_type')}\n"
                f"Amount: {fmt_inr(txn.get('amount'))}\n"
                f"Date: {txn.get('txn_date')}\n\n"
                "This will remove the payment from the transaction history "
                "and recalculate the loan's outstanding amount."
            )
        else:
            body = (
                "This will remove the payment from the transaction history "
                "and recalculate the loan's outstanding amount."
            )
        if not confirm_action(
            self,
            "Delete this payment?",
            body,
            "Delete Payment",
            danger=True,
            geometry="500x360",
        ):
            return
        try:
            db.delete_transaction(tid)
            keep_label = self._loan_var.get()
            self._on_borrower_change(self._borrower_var.get(), keep_loan_label=keep_label)
            self._load_table()
            self._status_lbl.configure(text="Payment deleted.")
        except ValueError as e:
            notify(
                self,
                "Payment could not be deleted.",
                explain_error(e),
                tone="error",
            )

    def _open_import_dialog(self):
        dialog = ImportDialog(self, db.DB_PATH)
        self.after(500, self.refresh)

    def _export_import_template(self):
        try:
            from src.services.import_template_generator import ImportTemplateGenerator
            from src.services.loan_matcher import LoanMatcher

            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"LendTrack_Import_Template_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )

            if not file_path:
                return

            matcher = LoanMatcher(db.DB_PATH)
            generator = ImportTemplateGenerator(db.DB_PATH, file_path)

            if generator.generate(matcher):
                notify(
                    self,
                    "Template saved.",
                    f"Template saved:\n{file_path}",
                    tone="success",
                    geometry="480x220",
                )
            else:
                notify(
                    self, "Template could not be saved.",
                    "The template file could not be created.",
                    tone="error",
                )

        except Exception as e:
            notify(
                self, "Template could not be saved.",
                explain_error(e, "The template file could not be created."),
                tone="error",
            )
