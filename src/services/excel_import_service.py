"""
Excel Import Service - Read and parse Excel transactions file
Now supports BOTH old format (Loan Display Name) and new format (Due Day)
Production-ready code with flexible column detection
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Tuple, Optional

class ExcelImportService:
    """Handles Excel file reading and validation for both old and new formats"""
    
    # Required columns that must exist
    REQUIRED_CORE_COLUMNS = ['Date', 'Borrower Name', 'Transaction Type', 'Amount']
    
    # Either old or new format specific columns
    OLD_FORMAT_COLUMN = 'Loan Display Name'
    NEW_FORMAT_COLUMN = 'Due Day'
    
    # Optional columns
    OPTIONAL_COLUMNS = ['Payment Mode', 'Notes']
    
    VALID_TRANSACTION_TYPES = ['Interest Received', 'Principal Received', 
                               'Loan Given', 'Adjustment']
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.import_format = None  # Will be 'old' or 'new' or 'mixed'
    
    def read_excel(self, file_path: str) -> Tuple[List[Dict], bool]:
        """
        Read Excel file and parse transactions
        Supports both old and new format
        Returns: (transactions_list, success_bool)
        """
        try:
            # Read the 'Daily Transactions' sheet
            df = pd.read_excel(file_path, sheet_name='Daily Transactions')
            
            # Detect format
            self.import_format = self._detect_format(df.columns)
            
            if not self.import_format:
                self.errors.append(
                    f"Excel must have either '{self.OLD_FORMAT_COLUMN}' (old format) "
                    f"or '{self.NEW_FORMAT_COLUMN}' (new format)"
                )
                return [], False
            
            print(f"Detected format: {self.import_format}")
            
            # Validate columns
            if not self._validate_columns(df.columns):
                return [], False
            
            # Convert to list of dicts
            transactions = []
            for idx, row in df.iterrows():
                try:
                    txn = self._parse_row(row, idx + 2)  # +2 because header is row 1
                    if txn:  # Only add if parsing succeeded
                        transactions.append(txn)
                except Exception as e:
                    self.errors.append(f"Row {idx + 2}: {str(e)}")
            
            if not transactions and self.errors:
                return [], False
            
            return transactions, True
        
        except FileNotFoundError:
            self.errors.append(f"File not found: {file_path}")
            return [], False
        except Exception as e:
            self.errors.append(f"Error reading Excel file: {str(e)}")
            return [], False
    
    def _detect_format(self, columns) -> Optional[str]:
        """Detect if file is old format, new format, or mixed"""
        has_old = self.OLD_FORMAT_COLUMN in columns
        has_new = self.NEW_FORMAT_COLUMN in columns
        
        if has_old and has_new:
            return 'mixed'
        elif has_old:
            return 'old'
        elif has_new:
            return 'new'
        else:
            return None
    
    def _validate_columns(self, columns) -> bool:
        """Validate that all required columns exist"""
        columns_list = list(columns)
        
        # Check core required columns
        missing_core = [col for col in self.REQUIRED_CORE_COLUMNS if col not in columns_list]
        if missing_core:
            self.errors.append(f"Missing required columns: {', '.join(missing_core)}")
            return False
        
        return True
    
    def _parse_row(self, row: pd.Series, row_num: int) -> Dict:
        """Parse a single row and validate"""
        
        # Parse date (handle both datetime and string)
        date_val = row['Date']
        if pd.isna(date_val):
            raise ValueError("Date is required")
        
        try:
            if isinstance(date_val, str):
                # Try multiple date formats
                for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%Y-%m-%d']:
                    try:
                        date_obj = datetime.strptime(date_val.strip(), fmt)
                        date_str = date_obj.strftime('%Y-%m-%d')
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"Cannot parse date: {date_val}")
            else:
                # Pandas datetime
                date_str = pd.Timestamp(date_val).strftime('%Y-%m-%d')
        except Exception as e:
            raise ValueError(f"Invalid date format: {str(e)}")
        
        # Parse borrower name
        borrower_name = str(row['Borrower Name']).strip()
        if not borrower_name or borrower_name == 'nan':
            raise ValueError("Borrower Name is required")
        
        # Validate transaction type
        txn_type = str(row['Transaction Type']).strip()
        if txn_type not in self.VALID_TRANSACTION_TYPES:
            raise ValueError(f"Invalid Transaction Type: {txn_type}. Must be one of: {', '.join(self.VALID_TRANSACTION_TYPES)}")
        
        # Parse amount
        try:
            amount = float(row['Amount'])
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            raise ValueError(f"Invalid amount: {row['Amount']}")
        
        # Parse payment mode
        payment_mode = str(row['Payment Mode']).strip() if pd.notna(row.get('Payment Mode')) else 'Cash'
        if payment_mode == 'nan':
            payment_mode = 'Cash'
        
        # Parse notes
        notes = str(row['Notes']).strip() if pd.notna(row.get('Notes')) else ''
        if notes == 'nan':
            notes = ''
        
        result = {
            'date': date_str,
            'borrower_name': borrower_name,
            'txn_type': txn_type,
            'amount': amount,
            'payment_mode': payment_mode,
            'notes': notes,
            'row_num': row_num,
        }
        
        # Handle format-specific fields
        if self.import_format in ('old', 'mixed') and pd.notna(row.get(self.OLD_FORMAT_COLUMN)):
            loan_display = str(row[self.OLD_FORMAT_COLUMN]).strip()
            if loan_display and loan_display != 'nan':
                result['loan_display'] = loan_display
                result['format_type'] = 'old'
        
        if self.import_format in ('new', 'mixed') and pd.notna(row.get(self.NEW_FORMAT_COLUMN)):
            try:
                due_day = int(float(row[self.NEW_FORMAT_COLUMN]))
                if 1 <= due_day <= 31:
                    result['due_day'] = due_day
                    result['format_type'] = 'new'
                else:
                    raise ValueError(f"Due Day must be between 1-31, got {due_day}")
            except (ValueError, TypeError):
                raise ValueError(f"Invalid Due Day: {row[self.NEW_FORMAT_COLUMN]}")
        
        # Validate that we have either old or new format field
        if 'loan_display' not in result and 'due_day' not in result:
            raise ValueError(f"Row must have either '{self.OLD_FORMAT_COLUMN}' or '{self.NEW_FORMAT_COLUMN}'")
        
        return result
    
    def get_errors(self) -> List[str]:
        """Return list of errors"""
        return self.errors
    
    def get_warnings(self) -> List[str]:
        """Return list of warnings"""