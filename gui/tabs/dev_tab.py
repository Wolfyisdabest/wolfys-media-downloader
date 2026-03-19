"""
gui/tabs/dev_tab.py
Developer mode tab — live logs, dependency versions, raw debug output.
Only visible when dev_mode is enabled in Settings.
"""

from __future__ import annotations
import logging
import subprocess
import sys
import threading
from typing import Dict

import customtkinter as ctk

from core.config import config
from core.deps import check_ytdlp, check_spotdl, check_ffmpeg, check_deno


class DevLogHandler(logging.Handler):
    """Routes WMD logger output into the dev tab textbox."""

    def __init__(self, textbox: ctk.CTkTextbox) -> None:
        super().__init__()
        self._box = textbox

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        def _write():
            self._box.configure(state="normal")
            self._box.insert("end", msg + "\n")
            self._box.see("end")
            self._box.configure(state="disabled")
        try:
            self._box.after(0, _write)
        except Exception:
            pass


class DevTab:
    def __init__(self, parent: ctk.CTkFrame, theme: Dict[str, str]) -> None:
        self.theme = theme
        self._log_handler: DevLogHandler | None = None
        self._build(parent)
        self._attach_logger()
        self._load_versions()

    def _build(self, parent: ctk.CTkFrame) -> None:
        T = self.theme

        outer = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=12, pady=10)

        # ── Header warning ─────────────────────────────────────────── #
        warn = ctk.CTkFrame(outer, fg_color="#2a1000", corner_radius=6)
        warn.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            warn,
            text="⚠  Developer Mode — for debugging only. Disable in Settings when done.",
            font=ctk.CTkFont(size=11),
            text_color=T["amber"],
        ).pack(padx=12, pady=6)

        # ── Dependency versions ────────────────────────────────────── #
        self._section(outer, "Dependency Versions")
        self.ver_frame = ctk.CTkFrame(outer, fg_color=T["bg_mid"], corner_radius=6)
        self.ver_frame.pack(fill="x", pady=(2, 8))

        ctk.CTkButton(
            outer, text="↺  Refresh Versions", height=28,
            fg_color="transparent", hover_color="#2a2a2a",
            border_color="#444444", border_width=1,
            text_color=T["text_dim"], font=ctk.CTkFont(size=11),
            command=self._load_versions,
        ).pack(anchor="w", pady=(0, 10))

        # ── Config dump ────────────────────────────────────────────── #
        self._section(outer, "Current Config (live)")
        self.config_box = ctk.CTkTextbox(
            outer, height=120,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=T["bg_dark"], text_color=T["text_primary"],
            border_color="#333333", border_width=1,
        )
        self.config_box.pack(fill="x", pady=(2, 4))
        self.config_box.configure(state="disabled")

        ctk.CTkButton(
            outer, text="↺  Refresh Config Dump", height=28,
            fg_color="transparent", hover_color="#2a2a2a",
            border_color="#444444", border_width=1,
            text_color=T["text_dim"], font=ctk.CTkFont(size=11),
            command=self._refresh_config,
        ).pack(anchor="w", pady=(0, 10))

        self._refresh_config()

        # ── Live log ───────────────────────────────────────────────── #
        self._section(outer, "Live Application Log")

        log_btns = ctk.CTkFrame(outer, fg_color="transparent")
        log_btns.pack(fill="x", pady=(0, 4))

        ctk.CTkButton(
            log_btns, text="Clear Log", height=28,
            fg_color="transparent", hover_color="#2a2a2a",
            border_color="#444444", border_width=1,
            text_color=T["text_dim"], font=ctk.CTkFont(size=11),
            command=self._clear_log,
        ).pack(side="left")

        # Log level selector
        ctk.CTkLabel(log_btns, text="Level:", font=ctk.CTkFont(size=11),
                     text_color=T["text_dim"]).pack(side="left", padx=(12, 4))
        self.level_combo = ctk.CTkComboBox(
            log_btns, values=["DEBUG", "INFO", "WARNING", "ERROR"],
            width=100, height=28,
            fg_color=T["bg_mid"], border_color="#333333",
            button_color=T["accent_red"], button_hover_color=T["accent_hover"],
            text_color=T["text_primary"], dropdown_fg_color=T["bg_mid"],
            command=self._change_log_level,
        )
        self.level_combo.set("DEBUG")
        self.level_combo.pack(side="left")

        self.log_box = ctk.CTkTextbox(
            outer, height=280,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=T["bg_dark"], text_color=T["text_primary"],
            border_color="#333333", border_width=1,
        )
        self.log_box.pack(fill="x", pady=(0, 10))
        self.log_box.configure(state="disabled")

        # ── Run command ────────────────────────────────────────────── #
        self._section(outer, "Run Raw Command")
        cmd_row = ctk.CTkFrame(outer, fg_color="transparent")
        cmd_row.pack(fill="x", pady=(2, 4))

        self.cmd_entry = ctk.CTkEntry(
            cmd_row, height=32, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=T["bg_mid"], border_color="#333333",
            text_color=T["text_primary"],
            placeholder_text="e.g. yt-dlp --version",
        )
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            cmd_row, text="Run", width=60, height=32,
            fg_color=T["accent_red"], hover_color=T["accent_hover"],
            text_color="#FFFFFF", font=ctk.CTkFont(size=11),
            command=self._run_command,
        ).pack(side="right")

        self.cmd_output = ctk.CTkTextbox(
            outer, height=120,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=T["bg_dark"], text_color=T["text_primary"],
            border_color="#333333", border_width=1,
        )
        self.cmd_output.pack(fill="x", pady=(0, 10))
        self.cmd_output.configure(state="disabled")

    # ------------------------------------------------------------------ #

    def _section(self, parent, text: str) -> None:
        ctk.CTkLabel(
            parent,
            text=text.upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=self.theme["text_dim"],
        ).pack(anchor="w", pady=(6, 1))

    def _attach_logger(self) -> None:
        logger = logging.getLogger("WMD")
        logger.setLevel(logging.DEBUG)
        self._log_handler = DevLogHandler(self.log_box)
        self._log_handler.setFormatter(logging.Formatter("%(levelname)s  %(message)s"))
        logger.addHandler(self._log_handler)

    def detach_logger(self) -> None:
        if self._log_handler:
            logging.getLogger("WMD").removeHandler(self._log_handler)

    def _change_log_level(self, value: str) -> None:
        level = getattr(logging, value, logging.DEBUG)
        if self._log_handler:
            self._log_handler.setLevel(level)

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _refresh_config(self) -> None:
        import json
        data = config._data.copy()
        # Redact secrets
        for key in ("spotify_client_id", "spotify_client_secret", "po_token"):
            if data.get(key):
                data[key] = "***"
        text = json.dumps(data, indent=2, default=str)
        self.config_box.configure(state="normal")
        self.config_box.delete("1.0", "end")
        self.config_box.insert("1.0", text)
        self.config_box.configure(state="disabled")

    def _load_versions(self) -> None:
        for w in self.ver_frame.winfo_children():
            w.destroy()
        T = self.theme

        threading.Thread(target=self._fetch_versions, daemon=True).start()

    def _fetch_versions(self) -> None:
        versions = {}
        cmds = {
            "yt-dlp":  [sys.executable, "-m", "yt_dlp",  "--version"],
            "spotdl":  [sys.executable, "-m", "spotdl",  "--version"],
            "ffmpeg":  ["ffmpeg", "-version"],
            "deno":    ["deno", "--version"],
            "python":  [sys.executable, "--version"],
        }
        for name, cmd in cmds.items():
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                out = (r.stdout or r.stderr or "").strip().splitlines()
                versions[name] = out[0] if out else "unknown"
            except Exception as e:
                versions[name] = f"not found ({e})"

        self.ver_frame.after(0, lambda: self._render_versions(versions))

    def _render_versions(self, versions: dict) -> None:
        for w in self.ver_frame.winfo_children():
            w.destroy()
        T = self.theme

        for name, ver in versions.items():
            row = ctk.CTkFrame(self.ver_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=T["text_primary"], width=80, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=ver, font=ctk.CTkFont(family="Consolas", size=10),
                         text_color=T["text_dim"], anchor="w").pack(side="left")

    def _run_command(self) -> None:
        cmd_str = self.cmd_entry.get().strip()
        if not cmd_str:
            return

        self.cmd_output.configure(state="normal")
        self.cmd_output.delete("1.0", "end")
        self.cmd_output.insert("end", f"$ {cmd_str}\n")
        self.cmd_output.configure(state="disabled")

        threading.Thread(
            target=self._exec_command,
            args=(cmd_str,),
            daemon=True,
        ).start()

    def _exec_command(self, cmd_str: str) -> None:
        try:
            proc = subprocess.Popen(
                cmd_str, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True,
            )
            for line in proc.stdout:  # type: ignore
                line = line.rstrip()
                def _write(l=line):
                    self.cmd_output.configure(state="normal")
                    self.cmd_output.insert("end", l + "\n")
                    self.cmd_output.see("end")
                    self.cmd_output.configure(state="disabled")
                self.cmd_output.after(0, _write)
            proc.wait()
            exit_msg = f"\n[exit code: {proc.returncode}]"
            self.cmd_output.after(0, lambda: self._append_cmd(exit_msg))
        except Exception as e:
            self.cmd_output.after(0, lambda: self._append_cmd(f"Error: {e}"))

    def _append_cmd(self, text: str) -> None:
        self.cmd_output.configure(state="normal")
        self.cmd_output.insert("end", text + "\n")
        self.cmd_output.see("end")
        self.cmd_output.configure(state="disabled")