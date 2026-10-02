"""
Import Dialog - GUI for importing transactions from Excel
Fixed version with proper wizard state management
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox, Text, DISABLED, NORMAL
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.excel_import_service import ExcelImportService
from services.loan_matcher import LoanMatcher
from services.duplicate_checker import DuplicateChecker
from services.historical_rebuild_service import HistoricalRebuildService
import database as db

# Colors
BG = "#0F1117"
CARD = "#1E2435"
CARD2 = "#252B3B"
ACCENT = "#4F8EF7"
GREEN = "#34C77B"
AMBER = "#F5A623"
RED = "#E85D5D"
TEXT = "#E8EBF2"
MUTED = "#7A849E"
BORDER = "#2C3347"


class ImportDialog(ctk.CTkToplevel):
    """Import transactions from Excel - 3 step wizard"""
    
    def __init__(self, parent, db_path: str):
        super().__init__(parent)
        self.title("Import Transactions from Excel")
        self.geometry("1000x750")
        self.resizable(True, True)
        self.configure(fg_color=BG)
        self.grab_set()
        self.lift()
        
        self.db_path = db_path
        self.transactions = []
        self.matched_txns = []
        self.review_txns = []
        self.error_txns = []
        self.duplicate_txns = []
        
        # Services
        self.excel_service = ExcelImportService()
        self.loan_matcher = None
        self.duplicate_checker = None
        self.rebuild_service = HistoricalRebuildService(db_path)
        
        self.current_step = 1
        
        self._build_ui()
    
    def _build_ui(self):
        """Build wizard UI with 3 frames"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Main container
        container = ctk.CTkFrame(self, fg_color=BG)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)
        
        # Step 1: Select file
        self.step1 = self._build_step1(container)
        self.step1.grid(row=0, column=0, sticky="nsew")
        
        # Step 2: Preview
        self.step2 = self._build_step2(container)
        self.step2.grid(row=0, column=0, sticky="nsew")
        self.step2.grid_remove()
        
        # Step 3: Results
        self.step3 = self._build_step3(container)
        self.step3.grid(row=0, column=0, sticky="nsew")
        self.step3.grid_remove()
    
    # ════════════════════════════════════════════════════════════════════════════
    # STEP 1: FILE SELECTION
    # ════════════════════════════════════════════════════════════════════════════
    
    def _build_step1(self, parent):
        """Step 1: Select Excel file"""
        frame = ctk.CTkFrame(parent, fg_color=BG)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        
        # Header
        ctk.CTkLabel(frame, text="Step 1: Select Excel File",
                    font=ctk.CTkFont("Segoe UI", 18, "bold"),
                    text_color=TEXT).grid(row=0, column=0, padx=30, pady=30, sticky="w")
        
        # Content
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.grid(row=1, column=0, padx=30, pady=20, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        
        # Instructions
        instructions = """
Required columns in Excel sheet "Daily Transactions":

OLD FORMAT (using Loan Display Name):
  • Date | Borrower Name | Loan Display Name | Transaction Type | Amount | Payment Mode | Notes

NEW FORMAT (using Due Day):
  • Date | Borrower Name | Due Day | Transaction Type | Amount | Payment Mode | Notes

Examples:
  OLD:  24/12/2025 | Prem Singh | 25-Jul-25 | ₹100000 | Due 25 | Interest Received | 6000 | Cash | Dec payment
  NEW:  24/12/2025 | Prem Singh | 25 | Interest Received | 6000 | Cash | Dec payment

Both formats are supported. Choose the one that's easiest for you.
        """
        
        ctk.CTkLabel(content, text=instructions,
                    font=ctk.CTkFont("Segoe UI", 11),
                    text_color=MUTED,
                    justify="left").pack(anchor="w", pady=20)
        
        # File selection
        self.file_label = ctk.CTkLabel(content, text="No file selected",
                                       font=ctk.CTkFont("Segoe UI", 12),
                                       text_color=AMBER)
        self.file_label.pack(anchor="w", pady=10)
        
        # Buttons
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(anchor="w", pady=30)
        
        ctk.CTkButton(btn_frame, text="📁 Select Excel File", width=180, height=40,
                     fg_color=ACCENT, hover_color="#3A72D8",
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     command=self._on_select_file).pack(side="left", padx=10)
        
        ctk.CTkButton(btn_frame, text="Cancel", width=140, height=40,
                     fg_color=CARD2, hover_color="#333B52",
                     font=ctk.CTkFont("Segoe UI", 12),
                     command=self.destroy).pack(side="left", padx=10)
        
        return frame
    
    def _on_select_file(self):
        """Handle file selection"""
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        print(f"[IMPORT] Selected file: {file_path}")
        
        # Read Excel
        transactions, success = self.excel_service.read_excel(file_path)
        
        if not success:
            errors = "\n".join(self.excel_service.get_errors())
            messagebox.showerror("Import Error", f"Failed to read Excel:\n\n{errors}")
            return
        
        if not transactions:
            messagebox.showerror("No Data", "No valid transactions found in file")
            return
        
        print(f"[IMPORT] Loaded {len(transactions)} transactions successfully")
        
        self.transactions = transactions
        self.file_label.configure(text=f"✓ Loaded: {len(transactions)} transactions")
        
        # Initialize services
        self.loan_matcher = LoanMatcher(self.db_path)
        self.duplicate_checker = DuplicateChecker(self.db_path)
        
        # Validate and match
        print("[IMPORT] Starting validation and matching...")
        self._validate_and_match()
        
        # Show preview
        print("[IMPORT] Showing preview...")
        self._show_preview()
        
        # Advance to step 2
        print("[IMPORT] Advancing to step 2")
        self._advance_to_step2()
    
    # ════════════════════════════════════════════════════════════════════════════
    # VALIDATION & MATCHING
    # ════════════════════════════════════════════════════════════════════════════
    
    def _validate_and_match(self):
        """Validate transactions and match to loans"""
        self.matched_txns = []
        self.review_txns = []
        self.error_txns = []
        self.duplicate_txns = []
        
        print(f"[VALIDATE] Processing {len(self.transactions)} transactions")
        
        for idx, txn in enumerate(self.transactions):
            matched_loan = None
            error_msg = None
            needs_review = False
            
            try:
                # OLD FORMAT: Use display name
                if 'loan_display' in txn:
                    print(f"[VALIDATE] Row {idx+1}: OLD FORMAT - {txn['borrower_name']} | {txn['loan_display']}")
                    loan, status = self.loan_matcher.match_by_display_name(
                        txn['borrower_name'], 
                        txn['loan_display']
                    )
                    
                    if status == 'matched':
                        matched_loan = loan
                    else:
                        error_msg = status
                
                # NEW FORMAT: Use due day
                elif 'due_day' in txn:
                    print(f"[VALIDATE] Row {idx+1}: NEW FORMAT - {txn['borrower_name']} | Due Day {txn['due_day']}")
                    
                    # Step 1: Match by borrower + due day
                    loan, candidates, step1_status = self.loan_matcher.match_by_borrower_due_day(
                        txn['borrower_name'],
                        txn['due_day']
                    )
                    
                    if step1_status == 'exact_match':
                        matched_loan = loan
                    elif step1_status == 'ambiguous':
                        # Step 2: Try interest-based matching
                        loan, step2_status = self.loan_matcher.match_by_borrower_due_day_interest(
                            txn['borrower_name'],
                            txn['due_day'],
                            txn['amount'],
                            txn['txn_type']
                        )
                        
                        if step2_status == 'matched_by_interest':
                            matched_loan = loan
                        else:
                            # Step 3: Need manual review
                            needs_review = True
                            self.review_txns.append({
                                'txn': txn,
                                'candidates': candidates,
                            })
                    else:
                        error_msg = step1_status
                
                # Check for duplicates
                if matched_loan and not needs_review:
                    if self.duplicate_checker.check_duplicate(txn, matched_loan['loan_id']):
                        print(f"[VALIDATE] Row {idx+1}: DUPLICATE")
                        self.duplicate_txns.append({
                            'txn': txn,
                            'loan': matched_loan,
                        })
                    else:
                        print(f"[VALIDATE] Row {idx+1}: MATCHED ✓")
                        self.matched_txns.append({
                            'txn': txn,
                            'loan': matched_loan,
                        })
                
                elif error_msg and not needs_review:
                    print(f"[VALIDATE] Row {idx+1}: ERROR - {error_msg}")
                    self.error_txns.append({
                        'txn': txn,
                        'error': error_msg,
                    })
            
            except Exception as e:
                print(f"[VALIDATE] Row {idx+1}: EXCEPTION - {str(e)}")
                self.error_txns.append({
                    'txn': txn,
                    'error': str(e),
                })
        
        print(f"[VALIDATE] Results: {len(self.matched_txns)} matched, "
              f"{len(self.review_txns)} review, {len(self.duplicate_txns)} dup, "
              f"{len(self.error_txns)} errors")
    
    # ════════════════════════════════════════════════════════════════════════════
    # STEP 2: PREVIEW
    # ════════════════════════════════════════════════════════════════════════════
    
    def _build_step2(self, parent):
        """Step 2: Preview transactions before import"""
        frame = ctk.CTkFrame(parent, fg_color=BG)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        
        # Header
        ctk.CTkLabel(frame, text="Step 2: Preview & Validate",
                    font=ctk.CTkFont("Segoe UI", 18, "bold"),
                    text_color=TEXT).grid(row=0, column=0, padx=30, pady=20, sticky="w")
        
        # Content
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=30, pady=(0, 20))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        
        # Text widget for preview
        text_frame = ctk.CTkFrame(content, fg_color=CARD,
                                 border_width=1, border_color=BORDER,
                                 corner_radius=8)
        text_frame.grid(row=0, column=0, sticky="nsew")
        
        self.preview_text = Text(text_frame, height=20, width=120,
                                bg=CARD, fg=TEXT, font=("Courier", 10),
                                insertbackground=TEXT, relief="flat", border=0,
                                wrap="word")
        self.preview_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=20)
        btn_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(btn_frame, text="← Back", width=120, height=40,
                     fg_color=CARD2, hover_color="#333B52",
                     font=ctk.CTkFont("Segoe UI", 12),
                     command=self._back_to_step1).grid(row=0, column=0, padx=10)
        
        ctk.CTkButton(btn_frame, text="Import Now →", width=140, height=40,
                     fg_color=GREEN, hover_color="#27A060",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     command=self._start_import).grid(row=0, column=2, padx=10)
        
        return frame
    
    def _show_preview(self):
        """Display preview in the text widget"""
        self.preview_text.configure(state=NORMAL)
        self.preview_text.delete("1.0", "end")
        
        # Summary section
        summary = f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                         IMPORT PREVIEW SUMMARY                             ║
