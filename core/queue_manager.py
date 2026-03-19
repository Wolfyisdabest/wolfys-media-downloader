"""
core/queue_manager.py
Thread-safe download queue. Each item runs in its own thread.
GUI subscribes via callbacks; CLI can poll status directly.
"""

from __future__ import annotations
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional

from core.downloader import download, FormatType
from core.config import config


class Status(Enum):
    PENDING   = auto()
    RUNNING   = auto()
    DONE      = auto()
    FAILED    = auto()
    CANCELLED = auto()


@dataclass
class QueueItem:
    url:        str
    dest:       Path
    fmt:        FormatType
    overwrite:  bool
    po_token:   Optional[str]
    id:         str              = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status:     Status           = Status.PENDING
    progress:   float            = 0.0
    filename:   str              = ""
    error:      str              = ""
    started_at: float            = 0.0
    ended_at:   float            = 0.0
    cancel_event: threading.Event = field(default_factory=threading.Event)


# Callback type: (item_id, status, progress, filename) -> None
ProgressCallback = Callable[[str, Status, float, str], None]


class DownloadQueue:
    """
    Manages a FIFO queue of download jobs.
    One job runs at a time (expandable to N workers later).
    """

    def __init__(self, on_update: Optional[ProgressCallback] = None) -> None:
        self._items:     Dict[str, QueueItem] = {}
        self._order:     List[str]            = []
        self._lock:      threading.Lock       = threading.Lock()
        self._on_update: Optional[ProgressCallback] = on_update
        self._worker:    Optional[threading.Thread] = None
        self._stop_flag: bool = False

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def add(
        self,
        url: str,
        dest: Path,
        fmt: FormatType = "mp3",
        overwrite: bool = False,
        po_token: Optional[str] = None,
    ) -> str:
        """Add a URL to the queue. Returns the item ID."""
        item = QueueItem(url=url, dest=dest, fmt=fmt, overwrite=overwrite, po_token=po_token)
        with self._lock:
            self._items[item.id] = item
            self._order.append(item.id)
        self._notify(item)
        self._ensure_worker()
        return item.id

    def cancel(self, item_id: str) -> None:
        """Cancel a pending or running item."""
        with self._lock:
            item = self._items.get(item_id)
            if item and item.status in (Status.PENDING, Status.RUNNING):
                item.cancel_event.set()
                item.status = Status.CANCELLED
                self._notify(item)

    def remove(self, item_id: str) -> None:
        """Remove a finished/cancelled item from the list."""
        with self._lock:
            if item_id in self._items:
                del self._items[item_id]
            if item_id in self._order:
                self._order.remove(item_id)

    def clear_finished(self) -> None:
        finished = [
            iid for iid, item in self._items.items()
            if item.status in (Status.DONE, Status.FAILED, Status.CANCELLED)
        ]
        for iid in finished:
            self.remove(iid)

    def get_all(self) -> List[QueueItem]:
        with self._lock:
            return [self._items[iid] for iid in self._order if iid in self._items]

    def set_callback(self, cb: ProgressCallback) -> None:
        self._on_update = cb

    # ------------------------------------------------------------------ #
    #  Internal worker                                                     #
    # ------------------------------------------------------------------ #

    def _ensure_worker(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._run_worker, daemon=True)
            self._worker.start()

    def _run_worker(self) -> None:
        while True:
            item = self._next_pending()
            if item is None:
                break  # Nothing left, thread exits cleanly

            self._run_item(item)

    def _next_pending(self) -> Optional[QueueItem]:
        with self._lock:
            for iid in self._order:
                item = self._items.get(iid)
                if item and item.status == Status.PENDING:
                    return item
        return None

    def _run_item(self, item: QueueItem) -> None:
        # Don't start if already cancelled before worker picked it up
        if item.cancel_event.is_set():
            item.status = Status.CANCELLED
            item.ended_at = time.time()
            self._notify(item)
            return

        item.status = Status.RUNNING
        item.started_at = time.time()
        self._notify(item)

        def on_progress(pct: float, fname: str) -> None:
            if item.cancel_event.is_set():
                raise Exception("Download cancelled by user.")
            item.progress = pct
            item.filename = fname
            self._notify(item)

        try:
            success = download(
                url=item.url,
                dest=item.dest,
                fmt=item.fmt,
                overwrite=item.overwrite,
                po_token=item.po_token,
                on_progress=on_progress,
            )
            if item.cancel_event.is_set():
                item.status = Status.CANCELLED
            else:
                item.status = Status.DONE if success else Status.FAILED
        except Exception as e:
            if item.cancel_event.is_set():
                item.status = Status.CANCELLED
            else:
                item.status = Status.FAILED
                item.error = str(e)

        item.ended_at = time.time()
        item.progress = 100.0 if item.status == Status.DONE else item.progress
        self._notify(item)

        # Write to history
        config.add_history({
            "url":    item.url,
            "dest":   str(item.dest),
            "fmt":    item.fmt,
            "status": item.status.name,
            "time":   item.ended_at,
        })

    def _notify(self, item: QueueItem) -> None:
        if self._on_update:
            try:
                self._on_update(item.id, item.status, item.progress, item.filename)
            except Exception:
                pass


# Singleton queue — shared between GUI tabs
queue = DownloadQueue()