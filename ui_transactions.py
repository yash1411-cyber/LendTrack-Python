"""
ui_transactions.py - Daily transaction entry, history, and Excel import
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import date, datetime
import os
from src.ui.import_dialog import ImportDialog
import database as db

BG    = "#0F1117"
CARD  = "#1E2435"
CARD2 = "#252B3B"
ACCENT= "#4F8EF7"
GREEN = "#34C77B"
AMBER = "#F5A623"
RED   = "#E85D5D"
TEXT  = "#E8EBF2"
MUTED = "#7A849E"
BORDER= "#2C3347"

TXN_TYPES = ["Interest Received", "Principal Received", "Loan Given"]
TXN_COLORS = {"Interest Received": GREEN,
               "Principal Received": ACCENT,
               "Loan Given": AMBER}


def _fmt(v):
    return f"₹{v:,.0f}"


class TransactionsFrame(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._build_ui()

    def refresh(self):
        self._populate_borrower_options()
        self._load_table()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Quick Entry panel ─────────────────────────────────────────────
        entry_panel = ctk.CTkFrame(self, fg_color=CARD,
                                   corner_radius=16,
                                   border_width=1, border_color=BORDER)
        entry_panel.grid(row=0, column=0, sticky="ew", padx=28, pady=24)
        entry_panel.grid_columnconfigure((1, 3, 5, 7), weight=1)

        # Header row with title and import buttons
        hdr_frame = ctk.CTkFrame(entry_panel, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, columnspan=8, sticky="ew", padx=16, pady=(14, 4))
        hdr_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr_frame, text="Record Transaction",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=TEXT).grid(row=0, column=0, sticky="w")

        # Button frame (right side)
        btn_frame = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(btn_frame, text="📄 Export Template", width=140, height=34,
                      fg_color=ACCENT, hover_color="#3A72D8",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      command=self._export_import_template).pack(side="left", padx=4)

        ctk.CTkButton(btn_frame, text="📥 Import Excel", width=140, height=34,
                      fg_color=GREEN, hover_color="#27A060",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      command=self._open_import_dialog).pack(side="left", padx=4)

        # Borrower
        ctk.CTkLabel(entry_panel, text="Borrower",
                     font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED
                     ).grid(row=1, column=0, padx=(16, 4), pady=10, sticky="e")
        self._borrower_var = ctk.StringVar()
        self._borrower_dd = ctk.CTkOptionMenu(entry_panel, values=["—"],
                                              variable=self._borrower_var,
                                              fg_color=BG, button_color=ACCENT,
                                              text_color=TEXT, height=36, width=200,
                                              command=self._on_borrower_change)
        self._borrower_dd.grid(row=1, column=1, padx=4, pady=10, sticky="ew")

        # Loan
        ctk.CTkLabel(entry_panel, text="Loan",
                     font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED
                     ).grid(row=1, column=2, padx=(12, 4), pady=10, sticky="e")
        self._loan_var = ctk.StringVar()
        self._loan_dd = ctk.CTkOptionMenu(entry_panel, values=["—"],
                                          variable=self._loan_var,
                                          fg_color=BG, button_color=ACCENT,
                                          text_color=TEXT, height=36, width=160)
        self._loan_dd.grid(row=1, column=3, padx=4, pady=10, sticky="ew")

        # Type
        ctk.CTkLabel(entry_panel, text="Type",
                     font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED
                     ).grid(row=1, column=4, padx=(12, 4), pady=10, sticky="e")
        self._type_var = ctk.StringVar(value=TXN_TYPES[0])
        ctk.CTkOptionMenu(entry_panel, values=TXN_TYPES,
                          variable=self._type_var,
                          fg_color=BG, button_color=ACCENT,
                          text_color=TEXT, height=36, width=170
                          ).grid(row=1, column=5, padx=4, pady=10, sticky="ew")

        # Amount
        ctk.CTkLabel(entry_panel, text="Amount",
                     font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED
                     ).grid(row=1, column=6, padx=(12, 4), pady=10, sticky="e")
        self._amount_entry = ctk.CTkEntry(entry_panel, placeholder_text="₹ 0",
                                          fg_color=BG, border_color=BORDER,
                                          text_color=TEXT, height=36, width=130)
        self._amount_entry.grid(row=1, column=7, padx=4, pady=10, sticky="ew")

        # Date + Notes row
        ctk.CTkLabel(entry_panel, text="Date",
                     font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED
                     ).grid(row=2, column=0, padx=(16, 4), pady=(0, 12), sticky="e")
        self._date_entry = ctk.CTkEntry(entry_panel,
                                        fg_color=BG, border_color=BORDER,
                                        text_color=TEXT, height=36, width=140)
        self._date_entry.insert(0, str(date.today()))
        self._date_entry.grid(row=2, column=1, padx=4, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(entry_panel, text="Notes",
                     font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED
                     ).grid(row=2, column=2, padx=(12, 4), pady=(0, 12), sticky="e")
        self._notes_entry = ctk.CTkEntry(entry_panel, placeholder_text="Optional note",
                                         fg_color=BG, border_color=BORDER,
                                         text_color=TEXT, height=36)
        self._notes_entry.grid(row=2, column=3, columnspan=3, padx=4, pady=(0, 12), sticky="ew")

        ctk.CTkButton(entry_panel, text="Save Transaction", width=160, height=36,
                      fg_color=GREEN, hover_color="#27A060",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      command=self._save).grid(row=2, column=6, columnspan=2,
                                               padx=(4, 16), pady=(0, 12), sticky="e")

        # Interest hint label
        self._hint_lbl = ctk.CTkLabel(entry_panel, text="",
                                      text_color=AMBER,
                                      font=ctk.CTkFont("Segoe UI", 11))
        self._hint_lbl.grid(row=3, column=0, columnspan=8,
                             sticky="w", padx=16, pady=(0, 12))

        # ── History table ──────────────────────────────────────────────────
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 20))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(content, text="Recent Transactions",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=TEXT).grid(row=0, column=0, sticky="w", pady=(0, 8))

        cols    = ["Date", "Borrower", "Loan", "Type", "Amount", "Notes", "Del"]
        weights = [1, 2, 1, 2, 1, 2, 1]
        tbl = ctk.CTkScrollableFrame(content, fg_color=CARD,
                                     corner_radius=14,
                                     border_width=1, border_color=BORDER)
        tbl.grid(row=1, column=0, sticky="nsew")
        for ci, w in enumerate(weights):
            tbl.grid_columnconfigure(ci, weight=w)
        self._tbl = tbl

        for ci, col in enumerate(cols):
            ctk.CTkLabel(tbl, text=col,
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=MUTED).grid(row=0, column=ci,
                                                padx=10, pady=10, sticky="w")
        self._row_widgets = []
        self.refresh()

    # ── HELPER METHODS ─────────────────────────────────────────────────────

    def _populate_borrower_options(self):
        borrowers = db.get_all_borrowers()
        opts = [f"{b['borrower_id']} – {b['name']}" for b in borrowers]
        self._borrower_dd.configure(values=opts or ["—"])
        if opts:
            self._borrower_var.set(opts[0])
            self._on_borrower_change(opts[0])

    def _on_borrower_change(self, val: str):
        """Populate loan dropdown and show interest hint."""
        try:
            bid = val.split("–")[0].strip()
        except Exception:
            return
        loans = db.get_loans_for_borrower(bid)
        opts = [f"{l['loan_id']} (₹{l['principal']:,.0f})" for l in loans
                if l["status"] == "Active"]
        self._loan_dd.configure(values=opts or ["—"])
        if opts:
            self._loan_var.set(opts[0])
            l = loans[0]
            pending = db.compute_pending_interest(l)
            exp = db.expected_monthly_interest(l)
            hint = f"Expected this month: ₹{exp:,.0f}"
            if pending > 0:
                hint += f"  •  Overdue: ₹{pending:,.0f}"
            self._hint_lbl.configure(text=hint)
        else:
            self._loan_var.set("—")
            self._hint_lbl.configure(text="No active loans for this borrower.")

    def _load_table(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()

        txns = db.get_all_transactions()
        if not txns:
            lbl = ctk.CTkLabel(self._tbl, text="No transactions yet.",
                               text_color=MUTED, font=ctk.CTkFont("Segoe UI", 13))
            lbl.grid(row=1, column=0, columnspan=7, pady=32)
            self._row_widgets.append(lbl)
            return

        for ri, t in enumerate(txns, start=1):
            bg = CARD if ri % 2 == 0 else CARD2
            rf = ctk.CTkFrame(self._tbl, fg_color=bg, corner_radius=0)
            rf.grid(row=ri, column=0, columnspan=7, sticky="ew")
            for ci in range(7):
                rf.grid_columnconfigure(ci, weight=[1,2,1,2,1,2,1][ci])
            self._row_widgets.append(rf)

            col = TXN_COLORS.get(t["txn_type"], TEXT)
            vals   = [t["txn_date"], t["borrower_name"], t["loan_id"] or "—",
                      t["txn_type"], _fmt(t["amount"]), t["notes"] or "—"]
            colors = [MUTED, TEXT, MUTED, col, col, MUTED]
            for ci, (v, c) in enumerate(zip(vals, colors)):
                ctk.CTkLabel(rf, text=v,
                             font=ctk.CTkFont("Segoe UI", 12),
                             text_color=c).grid(row=0, column=ci,
                                                padx=10, pady=7, sticky="w")
            ctk.CTkButton(rf, text="✕", width=28, height=26,
                          fg_color="transparent", hover_color=RED,
                          text_color=MUTED,
                          font=ctk.CTkFont("Segoe UI", 12),
                          command=lambda tid=t["id"]: self._delete_txn(tid)
                          ).grid(row=0, column=6, padx=8, pady=4)

    # ── TRANSACTION OPERATIONS ─────────────────────────────────────────────

    def _save(self):
        try:
            amount = float(self._amount_entry.get())
            if amount <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Error", "Enter a valid positive amount.")
            return

        bval = self._borrower_var.get()
        lval = self._loan_var.get()
        if "—" in bval:
            messagebox.showerror("Error", "Select a borrower.")
            return
        bid = bval.split("–")[0].strip()
        lid = lval.split("(")[0].strip() if "—" not in lval else None

        txn_date = self._date_entry.get().strip() or str(date.today())
        notes    = self._notes_entry.get().strip()
        txn_type = self._type_var.get()

        db.add_transaction(bid, lid, txn_type, amount, txn_date, notes)
        messagebox.showinfo("Saved", f"Transaction saved: {txn_type} – ₹{amount:,.0f}")

        # Reset fields
        self._amount_entry.delete(0, "end")
        self._notes_entry.delete(0, "end")
        self._load_table()

    def _delete_txn(self, tid: int):
        if messagebox.askyesno("Delete", "Remove this transaction?"):
            db.delete_transaction(tid)
            self._load_table()

    # ── IMPORT OPERATIONS ──────────────────────────────────────────────────

    def _open_import_dialog(self):
        """Open import dialog for Excel transactions"""
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lendtrack.db")
        dialog = ImportDialog(self, db_path)
        self.after(500, self.refresh)

    def _export_import_template(self):
        """Export Excel import template with pre-filled dropdowns"""
        try:
            from src.services.import_template_generator import ImportTemplateGenerator
            from src.services.loan_matcher import LoanMatcher

            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lendtrack.db")

            # Ask where to save
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"LendTrack_Import_Template_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )

            if not file_path:
                return

            # Generate template
            matcher = LoanMatcher(db_path)
            generator = ImportTemplateGenerator(db_path, file_path)

            if generator.generate(matcher):
                messagebox.showinfo("Success", f"Template exported:\n{file_path}\n\nOpen it to import transactions.")
            else:
                messagebox.showerror("Error", "Could not generate template")

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")