╚════════════════════════════════════════════════════════════════════════════╝

Total Records:           {len(self.transactions)}
  ✓ Ready to Import:     {len(self.matched_txns)}
  ⚠ Needs Review:        {len(self.review_txns)}
  ⊘ Duplicates (skip):   {len(self.duplicate_txns)}
  ✗ Errors (skip):       {len(self.error_txns)}

"""
        self.preview_text.insert("end", summary)
        
        # Matched transactions
        if self.matched_txns:
            self.preview_text.insert("end", """
╔════════════════════════════════════════════════════════════════════════════╗
║ ✓ READY TO IMPORT ({:}) """.format(len(self.matched_txns)))
            self.preview_text.insert("end", " " * (75 - len(f"READY TO IMPORT ({len(self.matched_txns)})")) + "║\n")
            self.preview_text.insert("end", "╚════════════════════════════════════════════════════════════════════════════╝\n\n")
            
            for item in self.matched_txns[:15]:
                txn = item['txn']
                loan = item['loan']
                self.preview_text.insert("end", 
                    f"  {txn['date']} | {txn['borrower_name']:20} | {txn['txn_type']:20} | ₹{txn['amount']:>10,.0f}\n"
                    f"    └─ Loan: {loan['loan_id']} ({loan['display_name']})\n\n")
            
            if len(self.matched_txns) > 15:
                self.preview_text.insert("end", f"  ... and {len(self.matched_txns) - 15} more\n\n")
        
        # Needs review
        if self.review_txns:
            self.preview_text.insert("end", f"""
