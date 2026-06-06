"""
gui/update_dialog.py
User-controlled update prompt and progress dialog.
"""

from __future__ import annotations

import threading
import sys
import webbrowser
from typing import Callable, Optional

import customtkinter as ctk

from core.config import config
from core.updater import UpdateInfo, launch_apply_script, prepare_update
from core.version import APP_VERSION


class UpdateDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        theme: dict[str, str],
        update: UpdateInfo,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        self.update = update
        self.on_close = on_close
        self.staging = None

        self.title("Update Available")
        self.geometry("560x460")
        self.resizable(False, False)
        self.configure(fg_color=theme["bg_dark"])
        self.protocol("WM_DELETE_WINDOW", self._remind_later)
        self.grab_set()
        self._build()

    def _build(self) -> None:
        T = self.theme
        ctk.CTkLabel(
            self,
            text=f"New version available: v{self.update.version}  (You have v{APP_VERSION})",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=T["accent_hover"],
        ).pack(anchor="w", padx=16, pady=(16, 6))

        asset_text = self.update.asset.name if self.update.asset else "No portable asset found"
        ctk.CTkLabel(
            self,
            text=f"Portable asset: {asset_text}",
            font=ctk.CTkFont(size=11),
            text_color=T["text_dim"],
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        self.notes = ctk.CTkTextbox(
            self,
            height=170,
            font=ctk.CTkFont(size=11),
            fg_color=T["bg_mid"],
            text_color=T["text_primary"],
            border_color="#333333",
            border_width=1,
        )
        self.notes.pack(fill="x", padx=16, pady=(0, 10))
        self.notes.insert("1.0", self.update.notes.strip() or "No release notes provided.")
        self.notes.configure(state="disabled")

        self.progress = ctk.CTkProgressBar(
            self,
            height=8,
            fg_color="#2a2a2a",
            progress_color=T["accent_red"],
            mode="determinate",
        )
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0, 6))

        self.status = ctk.CTkLabel(
            self,
            text="Choose an action.",
            font=ctk.CTkFont(size=11),
            text_color=T["text_dim"],
            anchor="w",
        )
        self.status.pack(fill="x", padx=16, pady=(0, 10))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))

        self.download_btn = ctk.CTkButton(
            row,
            text="Download",
            width=95,
            height=32,
            fg_color=T["bg_mid"],
            hover_color="#2a2a2a",
            border_color="#444444",
            border_width=1,
            text_color=T["text_primary"],
            command=self._download,
        )
        self.download_btn.pack(side="left", padx=(0, 6))

        self.update_btn = ctk.CTkButton(
            row,
            text="Update Now",
            width=105,
            height=32,
            fg_color=T["accent_red"],
            hover_color=T["accent_hover"],
            text_color="#FFFFFF",
            command=self._update_now,
        )
        self.update_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            row,
            text="Ignore",
            width=80,
            height=32,
            fg_color="transparent",
            hover_color="#2a2a2a",
            border_color="#444444",
            border_width=1,
            text_color=T["text_dim"],
            command=self._ignore,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            row,
            text="Remind Later",
            width=105,
            height=32,
            fg_color="transparent",
            hover_color="#2a2a2a",
            border_color="#444444",
            border_width=1,
            text_color=T["text_dim"],
            command=self._remind_later,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            row,
            text="GitHub",
            width=80,
            height=32,
            fg_color="transparent",
            hover_color="#2a2a2a",
            border_color="#444444",
            border_width=1,
            text_color=T["text_dim"],
            command=lambda: webbrowser.open(self.update.html_url),
        ).pack(side="right")

        if not self.update.asset:
            self.download_btn.configure(state="disabled")
            self.update_btn.configure(state="disabled")
            self.status.configure(
                text="Latest release exists, but no portable .zip asset was found.",
                text_color=T["error"],
            )

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.download_btn.configure(state=state)
        self.update_btn.configure(state=state)

    def _progress(self, _phase: str, pct: float, message: str) -> None:
        def apply() -> None:
            if pct:
                self.progress.set(max(0, min(1, pct / 100)))
            self.status.configure(text=message, text_color=self.theme["text_dim"])

        self.after(0, apply)

    def _prepare_async(self, apply_after: bool) -> None:
        def worker() -> None:
            try:
                self._progress("start", 1, "Preparing update...")
                staging = prepare_update(self.update, self._progress)
                self.staging = staging
                self.after(0, lambda: self._download_ready(apply_after))
            except Exception as e:
                message = str(e)
                self.after(0, lambda: self._failed(message))

        self._set_busy(True)
        threading.Thread(target=worker, daemon=True).start()

    def _download(self) -> None:
        self._prepare_async(apply_after=False)

    def _update_now(self) -> None:
        if self.staging:
            self._apply()
        else:
            self._prepare_async(apply_after=True)

    def _download_ready(self, apply_after: bool) -> None:
        self.progress.set(1)
        self._set_busy(False)
        if apply_after:
            self._apply()
            return
        self.status.configure(
            text="Update downloaded and staged. Choose Update Now to apply.",
            text_color=self.theme["success"],
        )

    def _apply(self) -> None:
        if not self.staging:
            self._failed("Update has not been staged yet.")
            return
        if not getattr(sys, "frozen", False):
            self._failed("Self-update can only be applied from the portable exe build.")
            return
        try:
            self.status.configure(text="Closing app to apply update...", text_color=self.theme["amber"])
            launch_apply_script(self.staging)
            self.after(300, lambda: self.master.destroy())
        except Exception as e:
            self._failed(str(e))

    def _failed(self, message: str) -> None:
        self._set_busy(False)
        self.status.configure(text=f"Update failed: {message}", text_color=self.theme["error"])

    def _ignore(self) -> None:
        config.set("skipped_update_version", self.update.version)
        self._close()

    def _remind_later(self) -> None:
        self._close()

    def _close(self) -> None:
        if self.on_close:
            self.on_close()
        self.destroy()
