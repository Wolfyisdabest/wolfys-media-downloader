"""
gui/tabs/history_tab.py
Shows the last 100 downloads from config history.
"""

from __future__ import annotations
import time
from typing import Dict

import customtkinter as ctk

from core.config import config


class HistoryTab:
    def __init__(self, parent: ctk.CTkFrame, theme: Dict[str, str]) -> None:
        self.theme = theme
        self._build(parent)

    def _build(self, parent: ctk.CTkFrame) -> None:
        T = self.theme

        hdr = ctk.CTkFrame(parent, fg_color="transparent", height=36)
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="DOWNLOAD HISTORY",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=T["text_dim"],
        ).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="Clear History",
            width=110,
            height=26,
            fg_color="transparent",
            hover_color="#2a2a2a",
            border_color="#444444",
            border_width=1,
            text_color=T["text_dim"],
            font=ctk.CTkFont(size=11),
            command=self._clear,
        ).pack(side="right")

        ctk.CTkButton(
            hdr,
            text="↺ Refresh",
            width=80,
            height=26,
            fg_color="transparent",
            hover_color="#2a2a2a",
            border_color="#444444",
            border_width=1,
            text_color=T["text_dim"],
            font=ctk.CTkFont(size=11),
            command=self._refresh,
        ).pack(side="right", padx=(0, 6))

        self.list_frame = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
            scrollbar_button_color=T["accent_red"],
        )
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._render()

    def _render(self) -> None:
        for w in self.list_frame.winfo_children():
            w.destroy()

        history = config.get("history", [])
        T = self.theme

        if not history:
            ctk.CTkLabel(
                self.list_frame,
                text="No downloads yet.",
                font=ctk.CTkFont(size=13),
                text_color=T["text_dim"],
            ).pack(pady=40)
            return

        for entry in history:
            row = ctk.CTkFrame(self.list_frame, fg_color=T["bg_mid"], corner_radius=5)
            row.pack(fill="x", padx=4, pady=2)

            status = entry.get("status", "?")
            color = T["success"] if status == "DONE" else T["error"]

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(5, 2))

            url = entry.get("url", "")
            ctk.CTkLabel(
                top,
                text=url[:70] + ("…" if len(url) > 70 else ""),
                font=ctk.CTkFont(size=12),
                text_color=T["text_primary"],
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(
                top,
                text=status,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=color,
                width=70,
                anchor="e",
            ).pack(side="right")

            bottom = ctk.CTkFrame(row, fg_color="transparent")
            bottom.pack(fill="x", padx=10, pady=(0, 5))

            dest = entry.get("dest", "")
            fmt  = entry.get("fmt", "")
            ts   = entry.get("time", 0)
            ts_str = time.strftime("%Y-%m-%d  %H:%M", time.localtime(ts)) if ts else ""

            ctk.CTkLabel(
                bottom,
                text=f"{fmt.upper()}  ·  {dest[:55]}{'…' if len(dest) > 55 else ''}  ·  {ts_str}",
                font=ctk.CTkFont(size=10),
                text_color=T["text_dim"],
                anchor="w",
            ).pack(side="left")

    def _refresh(self) -> None:
        self._render()

    def _clear(self) -> None:
        config.clear_history()
        self._render()
