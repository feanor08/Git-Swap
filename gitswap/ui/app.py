"""
gitswap/ui/app.py
-----------------
Main tkinter Application class and UI entry point.

Screen flow
-----------
                    ┌─ config exists & setup_complete? ─┐
  App.__init__  ────┤                                    ├──── _show_ready()
                    └────────────────────────────────────┘
                              │ no
                              ▼
                         _show_setup()
                              │ user fills form & clicks Run Setup
                              ▼
                         _do_setup()  ← runs in background thread
                              │ success
                              ▼
                         _show_ready()

Threading
---------
All SSH key generation and CLI calls happen in a daemon background thread so
the UI stays responsive.  Any UI update from the thread must be scheduled via
self.after() — tkinter is not thread-safe.
"""

import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from gitswap.config import load_config_or_none, save_config
from gitswap.constants import PERSONAL_PUB, WORK_PUB, PLATFORMS
from gitswap.ui.installer import install_gitswap
from gitswap.ui.theme import C, FT, FS, FB, FM, FMO
from gitswap.ui.widgets import lbl, card_frame, spacer, field_row, platform_selector

# ── Path resolution ───────────────────────────────────────────────────────────
# Resolved at import time so the app works regardless of the working directory.
_UI_DIR      = Path(__file__).parent.resolve()        # gitswap/ui/
_PACKAGE_DIR = _UI_DIR.parent.resolve()               # gitswap/
_PROJECT_DIR = _PACKAGE_DIR.parent.resolve()          # repo root
_CLI_SCRIPT  = _PROJECT_DIR / "git_identity_switcher.py"


# ── Subprocess helpers ────────────────────────────────────────────────────────

