#!/usr/bin/env python3
"""
git_identity_ui.py
------------------
macOS tkinter UI for git_identity_switcher.
Supports any Git hosting platform: GitHub, GitLab, Bitbucket, self-hosted, etc.

First run  → setup form
After setup → dashboard with copy-key buttons + gitSwap usage
"""

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CONFIG_FILE  = Path.home() / ".git_identity_switcher.json"
SCRIPT_DIR   = Path(__file__).parent.resolve()
CLI_SCRIPT   = SCRIPT_DIR / "git_identity_switcher.py"
PERSONAL_PUB = Path.home() / ".ssh" / "id_ed25519_personal.pub"
WORK_PUB     = Path.home() / ".ssh" / "id_ed25519_work.pub"
INSTALL_DIRS = [Path("/usr/local/bin"), Path.home() / ".local" / "bin"]

# ---------------------------------------------------------------------------
# Platform definitions
# ---------------------------------------------------------------------------

PLATFORMS = {
    "GitHub":    "github.com",
    "GitLab":    "gitlab.com",
    "Bitbucket": "bitbucket.org",
    "Other":     "",
}

# ---------------------------------------------------------------------------
# Dark theme
# ---------------------------------------------------------------------------

C = {
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

FT  = ("Helvetica Neue", 20, "bold")
FS  = ("Helvetica Neue", 13, "bold")
FB  = ("Helvetica Neue", 12)
FM  = ("Helvetica Neue", 10)
FMO = ("Menlo", 11)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else None
    except Exception:
        return None

def save_config(data):
    CONFIG_FILE.write_text(json.dumps(data, indent=2))
    CONFIG_FILE.chmod(0o600)

# ---------------------------------------------------------------------------
# System helpers
# ---------------------------------------------------------------------------

def run_cli(*args):
    r = subprocess.run([sys.executable, str(CLI_SCRIPT), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr

def pbcopy(text):
    subprocess.run(["pbcopy"], input=text, text=True, check=True)

def _detect_shell_rc() -> Path | None:
    """Return the rc file for the user's current shell, or None if unknown."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return Path.home() / ".zshrc"
    if "bash" in shell:
        # macOS bash uses .bash_profile for login shells
        bp = Path.home() / ".bash_profile"
        return bp if bp.exists() else Path.home() / ".bashrc"
    return None


def _ensure_path_in_rc(directory: Path) -> str:
    """
    Add `export PATH="<directory>:$PATH"` to the shell rc file if not already there.
    Returns a human-readable message about what happened.
    """
    rc = _detect_shell_rc()
    if rc is None:
        return "Could not detect shell — add this to your shell rc manually:\n" \
               f'  export PATH="{directory}:$PATH"'

    line = f'export PATH="{directory}:$PATH"'
    existing = rc.read_text() if rc.exists() else ""

    # Check if the directory is already exported anywhere in the file
    if str(directory) in existing:
        return f"{directory} already in {rc.name}"

    with rc.open("a") as f:
        f.write(f"\n# Added by git_identity_switcher\n{line}\n")

    return f"Added {directory} to {rc.name} — run: source ~/{rc.name}"


def install_gitswap(alias):
    script = (
        f"#!/bin/bash\n"
        f"# {alias} — swap git identity for the current repo\n"
        f'"{sys.executable}" "{CLI_SCRIPT}" swap "$@"\n'
    )
    for d in INSTALL_DIRS:
        try:
            d.mkdir(parents=True, exist_ok=True)
            target = d / alias
            target.write_text(script)
            target.chmod(0o755)
            # If we installed to a non-standard directory, make sure it's in PATH
            if d != INSTALL_DIRS[0]:
                path_msg = _ensure_path_in_rc(d)
                return True, f"{target}\n{path_msg}"
            return True, str(target)
        except PermissionError:
            continue
    return False, (
        f"Could not write to {INSTALL_DIRS[0]} or {INSTALL_DIRS[1]}.\n"
        "Try: sudo chmod o+w /usr/local/bin"
    )

# ---------------------------------------------------------------------------
# Reusable widgets
# ---------------------------------------------------------------------------

def lbl(parent, text, *, fg=None, font=FB, **kw):
    return tk.Label(parent, text=text, bg=parent["bg"],
                    fg=fg or C["text"], font=font, **kw)

def card_frame(parent, **kw):
    return tk.Frame(parent, bg=C["card"], **kw)

def spacer(parent, h=8):
    return tk.Frame(parent, bg=parent["bg"], height=h)

def field_row(parent, label_text, default=""):
    """Label + Entry row. Returns StringVar."""
    row = tk.Frame(parent, bg=C["card"])
    row.pack(fill="x", padx=16, pady=3)
    tk.Label(row, text=label_text, bg=C["card"], fg=C["muted"],
             font=FM, width=13, anchor="w").pack(side="left")
    var = tk.StringVar(value=default)
    tk.Entry(row, textvariable=var,
             bg=C["card2"], fg=C["text"],
             insertbackground=C["text"],
             relief="flat", font=FB,
             highlightbackground=C["border"],
             highlightthickness=1,
             ).pack(side="left", fill="x", expand=True, ipady=5, padx=(8, 0))
    return var


def platform_selector(parent, prefill_platform="GitHub", prefill_host=""):
    """
    A row of platform buttons + an editable host field.
    Returns (platform_var, host_var).

    - Selecting GitHub/GitLab/Bitbucket auto-fills host and locks the field.
    - Selecting 'Other' unlocks the host field for manual entry.
    """
    platform_var = tk.StringVar(value=prefill_platform)
    host_var     = tk.StringVar(value=prefill_host or PLATFORMS.get(prefill_platform, ""))

    # ── Platform button row ──────────────────────────────────────────────
    btn_row = tk.Frame(parent, bg=C["card"])
    btn_row.pack(fill="x", padx=16, pady=(6, 3))
    tk.Label(btn_row, text="Platform", bg=C["card"], fg=C["muted"],
             font=FM, width=13, anchor="w").pack(side="left")

    btn_container = tk.Frame(btn_row, bg=C["card"])
    btn_container.pack(side="left")

    buttons = {}
    host_entry_ref = [None]   # filled after host entry is created

    def select(name):
        platform_var.set(name)
        known_host = PLATFORMS.get(name, "")
        if known_host:
            host_var.set(known_host)
        # Highlight active button
        for n, b in buttons.items():
            if n == name:
                b.configure(bg=C["accent"], fg=C["sel_fg"],
                            font=("Helvetica Neue", 10, "bold"))
            else:
                b.configure(bg=C["card2"], fg=C["muted"],
                            font=FM)
        # Lock/unlock host field
        entry = host_entry_ref[0]
        if entry:
            if name == "Other":
                entry.configure(state="normal", fg=C["text"])
                if not host_var.get():
                    host_var.set("")
            else:
                entry.configure(state="readonly", fg=C["muted"])

    for name in PLATFORMS:
        b = tk.Button(btn_container, text=name,
                      bg=C["card2"], fg=C["muted"],
                      activebackground=C["accent"], activeforeground=C["sel_fg"],
                      font=FM, relief="flat", cursor="hand2",
                      padx=10, pady=4,
                      command=lambda n=name: select(n))
        b.pack(side="left", padx=(0, 4))
        buttons[name] = b

    # ── Host field ───────────────────────────────────────────────────────
    host_row = tk.Frame(parent, bg=C["card"])
    host_row.pack(fill="x", padx=16, pady=3)
    tk.Label(host_row, text="Host", bg=C["card"], fg=C["muted"],
             font=FM, width=13, anchor="w").pack(side="left")
    host_entry = tk.Entry(host_row, textvariable=host_var,
                          bg=C["card2"], fg=C["muted"],
                          insertbackground=C["text"],
                          relief="flat", font=FB,
                          highlightbackground=C["border"],
                          highlightthickness=1,
                          state="readonly")
    host_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(8, 0))
    host_entry_ref[0] = host_entry

    # Apply initial state
    select(prefill_platform)
    if prefill_platform == "Other" and prefill_host:
        host_var.set(prefill_host)

    return platform_var, host_var


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Git Identity Switcher")
        self.resizable(False, False)
        self.configure(bg=C["bg"])

        self._frame = tk.Frame(self, bg=C["bg"])
        self._frame.pack(fill="both", expand=True, padx=24, pady=24)

        cfg = load_config()
        if cfg and cfg.get("setup_complete"):
            self._show_ready(cfg)
        else:
            self._show_setup(cfg or {})

        # Force window to front (needed when launched via Finder / .command)
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.focus_force()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _resize(self, w, h):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _clear(self):
        for w in self._frame.winfo_children():
            w.destroy()

    # -----------------------------------------------------------------------
    # Screen 1: Setup
    # -----------------------------------------------------------------------

    def _show_setup(self, prefill):
        self._clear()
        self._resize(520, 680)
        f = self._frame

        # ── Fixed header (never scrolls) ─────────────────────────────────
        lbl(f, "Git Identity Switcher", font=FT).pack(anchor="w")
        lbl(f, "One-time setup — configure your two identities",
            fg=C["muted"], font=FB).pack(anchor="w", pady=(4, 12))

        # ── Scrollable middle section ─────────────────────────────────────
        # Canvas + scrollbar so the form fits any screen height.
        scroll_outer = tk.Frame(f, bg=C["bg"])
        scroll_outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_outer, bg=C["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(scroll_outer, orient="vertical",
                                 command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Inner frame — all form content goes here
        inner = tk.Frame(canvas, bg=C["bg"])
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        # Resize canvas scroll region when inner frame changes size
        def on_inner_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", on_inner_configure)

        # Make inner frame match canvas width
        def on_canvas_configure(e):
            canvas.itemconfig(inner_id, width=e.width)
        canvas.bind("<Configure>", on_canvas_configure)

        # Mousewheel scrolling
        def on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # ── Form sections (packed into inner, not f) ──────────────────────
        def section(title):
            lbl(inner, title, fg=C["accent"], font=FS).pack(anchor="w", pady=(8, 4))
            c = card_frame(inner)
            c.pack(fill="x")
            spacer(c).pack()
            return c

        pp = prefill.get("personal", {})
        pc = section("Personal Identity")
        p_plat_var, p_host_var = platform_selector(
            pc,
            prefill_platform=pp.get("platform", "GitHub"),
            prefill_host=pp.get("host", ""),
        )
        p_name  = field_row(pc, "Name",          pp.get("name", ""))
        p_email = field_row(pc, "Email",          pp.get("email", ""))
        p_path  = field_row(pc, "Username/Path",  pp.get("path", ""))
        lbl(pc, "  Your username or group/namespace on this platform",
            fg=C["muted"], font=FM).pack(anchor="w", padx=16)
        spacer(pc).pack()

        wp = prefill.get("work", {})
        wc = section("Work Identity")
        w_plat_var, w_host_var = platform_selector(
            wc,
            prefill_platform=wp.get("platform", "GitLab"),
            prefill_host=wp.get("host", ""),
        )
        w_name  = field_row(wc, "Name",          wp.get("name", ""))
        w_email = field_row(wc, "Email",          wp.get("email", ""))
        w_path  = field_row(wc, "Username/Path",  wp.get("path", ""))
        lbl(wc, "  Your username or group/namespace on this platform",
            fg=C["muted"], font=FM).pack(anchor="w", padx=16)
        spacer(wc).pack()

        ac = section("Global Command")
        alias_var = field_row(ac, "Command name", prefill.get("alias", "gitSwap"))
        lbl(ac, "  Installed to /usr/local/bin — use it from any repo",
            fg=C["muted"], font=FM).pack(anchor="w", padx=16)
        spacer(ac, 4).pack()

        # ── Fixed footer: status label + Run Setup button (always visible) ─
        tk.Frame(f, bg=C["border"], height=1).pack(fill="x", pady=(10, 0))

        sv = tk.StringVar()
        tk.Label(f, textvariable=sv, bg=C["bg"], fg=C["muted"],
                 font=FM, wraplength=472, justify="left",
                 ).pack(anchor="w", pady=(6, 0))

        btn_row = tk.Frame(f, bg=C["bg"])
        btn_row.pack(fill="x", pady=(8, 0))
        btn = tk.Button(btn_row, text="Run Setup",
                        bg=C["accent"], fg=C["bg"],
                        activebackground=C["accent"], activeforeground=C["bg"],
                        font=("Helvetica Neue", 13, "bold"),
                        relief="flat", cursor="hand2", padx=24, pady=10)
        btn.pack(side="right")
        btn.configure(command=lambda: self._do_setup(
            p_plat_var.get(), p_host_var.get().strip(),
            p_name.get().strip(), p_email.get().strip(), p_path.get().strip(),
            w_plat_var.get(), w_host_var.get().strip(),
            w_name.get().strip(), w_email.get().strip(), w_path.get().strip(),
            alias_var.get().strip(), btn, sv,
        ))

    def _do_setup(self,
                  p_plat, p_host, p_name, p_email, p_path,
                  w_plat, w_host, w_name, w_email, w_path,
                  alias, btn, sv):

        # Strip accidental URL scheme from hosts
        p_host = p_host.removeprefix("https://").removeprefix("http://").rstrip("/")
        w_host = w_host.removeprefix("https://").removeprefix("http://").rstrip("/")

        required = [
            ("Personal host",          p_host),
            ("Personal name",          p_name),
            ("Personal email",         p_email),
            ("Personal username/path", p_path),
            ("Work host",              w_host),
            ("Work name",              w_name),
            ("Work email",             w_email),
            ("Work username/path",     w_path),
            ("Command name",           alias),
        ]
        missing = [label for label, val in required if not val]
        if missing:
            messagebox.showerror("Missing fields",
                                 "Please fill in:\n• " + "\n• ".join(missing))
            return

        btn.configure(state="disabled", text="Setting up…")

        def step(msg):
            self.after(0, lambda: sv.set(msg))

        def worker():
            step("Generating SSH keys and updating ~/.ssh/config…")
            rc, out, err = run_cli(
                "setup",
                "--personal-host", p_host,
                "--work-host",     w_host,
            )
            if rc != 0:
                msg = (err or out).strip()
                self.after(0, lambda: (
                    sv.set(f"Error: {msg}"),
                    btn.configure(state="normal", text="Run Setup"),
                ))
                return

            step("Saving config…")
            cfg = {
                "personal": {"platform": p_plat, "host": p_host,
                             "name": p_name, "email": p_email, "path": p_path},
                "work":     {"platform": w_plat, "host": w_host,
                             "name": w_name, "email": w_email, "path": w_path},
                "alias":    alias,
                "setup_complete": True,
            }
            save_config(cfg)

            step(f"Installing '{alias}' command…")
            ok, info_msg = install_gitswap(alias)
            if not ok:
                self.after(0, lambda: messagebox.showwarning("Install warning", info_msg))

            self.after(300, lambda: self._show_ready(cfg))

        threading.Thread(target=worker, daemon=True).start()

    # -----------------------------------------------------------------------
    # Screen 2: Ready
    # -----------------------------------------------------------------------

    def _show_ready(self, cfg):
        self._clear()
        self._resize(500, 530)
        f = self._frame
        alias = cfg.get("alias", "gitSwap")

        lbl(f, "Git Identity Switcher", font=FT).pack(anchor="w")
        tk.Label(f, text="  ✓  Setup complete  ",
                 bg=C["success"], fg=C["bg"],
                 font=("Helvetica Neue", 11, "bold"),
                 padx=4, pady=3).pack(anchor="w", pady=(6, 18))

        lbl(f, "Add SSH keys to each platform",
            font=("Helvetica Neue", 14, "bold")).pack(anchor="w")
        lbl(f, "Press a button to copy — the key is never shown on screen.",
            fg=C["muted"], font=FM).pack(anchor="w", pady=(3, 12))

        p = cfg.get("personal", {})
        w = cfg.get("work", {})

        self._key_card(f,
            label    = "Personal",
            platform = p.get("platform", ""),
            host     = p.get("host", ""),
            pub_path = PERSONAL_PUB,
            btn_text = "Copy Personal SSH Key",
        )
        self._key_card(f,
            label    = "Work",
            platform = w.get("platform", ""),
            host     = w.get("host", ""),
            pub_path = WORK_PUB,
            btn_text = "Copy Work SSH Key",
        )

        # gitSwap info
        ic = card_frame(f)
        ic.pack(fill="x", pady=(0, 16))
        spacer(ic, 10).pack()
        lbl(ic, f"  '{alias}' is ready — run it inside any git repo",
            fg=C["text"], font=("Helvetica Neue", 12, "bold")).pack(anchor="w", padx=6)
        for cmd_str in (alias, f"{alias} work", f"{alias} personal"):
            tk.Label(ic, text=f"    $ {cmd_str}",
                     bg=C["card"], fg=C["accent"],
                     font=FMO).pack(anchor="w", padx=6)
        spacer(ic, 10).pack()

        # Bottom row
        br = tk.Frame(f, bg=C["bg"])
        br.pack(fill="x")
        tk.Button(br, text="Test Personal SSH",
                  bg=C["card2"], fg=C["text"],
                  activebackground=C["card2"], activeforeground=C["text"],
                  font=FB, relief="flat", cursor="hand2", padx=10, pady=6,
                  command=lambda: self._run_test("test-personal", "Personal"),
                  ).pack(side="left", padx=(0, 6))
        tk.Button(br, text="Test Work SSH",
                  bg=C["card2"], fg=C["text"],
                  activebackground=C["card2"], activeforeground=C["text"],
                  font=FB, relief="flat", cursor="hand2", padx=10, pady=6,
                  command=lambda: self._run_test("test-work", "Work"),
                  ).pack(side="left")
        tk.Button(br, text="Reconfigure",
                  bg=C["bg"], fg=C["muted"],
                  activebackground=C["bg"], activeforeground=C["muted"],
                  font=FM, relief="flat", cursor="hand2",
                  command=lambda: self._show_setup(cfg),
                  ).pack(side="right")

    def _key_card(self, parent, label, platform, host, pub_path, btn_text):
        c = card_frame(parent)
        c.pack(fill="x", pady=(0, 8))
        spacer(c, 12).pack()

        # Title row: "Personal  ·  GitHub  ·  github.com"
        title_parts = [label]
        if platform:
            title_parts.append(platform)
        if host and host not in PLATFORMS.values() or (host and platform == "Other"):
            title_parts.append(host)
        title = "   ·   ".join(title_parts)
        lbl(c, title, fg=C["accent"], font=FS).pack(anchor="w", padx=16)

        # SSH settings hint
        if host:
            lbl(c, f"{host} → SSH Settings / Keys",
                fg=C["muted"], font=FM).pack(anchor="w", padx=16, pady=(2, 10))

        lbl_var = tk.StringVar(value=btn_text)
        btn = tk.Button(c, textvariable=lbl_var,
                        bg=C["accent"], fg=C["bg"],
                        activebackground=C["accent"], activeforeground=C["bg"],
                        font=("Helvetica Neue", 12, "bold"),
                        relief="flat", cursor="hand2", padx=14, pady=7)
        btn.pack(anchor="w", padx=16)
        btn.configure(command=lambda: self._copy_key(pub_path, lbl_var, btn_text))
        spacer(c, 12).pack()

    def _copy_key(self, pub_path, lbl_var, original):
        if not pub_path.exists():
            messagebox.showerror("Key not found",
                                 f"{pub_path} not found.\nClick Reconfigure and run setup again.")
            return
        pbcopy(pub_path.read_text().strip())
        lbl_var.set("  ✓  Copied to clipboard!")
        self.after(2500, lambda: lbl_var.set(original))

    def _run_test(self, subcmd, label):
        def worker():
            rc, out, err = run_cli(subcmd)
            text = (out + err).strip() or "No output."
            self.after(0, lambda: messagebox.showinfo(f"SSH Test — {label}", text))
        threading.Thread(target=worker, daemon=True).start()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        app = App()
        app.mainloop()
    except Exception as exc:
        import traceback
        log = SCRIPT_DIR / "ui_error.log"
        log.write_text(traceback.format_exc())
        print(f"ERROR: {exc}")
        print(f"Full traceback: {log}")
        raise

if __name__ == "__main__":
    main()
