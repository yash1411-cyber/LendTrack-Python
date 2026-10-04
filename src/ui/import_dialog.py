"""
Import Dialog - GUI for importing transactions from Excel
"""

import customtkinter as ctk
from tkinter import filedialog
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.excel_import_service import ExcelImportService
from services.loan_matcher import LoanMatcher
from services.duplicate_checker import DuplicateChecker
from services.historical_rebuild_service import HistoricalRebuildService
from src.services.import_classify import (
    classify_import_rows,
    build_import_status,
    apply_review_resolution,
    review_dialog_was_cancelled,
    POSSIBLE_NAME_MATCH_REASON,
    write_batch_from_matched,
)
from src.ui.ambiguous_match_dialog import AmbiguousMatchDialog
import database as db

from src.ui.theme import (
    BG, CARD, CARD2, TEXT, MUTED, BORDER, GREEN, AMBER, RED,
    font_section, font_body, font_body_bold, font_meta, font_overline, font_title,
    RADIUS_CARD, S8, S12, S16, S24, ROW_PY,
    fmt_inr, primary_button, secondary_button, success_button,
    table_header, table_cell, bind_row_hover, tone_badge, setup_dialog,
    notify, explain_error, clamp_dialog_size, ellipsize, place_dialog,
)


FORMAT_HELP = (
    "Use an Excel sheet named Daily Transactions.\n\n"
    "Required columns:\n"
    "  Date, Borrower Name, Transaction Type, Amount\n\n"
    "Also include one of:\n"
    "  Due Day\n"
    "  or Loan Display Name\n\n"
    "Optional: Payment Mode, Notes\n\n"
    "Transaction Type must be Interest Received or Principal Received "
    "for payment rows.\n\n"
    "You can also save a blank template from this window or from "
    "the Transactions screen (Export Template)."
)


