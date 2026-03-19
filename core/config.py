"""
core/config.py
Configuration manager — loads, saves, and validates user settings.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict


DEFAULTS: Dict[str, Any] = {
    "theme": "Dark",
    "default_format": "mp3",
    "default_destination": str(Path.home() / "Downloads"),
    "overwrite_files": False,
    "show_debug_log": True,
    "po_token": "",
    "window_geometry": "720x600",
    "history": [],          # List of completed download records
}


class Config:
    """Persistent config stored at %APPDATA%/WolfysMediaDownloader/config.json"""

    CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "WolfysMediaDownloader"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    def __init__(self) -> None:
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = self._load()

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _load(self) -> Dict[str, Any]:
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    on_disk = json.load(f)
                return {**DEFAULTS, **on_disk}
            except Exception:
                pass
        return DEFAULTS.copy()

    def _save(self) -> None:
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Save failed: {e}")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def add_history(self, record: Dict[str, Any]) -> None:
        """Append a download record. Keeps latest 100 entries."""
        history: list = self._data.get("history", [])
        history.insert(0, record)
        self._data["history"] = history[:100]
        self._save()

    def clear_history(self) -> None:
        self._data["history"] = []
        self._save()

    @property
    def config_path(self) -> str:
        return str(self.CONFIG_FILE)


# Singleton
config = Config()
