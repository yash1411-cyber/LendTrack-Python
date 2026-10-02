# LendTrack – Private Money Lending Tracker

A modern offline Windows desktop application for tracking private money loans
with monthly interest, overdue tracking, and Excel reporting.

---

## 📁 Folder Structure

```
LendTrack/
├── main.py              # Entry point – main window + sidebar navigation
├── database.py          # SQLite layer – all DB logic & interest calculations
├── ui_dashboard.py      # Dashboard: summary cards + due-today list
├── ui_borrowers.py      # Borrower management (add/edit/delete/search)
├── ui_loans.py          # Loan management (multiple loans per borrower)
├── ui_transactions.py   # Daily transaction entry + history
├── ui_reports.py        # Borrower-wise report + Excel export
├── requirements.txt     # Python dependencies
├── build.bat            # One-click Windows EXE builder
└── lendtrack.db         # Auto-created SQLite database (on first run)
```

---

## ⚙️ Prerequisites

- Python 3.10 or 3.11 (recommended)
- Windows 10 / 11

---

## 🚀 How to Run Locally

### 1. Install Python
Download from https://python.org and check **"Add Python to PATH"** during install.

### 2. Install dependencies
Open Command Prompt in the project folder:
```
pip install -r requirements.txt
```

### 3. Run the app
```
python main.py
```

The SQLite database (`lendtrack.db`) is created automatically on first run in
the same folder as `main.py`.

---

## 📦 Package as Windows .EXE

### Quick build (double-click)
```
build.bat
```

### Manual build
```cmd
pip install pyinstaller

pyinstaller --onefile --windowed --name "LendTrack" ^
  --add-data "%LOCALAPPDATA%\Programs\Python\Python311\Lib\site-packages\customtkinter;customtkinter" ^
  --hidden-import customtkinter ^
  --hidden-import openpyxl ^
  main.py
```

The `.exe` will appear in the `dist\` folder.  
Copy `LendTrack.exe` anywhere – it runs fully offline. The database is created
next to the `.exe` on first launch.

> **Tip**: If PyInstaller cannot find the customtkinter path, replace the
> `%LOCALAPPDATA%\...` path with the actual location shown by:
> `python -c "import customtkinter; print(customtkinter.__file__)"`

---

## 💡 Interest Tracking Logic

```
Principal     = ₹1,00,000
Monthly Rate  = 3%
Expected/mo   = ₹3,000

If borrower pays ₹2,000:
  Pending     = ₹1,000   (stored, NOT compounded)

Next month expected = ₹3,000 (on principal) + ₹1,000 (overdue)
```

- Interest is **only** calculated on outstanding **principal**.
- Overdue interest accumulates as a running total — **never compounded**.
- Principal repayments directly reduce the outstanding principal on that loan.

---

## 🖥️ Screens

| Screen       | Features |
|---|---|
| Dashboard    | 5 summary cards, borrowers due today |
| Borrowers    | Add / Edit / Delete / Search (B001, B002…) |
| Loans        | Multiple loans per borrower, interest preview (L001, L002…) |
| Transactions | Quick entry, history table, delete entries |
| Reports      | Full summary table, Excel export |

---

## 🗄️ Database Tables

| Table             | Purpose |
|---|---|
| `borrowers`       | Borrower profiles |
| `loans`           | Loan records linked to borrowers |
| `transactions`    | All financial entries |
| `interest_ledger` | Monthly interest cycle tracking |

---

## 📤 Excel Export

Click **"Export to Excel"** on the Reports screen.  
Requires `openpyxl` (included in `requirements.txt`).
