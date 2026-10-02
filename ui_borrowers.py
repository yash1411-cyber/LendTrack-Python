"""
ui_borrowers.py - Add / Edit / Delete / Search borrowers.
"""

import customtkinter as ctk
from tkinter import messagebox
import database as db

BG    = "#0F1117"
CARD  = "#1E2435"
CARD2 = "#252B3B"
ACCENT= "#4F8EF7"
GREEN = "#34C77B"
RED   = "#E85D5D"
TEXT  = "#E8EBF2"
MUTED = "#7A849E"
BORDER= "#2C3347"
SIDEBAR="#161B27"


class BorrowersFrame(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._selected_id = None
        self._build_ui()

    # ── public ───────────────────────────────────────────────────────────────
    def refresh(self):
        self._load_table()

    # ── private ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header bar
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 0))
        ctk.CTkLabel(hdr, text="Borrowers",
                     font=ctk.CTkFont("Segoe UI", 24, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(hdr, text="+ Add Borrower", width=140, height=34,
                      fg_color=ACCENT, hover_color="#3A72D8",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      command=self._open_add_dialog).pack(side="right")

        # Content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=28, pady=16)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        # Search bar
        sb = ctk.CTkFrame(content, fg_color="transparent")
        sb.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._load_table())
        ctk.CTkEntry(sb, textvariable=self._search_var,
                     placeholder_text="🔍  Search borrowers…",
                     width=320, height=36,
                     fg_color=CARD, border_color=BORDER, text_color=TEXT).pack(side="left")

        # Table
        cols = ["ID", "Name", "Phone", "Notes", "Created", "Actions"]
        col_weights = [1, 2, 2, 3, 1, 1]

        tbl = ctk.CTkScrollableFrame(content, fg_color=CARD,
                                     corner_radius=14,
                                     border_width=1, border_color=BORDER)
        tbl.grid(row=1, column=0, sticky="nsew")
        for ci, (col, w) in enumerate(zip(cols, col_weights)):
            tbl.grid_columnconfigure(ci, weight=w)
        self._tbl = tbl

        # Header row
        for ci, col in enumerate(cols):
            ctk.CTkLabel(tbl, text=col,
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=MUTED).grid(row=0, column=ci,
                                                padx=12, pady=10, sticky="w")
        self._row_widgets = []
        self._load_table()

    def _load_table(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()

        q = self._search_var.get() if hasattr(self, "_search_var") else ""
        rows = db.get_all_borrowers(search=q)

        if not rows:
            lbl = ctk.CTkLabel(self._tbl, text="No borrowers found.",
                               text_color=MUTED,
                               font=ctk.CTkFont("Segoe UI", 13))
            lbl.grid(row=1, column=0, columnspan=6, pady=32)
            self._row_widgets.append(lbl)
            return

        for ri, b in enumerate(rows, start=1):
            bg = CARD if ri % 2 == 0 else CARD2
            rf = ctk.CTkFrame(self._tbl, fg_color=bg, corner_radius=0)
            rf.grid(row=ri, column=0, columnspan=6, sticky="ew")
            for ci in range(6):
                rf.grid_columnconfigure(ci, weight=[1,2,2,3,1,1][ci])
            self._row_widgets.append(rf)

            vals = [b["borrower_id"], b["name"], b["phone"] or "—",
                    (b["notes"] or "")[:40], b["created_at"]]
            for ci, v in enumerate(vals):
                ctk.CTkLabel(rf, text=v,
                             font=ctk.CTkFont("Segoe UI", 12),
                             text_color=TEXT).grid(row=0, column=ci,
                                                   padx=12, pady=8, sticky="w")

            # Action buttons
            btn_frame = ctk.CTkFrame(rf, fg_color="transparent")
            btn_frame.grid(row=0, column=5, padx=8, pady=4)
            ctk.CTkButton(btn_frame, text="Edit", width=56, height=28,
                          fg_color=ACCENT, hover_color="#3A72D8",
                          font=ctk.CTkFont("Segoe UI", 11),
                          command=lambda bid=b["borrower_id"]: self._open_edit_dialog(bid)
                          ).pack(side="left", padx=2)
            ctk.CTkButton(btn_frame, text="Del", width=48, height=28,
                          fg_color=RED, hover_color="#C04040",
                          font=ctk.CTkFont("Segoe UI", 11),
                          command=lambda bid=b["borrower_id"]: self._delete(bid)
                          ).pack(side="left", padx=2)

    # ── dialogs ──────────────────────────────────────────────────────────────
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
        if not messagebox.askyesno(
            "Delete Borrower",
            f"Delete borrower '{b['name']}' ({bid})?\n\n"
            "This is only allowed if the borrower has no loans and no transactions."
        ):
            return
        try:
            db.delete_borrower(bid)
            self._load_table()
        except ValueError as e:
            messagebox.showerror("Cannot Delete Borrower", str(e))


# ── Add / Edit Dialog ─────────────────────────────────────────────────────────

class BorrowerDialog(ctk.CTkToplevel):
    def __init__(self, parent, mode="add", borrower=None, on_save=None):
        super().__init__(parent)
        self._mode = mode
        self._borrower = borrower
        self._on_save = on_save

        self.title("Add Borrower" if mode == "add" else "Edit Borrower")
        self.geometry("420x340")
        self.resizable(False, False)
        self.configure(fg_color=CARD)
        self.grab_set()
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        pad = {"padx": 20, "pady": 8}

        ctk.CTkLabel(self, text="Borrower Name *",
                     text_color=TEXT, font=ctk.CTkFont("Segoe UI", 12)
                     ).grid(row=0, column=0, sticky="e", **pad)
        self._name = ctk.CTkEntry(self, placeholder_text="Full name",
                                  fg_color=BG, border_color=BORDER, text_color=TEXT,
                                  height=36)
        self._name.grid(row=0, column=1, sticky="ew", **pad)

        ctk.CTkLabel(self, text="Phone",
                     text_color=TEXT, font=ctk.CTkFont("Segoe UI", 12)
                     ).grid(row=1, column=0, sticky="e", **pad)
        self._phone = ctk.CTkEntry(self, placeholder_text="Optional",
                                   fg_color=BG, border_color=BORDER, text_color=TEXT,
                                   height=36)
        self._phone.grid(row=1, column=1, sticky="ew", **pad)

        ctk.CTkLabel(self, text="Notes",
                     text_color=TEXT, font=ctk.CTkFont("Segoe UI", 12)
                     ).grid(row=2, column=0, sticky="ne", padx=20, pady=8)
        self._notes = ctk.CTkTextbox(self, height=80,
                                     fg_color=BG, border_color=BORDER, text_color=TEXT)
        self._notes.grid(row=2, column=1, sticky="ew", padx=20, pady=8)

        # Pre-fill if editing
        if self._borrower:
            self._name.insert(0, self._borrower.get("name", ""))
            self._phone.insert(0, self._borrower.get("phone", "") or "")
            self._notes.insert("1.0", self._borrower.get("notes", "") or "")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, pady=16)
        ctk.CTkButton(btn_frame, text="Save", width=110, height=36,
                      fg_color=ACCENT, hover_color="#3A72D8",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Cancel", width=90, height=36,
                      fg_color=CARD2, hover_color="#333B52",
                      font=ctk.CTkFont("Segoe UI", 13),
                      command=self.destroy).pack(side="left", padx=8)

    def _save(self):
        name = self._name.get().strip()
        if not name:
            messagebox.showerror("Error", "Name is required.")
            return
        phone = self._phone.get().strip()
        notes = self._notes.get("1.0", "end").strip()

        if self._mode == "add":
            db.add_borrower(name, phone, notes)
        else:
            db.update_borrower(self._borrower["borrower_id"], name, phone, notes)
        if self._on_save:
            self._on_save()
        self.destroy()
