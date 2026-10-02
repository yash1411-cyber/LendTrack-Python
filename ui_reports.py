"""
ui_reports.py - Borrower-wise summary report + Excel export.
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
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
    return f"₹{v:,.0f}"


class ReportsFrame(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._report_data = []
        self._build_ui()

    def refresh(self):
        self._load()

    # ── UI ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 8))
        ctk.CTkLabel(hdr, text="Reports",
                     font=ctk.CTkFont("Segoe UI", 24, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(hdr, text="⬇ Export to Excel", width=160, height=34,
                      fg_color=GREEN, hover_color="#27A060",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      command=self._export_excel).pack(side="right")
        ctk.CTkButton(hdr, text="🔄 Refresh", width=100, height=34,
                      fg_color=CARD, hover_color=CARD2,
                      border_width=1, border_color=BORDER,
                      font=ctk.CTkFont("Segoe UI", 12),
                      text_color=TEXT,
                      command=self._load).pack(side="right", padx=(0, 10))

        # Summary band
        self._summary_frame = ctk.CTkFrame(self, fg_color=CARD,
                                           corner_radius=14,
                                           border_width=1, border_color=BORDER)
        self._summary_frame.grid(row=0, column=0, sticky="ew",
                                  padx=28, pady=(72, 4))
        self._summary_frame.grid_columnconfigure((0,1,2,3,4), weight=1)
        self._sum_labels = {}
        for ci, (key, lbl) in enumerate([
            ("total_principal",     "Total Outstanding"),
            ("total_given",         "Total Loans Given"),
            ("total_returned",      "Total Returned"),
            ("total_interest_recv", "Interest Received"),
            ("total_pending",       "Total Pending"),
        ]):
            f = ctk.CTkFrame(self._summary_frame, fg_color="transparent")
            f.grid(row=0, column=ci, padx=16, pady=12)
            ctk.CTkLabel(f, text=lbl,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=MUTED).pack()
            vl = ctk.CTkLabel(f, text="₹0",
                              font=ctk.CTkFont("Segoe UI", 16, "bold"),
                              text_color=TEXT)
            vl.pack()
            self._sum_labels[key] = vl

        # Table
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=28, pady=(8, 20))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        cols    = ["ID", "Name", "Phone",
                   "Principal Given", "Returned",
                   "Outstanding", "Exp. Interest/Mo",
                   "Interest Recv'd", "Pending Interest"]
        weights = [1, 2, 1, 2, 2, 2, 2, 2, 2]

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
        self._load()

    def _load(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()

        self._report_data = db.get_report_data()

        # Update summary band
        tp  = sum(r["outstanding_principal"]    for r in self._report_data)
        tg  = sum(r["total_principal_given"]    for r in self._report_data)
        tr  = sum(r["principal_returned"]       for r in self._report_data)
        tir = sum(r["interest_received"]        for r in self._report_data)
        tpd = sum(r["pending_interest"]         for r in self._report_data)
        for key, val in [("total_principal", tp), ("total_given", tg),
                         ("total_returned", tr), ("total_interest_recv", tir),
                         ("total_pending", tpd)]:
            c = RED if key == "total_pending" and val > 0 else GREEN if key in ("total_interest_recv",) else TEXT
            self._sum_labels[key].configure(text=_fmt(val), text_color=c)

        if not self._report_data:
            lbl = ctk.CTkLabel(self._tbl, text="No data yet.",
                               text_color=MUTED, font=ctk.CTkFont("Segoe UI", 13))
            lbl.grid(row=1, column=0, columnspan=9, pady=32)
            self._row_widgets.append(lbl)
            return

        for ri, r in enumerate(self._report_data, start=1):
            bg = CARD if ri % 2 == 0 else CARD2
            rf = ctk.CTkFrame(self._tbl, fg_color=bg, corner_radius=0)
            rf.grid(row=ri, column=0, columnspan=9, sticky="ew")
            for ci in range(9):
                rf.grid_columnconfigure(ci, weight=[1,2,1,2,2,2,2,2,2][ci])
            self._row_widgets.append(rf)

            pend_col = RED if r["pending_interest"] > 0 else TEXT
            vals   = [r["borrower_id"], r["name"], r["phone"] or "—",
                      _fmt(r["total_principal_given"]),
                      _fmt(r["principal_returned"]),
                      _fmt(r["outstanding_principal"]),
                      _fmt(r["expected_monthly_interest"]),
                      _fmt(r["interest_received"]),
                      _fmt(r["pending_interest"])]
            colors = [MUTED, TEXT, MUTED, TEXT, TEXT, ACCENT, GREEN, GREEN, pend_col]
            for ci, (v, col) in enumerate(zip(vals, colors)):
                ctk.CTkLabel(rf, text=v,
                             font=ctk.CTkFont("Segoe UI", 12),
                             text_color=col).grid(row=0, column=ci,
                                                  padx=10, pady=8, sticky="w")

    # ── Excel export ──────────────────────────────────────────────────────────
    def _export_excel(self):
        if not self._report_data:
            messagebox.showinfo("Export", "No data to export.")
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            messagebox.showerror("Missing library",
                                 "openpyxl is required for Excel export.\n"
                                 "Run:  pip install openpyxl")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"LendTrack_Report_{date.today()}.xlsx"
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Borrower Summary"

        # Styles
        hdr_fill = PatternFill("solid", fgColor="1E2435")
        hdr_font = Font(bold=True, color="4F8EF7", size=11)
        border   = Border(bottom=Side(style="thin", color="2C3347"))
        center   = Alignment(horizontal="center")

        headers = ["ID", "Name", "Phone",
                   "Principal Given", "Returned",
                   "Outstanding", "Exp Interest/Mo",
                   "Interest Received", "Pending Interest"]
        ws.append(headers)
        for cell in ws[1]:
            cell.font      = hdr_font
            cell.fill      = hdr_fill
            cell.alignment = center
            cell.border    = border

        for r in self._report_data:
            ws.append([
                r["borrower_id"], r["name"], r["phone"] or "",
                r["total_principal_given"], r["principal_returned"],
                r["outstanding_principal"], r["expected_monthly_interest"],
                r["interest_received"], r["pending_interest"],
            ])

        # Column widths
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 18

        wb.save(path)
        messagebox.showinfo("Exported", f"Report saved to:\n{path}")