╔════════════════════════════════════════════════════════════════════════════╗
║ ⚠ NEEDS MANUAL REVIEW ({len(self.review_txns)})""")
            self.preview_text.insert("end", " " * (75 - len(f"NEEDS MANUAL REVIEW ({len(self.review_txns)})")) + "║\n")
            self.preview_text.insert("end", "╚════════════════════════════════════════════════════════════════════════════╝\n")
            self.preview_text.insert("end", "These transactions have multiple matching loans. Manual selection required.\n\n")
            
            for item in self.review_txns[:5]:
                txn = item['txn']
                self.preview_text.insert("end", 
                    f"  {txn['date']} | {txn['borrower_name']:20} | {txn['txn_type']:20}\n"
                    f"    └─ Amount: ₹{txn['amount']:,.0f} | {len(item['candidates'])} matching loans\n\n")
            
            if len(self.review_txns) > 5:
                self.preview_text.insert("end", f"  ... and {len(self.review_txns) - 5} more\n\n")
        
        # Duplicates
        if self.duplicate_txns:
            self.preview_text.insert("end", f"""
╔════════════════════════════════════════════════════════════════════════════╗
║ ⊘ DUPLICATES - WILL BE SKIPPED ({len(self.duplicate_txns)})""")
            self.preview_text.insert("end", " " * (75 - len(f"DUPLICATES - WILL BE SKIPPED ({len(self.duplicate_txns)})")) + "║\n")
            self.preview_text.insert("end", "╚════════════════════════════════════════════════════════════════════════════╝\n\n")
            
            for item in self.duplicate_txns[:5]:
                txn = item['txn']
                self.preview_text.insert("end", 
                    f"  {txn['date']} | {txn['borrower_name']:20} | {txn['txn_type']:20} | ₹{txn['amount']:>10,.0f}\n\n")
            
            if len(self.duplicate_txns) > 5:
                self.preview_text.insert("end", f"  ... and {len(self.duplicate_txns) - 5} more\n\n")
        
        # Errors
        if self.error_txns:
            self.preview_text.insert("end", f"""
