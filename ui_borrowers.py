"""
ui_borrowers.py - Add / Edit / Delete / Search borrowers.
"""

import customtkinter as ctk
import database as db
from src.ui.theme import (
    BG, CARD, CARD2, TEXT, MUTED, BORDER, ACCENT,
    font_body, font_table, CONTENT_PAD, S8, S12, S16, S24, S32,
    RADIUS_CARD, RADIUS_CONTROL, BTN_HEIGHT_COMPACT, ROW_PY,
    fmt_inr, primary_button, secondary_button, danger_button,
    table_header, table_cell, bind_row_hover, setup_dialog, confirm_action,
    notify, explain_error, ellipsize,
)


class BorrowersFrame(ctk.CTkFrame):
    def __init__(self, parent, on_navigate=None, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._on_navigate = on_navigate
        self._selected_id = None
        self._build_ui()

    def refresh(self):
        self._load_table()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=CONTENT_PAD, pady=(S16, 0))
        primary_button(hdr, "+ Add Borrower", self._open_add_dialog, width=150).pack(
            side="right"
        )

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=CONTENT_PAD, pady=S16)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        sb = ctk.CTkFrame(content, fg_color="transparent")
        sb.grid(row=0, column=0, sticky="ew", pady=(0, S12))
        self._search_var = None
        self._search = ctk.CTkEntry(
            sb,
            placeholder_text="Search borrowers…",
            width=320,
            height=36,
            fg_color=CARD,
            border_color=BORDER,
            text_color=TEXT,
            corner_radius=RADIUS_CONTROL,
        )
        self._search.pack(side="left")
        self._search.bind("<KeyRelease>", lambda _e: self._load_table())

        cols = [
            "ID", "Name", "Phone", "Outstanding", "Active Loans",
            "Notes", "Created", "Actions",
        ]
        col_weights = [1, 2, 2, 2, 1, 2, 1, 2]

        tbl = ctk.CTkScrollableFrame(
            content, fg_color=CARD, corner_radius=RADIUS_CARD,
            border_width=1, border_color=BORDER,
        )
        tbl.grid(row=1, column=0, sticky="nsew")
        for ci, w in enumerate(col_weights):
            tbl.grid_columnconfigure(ci, weight=w)
        self._tbl = tbl
        self._col_weights = col_weights

        for ci, col in enumerate(cols):
            table_header(tbl, col).grid(
                row=0, column=ci, padx=S8, pady=10, sticky="w"
            )
        self._row_widgets = []
        self._load_table()

    def _borrower_summaries(self) -> dict:
        """UI aggregation from existing loan records. No new accounting."""
        summary = {}
        for loan in db.get_all_loans():
            bid = loan.get("borrower_id")
            if not bid:
                continue
            row = summary.setdefault(bid, {"outstanding": 0.0, "active": 0})
            if loan.get("status") == "Active":
                row["active"] += 1
                row["outstanding"] += float(
                    loan.get("outstanding_principal", loan.get("principal") or 0) or 0
                )
        return summary

    def _load_table(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()

        q = self._search.get() if hasattr(self, "_search") else ""
        rows = db.get_all_borrowers(search=q)
        n_cols = 8

        if not rows:
            if (q or "").strip():
                text = "No borrowers match your search."
            else:
                text = "No borrowers yet\nAdd a borrower to start tracking loans."
            lbl = ctk.CTkLabel(
                self._tbl, text=text, text_color=MUTED, font=font_body(),
                justify="left",
            )
            lbl.grid(row=1, column=0, columnspan=n_cols, pady=S32)
            self._row_widgets.append(lbl)
            return

        summaries = self._borrower_summaries()

        for ri, b in enumerate(rows, start=1):
            bg = CARD if ri % 2 == 0 else CARD2
            rf = ctk.CTkFrame(self._tbl, fg_color=bg, corner_radius=0)
            rf.grid(row=ri, column=0, columnspan=n_cols, sticky="ew")
            for ci in range(n_cols):
                rf.grid_columnconfigure(ci, weight=self._col_weights[ci])
            bind_row_hover(rf, bg)
            self._row_widgets.append(rf)

            stats = summaries.get(b["borrower_id"], {"outstanding": 0.0, "active": 0})
            created = (b.get("created_at") or "")[:10] or "—"
            notes = ellipsize(b["notes"] or "", 18)
            vals = [
                b["borrower_id"],
                ellipsize(b["name"], 18),
                ellipsize(b["phone"] or "—", 12),
                fmt_inr(stats["outstanding"]),
                str(stats["active"]),
                notes or "—",
                created,
            ]
            colors = [MUTED, TEXT, MUTED, ACCENT, TEXT, MUTED, MUTED]
            for ci, (v, col) in enumerate(zip(vals, colors)):
                table_cell(
                    rf, v, col, row=0, column=ci, padx=S8, pady=ROW_PY, sticky="w"
                )

            btn_frame = ctk.CTkFrame(rf, fg_color="transparent")
            btn_frame.grid(row=0, column=7, padx=S8, pady=4, sticky="e")
            secondary_button(
                btn_frame, "View Loans",
                lambda bid=b["borrower_id"]: self._view_loans(bid),
                width=88, height=BTN_HEIGHT_COMPACT, font=font_table(),
            ).pack(side="left", padx=2)
            primary_button(
                btn_frame, "Edit",
                lambda bid=b["borrower_id"]: self._open_edit_dialog(bid),
                width=52, height=BTN_HEIGHT_COMPACT, font=font_table(),
            ).pack(side="left", padx=2)
            danger_button(
                btn_frame, "Delete",
                lambda bid=b["borrower_id"]: self._delete(bid),
                width=60, height=BTN_HEIGHT_COMPACT, font=font_table(),
            ).pack(side="left", padx=2)

    def _view_loans(self, bid: str):
        if self._on_navigate:
            self._on_navigate("Loans", borrower_id=bid)

    def _open_add_dialog(self):
        BorrowerDialog(self, mode="add", on_save=self._load_table)

    def _open_edit_dialog(self, bid: str):
        b = db.get_borrower(bid)
        if b:
            BorrowerDialog(self, mode="edit", borrower=b, on_save=self._load_table)

    def _delete(self, bid: str):
        b = db.get_borrower(bid)
        if not b:
            return
        if not confirm_action(
            self,
            "Delete this borrower?",
            f"Borrower: {b['name']}\n"
            f"ID: {b.get('borrower_id') or bid}\n\n"
            "This removes the borrower only if they have no loans and no "
            "transaction history.\n\n"
            "If loans still exist, this borrower cannot be deleted.",
            "Delete Borrower",
            danger=True,
            geometry="480x340",
        ):
            return
        try:
            db.delete_borrower(bid)
            notify(
                self, "Borrower deleted.",
                "The borrower was removed.",
                tone="success", geometry="400x180",
            )
            self._load_table()
        except ValueError as e:
            notify(
                self,
                "Borrower could not be deleted.",
                explain_error(
                    e,
                    "This borrower cannot be deleted because loan or "
                    "transaction history exists.",
                ),
                tone="error",
                geometry="480x240",
            )


class BorrowerDialog(ctk.CTkToplevel):
    def __init__(self, parent, mode="add", borrower=None, on_save=None):
        super().__init__(parent)
        self._mode = mode
        self._borrower = borrower
        self._on_save = on_save
        setup_dialog(self, "Add Borrower" if mode == "add" else "Edit Borrower", "440x360")
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        pad = {"padx": S16, "pady": S8}

        ctk.CTkLabel(
            self, text="Borrower Name *", text_color=TEXT, font=font_body()
        ).grid(row=0, column=0, sticky="e", **pad)
        self._name = ctk.CTkEntry(
            self, placeholder_text="Full name",
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            height=36, corner_radius=RADIUS_CONTROL,
        )
        self._name.grid(row=0, column=1, sticky="ew", **pad)

        ctk.CTkLabel(self, text="Phone", text_color=TEXT, font=font_body()
                     ).grid(row=1, column=0, sticky="e", **pad)
        self._phone = ctk.CTkEntry(
            self, placeholder_text="Optional",
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            height=36, corner_radius=RADIUS_CONTROL,
        )
        self._phone.grid(row=1, column=1, sticky="ew", **pad)

        ctk.CTkLabel(self, text="Notes", text_color=TEXT, font=font_body()
                     ).grid(row=2, column=0, sticky="ne", padx=S16, pady=S8)
        self._notes = ctk.CTkTextbox(
            self, height=80, fg_color=BG, border_color=BORDER, text_color=TEXT,
            corner_radius=RADIUS_CONTROL,
        )
        self._notes.grid(row=2, column=1, sticky="ew", padx=S16, pady=S8)

        if self._borrower:
            self._name.insert(0, self._borrower.get("name", ""))
            self._phone.insert(0, self._borrower.get("phone", "") or "")
            self._notes.insert("1.0", self._borrower.get("notes", "") or "")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, pady=S16)
        secondary_button(btn_frame, "Cancel", self.destroy, width=90).pack(side="left", padx=S8)
        primary_button(
            btn_frame,
            "Save Changes" if self._mode == "edit" else "Add Borrower",
            self._save,
            width=140,
        ).pack(side="right", padx=S8)

    def _save(self):
        name = self._name.get().strip()
        if not name:
            notify(
                self, "Borrower could not be saved.",
                "Enter a borrower name.",
                tone="error",
            )
            return
        phone = self._phone.get().strip()
        notes = self._notes.get("1.0", "end").strip()

        try:
            if self._mode == "add":
                db.add_borrower(name, phone, notes)
                notify(
                    self, "Borrower added.",
                    "You can now create a loan for this person.",
                    tone="success", geometry="420x200",
                )
            else:
                db.update_borrower(self._borrower["borrower_id"], name, phone, notes)
                notify(
                    self, "Borrower changes saved.",
                    "The borrower details were updated.",
                    tone="success", geometry="420x200",
                )
        except Exception as e:
            notify(
                self, "Borrower could not be saved.",
                explain_error(e),
                tone="error",
            )
            return
        if self._on_save:
            self._on_save()
        self.destroy()
