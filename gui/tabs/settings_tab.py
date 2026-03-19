"""
gui/tabs/settings_tab.py
App settings — theme, default dest, format, ffmpeg check, dep status.
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from tkinter import filedialog
import tkinter as tk
from typing import Dict

import customtkinter as ctk

from core.config import config
from core.deps import check_ytdlp, check_spotdl, check_ffmpeg, check_deno


class SettingsTab:
    def __init__(self, parent: ctk.CTkFrame, theme: Dict[str, str]) -> None:
        self.theme = theme
        self._build(parent)

    def _section(self, parent, text: str) -> None:
        ctk.CTkLabel(
            parent,
            text=text.upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=self.theme["text_dim"],
        ).pack(anchor="w", pady=(12, 2))

    def _build(self, parent: ctk.CTkFrame) -> None:
        T = self.theme

        outer = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=14, pady=10)

        # ── Spotify API Credentials ────────────────────────────────── #
        self._section(outer, "Spotify API Credentials")

        ctk.CTkLabel(
            outer,
            text="Optional — uses SpotDL's default if left blank. Get your own at developer.spotify.com",
            font=ctk.CTkFont(size=10),
            text_color=T["text_dim"],
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        for label, key in [("Client ID", "spotify_client_id"), ("Client Secret", "spotify_client_secret")]:
            row = ctk.CTkFrame(outer, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12),
                         text_color=T["text_primary"], width=140, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(
                row, height=32, font=ctk.CTkFont(size=11),
                fg_color=T["bg_mid"], border_color="#333333",
                text_color=T["text_primary"],
                show="*" if "secret" in key else "",
            )
            saved = config.get(key, "")
            if saved:
                entry.insert(0, saved)
            entry.pack(side="left", fill="x", expand=True)
            setattr(self, f"_{key}_entry", entry)

        ctk.CTkButton(
            outer, text="Save Spotify Credentials", height=34,
            fg_color=T["accent_red"], hover_color=T["accent_hover"],
            text_color="#FFFFFF", font=ctk.CTkFont(size=12),
            command=self._save_spotify_creds,
        ).pack(anchor="w", pady=(6, 0))

        self._spotify_feedback = ctk.CTkLabel(
            outer, text="", font=ctk.CTkFont(size=11), text_color=T["amber"]
        )
        self._spotify_feedback.pack(anchor="w")

        # ── Appearance ─────────────────────────────────────────────── #
        self._section(outer, "Appearance")

        theme_row = ctk.CTkFrame(outer, fg_color="transparent")
        theme_row.pack(fill="x")

        ctk.CTkLabel(theme_row, text="Theme", font=ctk.CTkFont(size=12),
                     text_color=T["text_primary"], width=140, anchor="w").pack(side="left")

        self.theme_combo = ctk.CTkComboBox(
            theme_row, values=["Dark", "Light", "System"], width=140,
            fg_color=T["bg_mid"], border_color="#333333",
            button_color=T["accent_red"], button_hover_color=T["accent_hover"],
            text_color=T["text_primary"], dropdown_fg_color=T["bg_mid"],
            command=self._change_theme,
        )
        self.theme_combo.set(config.get("theme", "Dark"))
        self.theme_combo.pack(side="left")

        # ── Defaults ───────────────────────────────────────────────── #
        self._section(outer, "Download Defaults")

        # Default format
        fmt_row = ctk.CTkFrame(outer, fg_color="transparent")
        fmt_row.pack(fill="x", pady=2)
        ctk.CTkLabel(fmt_row, text="Default Format", font=ctk.CTkFont(size=12),
                     text_color=T["text_primary"], width=140, anchor="w").pack(side="left")
        self.fmt_combo = ctk.CTkComboBox(
            fmt_row, values=["mp3", "flac", "mp4", "mkv"], width=100,
            fg_color=T["bg_mid"], border_color="#333333",
            button_color=T["accent_red"], button_hover_color=T["accent_hover"],
            text_color=T["text_primary"], dropdown_fg_color=T["bg_mid"],
            command=lambda v: config.set("default_format", v),
        )
        self.fmt_combo.set(config.get("default_format", "mp3"))
        self.fmt_combo.pack(side="left")

        # Default destination
        dest_row = ctk.CTkFrame(outer, fg_color="transparent")
        dest_row.pack(fill="x", pady=2)
        ctk.CTkLabel(dest_row, text="Default Folder", font=ctk.CTkFont(size=12),
                     text_color=T["text_primary"], width=140, anchor="w").pack(side="left")
        self.dest_entry = ctk.CTkEntry(
            dest_row, height=32, font=ctk.CTkFont(size=11),
            fg_color=T["bg_mid"], border_color="#333333",
            text_color=T["text_primary"],
        )
        self.dest_entry.insert(0, config.get("default_destination", str(Path.home() / "Downloads")))
        self.dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            dest_row, text="Browse", width=70, height=32,
            fg_color=T["bg_mid"], hover_color="#2a2a2a",
            border_color="#444444", border_width=1,
            text_color=T["text_primary"], font=ctk.CTkFont(size=11),
            command=self._browse_dest,
        ).pack(side="right")

        # Save defaults button
        ctk.CTkButton(
            outer, text="Save Defaults", height=34,
            fg_color=T["accent_red"], hover_color=T["accent_hover"],
            text_color="#FFFFFF", font=ctk.CTkFont(size=12),
            command=self._save_defaults,
        ).pack(anchor="w", pady=(6, 0))

        # ── Dependency Status ──────────────────────────────────────── #
        self._section(outer, "Dependencies")

        self.dep_frame = ctk.CTkFrame(outer, fg_color=T["bg_mid"], corner_radius=6)
        self.dep_frame.pack(fill="x", pady=(2, 6))
        self._render_deps()

        ctk.CTkButton(
            outer, text="↺  Recheck Dependencies", height=32,
            fg_color="transparent", hover_color="#2a2a2a",
            border_color="#444444", border_width=1,
            text_color=T["text_dim"], font=ctk.CTkFont(size=11),
            command=self._render_deps,
        ).pack(anchor="w")

        ctk.CTkButton(
            outer, text="⬇  Install Missing Dependencies", height=32,
            fg_color=T["accent_red"], hover_color=T["accent_hover"],
            text_color="#FFFFFF", font=ctk.CTkFont(size=11),
            command=self._open_dep_installer,
        ).pack(anchor="w", pady=(6, 0))

        # ── Config path ────────────────────────────────────────────── #
        self._section(outer, "Config File")
        ctk.CTkLabel(
            outer,
            text=config.config_path,
            font=ctk.CTkFont(size=10),
            text_color=T["text_dim"],
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkButton(
            outer, text="Open Config Folder", height=30,
            fg_color="transparent", hover_color="#2a2a2a",
            border_color="#444444", border_width=1,
            text_color=T["text_dim"], font=ctk.CTkFont(size=11),
            command=self._open_config_folder,
        ).pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------ #

    def _render_deps(self) -> None:
        for w in self.dep_frame.winfo_children():
            w.destroy()
        T = self.theme

        deps = [
            ("yt-dlp",  check_ytdlp(),  "pip install yt-dlp"),
            ("SpotDL",  check_spotdl(), "pip install spotdl"),
            ("FFmpeg",  check_ffmpeg(), "https://ffmpeg.org/download.html"),
            ("Deno",    check_deno(),   "https://deno.com  (JS runtime for yt-dlp)"),
        ]
        for name, ok, fix in deps:
            row = ctk.CTkFrame(self.dep_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            dot_color = T["success"] if ok else T["error"]
            ctk.CTkLabel(row, text="●", font=ctk.CTkFont(size=13),
                         text_color=dot_color, width=20).pack(side="left")
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["text_primary"], width=70, anchor="w").pack(side="left")
            status_text = "Installed" if ok else f"Missing  —  {fix}"
            ctk.CTkLabel(row, text=status_text, font=ctk.CTkFont(size=11),
                         text_color=T["text_dim"] if ok else T["error"],
                         anchor="w").pack(side="left")

    def _open_dep_installer(self) -> None:
        from gui.dep_dialog import DepDialog
        # Find the root window
        root = self.dep_frame.winfo_toplevel()
        DepDialog(root, self.theme)

    def _save_spotify_creds(self) -> None:
        client_id = self._spotify_client_id_entry.get().strip()
        client_secret = self._spotify_client_secret_entry.get().strip()
        config.set("spotify_client_id", client_id)
        config.set("spotify_client_secret", client_secret)
        self._spotify_feedback.configure(text="✓ Saved.")
        self._spotify_feedback.after(3000, lambda: self._spotify_feedback.configure(text=""))

    def _change_theme(self, value: str) -> None:
        ctk.set_appearance_mode(value.lower())
        config.set("theme", value)

    def _browse_dest(self) -> None:
        root_tk = tk.Tk()
        root_tk.withdraw()
        path = filedialog.askdirectory(title="Default Download Folder")
        root_tk.destroy()
        if path:
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, path)

    def _save_defaults(self) -> None:
        config.set("default_destination", self.dest_entry.get().strip())
        config.set("default_format", self.fmt_combo.get())

    def _open_config_folder(self) -> None:
        import os
        folder = str(Path(config.config_path).parent)
        os.startfile(folder)