def _run_cli(*args: str) -> tuple[int, str, str]:
    """
    Invoke git_identity_switcher.py with the given subcommand arguments.
    Always uses the same Python interpreter that is running the UI.
    """
    result = subprocess.run(
        [sys.executable, str(_CLI_SCRIPT), *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _pbcopy(text: str) -> None:
    """Copy `text` to the macOS clipboard using pbcopy."""
    subprocess.run(["pbcopy"], input=text, text=True, check=True)


# ── Application ───────────────────────────────────────────────────────────────

class App(tk.Tk):
    """
    Root window for the Git-Swap UI.

    Manages two screens (setup form and ready dashboard) within a single
    content frame that is cleared and repopulated on screen transitions.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("Git Identity Switcher")
        self.resizable(False, False)
        self.configure(bg=C["bg"])

        # Single content frame — all screens are rendered inside this frame.
        # Calling _clear() destroys all children before drawing a new screen.
        self._frame = tk.Frame(self, bg=C["bg"])
        self._frame.pack(fill="both", expand=True, padx=24, pady=24)

        cfg = load_config_or_none()
        if cfg and cfg.get("setup_complete"):
            self._show_ready(cfg)
        else:
            self._show_setup(cfg or {})

        # Bring the window to the front — necessary when launched via
        # Finder or the .command double-click launcher.
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.focus_force()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resize(self, w: int, h: int) -> None:
        """Resize the window and centre it on screen."""
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _clear(self) -> None:
        """Destroy all children of the content frame (used on screen transitions)."""
        for widget in self._frame.winfo_children():
            widget.destroy()

    # ── Screen 1: Setup form ──────────────────────────────────────────────────

    def _show_setup(self, prefill: dict) -> None:
        """
        Render the first-run setup form.

        Layout:
          ┌─ fixed header (title + subtitle) ──────────────┐
          │ scrollable form area                            │
          │   Personal Identity card                        │
          │   Work Identity card                            │
          │   Global Command card                           │
          ├─ fixed footer (status label + Run Setup button) ┤
          └─────────────────────────────────────────────────┘

        The footer is always visible regardless of how tall the form content
        is on the user's screen.
        """
        self._clear()
        self._resize(520, 680)
        f = self._frame

        # ── Fixed header ──────────────────────────────────────────────────
        lbl(f, "Git Identity Switcher", font=FT).pack(anchor="w")
        lbl(f, "One-time setup — configure your two identities",
            fg=C["muted"], font=FB).pack(anchor="w", pady=(4, 12))

        # ── Scrollable form area ──────────────────────────────────────────
        scroll_outer = tk.Frame(f, bg=C["bg"])
        scroll_outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_outer, bg=C["bg"], highlightthickness=0)
        vsb    = tk.Scrollbar(scroll_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner    = tk.Frame(canvas, bg=C["bg"])
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        # Keep scroll region and inner width in sync with the canvas size
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(inner_id, width=e.width),
        )
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * e.delta / 120), "units"),
        )

        # ── Form section helper ───────────────────────────────────────────
        def section(title: str) -> tk.Frame:
            lbl(inner, title, fg=C["accent"], font=FS).pack(anchor="w", pady=(8, 4))
            c = card_frame(inner)
            c.pack(fill="x")
            spacer(c).pack()
            return c

        # ── Personal identity ─────────────────────────────────────────────
        pp  = prefill.get("personal", {})
        pc  = section("Personal Identity")
        p_plat_var, p_host_var = platform_selector(
            pc,
            prefill_platform=pp.get("platform", "GitHub"),
            prefill_host=pp.get("host", ""),
        )
        p_name  = field_row(pc, "Name",           pp.get("name", ""))
        p_email = field_row(pc, "Email",           pp.get("email", ""))
        p_path  = field_row(pc, "Username/Path",   pp.get("path", ""))
        lbl(pc, "  Your username or group/namespace on this platform",
            fg=C["muted"], font=FM).pack(anchor="w", padx=16)
        spacer(pc).pack()

        # ── Work identity ─────────────────────────────────────────────────
        wp  = prefill.get("work", {})
        wc  = section("Work Identity")
        w_plat_var, w_host_var = platform_selector(
            wc,
            prefill_platform=wp.get("platform", "GitLab"),
            prefill_host=wp.get("host", ""),
        )
        w_name  = field_row(wc, "Name",           wp.get("name", ""))
        w_email = field_row(wc, "Email",           wp.get("email", ""))
        w_path  = field_row(wc, "Username/Path",   wp.get("path", ""))
        lbl(wc, "  Your username or group/namespace on this platform",
            fg=C["muted"], font=FM).pack(anchor="w", padx=16)
        spacer(wc).pack()

        # ── Global command ────────────────────────────────────────────────
        ac        = section("Global Command")
        alias_var = field_row(ac, "Command name", prefill.get("alias", "gitSwap"))
        lbl(ac, "  Installed to /usr/local/bin — callable from any repo",
            fg=C["muted"], font=FM).pack(anchor="w", padx=16)
        spacer(ac, 4).pack()

        # ── Fixed footer ──────────────────────────────────────────────────
        tk.Frame(f, bg=C["border"], height=1).pack(fill="x", pady=(10, 0))

        sv = tk.StringVar()
        tk.Label(
            f, textvariable=sv,
            bg=C["bg"], fg=C["muted"],
            font=FM, wraplength=472, justify="left",
        ).pack(anchor="w", pady=(6, 0))

        btn_row = tk.Frame(f, bg=C["bg"])
        btn_row.pack(fill="x", pady=(8, 0))

        btn = tk.Button(
            btn_row, text="Run Setup",
            bg=C["accent"], fg=C["bg"],
            activebackground=C["accent"], activeforeground=C["bg"],
            font=("Helvetica Neue", 13, "bold"),
            relief="flat", cursor="hand2", padx=24, pady=10,
        )
        btn.pack(side="right")
        btn.configure(command=lambda: self._do_setup(
            p_plat_var.get(), p_host_var.get().strip(),
            p_name.get().strip(), p_email.get().strip(), p_path.get().strip(),
            w_plat_var.get(), w_host_var.get().strip(),
            w_name.get().strip(), w_email.get().strip(), w_path.get().strip(),
            alias_var.get().strip(), btn, sv,
        ))

    def _do_setup(
        self,
        p_plat: str, p_host: str, p_name: str, p_email: str, p_path: str,
        w_plat: str, w_host: str, w_name: str, w_email: str, w_path: str,
        alias: str, btn: tk.Button, sv: tk.StringVar,
    ) -> None:
        """
        Validate form inputs, then run SSH setup + install gitSwap in a
        background thread.  Transitions to the ready screen on success.
        """
        # Strip accidental URL schemes the user may have pasted
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
            messagebox.showerror(
                "Missing fields",
                "Please fill in:\n• " + "\n• ".join(missing),
            )
            return

        btn.configure(state="disabled", text="Setting up…")

        def step(msg: str) -> None:
            # All tkinter updates from non-main threads must use after()
            self.after(0, lambda: sv.set(msg))

        def worker() -> None:
            # 1. Generate SSH keys and write ~/.ssh/config
            step("Generating SSH keys and updating ~/.ssh/config…")
            rc, out, err = _run_cli(
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

            # 2. Persist identity config to disk
            step("Saving config…")
            cfg = {
                "personal": {
                    "platform": p_plat, "host": p_host,
                    "name": p_name, "email": p_email, "path": p_path,
                },
                "work": {
                    "platform": w_plat, "host": w_host,
                    "name": w_name, "email": w_email, "path": w_path,
                },
                "alias":          alias,
                "setup_complete": True,
            }
            save_config(cfg)

            # 3. Install the gitSwap shell script
            step(f"Installing '{alias}' command…")
            ok, info_msg = install_gitswap(alias, _CLI_SCRIPT)
            if not ok:
                self.after(0, lambda: messagebox.showwarning(
                    "Install warning", info_msg,
                ))

            # 4. Transition to the ready dashboard
            self.after(300, lambda: self._show_ready(cfg))

        threading.Thread(target=worker, daemon=True).start()

    # ── Screen 2: Ready dashboard ─────────────────────────────────────────────

    def _show_ready(self, cfg: dict) -> None:
        """
        Render the post-setup dashboard.

        Shows:
          - Copy-key buttons (one per identity)
          - gitSwap usage examples
          - SSH connectivity test buttons
          - Reconfigure link
        """
        self._clear()
        self._resize(500, 530)
        f     = self._frame
        alias = cfg.get("alias", "gitSwap")

        lbl(f, "Git Identity Switcher", font=FT).pack(anchor="w")
        tk.Label(
            f, text="  ✓  Setup complete  ",
            bg=C["success"], fg=C["bg"],
            font=("Helvetica Neue", 11, "bold"),
            padx=4, pady=3,
        ).pack(anchor="w", pady=(6, 18))

        lbl(f, "Add SSH keys to each platform",
            font=("Helvetica Neue", 14, "bold")).pack(anchor="w")
        lbl(f, "Press a button to copy — the key is never shown on screen.",
            fg=C["muted"], font=FM).pack(anchor="w", pady=(3, 12))

        p = cfg.get("personal", {})
        w = cfg.get("work", {})

        self._key_card(
            f,
            label    = "Personal",
            platform = p.get("platform", ""),
            host     = p.get("host", ""),
            pub_path = PERSONAL_PUB,
            btn_text = "Copy Personal SSH Key",
        )
        self._key_card(
            f,
            label    = "Work",
            platform = w.get("platform", ""),
            host     = w.get("host", ""),
            pub_path = WORK_PUB,
            btn_text = "Copy Work SSH Key",
        )

        # gitSwap usage examples
        ic = card_frame(f)
        ic.pack(fill="x", pady=(0, 16))
        spacer(ic, 10).pack()
        lbl(ic, f"  '{alias}' is ready — run it inside any git repo",
            fg=C["text"],
            font=("Helvetica Neue", 12, "bold"),
            ).pack(anchor="w", padx=6)
        for cmd_str in (alias, f"{alias} work", f"{alias} personal"):
            tk.Label(
                ic, text=f"    $ {cmd_str}",
                bg=C["card"], fg=C["accent"], font=FMO,
            ).pack(anchor="w", padx=6)
        spacer(ic, 10).pack()

        # Action row
        br = tk.Frame(f, bg=C["bg"])
        br.pack(fill="x")

        for text, subcmd, label in [
            ("Test Personal SSH", "test-personal", "Personal"),
            ("Test Work SSH",     "test-work",     "Work"),
        ]:
            tk.Button(
                br, text=text,
                bg=C["card2"], fg=C["text"],
                activebackground=C["card2"], activeforeground=C["text"],
                font=FB, relief="flat", cursor="hand2", padx=10, pady=6,
                command=lambda s=subcmd, l=label: self._run_test(s, l),
            ).pack(side="left", padx=(0, 6))

        tk.Button(
            br, text="Reconfigure",
            bg=C["bg"], fg=C["muted"],
            activebackground=C["bg"], activeforeground=C["muted"],
            font=FM, relief="flat", cursor="hand2",
            command=lambda: self._show_setup(cfg),
        ).pack(side="right")

    def _key_card(
        self,
        parent,
        label: str,
        platform: str,
        host: str,
        pub_path: Path,
        btn_text: str,
    ) -> None:
        """
        Render one identity card with a clipboard-copy button.
        The public key is never displayed — only copied to the clipboard.
        """
        c = card_frame(parent)
        c.pack(fill="x", pady=(0, 8))
        spacer(c, 12).pack()

        # Title: "Personal   ·   GitHub   ·   github.com"
        # Self-hosted hosts are shown explicitly; well-known ones are implicit.
        parts = [label]
        if platform:
            parts.append(platform)
        if host and host not in PLATFORMS.values():
            parts.append(host)
        lbl(c, "   ·   ".join(parts), fg=C["accent"], font=FS).pack(anchor="w", padx=16)

        if host:
            lbl(c, f"{host} → SSH Settings / Keys",
                fg=C["muted"], font=FM).pack(anchor="w", padx=16, pady=(2, 10))

        lbl_var = tk.StringVar(value=btn_text)
        btn = tk.Button(
            c, textvariable=lbl_var,
            bg=C["accent"], fg=C["bg"],
            activebackground=C["accent"], activeforeground=C["bg"],
            font=("Helvetica Neue", 12, "bold"),
            relief="flat", cursor="hand2", padx=14, pady=7,
        )
        btn.pack(anchor="w", padx=16)
        btn.configure(command=lambda: self._copy_key(pub_path, lbl_var, btn_text))
        spacer(c, 12).pack()

    def _copy_key(
        self, pub_path: Path, lbl_var: tk.StringVar, original: str
    ) -> None:
        """Copy the public key to the clipboard and briefly update the button label."""
        if not pub_path.exists():
            messagebox.showerror(
                "Key not found",
                f"{pub_path} does not exist.\n"
                "Click Reconfigure and run setup again.",
            )
            return
        _pbcopy(pub_path.read_text().strip())
        lbl_var.set("  ✓  Copied to clipboard!")
        self.after(2500, lambda: lbl_var.set(original))

    def _run_test(self, subcmd: str, label: str) -> None:
        """Run an SSH connectivity test in a background thread and show the result."""
        def worker() -> None:
            rc, out, err = _run_cli(subcmd)
            text = (out + err).strip() or "No output received."
            self.after(0, lambda: messagebox.showinfo(f"SSH Test — {label}", text))

        threading.Thread(target=worker, daemon=True).start()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Launch the Git-Swap UI.  Writes a traceback log on unexpected crash."""
    try:
        app = App()
        app.mainloop()
    except Exception as exc:
        import traceback
        log = _PROJECT_DIR / "ui_error.log"
        log.write_text(traceback.format_exc())
        print(f"ERROR: {exc}")
        print(f"Full traceback written to: {log}")
        raise
