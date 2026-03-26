"""
gitswap/ui/theme.py
-------------------
Visual constants: color palette and typography.

Kept as plain dicts and tuples (zero tkinter imports) so this module loads
instantly, can be unit-tested in isolation, and can be swapped for a light
theme without touching any widget code.

Color palette — macOS-inspired dark mode
  bg      window / outer background
  card    surface background (sections, cards)
  card2   input field background (slightly lighter than card)
  text    primary text
  muted   secondary / hint text
  accent  primary action color (blue buttons, active states)
  success confirmation badge (green)
  border  divider lines and Entry highlight rings
  sel_fg  foreground used on top of accent background (must be dark)

Typography — all fonts ship with macOS
  FT   Screen title       Helvetica Neue 20 bold
  FS   Section heading    Helvetica Neue 13 bold
  FB   Body / input       Helvetica Neue 12
  FM   Small / hint       Helvetica Neue 10
  FMO  Monospace examples Menlo 11
"""

# ── Colors ────────────────────────────────────────────────────────────────────

C: dict[str, str] = {
    "bg":      "#1c1c1e",
    "card":    "#2c2c2e",
    "card2":   "#3a3a3c",
    "text":    "#ffffff",
    "muted":   "#8e8e93",
    "accent":  "#0a84ff",
    "success": "#30d158",
    "border":  "#48484a",
    "sel_fg":  "#000000",
}

# ── Fonts ─────────────────────────────────────────────────────────────────────

FT  = ("Helvetica Neue", 20, "bold")
FS  = ("Helvetica Neue", 13, "bold")
FB  = ("Helvetica Neue", 12)
FM  = ("Helvetica Neue", 10)
FMO = ("Menlo", 11)
