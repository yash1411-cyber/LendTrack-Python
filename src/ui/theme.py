"""
Shared UI tokens and small helpers (UI Stage 1).

Presentation only. Does not touch accounting, matching, or database behavior.
"""

from __future__ import annotations

import customtkinter as ctk

# ── Colour tokens ──────────────────────────────────────────────────────────
BG = "#0F1117"
SIDEBAR = "#161B27"
CARD = "#1A2030"
CARD2 = "#232A3C"
BORDER = "#2C3347"
TEXT = "#E8EBF2"
MUTED = "#8B93A7"
ACCENT = "#4F8EF7"
HOVER = "#3A72D8"
GREEN = "#2FBF71"
GREEN_HOVER = "#289E5E"
AMBER = "#E0A23A"
RED = "#E85D5D"
NEUTRAL = "#7A849E"
NAV_ACTIVE = "#253354"
NAV_HOVER = "#1E2C4A"
ROW_HOVER = "#243049"
DANGER_HOVER = "#3A2228"

FONT_FAMILY = "Segoe UI"

# ── Spacing / radius ───────────────────────────────────────────────────────
S8 = 8
S12 = 12
S16 = 16
S24 = 24
S32 = 32
CONTENT_PAD = 24

RADIUS_CONTROL = 8
RADIUS_CARD = 12
RADIUS_BADGE = 6

BTN_HEIGHT = 36
BTN_HEIGHT_COMPACT = 28
ROW_PY = 8


def font_title():
    return ctk.CTkFont(FONT_FAMILY, 22, "bold")


def font_section():
    return ctk.CTkFont(FONT_FAMILY, 15, "bold")


def font_body():
    return ctk.CTkFont(FONT_FAMILY, 13)


def font_body_bold():
    return ctk.CTkFont(FONT_FAMILY, 13, "bold")


def font_table():
    return ctk.CTkFont(FONT_FAMILY, 12)


def font_meta():
    return ctk.CTkFont(FONT_FAMILY, 11)


def font_meta_bold():
    return ctk.CTkFont(FONT_FAMILY, 11, "bold")


def font_overline():
    return ctk.CTkFont(FONT_FAMILY, 10)


def fmt_inr(val) -> str:
    """Presentation-only Indian rupee formatting."""
    try:
        return f"₹{float(val):,.0f}"
    except (TypeError, ValueError):
        return "₹0"


def ellipsize(text, max_chars: int = 24) -> str:
    """Visual truncation only — does not change stored data."""
    s = str(text or "").replace("\n", " ").strip()
    if len(s) <= max_chars:
        return s
    return s[: max(1, max_chars - 1)] + "…"


def clamp_dialog_size(width: int, height: int, parent=None) -> str:
    """Keep dialogs inside the screen / parent window so they remain usable at 1024×640."""
    sw, sh = 1280, 780
    try:
        top = None
        if parent is not None:
            top = parent.winfo_toplevel()
        if top is not None:
            sw = int(top.winfo_screenwidth() or sw)
            sh = int(top.winfo_screenheight() or sh)
            pw = int(top.winfo_width() or 0)
            ph = int(top.winfo_height() or 0)
            if pw >= 400:
                sw = min(sw, pw)
            if ph >= 300:
                sh = min(sh, ph)
    except Exception:
        pass
    w = max(360, min(int(width), max(360, sw - 48)))
    h = max(200, min(int(height), max(200, sh - 72)))
    return f"{w}x{h}"


