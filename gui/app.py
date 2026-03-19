"""
gui/app.py
Main application window. Tabbed layout: Download | Queue | History | Settings.
Built with CustomTkinter. Expandable — new tabs = new files.
"""

from __future__ import annotations
import logging
import ctypes
import sys
from pathlib import Path
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

# Resolve logo path — works in dev (relative to gui/) and as PyInstaller exe
def _get_asset_path(filename: str) -> Path:
    """Returns the correct path to a bundled asset in both dev and exe modes."""
    if getattr(sys, "frozen", False):
        # PyInstaller extracts bundled files to sys._MEIPASS
        return Path(sys._MEIPASS) / filename  # type: ignore
    else:
        # Dev mode — logo sits next to main.py (one level up from gui/)
        return Path(__file__).parent.parent / filename

LOGO_PNG = _get_asset_path("Wolfysdownloaderlogo.png")
LOGO_ICO = _get_asset_path("Wolfysdownloaderlogo.ico")


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

        # Apply window icon — try ICO first (best on Windows), fallback to PNG
        try:
            if LOGO_ICO.exists():
                self.root.iconbitmap(str(LOGO_ICO))
            elif LOGO_PNG.exists():
                from PIL import Image, ImageTk  # type: ignore
                img = Image.open(LOGO_PNG).resize((32, 32))
                photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, photo)
                self._icon_ref = photo  # prevent GC
        except Exception:
            pass  # Non-fatal — window just uses default icon

        self._build_header()
        self._build_tabs()

        # Wire queue updates to queue tab
        queue.set_callback(self._tabs["queue"].on_queue_update)

        # First-run dependency check — runs after mainloop starts
        self.root.after(500, self._check_deps)
        # Pre-fetch yt-dlp EJS solver script in background
        import threading
        threading.Thread(target=self._prefetch_components, daemon=True).start()

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

        # Logo image in header
        try:
            from PIL import Image
            img = Image.open(LOGO_PNG).resize((36, 36), Image.LANCZOS)
            self._header_logo = ctk.CTkImage(light_image=img, dark_image=img, size=(36, 36))
            ctk.CTkLabel(
                header,
                image=self._header_logo,
                text="",
            ).pack(side="left", padx=(12, 4), pady=8)
        except Exception:
            pass

        title = ctk.CTkLabel(
            header,
            text="Wolfy's Media Downloader",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=THEME["accent_hover"],
        )
        title.pack(side="left", padx=(2, 6), pady=8)

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

        tab_names = ["Download", "Queue", "History", "Settings"]
        if config.get("dev_mode", False):
            tab_names.append("Dev")

        for name in tab_names:
            tabview.add(name)

        tab_classes = {
            "Download": DownloadTab,
            "Queue":    QueueTab,
            "History":  HistoryTab,
            "Settings": SettingsTab,
        }

        if config.get("dev_mode", False):
            from gui.tabs.dev_tab import DevTab
            tab_classes["Dev"] = DevTab

        self._tabs: dict = {}
        for name, cls in tab_classes.items():
            frame = tabview.tab(name)
            frame.configure(fg_color=THEME["bg_panel"])
            self._tabs[name.lower()] = cls(frame, THEME)

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def _prefetch_components(self) -> None:
        from core.deps import prefetch_remote_components
        prefetch_remote_components()

    def _check_deps(self) -> None:
        """
        Auto-install ffmpeg silently. Only show dialog if it fails.
        yt-dlp is bundled. spotdl is lazy. deno is optional.
        """
        from core.deps import ensure_ffmpeg, any_missing
        # Try silent ffmpeg install first
        ensure_ffmpeg(log=lambda m: logger.info(f"[setup] {m}"))
        # Only pop dialog if something mandatory is still missing
        if any_missing():
            DepDialog.show_if_needed(self.root, THEME)

    def _on_close(self) -> None:
        config.set("window_geometry", self.root.geometry())
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()