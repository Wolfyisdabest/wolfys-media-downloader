"""
gui/dep_dialog.py
First-run (and on-demand) dependency installer dialog.
Shows missing deps, lets user install them with a live log.
"""

from __future__ import annotations
import threading
from typing import Dict

import customtkinter as ctk

from core.deps import check_all, install_dep, install_all_missing


class DepDialog(ctk.CTkToplevel):
    """
    Modal-style dialog showing dependency status + install buttons.
    Call DepDialog.show_if_needed(parent, theme) to only show when something is missing.
    """

    def __init__(self, parent, theme: Dict[str, str]) -> None:
        super().__init__(parent)
        self.theme = theme
        T = theme

        self.title("🐺 Dependency Check")
        self.geometry("520x480")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_dark"])
        self.grab_set()  # modal

        self._status: Dict[str, bool] = check_all()
        self._build()

    def _build(self) -> None:
        T = self.theme

        ctk.CTkLabel(
            self,
            text="Dependency Check",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=T["accent_hover"],
        ).pack(pady=(16, 4))

        ctk.CTkLabel(
            self,
            text="Some required dependencies are missing or not detected.",
            font=ctk.CTkFont(size=11),
            text_color=T["text_dim"],
        ).pack(pady=(0, 10))

        # Dep rows
        self._rows_frame = ctk.CTkFrame(self, fg_color=T["bg_mid"], corner_radius=8)
        self._rows_frame.pack(fill="x", padx=16)
        self._render_rows()

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(10, 6))

        ctk.CTkButton(
            btn_row,
            text="Install All Missing",
            height=36,
            fg_color=T["accent_red"],
            hover_color=T["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._install_all,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            btn_row,
            text="Skip",
            height=36,
            fg_color="transparent",
            hover_color="#2a2a2a",
            border_color="#444444",
            border_width=1,
            text_color=T["text_dim"],
            font=ctk.CTkFont(size=12),
            command=self.destroy,
        ).pack(side="right", width=80)

        # Log output
        ctk.CTkLabel(
            self,
            text="INSTALL LOG",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=T["text_dim"],
        ).pack(anchor="w", padx=16)

        self._log = ctk.CTkTextbox(
            self,
            height=140,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=T["bg_dark"],
            text_color=T["text_primary"],
            border_color="#333333",
            border_width=1,
        )
        self._log.pack(fill="both", expand=True, padx=16, pady=(2, 14))
        self._log.configure(state="disabled")

    def _render_rows(self) -> None:
        for w in self._rows_frame.winfo_children():
            w.destroy()
        T = self.theme

        DEP_LABELS = {
            "yt-dlp": "yt-dlp  (YouTube downloader)",
            "spotdl":  "SpotDL  (Spotify downloader)",
            "ffmpeg":  "FFmpeg  (audio/video converter)",
            "deno":    "Deno  (JS runtime — required by yt-dlp)",
        }

        for name, ok in self._status.items():
            row = ctk.CTkFrame(self._rows_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=5)

            ctk.CTkLabel(
                row, text="●",
                font=ctk.CTkFont(size=13),
                text_color=T["success"] if ok else T["error"],
                width=20,
            ).pack(side="left")

            ctk.CTkLabel(
                row,
                text=DEP_LABELS.get(name, name),
                font=ctk.CTkFont(size=12),
                text_color=T["text_primary"] if not ok else T["text_dim"],
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            if not ok:
                ctk.CTkButton(
                    row,
                    text="Install",
                    width=70,
                    height=26,
                    fg_color=T["accent_red"],
                    hover_color=T["accent_hover"],
                    text_color="#FFFFFF",
                    font=ctk.CTkFont(size=11),
                    command=lambda n=name: self._install_one(n),
                ).pack(side="right")

    def _log_write(self, msg: str) -> None:
        def _do():
            self._log.configure(state="normal")
            self._log.insert("end", msg + "\n")
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _do)

    def _install_one(self, name: str) -> None:
        threading.Thread(
            target=self._run_install,
            args=([name],),
            daemon=True,
        ).start()

    def _install_all(self) -> None:
        missing = [n for n, ok in self._status.items() if not ok]
        threading.Thread(
            target=self._run_install,
            args=(missing,),
            daemon=True,
        ).start()

    def _run_install(self, names: list[str]) -> None:
        for name in names:
            install_dep(name, log=self._log_write)
        # Recheck and refresh rows
        self._status = check_all()
        self.after(0, self._render_rows)

    # ------------------------------------------------------------------ #
    #  Class method: show only if deps are missing                        #
    # ------------------------------------------------------------------ #

    @classmethod
    def show_if_needed(cls, parent, theme: Dict[str, str]) -> None:
        from core.deps import any_missing
        if any_missing():
            cls(parent, theme)
