"""
Import Template Generator - Export Excel template for new import format
"""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from datetime import date
from typing import List, Tuple

class ImportTemplateGenerator:
    """Generate pre-filled Excel import template"""
    
    def __init__(self, db_path: str, output_path: str):
        self.db_path = db_path
        self.output_path = output_path
    
    def generate(self, loan_matcher) -> bool:
        """
        Generate Excel template with:
        - Headers
        - Sample row
        - Dropdown lists for borrower + due day combinations
        """
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Daily Transactions"
            
            # Styles
            header_fill = PatternFill(start_color="4F8EF7", end_color="4F8EF7", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF", size=11)
            header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            border = Border(
                left=Side(style="thin"),
                right=Side(style="thin"),
                top=Side(style="thin"),
                bottom=Side(style="thin")
            )
            
            # Headers
            headers = ["Date", "Borrower Name", "Due Day", "Transaction Type", "Amount", "Payment Mode", "Notes"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_alignment
                cell.border = border
            
            # Column widths
            ws.column_dimensions['A'].width = 14  # Date
            ws.column_dimensions['B'].width = 20  # Borrower Name
            ws.column_dimensions['C'].width = 10  # Due Day
            ws.column_dimensions['D'].width = 20  # Transaction Type
            ws.column_dimensions['E'].width = 12  # Amount
            ws.column_dimensions['F'].width = 15  # Payment Mode
            ws.column_dimensions['G'].width = 25  # Notes

            date_format = "YYYY-MM-DD"
            for row in range(2, 101):
                cell = ws.cell(row=row, column=1)
                cell.number_format = date_format

            # Sample data row — Date is a real Excel date, not a text string
            sample_row = 2
            sample_date = ws.cell(row=sample_row, column=1, value=date.today())
            sample_date.number_format = date_format
            ws.cell(row=sample_row, column=2, value="Borrower Name")
            ws.cell(row=sample_row, column=3, value=5)
            ws.cell(row=sample_row, column=4, value="Interest Received")
            ws.cell(row=sample_row, column=5, value=3000)
            ws.cell(row=sample_row, column=6, value="Cash")
            ws.cell(row=sample_row, column=7, value="Example note")
            
            # Add data validation for dropdowns
            self._add_dropdowns(ws, loan_matcher)
            
            # Freeze header row
            ws.freeze_panes = "A2"
            
            wb.save(self.output_path)
            return True
        
        except Exception as e:
            print(f"Error generating template: {e}")
            return False
    
    def _add_dropdowns(self, ws, loan_matcher):
        """Add dropdown lists for borrower + due day combinations"""
        try:
            # Get all borrower + due day pairs
            pairs = loan_matcher.get_borrower_due_days()
            
            # Create hidden sheet for validation data
            data_ws = ws.parent.create_sheet("Validation Data")
            
            # Populate validation data (2 columns: Borrower, DueDay)
            for row, (borrower, due_day) in enumerate(pairs, 1):
                data_ws.cell(row=row, column=1, value=borrower)
                data_ws.cell(row=row, column=2, value=due_day)
            
            # Hide validation data sheet
            data_ws.sheet_state = 'hidden'
            
            # Create named ranges for dropdowns (optional - for advanced users)
            # For now, just add basic validation to first 100 rows
            
            date_dv = DataValidation(
                type="date",
                operator="between",
                formula1="DATE(1990,1,1)",
                formula2="DATE(2100,12,31)",
                allow_blank=True,
            )
            date_dv.errorTitle = "Invalid date"
            date_dv.error = "Enter a real date in the Date column. Excel can pick the date for you."
            date_dv.promptTitle = "Date"
            date_dv.prompt = "Pick a date in Excel, or type a date. It will be stored as YYYY-MM-DD."
            date_dv.showInputMessage = True
            date_dv.showErrorMessage = True
            ws.add_data_validation(date_dv)
            date_dv.add("A2:A100")

            # Transaction Type dropdown
            txn_types = DataValidation(type="list", formula1='"Interest Received,Principal Received,Loan Given,Adjustment"')
            txn_types.error = 'Must be one of: Interest Received, Principal Received, Loan Given, Adjustment'
            txn_types.errorTitle = 'Invalid Transaction Type'
            ws.add_data_validation(txn_types)
            txn_types.add(f'D2:D100')
            
            # Payment Mode dropdown
            payment_modes = DataValidation(type="list", formula1='"Cash,Online,Cheque,UPI"')
            payment_modes.error = 'Must be one of: Cash, Online, Cheque, UPI'
            payment_modes.errorTitle = 'Invalid Payment Mode'
            ws.add_data_validation(payment_modes)
            payment_modes.add(f'F2:F100')
            
        except Exception as e:
            print(f"Error adding dropdowns: {e}")