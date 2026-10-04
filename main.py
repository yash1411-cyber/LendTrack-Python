"""
main.py - LendTrack: Private Money Lending Tracker
Entry point. Builds the main window, sidebar, and navigation.

Run:   python main.py
Build: pyinstaller --onefile --windowed --name LendTrack main.py
"""

import customtkinter as ctk
from datetime import date
import database as db

# Import screen modules
from ui_dashboard    import DashboardFrame
from ui_borrowers    import BorrowersFrame
from ui_loans        import LoansFrame
from ui_transactions import TransactionsFrame
from ui_reports      import ReportsFrame
from src.ui.theme import (
    BG, SIDEBAR, TEXT, MUTED, BORDER, NAV_HOVER, NAV_ACTIVE,
    font_section, font_overline, font_body, font_meta,
    RADIUS_CONTROL, BTN_HEIGHT, S16, S24,
)

# ── Theme ──────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ── Main Application Window ────────────────────────────────────────────────────

class LendTrackApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        db.initialize_db()

        self.title("LendTrack – Money Lending Tracker")
        self.geometry("1280x780")
        self.minsize(1024, 640)
        self.configure(fg_color=BG)

        # ── Try to set an icon (ignore if not present) ──────────────────────
        try:
            self.iconbitmap("icon.ico")
        except Exception:
            pass

        self._current_screen = None
        self._nav_buttons   = {}
        self._screens       = {}

        self._build_layout()
        self._navigate("Dashboard")

    # ── Layout ─────────────────────────────────────────────────────────────────
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Sidebar ────────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(self, fg_color=SIDEBAR, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(10, weight=1)  # push bottom items down

        # Logo / Brand
        brand = ctk.CTkFrame(sidebar, fg_color="transparent", height=70)
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(20, 8))
        brand.grid_propagate(False)
        name_col = ctk.CTkFrame(brand, fg_color="transparent")
        name_col.pack(side="left")
        ctk.CTkLabel(name_col, text="LendTrack",
                     font=font_section(),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(name_col, text="Lending Manager",
                     font=font_overline(),
                     text_color=MUTED).pack(anchor="w")

        # Divider
        ctk.CTkFrame(sidebar, fg_color=BORDER, height=1
                     ).grid(row=1, column=0, sticky="ew", padx=14, pady=8)

        # Navigation items
        nav_items = [
            "Dashboard",
            "Borrowers",
            "Loans",
            "Transactions",
            "Reports",
        ]
        for ri, label in enumerate(nav_items, start=2):
            btn = self._make_nav_button(sidebar, label)
            btn.grid(row=ri, column=0, sticky="ew", padx=10, pady=3)
            self._nav_buttons[label] = btn

        # Bottom: date
        ctk.CTkLabel(sidebar,
                     text=date.today().strftime("%d %b %Y"),
                     font=font_meta(),
                     text_color=MUTED).grid(row=11, column=0, pady=S24)

        # ── Top header bar (single page-title location) ────────────────────
        topbar = ctk.CTkFrame(self, fg_color=SIDEBAR, height=56, corner_radius=0)
        topbar.grid(row=0, column=1, sticky="ew")
        topbar.grid_propagate(False)
        topbar.grid_columnconfigure(1, weight=1)

        self._page_title = ctk.CTkLabel(
            topbar, text="Dashboard", font=font_section(), text_color=TEXT
        )
        self._page_title.grid(row=0, column=0, padx=S24, sticky="w")

        self._search_var = None
        self._search = ctk.CTkEntry(
            topbar,
            placeholder_text="Search borrowers…",
            width=280,
            height=34,
            fg_color=BG,
            border_color=BORDER,
            text_color=TEXT,
            corner_radius=RADIUS_CONTROL,
        )
        self._search.grid(row=0, column=1, padx=(0, S16), pady=10, sticky="e")
        self._search.bind("<KeyRelease>", self._on_global_search)

        # ── Main content area ──────────────────────────────────────────────
        self._content_area = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._content_area.grid(row=1, column=1, sticky="nsew")
        self._content_area.grid_columnconfigure(0, weight=1)
        self._content_area.grid_rowconfigure(0, weight=1)

    def _make_nav_button(self, parent, label: str) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=f"  {label}",
            anchor="w",
            height=BTN_HEIGHT,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            hover_color=NAV_HOVER,
            text_color=MUTED,
            font=font_body(),
            command=lambda l=label: self._navigate(l),
        )

    # ── Navigation ────────────────────────────────────────────────────────────
    def _navigate(self, label: str, borrower_id=None):
        # Deactivate old button
        if self._current_screen and self._current_screen in self._nav_buttons:
            self._nav_buttons[self._current_screen].configure(
                fg_color="transparent", text_color=MUTED
            )

        # Activate new button
        if label in self._nav_buttons:
            self._nav_buttons[label].configure(
                fg_color=NAV_ACTIVE, text_color=TEXT
            )

        self._page_title.configure(text=label)
        self._current_screen = label

        if label not in self._screens:
            if label == "Dashboard":
                frame = DashboardFrame(
                    self._content_area, on_navigate=self._navigate
                )
            elif label == "Borrowers":
                frame = BorrowersFrame(
                    self._content_area, on_navigate=self._navigate
                )
            else:
                screen_map = {
                    "Loans":        LoansFrame,
                    "Transactions": TransactionsFrame,
                    "Reports":      ReportsFrame,
                }
                cls = screen_map.get(label)
                if not cls:
                    return
                frame = cls(self._content_area)
            self._screens[label] = frame

        for name, frame in self._screens.items():
            if name == label:
                frame.grid(row=0, column=0, sticky="nsew")
                if label == "Loans" and hasattr(frame, "focus_borrower"):
                    frame.focus_borrower(borrower_id)
                else:
                    frame.refresh()
            else:
                frame.grid_remove()

    def _on_global_search(self, *_):
        """Forward search text to Borrowers screen."""
        q = self._search.get()
        if q:
            self._navigate("Borrowers")
            b_screen = self._screens.get("Borrowers")
            if b_screen and hasattr(b_screen, "_search"):
                b_screen._search.delete(0, "end")
                b_screen._search.insert(0, q)
                b_screen._load_table()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = LendTrackApp()
    app.mainloop()
