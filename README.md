# LendTrack – Private Money Lending Tracker

Offline Windows desktop app for tracking private money loans: borrowers, loans,
outstanding principal, monthly interest, payments, Excel import, and reports.

Python **3.11 is preferred**. Python 3.10 also works. Windows 10 or 11.

---

## Fresh setup on a new Windows laptop

### 1. Clone the repository

```cmd
git clone <repository-url>
cd LendTrack-Python
```

### 2. Install Python

Install **Python 3.11** from https://www.python.org/downloads/

During setup:

- Check **Add python.exe to PATH**
- Use the official installer (not the Microsoft Store build if you can avoid it)

CustomTkinter needs **Tkinter** (Tcl/Tk). The official python.org installer includes it.
If `import tkinter` fails later, reinstall Python and enable **tcl/tk**.

### 3. Create and activate a virtual environment

From the repository root:

```cmd
py -3.11 -m venv .venv
.venv\Scripts\activate
```

`.venv` is local to this machine. Do **not** commit it (it is gitignored).

### 4. Install runtime dependencies

```cmd
pip install -r requirements.txt
```

This installs:

- `customtkinter` — desktop UI (requires Tkinter)
- `openpyxl` — Excel template and report export
- `pandas` — reading Excel import files
- `pyinstaller` — optional Windows EXE packaging

### 5. Confirm Tkinter

With the venv active:

```cmd
python -c "import tkinter; import customtkinter; print('Tkinter and CustomTkinter OK')"
```

### 6. Run the application

```cmd
python main.py
```

Or double-click **`LendTrack.bat`** in the repo root. The launcher:

- uses this folder (no machine-specific paths)
- prefers `.venv\Scripts\python.exe` if it exists
- otherwise falls back to `py -3.11`

`LendTrack.vbs` is an optional companion that starts `.venv` with `pythonw` (no console). It does not fall back to `py -3.11`; use the `.bat` if the venv is missing.

### 7. Where the database lives

**Source run** (Python / `LendTrack.bat`):
`lendtrack.db` is created next to `database.py` / `main.py` (the repository root).

**Frozen PyInstaller EXE**:
`%LOCALAPPDATA%\LendTrack\lendtrack.db`

The source database and the frozen EXE database are separate. The app does
**not** automatically copy, migrate, import, or seed the repository database
into the EXE location.

- `lendtrack.db` is **local financial data**. It is gitignored. Do not commit it.
- Normal startup **creates tables if they are missing**.
- Normal startup **does not** seed demo data.
- Normal startup **does not** reset or overwrite an existing database file.

### 8. Run tests (development)

`pytest` is **not** a runtime dependency. Install it in the venv when you need tests:

```cmd
pip install pytest
pytest -q
```

---

## Project structure

```
LendTrack-Python/
├── main.py                 # Window, sidebar, navigation
├── database.py             # SQLite path, schema, accounting queries
├── ui_dashboard.py
├── ui_borrowers.py
├── ui_loans.py
├── ui_transactions.py
├── ui_reports.py
├── LendTrack.bat           # Dev launcher (repo-relative)
├── LendTrack.vbs           # Optional silent launcher (venv pythonw)
├── build.bat               # Portable PyInstaller build
├── requirements.txt
├── src/
│   ├── ui/                 # Theme, import dialogs, date picker
│   └── services/           # Excel import, matching, template, rebuild
├── tests/                  # pytest suite (uses temporary databases)
└── scripts/                # Dev-only helpers (see warning below)
```

`lendtrack.db` appears in this folder after the first run; it is not in git.

---

## Interest and principal (current model)

Documentation only — the application already implements this.

- **Original Principal** is the foundational **Loan Given** amount for that loan.
- **Outstanding** is derived from transactions (Loan Given minus Principal Received).
- **Expected monthly interest** is calculated on the **current outstanding principal**, not on a reduced “balance column”.
- **Principal Received** reduces outstanding; it does not rewrite Original Principal.
- **Interest Received** does not reduce outstanding.
- Editing a loan updates that loan’s existing Loan Given. It must **not** create another Loan Given.
- Close / Reopen change status only; history and loan identity stay.

Example: Original Principal ₹1,00,000, monthly rate 3%. Expected interest starts at ₹3,000.
After ₹20,000 Principal Received, outstanding is ₹80,000 and expected monthly interest is ₹2,400.
Unpaid expected interest can accumulate as pending; it is **not compounded** into principal.

---

## Excel import (current behaviour)

From **Transactions**:

- **Export Template** writes an Excel workbook (`Daily Transactions` sheet).
- **Import Excel** reads that sheet. Nothing is saved until you confirm **Import Now**.

Supported payment types in the UI and in newly generated templates:
**Interest Received**, **Principal Received**. Older workbooks may still
contain other type names; the import engine does not silently create
borrowers or loans, and unsupported types fail rather than invent data.

Dates: existing text formats such as `YYYY-MM-DD` still import. New templates
use real Excel date cells formatted as `YYYY-MM-DD`.

Workflow:

1. Review classified rows (ready / needs review / duplicate / cannot import).
2. Ambiguous or similar-name matches require an explicit **Select** or **Skip**.
   Closing that dialog skips the row; it does not pick a loan.
3. Duplicates are not imported again.
4. Writes are atomic: a failed batch rolls back; no partial import.
5. Result titles stay honest (complete / skipped rows / none / failed).

---

## Reports Excel export

**Reports → Export to Excel** writes a borrower summary workbook (`openpyxl`).

---

## Package as a Windows EXE

Use the **same venv** that can run the app. From the repo root:

```cmd
.venv\Scripts\activate
build.bat
```

`build.bat` discovers the installed **customtkinter** package from the active
Python interpreter. It does **not** use a hardcoded `C:\Users\...` path.

If customtkinter or PyInstaller is missing, the script stops with a clear error.

Output: `dist\LendTrack.exe`. A frozen EXE stores its database at
`%LOCALAPPDATA%\LendTrack\lendtrack.db` (not next to the extract directory,
and not the repository `lendtrack.db`). Treat that as application-local data.

Do not point a build at a production lending database.

---

## Development-only: seed script

`scripts/seed_dev_db.py` is **development-only** and **destructive**.

It deletes the SQLite file at `database.DB_PATH` and writes synthetic data.
It prints the resolved database path and requires typing **`YES`**
(exact, case-sensitive) before it changes anything. Any other input,
including blank, cancels with no deletion or write.

**Do not run it** against a production database or any `lendtrack.db`
that contains real lending records.

---

## Screens

| Screen       | Role |
|--------------|------|
| Dashboard    | Outstanding, interest summaries, due today, recent activity |
| Borrowers    | Add / edit / delete / search; outstanding and active loan counts |
| Loans        | Multiple loans per borrower; Close / Reopen; original vs outstanding |
| Transactions | Record Interest or Principal Received; history; Excel import |
| Reports      | Borrower summary and Excel export |
