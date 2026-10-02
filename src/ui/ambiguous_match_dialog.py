"""
Ambiguous Match Dialog - Resolve multiple loan matches interactively
"""

import customtkinter as ctk
from tkinter import messagebox

# Colors (match your app theme)
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


class AmbiguousMatchDialog(ctk.CTkToplevel):
    """Dialog for resolving ambiguous loan matches"""
    
    def __init__(self, parent, borrower_name: str, due_day: int, 
                 candidates: list, txn_data: dict):
        super().__init__(parent)
        self.title("Multiple Loans Found - Select One")
        self.geometry("700x500")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.grab_set()
        self.lift()
        
        self.borrower_name = borrower_name
        self.due_day = due_day
        self.candidates = candidates
        self.txn_data = txn_data
        self.selected_loan = None
        self.skip = False
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the dialog"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        hdr = ctk.CTkLabel(self, 
                          text=f"Multiple loans found for {self.borrower_name} (Due Day {self.due_day})",
                          font=ctk.CTkFont("Segoe UI", 14, "bold"),
                          text_color=TEXT)
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        
        # Transaction info
        info_frame = ctk.CTkFrame(self, fg_color=CARD,
                                 border_width=1, border_color=BORDER,
                                 corner_radius=8)
        info_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(0, 20), 
                       ipady=10)
        info_frame.grid_columnconfigure(1, weight=1)
        
        info_text = (f"Date: {self.txn_data['date']} | "
                    f"Type: {self.txn_data['txn_type']} | "
                    f"Amount: ₹{self.txn_data['amount']:,.0f}")
        
        ctk.CTkLabel(info_frame, text=info_text,
                    font=ctk.CTkFont("Segoe UI", 11),
                    text_color=MUTED).grid(row=0, column=0, columnspan=2,
                                          sticky="ew", padx=10)
        
        # Candidates frame
        ctk.CTkLabel(self, text="Select the correct loan:",
                    font=ctk.CTkFont("Segoe UI", 12, "bold"),
                    text_color=TEXT).grid(row=1, column=0, sticky="w", 
                                         padx=20, pady=(0, 10))
        
        candidates_frame = ctk.CTkScrollableFrame(self, fg_color=CARD,
                                                 border_width=1, border_color=BORDER,
                                                 corner_radius=8)
        candidates_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        self.grid_rowconfigure(2, weight=1)
        
        self.selected_var = ctk.StringVar()
        
        for idx, candidate in enumerate(self.candidates):
            self._create_candidate_button(candidates_frame, idx, candidate)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=20)
        btn_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(btn_frame, text="Skip This Row", width=120, height=36,
                     fg_color=AMBER, hover_color="#E8962C",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     command=self._skip).grid(row=0, column=0, padx=8)
        
        ctk.CTkButton(btn_frame, text="Select & Continue", width=140, height=36,
                     fg_color=GREEN, hover_color="#27A060",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     command=self._confirm).grid(row=0, column=2, padx=8)
    
    def _create_candidate_button(self, parent, idx: int, candidate: dict):
        """Create a selectable candidate loan button"""
        btn = ctk.CTkFrame(parent, fg_color=CARD2,
                          border_width=2, border_color=BORDER,
                          corner_radius=8,
                          height=80)
        btn.pack(fill="x", pady=6, padx=2)
        btn.grid_propagate(False)
        btn.grid_columnconfigure(1, weight=1)
        
        # Radio button
        radio_var = ctk.StringVar(value="")
        radio = ctk.CTkCheckBox(btn, text="", variable=radio_var,
                               onvalue=str(idx), offvalue="",
                               command=lambda: self.selected_var.set(str(idx)))
        radio.grid(row=0, column=0, sticky="w", padx=10, pady=8)
        
        # Loan info
        info_frame = ctk.CTkFrame(btn, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", padx=10, pady=8)
        info_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(info_frame, 
                    text=f"{candidate['loan_id']} | Start: {candidate['start_date']}",
                    font=ctk.CTkFont("Segoe UI", 11, "bold"),
                    text_color=TEXT).grid(row=0, column=0, columnspan=2, sticky="w")
        
        ctk.CTkLabel(info_frame, 
                    text=f"Principal: ₹{candidate['principal']:,.0f}",
                    font=ctk.CTkFont("Segoe UI", 10),
                    text_color=MUTED).grid(row=1, column=0, sticky="w", pady=2)
        
        ctk.CTkLabel(info_frame, 
                    text=f"Outstanding: ₹{candidate['outstanding_principal']:,.0f}",
                    font=ctk.CTkFont("Segoe UI", 10),
                    text_color=MUTED).grid(row=1, column=1, sticky="e")
        
        ctk.CTkLabel(info_frame, 
                    text=f"Interest Rate: {candidate['interest_rate']}% | Expected: ₹{candidate['expected_interest']:,.0f}/mo",
                    font=ctk.CTkFont("Segoe UI", 10),
                    text_color=GREEN).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)
        
        # Store reference
        if idx == 0:
            radio.select()
            self.selected_var.set("0")
    
    def _confirm(self):
        """Confirm selection"""
        try:
            idx = int(self.selected_var.get())
            self.selected_loan = self.candidates[idx]
            self.destroy()
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Please select a loan")
    
    def _skip(self):
        """Skip this row"""
        self.skip = True
        self.destroy()
    
    def get_result(self) -> Tuple[dict, bool]:
        """Return (selected_loan, skip_flag)"""
        return self.selected_loan, self.skip