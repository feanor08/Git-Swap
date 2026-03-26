"""
gitswap/ui/widgets.py
---------------------
Reusable tkinter widget factory functions.

Every function accepts a `parent` Frame and returns either a widget or a
StringVar.  All styling is sourced from theme.py so visual changes only
require editing one file.

Functions
---------
  lbl()               Plain label inheriting parent background.
  card_frame()        Flat "card" frame with surface background.
  spacer()            Invisible vertical gap.
  field_row()         Label + single-line Entry.  Returns StringVar.
  platform_selector() Toggle-button group + host field.
                      Returns (platform_var, host_var).
"""

import tkinter as tk

from gitswap.constants import PLATFORMS
from gitswap.ui.theme import C, FB, FM, FS


# ── Basic building blocks ─────────────────────────────────────────────────────

def lbl(parent, text: str, *, fg: str | None = None, font=FB, **kw) -> tk.Label:
    """Plain label that inherits the parent's background colour."""
    return tk.Label(
        parent, text=text,
        bg=parent["bg"], fg=fg or C["text"],
        font=font, **kw,
    )


def card_frame(parent, **kw) -> tk.Frame:
    """A flat 'card' frame using the surface background colour."""
    return tk.Frame(parent, bg=C["card"], **kw)


def spacer(parent, h: int = 8) -> tk.Frame:
    """Invisible vertical spacer of height `h` pixels."""
    return tk.Frame(parent, bg=parent["bg"], height=h)


# ── Form components ───────────────────────────────────────────────────────────

def field_row(parent, label_text: str, default: str = "") -> tk.StringVar:
    """
    A fixed-width label followed by a single-line text entry, both packed
    into `parent`.

    Returns the StringVar tied to the Entry so the caller can read or set
    the value without holding a reference to the widget itself.
    """
    row = tk.Frame(parent, bg=C["card"])
    row.pack(fill="x", padx=16, pady=3)

    tk.Label(
        row, text=label_text,
        bg=C["card"], fg=C["muted"],
        font=FM, width=13, anchor="w",
    ).pack(side="left")

    var = tk.StringVar(value=default)
    tk.Entry(
        row,
        textvariable=var,
        bg=C["card2"], fg=C["text"],
        insertbackground=C["text"],
        relief="flat", font=FB,
        highlightbackground=C["border"],
        highlightthickness=1,
    ).pack(side="left", fill="x", expand=True, ipady=5, padx=(8, 0))

    return var


def platform_selector(
    parent,
    prefill_platform: str = "GitHub",
    prefill_host: str = "",
) -> tuple[tk.StringVar, tk.StringVar]:
    """
    A row of platform toggle-buttons followed by an editable host field.

    Behaviour:
      - Clicking GitHub / GitLab / Bitbucket auto-fills the host field with
        the canonical hostname and locks it to read-only.
      - Clicking Other unlocks the host field for free-text entry.
      - The active button is highlighted in the accent colour.

    Returns:
      platform_var  StringVar tracking the selected platform name.
      host_var      StringVar tracking the SSH hostname.
    """
    platform_var = tk.StringVar(value=prefill_platform)
    host_var     = tk.StringVar(value=prefill_host or PLATFORMS.get(prefill_platform, ""))

    # ── Platform button row ───────────────────────────────────────────────
    btn_row = tk.Frame(parent, bg=C["card"])
    btn_row.pack(fill="x", padx=16, pady=(6, 3))

    tk.Label(
        btn_row, text="Platform",
        bg=C["card"], fg=C["muted"],
        font=FM, width=13, anchor="w",
    ).pack(side="left")

    btn_container = tk.Frame(btn_row, bg=C["card"])
    btn_container.pack(side="left")

    buttons: dict[str, tk.Button] = {}
    host_entry_ref: list = [None]   # filled once the Entry is created below

    def select(name: str) -> None:
        """Highlight the chosen button and lock/unlock the host field."""
        platform_var.set(name)

        # Auto-fill host for known platforms
        known = PLATFORMS.get(name, "")
        if known:
            host_var.set(known)

        # Update button styles
        for n, b in buttons.items():
            if n == name:
                b.configure(bg=C["accent"], fg=C["sel_fg"],
                            font=("Helvetica Neue", 10, "bold"))
            else:
                b.configure(bg=C["card2"], fg=C["muted"], font=FM)

        # Lock host for known platforms; unlock for "Other"
        entry = host_entry_ref[0]
        if entry:
            if name == "Other":
                entry.configure(state="normal", fg=C["text"])
            else:
                entry.configure(state="readonly", fg=C["muted"])

    for name in PLATFORMS:
        btn = tk.Button(
            btn_container, text=name,
            bg=C["card2"], fg=C["muted"],
            activebackground=C["accent"], activeforeground=C["sel_fg"],
            font=FM, relief="flat", cursor="hand2",
            padx=10, pady=4,
            command=lambda n=name: select(n),
        )
        btn.pack(side="left", padx=(0, 4))
        buttons[name] = btn

    # ── Host field ────────────────────────────────────────────────────────
    host_row = tk.Frame(parent, bg=C["card"])
    host_row.pack(fill="x", padx=16, pady=3)

    tk.Label(
        host_row, text="Host",
        bg=C["card"], fg=C["muted"],
        font=FM, width=13, anchor="w",
    ).pack(side="left")

    host_entry = tk.Entry(
        host_row,
        textvariable=host_var,
        bg=C["card2"], fg=C["muted"],
        insertbackground=C["text"],
        relief="flat", font=FB,
        highlightbackground=C["border"],
        highlightthickness=1,
        state="readonly",           # locked until "Other" is selected
    )
    host_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(8, 0))
    host_entry_ref[0] = host_entry

    # Apply the initial selection (highlights button, locks/unlocks host)
    select(prefill_platform)
    if prefill_platform == "Other" and prefill_host:
        host_var.set(prefill_host)

    return platform_var, host_var
