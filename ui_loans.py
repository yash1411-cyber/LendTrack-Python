"""
ui_loans.py - Loan management: add/edit/delete loans per borrower.
"""

import customtkinter as ctk
from datetime import date
import database as db
from src.ui.theme import (
    BG, CARD, CARD2, TEXT, MUTED, BORDER, ACCENT, GREEN, RED, HOVER,
    font_body, font_table, font_overline, font_meta, CONTENT_PAD,
    S8, S12, S16, S24, S32, RADIUS_CARD, RADIUS_CONTROL, BTN_HEIGHT_COMPACT, ROW_PY,
    fmt_inr, primary_button, secondary_button, danger_button,
    table_header, table_cell, bind_row_hover, status_badge, setup_dialog,
    confirm_action, notify, explain_error, ellipsize,
)
from src.ui.date_picker import attach_date_picker


class LoansFrame(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._focus_borrower_id = None
        self._build_ui()

    def refresh(self):
        self._load_table()

    def focus_borrower(self, borrower_id=None):
        self._focus_borrower_id = borrower_id
        self._load_table()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=CONTENT_PAD, pady=(S16, 0))

        right_bar = ctk.CTkFrame(hdr, fg_color="transparent")
        right_bar.pack(side="right")

        self._status_var = ctk.StringVar(value="All")
        ctk.CTkSegmentedButton(
            right_bar,
            values=["All", "Active", "Closed"],
            variable=self._status_var,
            command=lambda _: self._load_table(),
            width=200,
            height=34,
            fg_color=CARD,
            selected_color=ACCENT,
            selected_hover_color=HOVER,
            unselected_color=CARD,
            text_color=TEXT,
        ).pack(side="left", padx=(0, S12))

        primary_button(right_bar, "+ New Loan", self._open_add_dialog, width=130).pack(
            side="left"
        )

        self._focus_bar = ctk.CTkFrame(self, fg_color="transparent")
        self._focus_bar.grid(row=1, column=0, sticky="ew", padx=CONTENT_PAD, pady=(S8, 0))
        self._focus_lbl = ctk.CTkLabel(
            self._focus_bar, text="", font=font_meta(), text_color=MUTED
        )
        self._focus_lbl.pack(side="left")
        self._clear_focus_btn = secondary_button(
            self._focus_bar, "Show all loans", self._clear_focus, width=130,
            height=BTN_HEIGHT_COMPACT, font=font_table(),
        )

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=CONTENT_PAD, pady=S16)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        cols = [
            "Loan ID", "Borrower", "Original", "Outstanding", "Rate", "Due Day",
            "Expected / Month", "Pending Interest", "Status", "Actions",
        ]
        weights = [1, 2, 2, 2, 1, 1, 2, 2, 1, 3]
        self._col_weights = weights

        tbl = ctk.CTkScrollableFrame(
            content, fg_color=CARD, corner_radius=RADIUS_CARD,
            border_width=1, border_color=BORDER,
        )
        tbl.grid(row=0, column=0, sticky="nsew")
        for ci, w in enumerate(weights):
            tbl.grid_columnconfigure(ci, weight=w)
        self._tbl = tbl

        for ci, col in enumerate(cols):
            table_header(tbl, col).grid(
                row=0, column=ci, padx=S8, pady=10, sticky="w"
            )
        self._row_widgets = []
        self._load_table()

    def _clear_focus(self):
        self._focus_borrower_id = None
        self._load_table()

    def _load_table(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()

        status = self._status_var.get() if hasattr(self, "_status_var") else "All"
        loans = db.get_all_loans(status_filter="" if status == "All" else status)

        focus_id = self._focus_borrower_id
        if focus_id:
            loans = [l for l in loans if l.get("borrower_id") == focus_id]
            name = ""
            if loans:
                name = loans[0].get("borrower_name") or ""
            else:
                b = db.get_borrower(focus_id)
                name = (b or {}).get("name") or focus_id
            self._focus_lbl.configure(text=f"Showing loans for {name}")
            self._clear_focus_btn.pack(side="right")
        else:
            self._focus_lbl.configure(text="")
            self._clear_focus_btn.pack_forget()

        n_cols = 10
        if not loans:
            if focus_id:
                text = "No loans for this borrower in the current filter."
            elif status == "Active":
                text = "No active loans."
            elif status == "Closed":
                text = "No closed loans."
            else:
                text = "No loans yet. Click '+ New Loan' to add one."
            lbl = ctk.CTkLabel(
                self._tbl, text=text, text_color=MUTED, font=font_body(),
            )
            lbl.grid(row=1, column=0, columnspan=n_cols, pady=S32)
            self._row_widgets.append(lbl)
            return

        for ri, l in enumerate(loans, start=1):
            bg = CARD if ri % 2 == 0 else CARD2
            rf = ctk.CTkFrame(self._tbl, fg_color=bg, corner_radius=0)
            rf.grid(row=ri, column=0, columnspan=n_cols, sticky="ew")
            for ci in range(n_cols):
                rf.grid_columnconfigure(ci, weight=self._col_weights[ci])
            bind_row_hover(rf, bg)
            self._row_widgets.append(rf)

            exp = db.expected_monthly_interest(l)
            pending = db.compute_pending_interest(l)
            pending_color = RED if pending > 0 else TEXT
            original = l.get("original_principal", l["principal"])
            outstanding = l.get("outstanding_principal", l["principal"])

            vals = [
                l["loan_id"], ellipsize(l["borrower_name"], 18),
                fmt_inr(original), fmt_inr(outstanding),
                f"{l['interest_rate']}%", str(l["due_day"]),
                fmt_inr(exp), fmt_inr(pending),
            ]
            colors = [MUTED, TEXT, TEXT, ACCENT, TEXT, TEXT, GREEN, pending_color]
            for ci, (v, col) in enumerate(zip(vals, colors)):
                table_cell(
                    rf, v, col, row=0, column=ci, padx=S8, pady=ROW_PY, sticky="w"
                )

            badge = status_badge(rf, l["status"])
            badge.grid(row=0, column=8, padx=S8, pady=4, sticky="w")

            af = ctk.CTkFrame(rf, fg_color="transparent")
            af.grid(row=0, column=9, padx=4, pady=4, sticky="e")
            primary_button(
                af, "Edit",
                lambda lid=l["loan_id"]: self._open_edit_dialog(lid),
                width=52, height=BTN_HEIGHT_COMPACT, font=font_table(),
            ).pack(side="left", padx=2)
            if l["status"] == "Active":
                secondary_button(
                    af, "Close Loan",
                    lambda lid=l["loan_id"]: self._close(lid),
                    width=88, height=BTN_HEIGHT_COMPACT, font=font_table(),
                ).pack(side="left", padx=2)
            else:
                secondary_button(
                    af, "Reopen Loan",
                    lambda lid=l["loan_id"]: self._reopen(lid),
                    width=96, height=BTN_HEIGHT_COMPACT, font=font_table(),
                ).pack(side="left", padx=2)
            danger_button(
                af, "Delete",
                lambda lid=l["loan_id"]: self._delete(lid),
                width=60, height=BTN_HEIGHT_COMPACT, font=font_table(),
            ).pack(side="left", padx=2)

    def _open_add_dialog(self):
        borrowers = db.get_all_borrowers()
        if not borrowers:
            notify(
                self,
                "Add a borrower first",
                "You need a borrower before you can create a loan.\n\n"
                "Open Borrowers and add one, then come back here.",
                tone="warning",
            )
            return
        LoanDialog(self, mode="add", on_save=self._load_table)

    def _open_edit_dialog(self, lid):
        loan = db.get_loan(lid)
        if loan:
            LoanDialog(self, mode="edit", loan=loan, on_save=self._load_table)

    def _close(self, lid):
        loan = db.get_loan(lid)
        if not loan:
            return
        name = loan.get("borrower_name") or loan.get("borrower_id")
        outstanding = loan.get("outstanding_principal", loan.get("principal"))
        if not confirm_action(
            self,
            "Close this loan?",
            f"Loan: {loan.get('loan_id')}\n"
            f"Borrower: {name}\n"
            f"Outstanding: {fmt_inr(outstanding)}\n\n"
            "Closing the loan changes its status to Closed. "
            "The loan history is preserved.\n\n"
            "This does not delete the loan, write a payment, or change Original Principal.",
            "Close Loan",
            geometry="500x340",
        ):
            return
        db.close_loan(lid)
        notify(
            self,
            "Loan closed.",
            "Status is now Closed. The loan history is unchanged.",
            tone="success",
            geometry="420x200",
        )
        self._load_table()

    def _reopen(self, lid):
        loan = db.get_loan(lid)
        if not loan:
            return
        name = loan.get("borrower_name") or loan.get("borrower_id")
        outstanding = loan.get("outstanding_principal", loan.get("principal"))
        if not confirm_action(
            self,
            "Reopen this loan?",
            f"Loan: {loan.get('loan_id')}\n"
            f"Borrower: {name}\n"
            f"Outstanding: {fmt_inr(outstanding)}\n\n"
            "Reopening changes the loan status back to Active. "
            "Existing loan history is preserved.",
            "Reopen Loan",
            geometry="500x320",
        ):
            return
        db.reopen_loan(lid)
        notify(
            self,
            "Loan reopened.",
            "Status is now Active. The loan history is unchanged.",
            tone="success",
            geometry="420x200",
        )
        self._load_table()

    def _delete(self, lid):
        loan = db.get_loan(lid)
        if not loan:
            return
        name = loan.get("borrower_name") or loan.get("borrower_id")
        original = loan.get("original_principal", loan.get("principal"))
        outstanding = loan.get("outstanding_principal", loan.get("principal"))
        if not confirm_action(
            self,
            "Delete this loan?",
            f"Borrower: {name}\n"
            f"Loan: {loan.get('loan_id')}\n"
            f"Original Principal: {fmt_inr(original)}\n"
            f"Outstanding: {fmt_inr(outstanding)}\n"
            f"Status: {loan.get('status') or '—'}\n\n"
            "This removes the loan only when it has no transaction history.\n"
            "If history exists, the loan cannot be deleted. Use Close Loan instead.",
            "Delete Loan",
            danger=True,
            geometry="500x380",
        ):
            return
        try:
            db.delete_loan(lid)
            notify(
                self,
                "Loan deleted.",
                "The loan was removed.",
                tone="success",
                geometry="400x180",
            )
            self._load_table()
        except ValueError as e:
            notify(
                self,
                "Loan could not be deleted.",
                explain_error(
                    e,
                    "This loan cannot be deleted because it has transaction history.",
                )
                + "\n\nUse Close Loan to finish it while keeping its records.",
                tone="error",
                geometry="480x260",
            )


class LoanDialog(ctk.CTkToplevel):
    def __init__(self, parent, mode="add", loan=None, on_save=None):
        super().__init__(parent)
        self._mode = mode
        self._loan = loan
        self._on_save = on_save
        self._borrower_id_map = {}

        setup_dialog(
            self,
            "New Loan" if mode == "add" else "Edit Loan",
            "520x540",
            resizable=True,
        )
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        p = {"padx": S16, "pady": 6}

        borrowers = db.get_all_borrowers()
        display_labels = []
        for b in borrowers:
            lbl = f"{b['borrower_id']}  {b['name']}"
            display_labels.append(lbl)
            self._borrower_id_map[lbl] = b["borrower_id"]

        ctk.CTkLabel(self, text="Borrower *", text_color=TEXT, font=font_body()
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
            width=300,
            corner_radius=RADIUS_CONTROL,
        )
        self._borrower_dd.grid(row=0, column=1, sticky="ew", **p)
        if self._mode == "edit":
            self._borrower_dd.configure(state="disabled")

        ctk.CTkLabel(self, text="Original Principal *", text_color=TEXT, font=font_body()
                     ).grid(row=1, column=0, sticky="ne", **p)
        pf = ctk.CTkFrame(self, fg_color="transparent")
        pf.grid(row=1, column=1, sticky="ew", **p)
        self._entries = {}
        e = ctk.CTkEntry(
            pf, placeholder_text="e.g. 100000",
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            height=36, corner_radius=RADIUS_CONTROL,
        )
        e.pack(fill="x")
        if self._mode == "edit":
            ctk.CTkLabel(
                pf,
                text="Changes to the original principal update this existing loan. "
                     "They do not create another Loan Given transaction.",
                font=font_overline(),
                text_color=MUTED,
                wraplength=360,
                justify="left",
                anchor="w",
            ).pack(fill="x", pady=(4, 0))
        self._entries["principal"] = e

        ctk.CTkLabel(
            self, text="Monthly Interest Rate (%) *", text_color=TEXT, font=font_body()
        ).grid(row=2, column=0, sticky="e", **p)
        e = ctk.CTkEntry(
            self, placeholder_text="e.g. 3.0",
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            height=36, corner_radius=RADIUS_CONTROL,
        )
        e.grid(row=2, column=1, sticky="ew", **p)
        self._entries["interest"] = e

        ctk.CTkLabel(self, text="Due Day (1–31) *", text_color=TEXT, font=font_body()
                     ).grid(row=3, column=0, sticky="e", **p)
        e = ctk.CTkEntry(
            self, placeholder_text="e.g. 5",
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            height=36, corner_radius=RADIUS_CONTROL,
        )
        e.grid(row=3, column=1, sticky="ew", **p)
        self._entries["due_day"] = e

        ctk.CTkLabel(self, text="Start Date", text_color=TEXT, font=font_body()
                     ).grid(row=4, column=0, sticky="ne", **p)
        df = ctk.CTkFrame(self, fg_color="transparent")
        df.grid(row=4, column=1, sticky="ew", **p)
        row = ctk.CTkFrame(df, fg_color="transparent")
        row.pack(fill="x")
        e = ctk.CTkEntry(
            row, placeholder_text=str(date.today()),
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            height=36, corner_radius=RADIUS_CONTROL,
        )
        attach_date_picker(self, e, button_parent=row)
        e.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            df, text="YYYY-MM-DD", font=font_overline(), text_color=MUTED, anchor="w"
        ).pack(fill="x", pady=(4, 0))
        self._entries["start_date"] = e

        ctk.CTkLabel(self, text="Status", text_color=TEXT, font=font_body()
                     ).grid(row=5, column=0, sticky="ne", **p)
        sf = ctk.CTkFrame(self, fg_color="transparent")
        sf.grid(row=5, column=1, sticky="ew", **p)
        self._status_var = ctk.StringVar(value="Active")
        ctk.CTkOptionMenu(
            sf, values=["Active", "Closed"],
            variable=self._status_var,
            fg_color=BG, button_color=ACCENT,
            text_color=TEXT, height=36, corner_radius=RADIUS_CONTROL,
        ).pack(fill="x")
        ctk.CTkLabel(
            sf,
            text="To close or reopen without changing other fields, use "
                 "Close Loan / Reopen Loan on the Loans screen.",
            font=font_overline(),
            text_color=MUTED,
            wraplength=320,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        self._preview = ctk.CTkLabel(
            self, text="", text_color=GREEN, font=font_meta(),
            justify="left", wraplength=360, anchor="w",
        )
        self._preview.grid(row=6, column=1, sticky="w", padx=S16, pady=(4, 0))
        self._entries["principal"].bind("<KeyRelease>", lambda _: self._update_preview())
        self._entries["interest"].bind("<KeyRelease>", lambda _: self._update_preview())

        if self._mode == "edit" and self._loan:
            self._entries["principal"].insert(
                0, str(self._loan.get("original_principal", self._loan["principal"]))
            )
            self._entries["interest"].insert(0, str(self._loan["interest_rate"]))
            self._entries["due_day"].insert(0, str(self._loan["due_day"]))
            self._entries["start_date"].insert(0, self._loan.get("start_date", "") or "")
            self._status_var.set(self._loan.get("status", "Active"))
            self._update_preview()

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=7, column=0, columnspan=2, pady=S16)
        secondary_button(bf, "Cancel", self.destroy, width=100).pack(side="left", padx=S8)
        primary_button(
            bf,
            "Save Changes" if self._mode == "edit" else "Create Loan",
            self._save,
            width=140,
        ).pack(side="right", padx=S8)

    def _update_preview(self):
        try:
            r = float(self._entries["interest"].get())
            if self._mode == "edit" and self._loan:
                loan = dict(self._loan)
                loan["interest_rate"] = r
                outstanding = loan.get("outstanding_principal", loan.get("principal"))
                exp = db.expected_monthly_interest(loan)
                self._preview.configure(
                    text=(
                        f"Outstanding: {fmt_inr(outstanding)}\n"
                        f"Monthly rate: {r:g}%\n"
                        f"Expected monthly interest: {fmt_inr(exp)}\n"
                        "Monthly interest on current outstanding."
                    )
                )
            else:
                p = float(self._entries["principal"].get())
                exp = db.expected_monthly_interest(
                    {"outstanding_principal": p, "interest_rate": r}
                )
                self._preview.configure(
                    text=(
                        f"Expected monthly interest: {fmt_inr(exp)}\n"
                        "On this amount until repayments are recorded."
                    )
                )
        except Exception:
            self._preview.configure(text="")

    def _save(self):
        try:
            principal = float(self._entries["principal"].get())
            assert principal > 0
        except Exception:
            notify(
                self, "Loan could not be saved.",
                "Original Principal must be a positive number.\nExample: 100000",
                tone="error",
            )
            return

        try:
            interest = float(self._entries["interest"].get())
            assert interest > 0
        except Exception:
            notify(
                self, "Loan could not be saved.",
                "Monthly Interest Rate must be a positive number.\nExample: 3.0",
                tone="error",
            )
            return

        try:
            due_day = int(self._entries["due_day"].get())
            assert 1 <= due_day <= 31
        except Exception:
            notify(
                self, "Loan could not be saved.",
                "Due day must be a whole number between 1 and 31.\nExample: 5",
                tone="error",
            )
            return

        start_date = self._entries["start_date"].get().strip()
        if not start_date:
            if self._mode == "edit" and self._loan:
                start_date = self._loan.get("start_date") or str(date.today())
            else:
                start_date = str(date.today())
        status = self._status_var.get()

        if self._mode == "add":
            selected_label = self._borrower_var.get()
            borrower_id = self._borrower_id_map.get(selected_label)
            if not borrower_id:
                notify(
                    self, "Loan could not be saved.",
                    "Select a borrower from the list.",
                    tone="error",
                )
                return
            try:
                lid = db.add_loan(borrower_id, principal, interest, due_day, start_date)
            except Exception as e:
                notify(
                    self, "Loan could not be saved.",
                    explain_error(e),
                    tone="error",
                )
                return
            saved = db.get_loan(lid) or {}
            outstanding = saved.get("outstanding_principal", principal)
            notify(
                self,
                "Loan created.",
                f"Outstanding: {fmt_inr(outstanding)}",
                tone="success",
            )
        else:
            try:
                prev_status = (self._loan or {}).get("status", "Active")
                if (
                    prev_status == "Closed"
                    and status == "Active"
                    and abs(float(self._loan.get("original_principal", self._loan["principal"])) - principal) < 1e-9
                    and float(self._loan["interest_rate"]) == float(interest)
                    and int(self._loan["due_day"]) == int(due_day)
                    and (self._loan.get("start_date") or "") == start_date
                ):
                    db.reopen_loan(self._loan["loan_id"])
                else:
                    db.update_loan(
                        self._loan["loan_id"], principal, interest,
                        due_day, start_date, status
                    )
                saved = db.get_loan(self._loan["loan_id"]) or {}
                outstanding = saved.get(
                    "outstanding_principal", saved.get("principal", principal)
                )
                notify(
                    self,
                    "Loan changes saved.",
                    f"Outstanding: {fmt_inr(outstanding)}",
                    tone="success",
                )
            except ValueError as e:
                notify(
                    self, "Loan could not be saved.",
                    explain_error(e),
                    tone="error",
                )
                return

        if self._on_save:
            self._on_save()
        self.destroy()
