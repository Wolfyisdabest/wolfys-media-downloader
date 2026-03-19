"""
gui/app.py
Main application window. Tabbed layout: Download | Queue | History | Settings.
Built with CustomTkinter. Expandable — new tabs = new files.
"""

from __future__ import annotations
import logging
import ctypes
import sys
from typing import Optional

import customtkinter as ctk

from core.config import config
from core.queue_manager import queue
from gui.dep_dialog import DepDialog
from gui.tabs.download_tab import DownloadTab
from gui.tabs.queue_tab import QueueTab
from gui.tabs.history_tab import HistoryTab
from gui.tabs.settings_tab import SettingsTab

logger = logging.getLogger("WMD")


# ------------------------------------------------------------------ #
#  Theme constants — dark-red / black / amber wolf aesthetic          #
# ------------------------------------------------------------------ #

THEME = {
    "bg_dark":      "#0d0d0d",
    "bg_mid":       "#141414",
    "bg_panel":     "#1a1a1a",
    "accent_red":   "#8B0000",
    "accent_hover": "#B22222",
    "amber":        "#D4870A",
    "text_primary": "#E8E8E8",
    "text_dim":     "#777777",
    "success":      "#4CAF50",
    "error":        "#CF4444",
}


def apply_theme() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")


class WolfyApp:
    def __init__(self) -> None:
        apply_theme()

        # Hide console window when running as frozen exe
        if getattr(sys, "frozen", False):
            try:
                ctypes.windll.user32.ShowWindow(
                    ctypes.windll.kernel32.GetConsoleWindow(), 0
                )
            except Exception:
                pass

        self.root = ctk.CTk()
        self.root.title("🐺 Wolfy's Media Downloader  V2.0")
        self.root.geometry(config.get("window_geometry", "760x620"))
        self.root.minsize(680, 520)
        self.root.configure(fg_color=THEME["bg_dark"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_header()
        self._build_tabs()

        # Wire queue updates to queue tab
        queue.set_callback(self._tabs["queue"].on_queue_update)

        # First-run dependency check — runs after mainloop starts
        self.root.after(500, self._check_deps)

    # ------------------------------------------------------------------ #
    #  Layout                                                              #
    # ------------------------------------------------------------------ #

    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self.root,
            fg_color=THEME["bg_mid"],
            corner_radius=0,
            height=54,
        )
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        title = ctk.CTkLabel(
            header,
            text="🐺  Wolfy's Media Downloader",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=THEME["accent_hover"],
        )
        title.pack(side="left", padx=18, pady=8)

        version = ctk.CTkLabel(
            header,
            text="V2.0",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=THEME["text_dim"],
        )
        version.pack(side="left", pady=8)

    def _build_tabs(self) -> None:
        tabview = ctk.CTkTabview(
            self.root,
            fg_color=THEME["bg_panel"],
            segmented_button_fg_color=THEME["bg_mid"],
            segmented_button_selected_color=THEME["accent_red"],
            segmented_button_selected_hover_color=THEME["accent_hover"],
            segmented_button_unselected_color=THEME["bg_mid"],
            segmented_button_unselected_hover_color="#222222",
            text_color=THEME["text_primary"],
            text_color_disabled=THEME["text_dim"],
            border_color=THEME["accent_red"],
            border_width=1,
        )
        tabview.pack(fill="both", expand=True, padx=10, pady=(6, 10))

        for name in ("Download", "Queue", "History", "Settings"):
            tabview.add(name)

        tab_classes = {
            "Download": DownloadTab,
            "Queue":    QueueTab,
            "History":  HistoryTab,
            "Settings": SettingsTab,
        }

        self._tabs: dict = {}
        for name, cls in tab_classes.items():
            frame = tabview.tab(name)
            frame.configure(fg_color=THEME["bg_panel"])
            self._tabs[name.lower()] = cls(frame, THEME)

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def _check_deps(self) -> None:
        DepDialog.show_if_needed(self.root, THEME)

    def _on_close(self) -> None:
        config.set("window_geometry", self.root.geometry())
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()