def place_dialog(win, parent=None) -> None:
    """Center a dialog on the parent window so it stays on-screen at 1024×640."""
    try:
        win.update_idletasks()
        top = None
        if parent is not None:
            top = parent.winfo_toplevel()
        elif getattr(win, "master", None) is not None:
            top = win.master.winfo_toplevel()
        if top is None:
            return
        try:
            win.transient(top)
        except Exception:
            pass
        pw = int(top.winfo_width() or 0)
        ph = int(top.winfo_height() or 0)
        px = int(top.winfo_rootx() or 0)
        py = int(top.winfo_rooty() or 0)
        ww = int(win.winfo_width() or win.winfo_reqwidth() or 0)
        hh = int(win.winfo_height() or win.winfo_reqheight() or 0)
        if pw < 50 or ph < 50 or ww < 50 or hh < 50:
            return
        x = px + max(8, (pw - ww) // 2)
        y = py + max(8, (ph - hh) // 2)
        win.geometry(f"+{x}+{y}")
    except Exception:
        pass


def primary_button(parent, text: str, command=None, **kwargs) -> ctk.CTkButton:
    opts = {
        "text": text,
        "command": command,
        "fg_color": ACCENT,
        "hover_color": HOVER,
        "text_color": TEXT,
        "height": BTN_HEIGHT,
        "corner_radius": RADIUS_CONTROL,
        "font": font_body_bold(),
    }
    opts.update(kwargs)
    return ctk.CTkButton(parent, **opts)


def secondary_button(parent, text: str, command=None, **kwargs) -> ctk.CTkButton:
    opts = {
        "text": text,
        "command": command,
        "fg_color": CARD2,
        "hover_color": ROW_HOVER,
        "text_color": TEXT,
        "border_width": 1,
        "border_color": BORDER,
        "height": BTN_HEIGHT,
        "corner_radius": RADIUS_CONTROL,
        "font": font_body(),
    }
    opts.update(kwargs)
    return ctk.CTkButton(parent, **opts)


def success_button(parent, text: str, command=None, **kwargs) -> ctk.CTkButton:
    opts = {
        "text": text,
        "command": command,
        "fg_color": GREEN,
        "hover_color": GREEN_HOVER,
        "text_color": TEXT,
        "height": BTN_HEIGHT,
        "corner_radius": RADIUS_CONTROL,
        "font": font_body_bold(),
    }
    opts.update(kwargs)
    return ctk.CTkButton(parent, **opts)


def danger_button(parent, text: str, command=None, **kwargs) -> ctk.CTkButton:
    """Outline/subordinate destructive control — not a filled primary."""
    opts = {
        "text": text,
        "command": command,
        "fg_color": "transparent",
        "hover_color": DANGER_HOVER,
        "text_color": RED,
        "border_width": 1,
        "border_color": RED,
        "height": BTN_HEIGHT,
        "corner_radius": RADIUS_CONTROL,
        "font": font_body(),
    }
    opts.update(kwargs)
    return ctk.CTkButton(parent, **opts)


def metric_card(
    parent,
    title: str,
    value_color: str = ACCENT,
    prominent: bool = False,
    caption: str = "",
):
    """Label-above-value card. Returns (card, value_label)."""
    card = ctk.CTkFrame(
        parent,
        fg_color=CARD,
        corner_radius=RADIUS_CARD,
        border_width=1,
        border_color=BORDER,
    )
    title_pad = (16, 4) if prominent else (14, 4)
    ctk.CTkLabel(
        card,
        text=title,
        font=font_meta_bold() if prominent else font_overline(),
        text_color=MUTED,
        wraplength=280,
        justify="left",
        anchor="w",
    ).pack(anchor="w", padx=S16, pady=title_pad)
    value_lbl = ctk.CTkLabel(
        card,
        text=fmt_inr(0),
        font=font_title(),
        text_color=value_color,
        anchor="w",
    )
    value_lbl.pack(anchor="w", padx=S16, pady=(0, 4 if caption else 14))
    if caption:
        ctk.CTkLabel(
            card, text=caption, font=font_overline(), text_color=MUTED, anchor="w",
        ).pack(anchor="w", padx=S16, pady=(0, 14))
    return card, value_lbl


def table_header(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent, text=text, font=font_meta_bold(), text_color=MUTED
    )


def table_cell(parent, text: str, color: str = TEXT, wraplength: int = 0, **grid_kwargs) -> ctk.CTkLabel:
    opts = {
        "text": text,
        "font": font_table(),
        "text_color": color,
        "anchor": "w",
        "justify": "left",
    }
    if wraplength:
        opts["wraplength"] = wraplength
    lbl = ctk.CTkLabel(parent, **opts)
    if grid_kwargs:
        lbl.grid(**grid_kwargs)
    return lbl


def bind_row_hover(row, rest_color: str) -> None:
    def _enter(_e=None):
        try:
            row.configure(fg_color=ROW_HOVER)
        except Exception:
            pass

    def _leave(_e=None):
        try:
            row.configure(fg_color=rest_color)
        except Exception:
            pass

    row.bind("<Enter>", _enter)
    row.bind("<Leave>", _leave)


def status_badge(parent, status: str) -> ctk.CTkFrame:
    """Visual pill only — does not change status values."""
    label = status or ""
    active = label.strip().lower() == "active"
    fg = "#163328" if active else CARD2
    accent = GREEN if active else NEUTRAL
    pill = ctk.CTkFrame(
        parent,
        fg_color=fg,
        corner_radius=RADIUS_BADGE,
        border_width=1,
        border_color=accent,
    )
    ctk.CTkLabel(
        pill, text=label, font=font_overline(), text_color=accent
    ).pack(padx=S8, pady=2)
    return pill


def tone_badge(parent, text: str, tone: str = "neutral") -> ctk.CTkFrame:
    """Generic status pill for import/review labels."""
    tones = {
        "success": (GREEN, "#163328"),
        "warning": (AMBER, CARD2),
        "danger": (RED, DANGER_HOVER),
        "info": (ACCENT, NAV_ACTIVE),
        "neutral": (NEUTRAL, CARD2),
    }
    accent, fg = tones.get(tone, tones["neutral"])
    pill = ctk.CTkFrame(
        parent,
        fg_color=fg,
        corner_radius=RADIUS_BADGE,
        border_width=1,
        border_color=accent,
    )
    ctk.CTkLabel(
        pill, text=text, font=font_overline(), text_color=accent
    ).pack(padx=S8, pady=2)
    return pill


def setup_dialog(win, title: str, geometry: str, resizable: bool = False) -> None:
    win.title(title)
    parent = win.master if getattr(win, "master", None) else None
    try:
        w_s, h_s = geometry.lower().split("x", 1)
        geometry = clamp_dialog_size(int(w_s), int(h_s), parent)
    except Exception:
        pass
    win.geometry(geometry)
    win.resizable(resizable, resizable)
    win.configure(fg_color=CARD)
    try:
        win.grab_set()
        win.lift()
        win.focus_force()
    except Exception:
        pass
    win.bind("<Escape>", lambda _e: win.destroy())
    place_dialog(win, parent)


def explain_error(err, fallback: str = "Something went wrong while saving the changes.") -> str:
    """Turn a known exception into short user-facing text. Does not guess unknown causes."""
    raw = str(err or "").strip()
    if not raw:
        return fallback
    head = raw.split(":", 1)[0].strip()
    if head.endswith(("Error", "Exception", "Warning")) and ": " in raw:
        raw = raw.split(":", 1)[1].strip()
    lower = raw.lower()
    if raw.startswith("Traceback") or "traceback (most recent" in lower:
        return fallback
    if "foreign key" in lower:
        return "This borrower cannot be deleted because loan or transaction history exists."
    if "cannot delete borrower" in lower:
        return "This borrower cannot be deleted while loan or transaction history exists."
    if "loan given" in lower and "cannot delete" in lower:
        return "Loan Given is the original loan amount and cannot be deleted."
    if "cannot delete loan" in lower and "transaction" in lower:
        return "This loan cannot be deleted because it has transaction history."
    if "exceeds outstanding" in lower:
        return "This principal payment is larger than the current outstanding amount."
    if "cannot be less than" in lower and "repaid" in lower:
        return "Original Principal cannot be less than the principal already repaid."
    if "unsupported transaction type" in lower or "adjustment transactions" in lower:
        return "That payment type is not allowed."
    if "amount must be positive" in lower:
        return "Enter a valid positive amount."
    if len(raw) > 280:
        return fallback
    return raw


def notify(
    parent,
    title: str,
    body: str,
    tone: str = "info",
    geometry: str = "440x240",
) -> None:
    """Single-button information / success / warning / error dialog."""
    win = ctk.CTkToplevel(parent)
    setup_dialog(win, title, geometry)
    win.grid_columnconfigure(0, weight=1)
    win.grid_rowconfigure(1, weight=1)
    accent = {"success": GREEN, "warning": AMBER, "danger": RED, "error": RED}.get(tone, TEXT)
    ctk.CTkLabel(
        win, text=title, font=font_section(), text_color=accent, anchor="w",
        wraplength=400, justify="left",
    ).grid(row=0, column=0, sticky="ew", padx=S16, pady=(S16, S8))
    ctk.CTkLabel(
        win,
        text=body,
        font=font_body(),
        text_color=MUTED,
        justify="left",
        wraplength=400,
        anchor="w",
    ).grid(row=1, column=0, sticky="nsew", padx=S16, pady=(0, S8))
    bf = ctk.CTkFrame(win, fg_color="transparent")
    bf.grid(row=2, column=0, sticky="ew", padx=S16, pady=S16)
    btn = primary_button(bf, "Close", win.destroy, width=110)
    if tone == "success":
        btn.configure(fg_color=GREEN, hover_color=GREEN_HOVER)
    elif tone in ("danger", "error"):
        btn.configure(fg_color=RED, hover_color=DANGER_HOVER)
    btn.pack(side="right")
    win.bind("<Return>", lambda _e: win.destroy())
    win.wait_window()


def confirm_action(
    parent,
    title: str,
    body: str,
    confirm_text: str,
    danger: bool = False,
    geometry: str = "480x320",
) -> bool:
    """Modal confirm. Returns True only if the user chooses the confirm action."""
    win = ctk.CTkToplevel(parent)
    setup_dialog(win, title, geometry)
    win.grid_columnconfigure(0, weight=1)
    win.grid_rowconfigure(1, weight=1)
    result = {"ok": False}

    ctk.CTkLabel(
        win, text=title, font=font_section(), text_color=TEXT, anchor="w",
        wraplength=440, justify="left",
    ).grid(row=0, column=0, sticky="ew", padx=S16, pady=(S16, S8))
    ctk.CTkLabel(
        win,
        text=body,
        font=font_body(),
        text_color=MUTED,
        justify="left",
        wraplength=440,
        anchor="w",
    ).grid(row=1, column=0, sticky="nsew", padx=S16, pady=(0, S8))

    bf = ctk.CTkFrame(win, fg_color="transparent")
    bf.grid(row=2, column=0, sticky="ew", padx=S16, pady=S16)

    def _yes():
        result["ok"] = True
        win.destroy()

    def _no(_e=None):
        result["ok"] = False
        win.destroy()

    secondary_button(bf, "Cancel", _no, width=110).pack(side="left")
    maker = danger_button if danger else primary_button
    maker(bf, confirm_text, _yes, width=170).pack(side="right")
    win.protocol("WM_DELETE_WINDOW", _no)
    win.bind("<Escape>", _no)
    if not danger:
        win.bind("<Return>", lambda _e: _yes())
    win.wait_window()
    return bool(result["ok"])