╔════════════════════════════════════════════════════════════════════════════╗
║ ✗ ERRORS - WILL BE SKIPPED ({len(self.error_txns)})""")
            self.preview_text.insert("end", " " * (75 - len(f"ERRORS - WILL BE SKIPPED ({len(self.error_txns)})")) + "║\n")
            self.preview_text.insert("end", "╚════════════════════════════════════════════════════════════════════════════╝\n\n")
            
            for item in self.error_txns[:5]:
                txn = item['txn']
                self.preview_text.insert("end", 
                    f"  Row {txn['row_num']}: {txn['borrower_name']}\n"
                    f"    Error: {item['error']}\n\n")
            
            if len(self.error_txns) > 5:
                self.preview_text.insert("end", f"  ... and {len(self.error_txns) - 5} more\n\n")
        
        self.preview_text.configure(state=DISABLED)
    
    # ════════════════════════════════════════════════════════════════════════════
    # STEP 3: RESULTS
    # ════════════════════════════════════════════════════════════════════════════
    
    def _build_step3(self, parent):
        """Step 3: Import complete - show results"""
        frame = ctk.CTkFrame(parent, fg_color=BG)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        
        # Header
        ctk.CTkLabel(frame, text="Step 3: Import Complete",
                    font=ctk.CTkFont("Segoe UI", 18, "bold"),
                    text_color=TEXT).grid(row=0, column=0, padx=30, pady=20, sticky="w")
        
        # Summary cards
        cards_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cards_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(0, 20))
        cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.result_cards = {}
        
        card_configs = [
            ('imported', 'Imported', GREEN),
            ('matched', 'Matched', ACCENT),
            ('duplicates', 'Duplicates', AMBER),
            ('errors', 'Errors', RED),
        ]
        
        for col, (key, label, color) in enumerate(card_configs):
            card = ctk.CTkFrame(cards_frame, fg_color=CARD,
                               border_width=1, border_color=BORDER,
                               corner_radius=12)
            card.grid(row=1, column=col, padx=8, sticky="ew")
            
            ctk.CTkLabel(card, text=label,
                        font=ctk.CTkFont("Segoe UI", 11),
                        text_color=MUTED).pack(pady=(12, 4), padx=10)
            
            val_label = ctk.CTkLabel(card, text="0",
                                    font=ctk.CTkFont("Segoe UI", 26, "bold"),
                                    text_color=color)
            val_label.pack(pady=(0, 12), padx=10)
            
            self.result_cards[key] = val_label
        
        # Results text
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=30, pady=20)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        
        ctk.CTkLabel(content, text="Import Details:",
                    font=ctk.CTkFont("Segoe UI", 12, "bold"),
                    text_color=TEXT).pack(anchor="w", pady=(0, 10))
        
        text_frame = ctk.CTkFrame(content, fg_color=CARD,
                                 border_width=1, border_color=BORDER,
                                 corner_radius=8)
        text_frame.pack(fill="both", expand=True, pady=10)
        
        self.result_text = Text(text_frame, height=15, width=120,
                               bg=CARD, fg=TEXT, font=("Courier", 10),
                               insertbackground=TEXT, relief="flat", border=0,
                               wrap="word")
        self.result_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Close button
        ctk.CTkButton(frame, text="✓ Close", width=120, height=40,
                     fg_color=GREEN, hover_color="#27A060",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     command=self.destroy).grid(row=2, column=0, padx=30, pady=20)
        
        return frame
    
    # ════════════════════════════════════════════════════════════════════════════
    # IMPORT EXECUTION
    # ════════════════════════════════════════════════════════════════════════════
    
    def _start_import(self):
        """Import matched transactions atomically (all-or-nothing)."""
        if len(self.matched_txns) == 0 and len(self.review_txns) == 0:
            messagebox.showwarning("No Data", "No valid transactions to import")
            return
        
        if not messagebox.askyesno("Confirm Import", 
            f"Import {len(self.matched_txns)} transactions?\n\n"
            f"({len(self.review_txns)} will need manual review)\n"
            f"({len(self.duplicate_txns)} duplicates will be skipped)\n"
            f"({len(self.error_txns)} errors will be skipped)"):
            return
        
        print("[IMPORT] Starting atomic import...")
        
        batch = []
        for item in self.matched_txns:
            txn = item['txn']
            loan = item['loan']
            batch.append({
                "borrower_id": loan["borrower_id"],
                "loan_id": loan["loan_id"],
                "txn_type": txn["txn_type"],
                "amount": txn["amount"],
                "txn_date": txn["date"],
                "notes": txn.get("notes", ""),
                "payment_mode": txn.get("payment_mode"),
            })

        imported = 0
        failed = 0
        error_message = ""

        if batch:
            try:
                imported = db.add_transactions_batch(batch)
            except Exception as e:
                print(f"[IMPORT] Batch failed — rolled back: {e}")
                imported = 0
                failed = len(batch)
                error_message = str(e)
                messagebox.showerror(
                    "Import Failed",
                    f"Import was rolled back. No transactions were saved.\n\n{error_message}"
                )

        # Historical rebuild is deferred to Stage 5 (schema/principal model mismatch).
        print("[IMPORT] Skipping historical rebuild (deferred to Stage 5)")

        print(f"[IMPORT] Complete - {imported} imported, {failed} failed")
        self._show_results(imported, failed, error_message=error_message)
        
        # Advance to step 3
        self._advance_to_step3()
    
    def _show_results(self, imported, failed, error_message: str = ""):
        """Display import results"""
        self.result_cards['imported'].configure(text=str(imported))
        self.result_cards['matched'].configure(text=str(len(self.matched_txns)))
        self.result_cards['duplicates'].configure(text=str(len(self.duplicate_txns)))
        self.result_cards['errors'].configure(text=str(len(self.error_txns) + (1 if failed else 0)))
        
        if failed:
            status_line = "Status: ✗ IMPORT ROLLED BACK (no rows saved)"
            rebuild_note = "Financial metrics were not recalculated."
            fail_line = f"✗ Batch failures:        {failed}\n✗ Error: {error_message}\n"
        else:
            status_line = "Status: ✓ IMPORT SUCCESSFUL"
            rebuild_note = (
                "Note: historical metric rebuild is deferred (Stage 5).\n"
                "Dashboard values use live calculations from transactions."
            )
            fail_line = ""

        result_text = f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                         IMPORT COMPLETED                                   ║
╚════════════════════════════════════════════════════════════════════════════╝

✓ Imported:              {imported}
⊘ Duplicates (skipped):  {len(self.duplicate_txns)}
✗ Prefail errors (skip): {len(self.error_txns)}
{fail_line}
{rebuild_note}

{status_line}
"""
        
        self.result_text.configure(state=NORMAL)
        self.result_text.insert("1.0", result_text)
        self.result_text.configure(state=DISABLED)
    
    # ════════════════════════════════════════════════════════════════════════════
    # WIZARD NAVIGATION
    # ════════════════════════════════════════════════════════════════════════════
    
    def _advance_to_step2(self):
        """Move to step 2"""
        print("[WIZARD] Advancing to step 2")
        self.step1.grid_remove()
        self.step2.grid()
        self.current_step = 2
    
    def _back_to_step1(self):
        """Go back to step 1"""
        print("[WIZARD] Going back to step 1")
        self.step2.grid_remove()
        self.step1.grid()
        self.current_step = 1
    
    def _advance_to_step3(self):
        """Move to step 3"""
        print("[WIZARD] Advancing to step 3")
        self.step2.grid_remove()
        self.step3.grid()
        self.current_step = 3