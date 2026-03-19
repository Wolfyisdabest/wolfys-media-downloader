"""
gui/tabs/queue_tab.py
Live download queue view — one row per item with progress bar.
Updated via queue_manager callbacks (thread-safe via after()).
"""

from __future__ import annotations
from typing import Dict

import customtkinter as ctk

from core.queue_manager import Status, queue as q


# Status display config
STATUS_COLORS = {
    Status.PENDING:   "#777777",
    Status.RUNNING:   "#D4870A",
    Status.DONE:      "#4CAF50",
    Status.FAILED:    "#CF4444",
    Status.CANCELLED: "#555555",
}
STATUS_LABELS = {
    Status.PENDING:   "Pending",
    Status.RUNNING:   "Downloading",
    Status.DONE:      "Done",
    Status.FAILED:    "Failed",
    Status.CANCELLED: "Cancelled",
}


class QueueRow:
    """One row in the queue representing a single download item."""

    def __init__(self, parent: ctk.CTkScrollableFrame, item_id: str, url: str, theme: Dict) -> None:
        self.item_id = item_id
        self.theme   = theme

        T = theme
        self.frame = ctk.CTkFrame(parent, fg_color=T["bg_mid"], corner_radius=6)
        self.frame.pack(fill="x", padx=4, pady=3)

        # Top row: URL + status badge
        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(7, 2))

        self.url_label = ctk.CTkLabel(
            top,
            text=url[:72] + ("…" if len(url) > 72 else ""),
            font=ctk.CTkFont(size=12),
            text_color=T["text_primary"],
            anchor="w",
        )
        self.url_label.pack(side="left", fill="x", expand=True)

        self.status_label = ctk.CTkLabel(
            top,
            text="Pending",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=STATUS_COLORS[Status.PENDING],
            width=90,
            anchor="e",
        )
        self.status_label.pack(side="right")

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self.frame,
            height=6,
            corner_radius=3,
            fg_color="#2a2a2a",
            progress_color=T["accent_red"],
            mode="determinate",
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 4))

        # Bottom: filename + cancel button
        bottom = ctk.CTkFrame(self.frame, fg_color="transparent")
        bottom.pack(fill="x", padx=10, pady=(0, 6))

        self.file_label = ctk.CTkLabel(
            bottom,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=T["text_dim"],
            anchor="w",
        )
        self.file_label.pack(side="left", fill="x", expand=True)

        self.cancel_btn = ctk.CTkButton(
            bottom,
            text="✕",
            width=26,
            height=20,
            fg_color="transparent",
            hover_color="#2a2a2a",
            text_color=T["text_dim"],
            font=ctk.CTkFont(size=11),
            command=self._cancel,
        )
        self.cancel_btn.pack(side="right")

    def update(self, status: Status, progress: float, filename: str) -> None:
        color = STATUS_COLORS.get(status, "#777777")
        self.status_label.configure(
            text=STATUS_LABELS.get(status, "?"),
            text_color=color,
        )
        self.progress_bar.set(progress / 100.0)
        if status == Status.RUNNING:
            self.progress_bar.configure(progress_color=self.theme["accent_red"])
        elif status == Status.DONE:
            self.progress_bar.configure(progress_color=self.theme["success"])
        elif status == Status.FAILED:
            self.progress_bar.configure(progress_color=self.theme["error"])

        if filename:
            self.file_label.configure(text=filename[:80])

        # Hide cancel once terminal
        if status in (Status.DONE, Status.FAILED, Status.CANCELLED):
            self.cancel_btn.configure(state="disabled")

    def _cancel(self) -> None:
        q.cancel(self.item_id)


class QueueTab:
    def __init__(self, parent: ctk.CTkFrame, theme: Dict[str, str]) -> None:
        self.theme = theme
        self.rows: Dict[str, QueueRow] = {}
        self._build(parent)

    def _build(self, parent: ctk.CTkFrame) -> None:
        T = self.theme

        # Header bar
        hdr = ctk.CTkFrame(parent, fg_color="transparent", height=36)
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="DOWNLOAD QUEUE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=T["text_dim"],
        ).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="Clear Finished",
            width=110,
            height=26,
            fg_color="transparent",
            hover_color="#2a2a2a",
            border_color="#444444",
            border_width=1,
            text_color=T["text_dim"],
            font=ctk.CTkFont(size=11),
            command=self._clear_finished,
        ).pack(side="right")

        # Scrollable queue list
        self.list_frame = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
            scrollbar_button_color=T["accent_red"],
        )
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Empty state label
        self.empty_label = ctk.CTkLabel(
            self.list_frame,
            text="Queue is empty.\nAdd URLs from the Download tab.",
            font=ctk.CTkFont(size=13),
            text_color=T["text_dim"],
        )
        self.empty_label.pack(pady=40)

    # ------------------------------------------------------------------ #
    #  Queue callback (called from worker thread — marshalled via after)  #
    # ------------------------------------------------------------------ #

    def on_queue_update(self, item_id: str, status: Status, progress: float, filename: str) -> None:
        """Called by queue_manager on any status/progress change."""
        # Marshal to main thread
        self.list_frame.after(0, lambda: self._update_ui(item_id, status, progress, filename))

    def _update_ui(self, item_id: str, status: Status, progress: float, filename: str) -> None:
        # Get URL for new rows
        all_items = {i.id: i for i in q.get_all()}
        item = all_items.get(item_id)
        if not item:
            return

        if item_id not in self.rows:
            # New item — create row
            row = QueueRow(self.list_frame, item_id, item.url, self.theme)
            self.rows[item_id] = row
            self._update_empty_state()

        self.rows[item_id].update(status, progress, filename)

    def _clear_finished(self) -> None:
        q.clear_finished()
        finished = [
            iid for iid, row in self.rows.items()
            if row.status_label.cget("text") in ("Done", "Failed", "Cancelled")
        ]
        for iid in finished:
            self.rows[iid].frame.destroy()
            del self.rows[iid]
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        if self.rows:
            self.empty_label.pack_forget()
        else:
            self.empty_label.pack(pady=40)
