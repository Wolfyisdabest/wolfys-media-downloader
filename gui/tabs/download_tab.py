"""
gui/tabs/download_tab.py
Main download tab — URL entry, format, destination, add to queue.
"""

from __future__ import annotations
from pathlib import Path
from tkinter import filedialog
import tkinter as tk
from typing import Dict

import customtkinter as ctk

from core.config import config
from core.queue_manager import queue


class DownloadTab:
    def __init__(self, parent: ctk.CTkFrame, theme: Dict[str, str]) -> None:
        self.theme = theme
        self.parent = parent
        self._build(parent)

    def _build(self, parent: ctk.CTkFrame) -> None:
        T = self.theme

        outer = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        # ── URL Input ──────────────────────────────────────────────── #
        self._section_label(outer, "Media URL")

        url_row = ctk.CTkFrame(outer, fg_color="transparent")
        url_row.pack(fill="x", pady=(2, 8))

        self.url_entry = ctk.CTkEntry(
            url_row,
            placeholder_text="Paste YouTube, Spotify, SoundCloud... URL here",
            height=38,
            font=ctk.CTkFont(size=13),
            fg_color=T["bg_mid"],
            border_color=T["accent_red"],
            border_width=1,
            text_color=T["text_primary"],
        )
        self.url_entry.pack(fill="x", ipady=2)

        # ── Destination ────────────────────────────────────────────── #
        self._section_label(outer, "Destination Folder")

        dest_row = ctk.CTkFrame(outer, fg_color="transparent")
        dest_row.pack(fill="x", pady=(2, 8))

        self.dest_entry = ctk.CTkEntry(
            dest_row,
            height=38,
            font=ctk.CTkFont(size=12),
            fg_color=T["bg_mid"],
            border_color="#333333",
            border_width=1,
            text_color=T["text_primary"],
        )
        self.dest_entry.insert(0, config.get("default_destination", str(Path.home() / "Downloads")))
        self.dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        browse_btn = ctk.CTkButton(
            dest_row,
            text="Browse",
            width=80,
            height=38,
            fg_color=T["bg_mid"],
            hover_color="#2a2a2a",
            border_color="#444444",
            border_width=1,
            text_color=T["text_primary"],
            font=ctk.CTkFont(size=12),
            command=self._browse,
        )
        browse_btn.pack(side="right")

        # ── Format + Options row ───────────────────────────────────── #
        opts_row = ctk.CTkFrame(outer, fg_color="transparent")
        opts_row.pack(fill="x", pady=(0, 10))

        # Format selector
        fmt_col = ctk.CTkFrame(opts_row, fg_color="transparent")
        fmt_col.pack(side="left", padx=(0, 16))
        self._section_label(fmt_col, "Format")
        self.fmt_combo = ctk.CTkComboBox(
            fmt_col,
            values=["mp3", "flac", "mp4", "mkv"],
            width=110,
            height=36,
            fg_color=T["bg_mid"],
            border_color="#333333",
            button_color=T["accent_red"],
            button_hover_color=T["accent_hover"],
            text_color=T["text_primary"],
            font=ctk.CTkFont(size=13),
            dropdown_fg_color=T["bg_mid"],
        )
        self.fmt_combo.set(config.get("default_format", "mp3"))
        self.fmt_combo.pack()

        # Overwrite toggle
        ow_col = ctk.CTkFrame(opts_row, fg_color="transparent")
        ow_col.pack(side="left", padx=(0, 16))
        self._section_label(ow_col, " ")  # spacer
        self.overwrite_var = ctk.BooleanVar(value=config.get("overwrite_files", False))
        ctk.CTkCheckBox(
            ow_col,
            text="Overwrite existing",
            variable=self.overwrite_var,
            font=ctk.CTkFont(size=12),
            text_color=T["text_primary"],
            checkmark_color=T["amber"],
            fg_color=T["accent_red"],
            hover_color=T["accent_hover"],
            border_color="#555555",
        ).pack()

        # ── PO Token (collapsible) ─────────────────────────────────── #
        self._section_label(outer, "YouTube PO Token  (optional)")
        self.po_entry = ctk.CTkEntry(
            outer,
            placeholder_text="Leave blank unless YouTube is blocking downloads",
            height=34,
            font=ctk.CTkFont(size=11),
            fg_color=T["bg_mid"],
            border_color="#333333",
            border_width=1,
            text_color=T["text_primary"],
        )
        saved_token = config.get("po_token", "")
        if saved_token:
            self.po_entry.insert(0, saved_token)
        self.po_entry.pack(fill="x", pady=(2, 12))

        # ── Add to Queue button ────────────────────────────────────── #
        add_btn = ctk.CTkButton(
            outer,
            text="＋  Add to Queue",
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=T["accent_red"],
            hover_color=T["accent_hover"],
            text_color="#FFFFFF",
            corner_radius=6,
            command=self._add_to_queue,
        )
        add_btn.pack(fill="x", pady=(4, 0))

        # ── Feedback label ─────────────────────────────────────────── #
        self.feedback_label = ctk.CTkLabel(
            outer,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=T["amber"],
        )
        self.feedback_label.pack(pady=(6, 0))

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    def _section_label(self, parent, text: str) -> None:
        ctk.CTkLabel(
            parent,
            text=text.upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=self.theme["text_dim"],
        ).pack(anchor="w", pady=(6, 1))

    def _browse(self) -> None:
        root_tk = tk.Tk()
        root_tk.withdraw()
        path = filedialog.askdirectory(
            title="🐺 Select Destination Folder",
            initialdir=self.dest_entry.get() or str(Path.home() / "Downloads"),
        )
        root_tk.destroy()
        if path:
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, path)
            config.set("default_destination", path)

    def _add_to_queue(self) -> None:
        url  = self.url_entry.get().strip()
        dest = self.dest_entry.get().strip()
        fmt  = self.fmt_combo.get()
        overwrite = self.overwrite_var.get()
        po_token  = self.po_entry.get().strip() or None

        if not url:
            self._feedback("⚠  Please enter a URL.", error=True)
            return
        if not dest:
            self._feedback("⚠  Please set a destination folder.", error=True)
            return

        # Persist prefs
        config.set("default_format", fmt)
        config.set("overwrite_files", overwrite)
        if po_token:
            config.set("po_token", po_token)

        queue.add(
            url=url,
            dest=Path(dest).resolve(),
            fmt=fmt,  # type: ignore
            overwrite=overwrite,
            po_token=po_token,
        )

        self.url_entry.delete(0, "end")
        self._feedback(f"✓  Added to queue: {url[:60]}{'...' if len(url) > 60 else ''}")

    def _feedback(self, msg: str, error: bool = False) -> None:
        color = self.theme["error"] if error else self.theme["amber"]
        self.feedback_label.configure(text=msg, text_color=color)
        self.parent.after(4000, lambda: self.feedback_label.configure(text=""))
