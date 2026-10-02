"""
ui_loans.py - Loan management: add/edit/delete loans per borrower.
"""

import customtkinter as ctk
from tkinter import messagebox
from datetime import date
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


def _fmt(v):
    return f"Rs.{v:,.0f}"


class LoansFrame(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._build_ui()

    def refresh(self):
        self._load_table()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header row
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 0))

        ctk.CTkLabel(hdr, text="Loans",
                     font=ctk.CTkFont("Segoe UI", 24, "bold"),
                     text_color=TEXT).pack(side="left")

        right_bar = ctk.CTkFrame(hdr, fg_color="transparent")
        right_bar.pack(side="right")

        self._status_var = ctk.StringVar(value="All")
        ctk.CTkSegmentedButton(right_bar,
                               values=["All", "Active", "Closed"],
                               variable=self._status_var,
                               command=lambda _: self._load_table(),
                               width=200, height=34,
                               fg_color=CARD, selected_color=ACCENT,
                               selected_hover_color="#3A72D8",
                               unselected_color=CARD,
                               text_color=TEXT).pack(side="left", padx=(0, 12))

        ctk.CTkButton(right_bar, text="+ New Loan", width=130, height=34,
                      fg_color=ACCENT, hover_color="#3A72D8",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      command=self._open_add_dialog).pack(side="left")

        # Table area
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=28, pady=16)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        cols    = ["Loan ID", "Borrower", "Principal", "Rate", "Due Day",
                   "Exp. Interest", "Pending", "Status", "Actions"]
        weights = [1, 2, 2, 1, 1, 2, 2, 1, 1]

        tbl = ctk.CTkScrollableFrame(content, fg_color=CARD,
                                     corner_radius=14,
                                     border_width=1, border_color=BORDER)
        tbl.grid(row=0, column=0, sticky="nsew")
        for ci, w in enumerate(weights):
            tbl.grid_columnconfigure(ci, weight=w)
        self._tbl = tbl

        for ci, col in enumerate(cols):
            ctk.CTkLabel(tbl, text=col,
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=MUTED).grid(row=0, column=ci,
                                                padx=10, pady=10, sticky="w")
        self._row_widgets = []
        self._load_table()

    def _load_table(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()

        status = self._status_var.get() if hasattr(self, "_status_var") else "All"
        loans = db.get_all_loans(status_filter="" if status == "All" else status)

        if not loans:
            lbl = ctk.CTkLabel(self._tbl, text="No loans yet. Click '+ New Loan' to add one.",
                               text_color=MUTED,
                               font=ctk.CTkFont("Segoe UI", 13))
            lbl.grid(row=1, column=0, columnspan=9, pady=32)
            self._row_widgets.append(lbl)
            return

        for ri, l in enumerate(loans, start=1):
            bg = CARD if ri % 2 == 0 else CARD2
            rf = ctk.CTkFrame(self._tbl, fg_color=bg, corner_radius=0)
            rf.grid(row=ri, column=0, columnspan=9, sticky="ew")
            for ci in range(9):
                rf.grid_columnconfigure(ci, weight=[1,2,2,1,1,2,2,1,1][ci])
            self._row_widgets.append(rf)

            exp     = db.expected_monthly_interest(l)
            pending = db.compute_pending_interest(l) if l["status"] == "Active" else 0
            status_color  = GREEN if l["status"] == "Active" else MUTED
            pending_color = RED if pending > 0 else TEXT

            vals   = [l["loan_id"], l["borrower_name"], _fmt(l["principal"]),
                      f"{l['interest_rate']}%", str(l["due_day"]),
                      _fmt(exp), _fmt(pending), l["status"]]
            colors = [TEXT, TEXT, TEXT, TEXT, TEXT, GREEN, pending_color, status_color]
            for ci, (v, col) in enumerate(zip(vals, colors)):
                ctk.CTkLabel(rf, text=v,
                             font=ctk.CTkFont("Segoe UI", 12),
                             text_color=col).grid(row=0, column=ci,
                                                  padx=10, pady=8, sticky="w")
            af = ctk.CTkFrame(rf, fg_color="transparent")
            af.grid(row=0, column=8, padx=6, pady=4)
            ctk.CTkButton(af, text="Edit", width=52, height=26,
                          fg_color=ACCENT, hover_color="#3A72D8",
                          font=ctk.CTkFont("Segoe UI", 11),
                          command=lambda lid=l["loan_id"]: self._open_edit_dialog(lid)
                          ).pack(side="left", padx=2)
            ctk.CTkButton(af, text="Del", width=44, height=26,
                          fg_color=RED, hover_color="#C04040",
                          font=ctk.CTkFont("Segoe UI", 11),
                          command=lambda lid=l["loan_id"]: self._delete(lid)
                          ).pack(side="left", padx=2)

    def _open_add_dialog(self):
        borrowers = db.get_all_borrowers()
        if not borrowers:
            messagebox.showwarning(
                "No Borrowers Found",
                "You need to add a borrower first.\n\n"
                "Go to the Borrowers screen and click '+ Add Borrower', then come back here."
            )
            return
        LoanDialog(self, mode="add", on_save=self._load_table)

    def _open_edit_dialog(self, lid):
        loan = db.get_loan(lid)
        if loan:
            LoanDialog(self, mode="edit", loan=loan, on_save=self._load_table)

   

    def _delete(self, lid):
        if messagebox.askyesno("Delete Loan", f"Delete loan {lid}? This cannot be undone."):
            try:
                db.delete_loan(lid)
                messagebox.showinfo("Success", f"Loan {lid} deleted successfully")
                self._load_table()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete loan:\n{str(e)}")
# ── Loan Dialog ───────────────────────────────────────────────────────────────

class LoanDialog(ctk.CTkToplevel):
    def __init__(self, parent, mode="add", loan=None, on_save=None):
        super().__init__(parent)
        self._mode    = mode
        self._loan    = loan
        self._on_save = on_save
        # Maps display string -> actual borrower_id (no string splitting needed)
        self._borrower_id_map = {}

        self.title("New Loan" if mode == "add" else "Edit Loan")
        self.geometry("500x460")
        self.resizable(False, False)
        self.configure(fg_color=CARD)
        self.grab_set()
        self.lift()
        self.focus_force()
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        p = {"padx": 20, "pady": 8}

        # ── Borrower selector ─────────────────────────────────────────────
        borrowers = db.get_all_borrowers()
        display_labels = []
        for b in borrowers:
            lbl = f"{b['borrower_id']}  {b['name']}"
            display_labels.append(lbl)
            self._borrower_id_map[lbl] = b["borrower_id"]

        ctk.CTkLabel(self, text="Borrower *", text_color=TEXT,
                     font=ctk.CTkFont("Segoe UI", 12)
                     ).grid(row=0, column=0, sticky="e", **p)

        self._borrower_var = ctk.StringVar()

        if self._mode == "edit" and self._loan:
            for lbl, bid in self._borrower_id_map.items():
                if bid == self._loan["borrower_id"]:
                    self._borrower_var.set(lbl)
                    break
        elif display_labels:
            self._borrower_var.set(display_labels[0])

        self._borrower_dd = ctk.CTkOptionMenu(
            self,
            values=display_labels,
            variable=self._borrower_var,
            fg_color=BG,
            button_color=ACCENT,
            text_color=TEXT,
            height=36,
            dynamic_resizing=False,
            width=300
        )
        self._borrower_dd.grid(row=0, column=1, sticky="ew", **p)
        if self._mode == "edit":
            self._borrower_dd.configure(state="disabled")

        # ── Input fields ──────────────────────────────────────────────────
        fields = [
            ("Principal Amount *", "principal", "e.g. 100000"),
            ("Interest Rate % *",  "interest",  "e.g. 3.0"),
            ("Due Day (1-31) *",   "due_day",   "e.g. 5"),
            ("Start Date",         "start_date", str(date.today())),
        ]
        self._entries = {}
        for ri, (lbl_text, key, ph) in enumerate(fields, start=1):
            ctk.CTkLabel(self, text=lbl_text, text_color=TEXT,
                         font=ctk.CTkFont("Segoe UI", 12)
                         ).grid(row=ri, column=0, sticky="e", **p)
            e = ctk.CTkEntry(self, placeholder_text=ph,
                             fg_color=BG, border_color=BORDER,
                             text_color=TEXT, height=36)
            e.grid(row=ri, column=1, sticky="ew", **p)
            self._entries[key] = e

        # ── Status ────────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Status", text_color=TEXT,
                     font=ctk.CTkFont("Segoe UI", 12)
                     ).grid(row=5, column=0, sticky="e", **p)
        self._status_var = ctk.StringVar(value="Active")
        ctk.CTkOptionMenu(self, values=["Active", "Closed"],
                          variable=self._status_var,
                          fg_color=BG, button_color=ACCENT,
                          text_color=TEXT, height=36
                          ).grid(row=5, column=1, sticky="ew", **p)

        # ── Interest preview label ─────────────────────────────────────────
        self._preview = ctk.CTkLabel(self, text="",
                                     text_color=GREEN,
                                     font=ctk.CTkFont("Segoe UI", 12))
        self._preview.grid(row=6, column=1, sticky="w", padx=20)
        self._entries["principal"].bind("<KeyRelease>", lambda _: self._update_preview())
        self._entries["interest"].bind("<KeyRelease>",  lambda _: self._update_preview())

        # Pre-fill when editing
        if self._mode == "edit" and self._loan:
            self._entries["principal"].insert(0, str(self._loan["principal"]))
            self._entries["interest"].insert(0,  str(self._loan["interest_rate"]))
            self._entries["due_day"].insert(0,   str(self._loan["due_day"]))
            self._entries["start_date"].insert(0, self._loan.get("start_date", "") or "")
            self._status_var.set(self._loan.get("status", "Active"))
            self._update_preview()

        # ── Buttons ───────────────────────────────────────────────────────
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=7, column=0, columnspan=2, pady=20)
        ctk.CTkButton(bf, text="Save Loan", width=130, height=38,
                      fg_color=ACCENT, hover_color="#3A72D8",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(bf, text="Cancel", width=100, height=38,
                      fg_color=CARD2, hover_color="#333B52",
                      font=ctk.CTkFont("Segoe UI", 13),
                      text_color=TEXT,
                      command=self.destroy).pack(side="left", padx=8)

    def _update_preview(self):
        try:
            p   = float(self._entries["principal"].get())
            r   = float(self._entries["interest"].get())
            exp = round(p * r / 100, 2)
            self._preview.configure(text=f"Monthly interest will be: Rs.{exp:,.0f}")
        except Exception:
            self._preview.configure(text="")

    def _save(self):
        # Validate principal
        try:
            principal = float(self._entries["principal"].get())
            assert principal > 0
        except Exception:
            messagebox.showerror("Invalid Input",
                                 "Principal amount must be a positive number.\nExample: 100000")
            return

        # Validate interest rate
        try:
            interest = float(self._entries["interest"].get())
            assert interest > 0
        except Exception:
            messagebox.showerror("Invalid Input",
                                 "Interest rate must be a positive number.\nExample: 3.0")
            return

        # Validate due day
        try:
            due_day = int(self._entries["due_day"].get())
            assert 1 <= due_day <= 31
        except Exception:
            messagebox.showerror("Invalid Input",
                                 "Due day must be a whole number between 1 and 31.\nExample: 5")
            return

        start_date = self._entries["start_date"].get().strip() or str(date.today())
        status     = self._status_var.get()

        if self._mode == "add":
            selected_label = self._borrower_var.get()
            borrower_id    = self._borrower_id_map.get(selected_label)
            if not borrower_id:
                messagebox.showerror("Error", "Please select a valid borrower from the dropdown.")
                return
            lid = db.add_loan(borrower_id, principal, interest, due_day, start_date)
            messagebox.showinfo(
                "Loan Added",
                f"Loan saved successfully!\n\n"
                f"Loan ID     : {lid}\n"
                f"Borrower    : {selected_label}\n"
                f"Principal   : Rs.{principal:,.0f}\n"
                f"Rate        : {interest}% / month\n"
                f"Monthly Int : Rs.{principal*interest/100:,.0f}"
            )
        else:
            db.update_loan(self._loan["loan_id"], principal, interest,
                           due_day, start_date, status)
            messagebox.showinfo("Updated", "Loan updated successfully!")

        if self._on_save:
            self._on_save()
        self.destroy()