class ImportDialog(ctk.CTkToplevel):
    """Import transactions from Excel."""

    def __init__(self, parent, db_path: str):
        super().__init__(parent)
        self.title("Import Excel Data")
        geom = clamp_dialog_size(900, 580, parent)
        self.geometry(geom)
        self.minsize(640, 420)
        self.resizable(True, True)
        self.configure(fg_color=BG)
        self.grab_set()
        self.lift()
        self.bind("<Escape>", lambda _e: self.destroy())
        place_dialog(self, parent)

        self.db_path = db_path
        self.transactions = []
        self.matched_txns = []
        self.review_txns = []
        self.error_txns = []
        self.duplicate_txns = []
        self.skipped_review_txns = []

        self.excel_service = ExcelImportService()
        self.loan_matcher = None
        self.duplicate_checker = None
        self.rebuild_service = HistoricalRebuildService(db_path)

        self.current_step = 1
        self._preview_rows = []

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        container = ctk.CTkFrame(self, fg_color=BG)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        self.step1 = self._build_step1(container)
        self.step1.grid(row=0, column=0, sticky="nsew")

        self.step2 = self._build_step2(container)
        self.step2.grid(row=0, column=0, sticky="nsew")
        self.step2.grid_remove()

        self.step_confirm = self._build_confirm(container)
        self.step_confirm.grid(row=0, column=0, sticky="nsew")
        self.step_confirm.grid_remove()

        self.step3 = self._build_step3(container)
        self.step3.grid(row=0, column=0, sticky="nsew")
        self.step3.grid_remove()

    def _build_step1(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=BG)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text="Import Excel Data", font=font_section(), text_color=TEXT
        ).grid(row=0, column=0, padx=S24, pady=(S24, S8), sticky="w")

        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.grid(row=1, column=0, padx=S24, pady=S16, sticky="nsew")

        ctk.CTkLabel(
            content,
            text="Select an Excel file to review its contents. "
                 "Nothing is imported until you confirm.",
            font=font_body(),
            text_color=MUTED,
            wraplength=640,
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(0, S16))

        self.file_label = ctk.CTkLabel(
            content,
            text="Select an Excel file to begin.",
            font=font_body(),
            text_color=AMBER,
            anchor="w",
        )
        self.file_label.pack(anchor="w", pady=(0, S16))

        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(anchor="w", pady=S8)
        primary_button(btn_frame, "Select Excel File", self._on_select_file, width=180).pack(
            side="left", padx=(0, S8)
        )
        secondary_button(btn_frame, "Excel format", self._show_format_help, width=140).pack(
            side="left", padx=S8
        )
        secondary_button(btn_frame, "Save template", self._export_template, width=140).pack(
            side="left", padx=S8
        )
        secondary_button(btn_frame, "Cancel", self.destroy, width=110).pack(
            side="left", padx=S8
        )
        return frame

    def _show_format_help(self):
        win = ctk.CTkToplevel(self)
        setup_dialog(win, "Excel format", "520x420")
        ctk.CTkLabel(
            win, text="How should my Excel file look?",
            font=font_section(), text_color=TEXT, anchor="w",
        ).pack(fill="x", padx=S16, pady=(S16, S8))
        ctk.CTkLabel(
            win, text=FORMAT_HELP, font=font_meta(), text_color=MUTED,
            justify="left", wraplength=460, anchor="w",
        ).pack(fill="both", expand=True, padx=S16, pady=(0, S16))
        primary_button(win, "Close", win.destroy, width=100).pack(pady=(0, S16))

    def _export_template(self):
        try:
            from src.services.import_template_generator import ImportTemplateGenerator
            from src.services.loan_matcher import LoanMatcher

            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"LendTrack_Import_Template_{datetime.now().strftime('%Y%m%d')}.xlsx",
            )
            if not file_path:
                return
            matcher = LoanMatcher(self.db_path)
            generator = ImportTemplateGenerator(self.db_path, file_path)
            if generator.generate(matcher):
                notify(
                    self, "Template saved.",
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

    def _on_select_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if not file_path:
            return

        transactions, success = self.excel_service.read_excel(file_path)
        if not success:
            errors = "\n".join(self.excel_service.get_errors())
            notify(
                self,
                "Could not read file",
                "The Excel file could not be read.\n\n"
                + (explain_error(errors) if errors else "Check that the sheet is named Daily Transactions."),
                tone="error",
                geometry="480x280",
            )
            return
        if not transactions:
            self.file_label.configure(text="No importable rows were found in this file.")
            return

        self.transactions = transactions
        self.file_label.configure(
            text=f"File loaded — {len(transactions)} row(s) found. Review next."
        )
        self.loan_matcher = LoanMatcher(self.db_path)
        self.duplicate_checker = DuplicateChecker(self.db_path)
        self._validate_and_match()
        self._show_preview()
        self._advance_to_step2()

    def _validate_and_match(self):
        result = classify_import_rows(
            self.transactions, self.loan_matcher, self.duplicate_checker
        )
        self.matched_txns = result["matched_txns"]
        self.review_txns = result["review_txns"]
        self.duplicate_txns = result["duplicate_txns"]
        self.error_txns = result["error_txns"]
        self.skipped_review_txns = []

    def _build_step2(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=BG)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=S24, pady=(S16, 4))
        ctk.CTkLabel(
            hdr, text="Review Import", font=font_section(), text_color=TEXT
        ).pack(anchor="w")
        self._review_sub = ctk.CTkLabel(
            hdr,
            text="These rows are classified. Nothing is written until you confirm.",
            font=font_meta(),
            text_color=MUTED,
        )
        self._review_sub.pack(anchor="w", pady=(4, 0))

        cards = ctk.CTkFrame(frame, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", padx=S16, pady=S12)
        cards.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self._sum_labels = {}
        for col, (key, title) in enumerate([
            ("found", "Rows found"),
            ("ready", "Ready"),
            ("review", "Needs review"),
            ("duplicates", "Duplicates"),
            ("errors", "Can't import"),
        ]):
            card = ctk.CTkFrame(
                cards, fg_color=CARD, border_width=1, border_color=BORDER,
                corner_radius=RADIUS_CARD,
            )
            card.grid(row=0, column=col, padx=S8, sticky="ew")
            ctk.CTkLabel(card, text=title, font=font_overline(), text_color=MUTED).pack(
                anchor="w", padx=S12, pady=(10, 2)
            )
            val = ctk.CTkLabel(card, text="0", font=font_title(), text_color=TEXT)
            val.pack(anchor="w", padx=S12, pady=(0, 10))
            self._sum_labels[key] = val

        table_wrap = ctk.CTkFrame(
            frame, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=RADIUS_CARD,
        )
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=S24, pady=(0, 8))
        table_wrap.grid_columnconfigure(0, weight=1)
        table_wrap.grid_rowconfigure(0, weight=1)
        self.preview_table = ctk.CTkScrollableFrame(
            table_wrap, fg_color=CARD, corner_radius=0
        )
        self.preview_table.grid(row=0, column=0, sticky="nsew")
        cols = ["Date", "Borrower", "Amount", "Type", "Loan", "Status"]
        weights = [1, 2, 1, 2, 2, 1]
        for ci, w in enumerate(weights):
            self.preview_table.grid_columnconfigure(ci, weight=w)
        for ci, col in enumerate(cols):
            table_header(self.preview_table, col).grid(
                row=0, column=ci, padx=S12, pady=10, sticky="w"
            )

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", padx=S24, pady=S16)
        btn_frame.grid_columnconfigure(1, weight=1)
        secondary_button(btn_frame, "Back", self._back_to_step1, width=120).grid(
            row=0, column=0, padx=(0, 10)
        )
        self._continue_btn = success_button(
            btn_frame, "Continue", self._continue_from_review, width=180
        )
        self._continue_btn.grid(row=0, column=2)
        return frame

    def _preview_items(self):
        rows = []
        for item in self.matched_txns:
            loan = item.get("loan") or {}
            rows.append((item["txn"], "Ready", "success", loan.get("loan_id") or "—"))
        for item in self.review_txns:
            rows.append((item["txn"], "Needs review", "warning", "Needs a choice"))
        for item in self.duplicate_txns:
            loan = item.get("loan") or {}
            rows.append((item["txn"], "Duplicate", "neutral", loan.get("loan_id") or "—"))
        for item in self.error_txns:
            rows.append((
                item["txn"],
                "Can't import",
                "danger",
                item.get("error") or "—",
            ))
        return rows

    def _show_preview(self):
        found = len(self.transactions)
        ready = len(self.matched_txns)
        review = len(self.review_txns)
        dups = len(self.duplicate_txns)
        errors = len(self.error_txns)
        self._sum_labels["found"].configure(text=str(found))
        self._sum_labels["ready"].configure(text=str(ready), text_color=GREEN)
        self._sum_labels["review"].configure(text=str(review), text_color=AMBER)
        self._sum_labels["duplicates"].configure(text=str(dups), text_color=MUTED)
        self._sum_labels["errors"].configure(text=str(errors), text_color=RED)

        if review:
            self._review_sub.configure(text="Some rows need your attention before import.")
            self._continue_btn.configure(text="Review & Continue")
        elif ready:
            self._review_sub.configure(text="These rows are ready to import.")
            self._continue_btn.configure(text="Continue")
        else:
            self._review_sub.configure(text="No new rows are ready to import.")
            self._continue_btn.configure(text="Continue")

        for w in self._preview_rows:
            w.destroy()
        self._preview_rows.clear()

        items = self._preview_items()
        if not items:
            lbl = ctk.CTkLabel(
                self.preview_table,
                text="No importable rows were found in this file.",
                font=font_body(),
                text_color=MUTED,
            )
            lbl.grid(row=1, column=0, columnspan=6, pady=S24)
            self._preview_rows.append(lbl)
            return

        for ri, (txn, status, tone, loan_txt) in enumerate(items, start=1):
            bg = CARD if ri % 2 == 0 else CARD2
            rf = ctk.CTkFrame(self.preview_table, fg_color=bg, corner_radius=0)
            rf.grid(row=ri, column=0, columnspan=6, sticky="ew")
            for ci in range(6):
                rf.grid_columnconfigure(ci, weight=[1, 2, 1, 2, 2, 1][ci])
            bind_row_hover(rf, bg)
            self._preview_rows.append(rf)
            vals = [
                str(txn.get("date") or "—"),
                ellipsize(txn.get("borrower_name") or "—", 22),
                fmt_inr(txn.get("amount") or 0),
                ellipsize(txn.get("txn_type") or "—", 22),
                ellipsize(loan_txt, 36),
            ]
            colors = [MUTED, TEXT, TEXT, TEXT, MUTED]
            for ci, (v, col) in enumerate(zip(vals, colors)):
                table_cell(rf, v, col, row=0, column=ci, padx=S12, pady=ROW_PY, sticky="w")
            pill = tone_badge(rf, status, tone)
            pill.grid(row=0, column=5, padx=S8, pady=4, sticky="w")

    def _build_confirm(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=BG)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text="Confirm Import", font=font_section(), text_color=TEXT
        ).grid(row=0, column=0, padx=S24, pady=(S24, 8), sticky="w")

        body = ctk.CTkFrame(
            frame, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=RADIUS_CARD,
        )
        body.grid(row=1, column=0, sticky="nsew", padx=S24, pady=S16)
        self._confirm_title = ctk.CTkLabel(
            body, text="Ready to import", font=font_body_bold(), text_color=TEXT
        )
        self._confirm_title.pack(anchor="w", padx=S16, pady=(S16, S8))
        self._confirm_body = ctk.CTkLabel(
            body, text="", font=font_body(), text_color=MUTED,
            justify="left", wraplength=640, anchor="w",
        )
        self._confirm_body.pack(anchor="w", padx=S16, pady=(0, S16))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=S24, pady=S16)
        secondary_button(btn_frame, "Back", self._back_to_review, width=120).pack(
            side="left"
        )
        self._import_now_btn = success_button(
            btn_frame, "Import Now", self._execute_import, width=160
        )
        self._import_now_btn.pack(side="right")
        return frame

    def _refresh_confirm(self):
        ready = len(self.matched_txns)
        skipped = len(self.skipped_review_txns)
        dups = len(self.duplicate_txns)
        errors = len(self.error_txns)
        review_left = len(self.review_txns)
        lines = [
            f"{ready} row(s) will be imported.",
            f"{skipped} row(s) will be skipped.",
        ]
        if dups:
            lines.append(f"{dups} duplicate row(s) will not be imported.")
        if errors:
            lines.append(f"{errors} row(s) can't be imported.")
        if review_left:
            lines.append(f"{review_left} row(s) still need review.")
        if ready == 0:
            self._confirm_title.configure(text="No rows to import")
            self._confirm_body.configure(
                text="\n".join(lines) + "\n\nNo new rows are ready to import."
            )
            self._import_now_btn.configure(state="disabled")
        else:
            self._confirm_title.configure(text="Ready to import")
            self._confirm_body.configure(text="\n".join(lines))
            self._import_now_btn.configure(state="normal")

    def _continue_from_review(self):
        if self.review_txns:
            if not self._resolve_review_txns():
                return
        self._refresh_confirm()
        self.step2.grid_remove()
        self.step_confirm.grid()
        self.current_step = "confirm"

    def _build_step3(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=BG)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        self._result_title = ctk.CTkLabel(
            frame, text="Import Complete", font=font_section(), text_color=TEXT
        )
        self._result_title.grid(row=0, column=0, padx=S24, pady=(S16, 8), sticky="w")

        cards_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cards_frame.grid(row=1, column=0, sticky="ew", padx=S16, pady=(0, S12))
        cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.result_cards = {}
        for col, (key, label, color) in enumerate([
            ("imported", "Imported", GREEN),
            ("skipped", "Skipped", AMBER),
            ("duplicates", "Duplicates", MUTED),
            ("errors", "Can't import", RED),
        ]):
            card = ctk.CTkFrame(
                cards_frame, fg_color=CARD, border_width=1, border_color=BORDER,
                corner_radius=RADIUS_CARD,
            )
            card.grid(row=0, column=col, padx=S8, sticky="ew")
            ctk.CTkLabel(card, text=label, font=font_meta(), text_color=MUTED).pack(
                pady=(12, 4), padx=10
            )
            val_label = ctk.CTkLabel(card, text="0", font=font_title(), text_color=color)
            val_label.pack(pady=(0, 12), padx=10)
            self.result_cards[key] = val_label

        detail = ctk.CTkFrame(
            frame, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=RADIUS_CARD,
        )
        detail.grid(row=2, column=0, sticky="nsew", padx=S24, pady=(0, 8))
        self._result_detail = ctk.CTkLabel(
            detail, text="", font=font_body(), text_color=MUTED,
            justify="left", wraplength=800, anchor="w",
        )
        self._result_detail.pack(anchor="w", padx=S16, pady=S16)

        success_button(frame, "Close", self.destroy, width=120).grid(
            row=3, column=0, padx=S24, pady=S16
        )
        return frame

    def _resolve_review_txns(self) -> bool:
        if not self.review_txns:
            return True

        pending = list(self.review_txns)
        self.review_txns = []
        self.skipped_review_txns = []

        for item in pending:
            txn = item["txn"]
            due_day = txn.get("due_day")
            dialog = AmbiguousMatchDialog(
                self,
                borrower_name=txn.get("borrower_name", ""),
                candidates=item.get("candidates") or [],
                txn_data=txn,
                due_day=due_day,
                reason=item.get("reason", ""),
                possible_name_match=item.get("reason") == POSSIBLE_NAME_MATCH_REASON,
            )
            self.wait_window(dialog)
            selected, skipped = dialog.get_result()

            if review_dialog_was_cancelled(selected, skipped):
                self.review_txns = pending
                self.skipped_review_txns = []
                notify(
                    self,
                    "Import cancelled",
                    "Review was cancelled. No rows were imported.",
                    tone="info",
                )
                return False

            apply_review_resolution(
                item,
                selected,
                skipped,
                self.duplicate_checker,
                self.matched_txns,
                self.duplicate_txns,
                self.skipped_review_txns,
            )

        return True

    def _execute_import(self):
        if len(self.matched_txns) == 0:
            self._show_results(0, 0, error_message="")
            self._advance_to_step3()
            return

        batch = write_batch_from_matched(self.matched_txns)

        imported = 0
        failed = 0
        error_message = ""

        if batch:
            try:
                imported = db.add_transactions_batch(batch)
            except Exception as e:
                imported = 0
                failed = len(batch)
                error_message = explain_error(
                    e, "Something went wrong while saving the import."
                )

        if imported and not failed:
            self.rebuild_service.rebuild_all()

        self._show_results(imported, failed, error_message=error_message)
        self._advance_to_step3()

    def _show_results(self, imported, failed, error_message: str = ""):
        skipped_review = getattr(self, "skipped_review_txns", []) or []
        status = build_import_status(
            imported=imported,
            failed=failed,
            matched_count=len(self.matched_txns),
            duplicate_count=len(self.duplicate_txns),
            error_count=len(self.error_txns),
            review_count=len(self.review_txns),
            error_message=error_message,
            skipped_review_count=len(skipped_review),
        )

        skipped_total = len(skipped_review)
        self.result_cards["imported"].configure(text=str(imported))
        self.result_cards["skipped"].configure(text=str(skipped_total))
        self.result_cards["duplicates"].configure(text=str(len(self.duplicate_txns)))
        self.result_cards["errors"].configure(
            text=str(len(self.error_txns) + (1 if failed else 0))
        )

        kind = status.get("status")
        extra_skips = skipped_total + len(self.duplicate_txns) + len(self.error_txns)
        if kind == "rolled_back":
            title = "Import Failed"
            body = (
                "No rows were saved. The import was rolled back.\n\n"
                + (error_message or status.get("detail") or "")
            )
        elif imported > 0 and extra_skips:
            title = "Finished with Skipped Rows"
            body = (
                f"{imported} row(s) imported. "
                f"{extra_skips} row(s) were skipped or could not be imported."
            )
        elif imported > 0:
            title = "Import Complete"
            body = f"{imported} row(s) imported successfully."
        else:
            title = "No Rows Imported"
            body = "0 rows were imported."
            detail = status.get("detail") or ""
            if detail:
                body += "\n\n" + detail

        if imported and not failed:
            body += (
                "\n\nExisting loan history was kept. "
                "Outstanding and interest still use live calculations."
            )
        elif failed:
            body += "\n\nFinancial totals were not recalculated."

        self._result_title.configure(text=title)
        self._result_detail.configure(text=body)

    def _advance_to_step2(self):
        self.step1.grid_remove()
        self.step_confirm.grid_remove()
        self.step2.grid()
        self.current_step = 2

    def _back_to_step1(self):
        self.step2.grid_remove()
        self.step1.grid()
        self.current_step = 1

    def _back_to_review(self):
        if self.loan_matcher and self.duplicate_checker and self.transactions:
            self._validate_and_match()
            self._show_preview()
        self.step_confirm.grid_remove()
        self.step2.grid()
        self.current_step = 2

    def _advance_to_step3(self):
        self.step2.grid_remove()
        self.step_confirm.grid_remove()
        self.step3.grid()
        self.current_step = 3
