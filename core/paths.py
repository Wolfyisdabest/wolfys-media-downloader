"""
core/paths.py
Portable application paths.
"""

from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = app_dir()
DATA_DIR = APP_DIR / "Data"
CONFIG_DIR = DATA_DIR / "config"
LOGS_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
TEMP_UPDATE_DIR = DATA_DIR / "temp_update"


def ensure_data_dirs() -> None:
    for path in (CONFIG_DIR, LOGS_DIR, CACHE_DIR, TEMP_UPDATE_DIR):
        path.mkdir(parents=True, exist_ok=True)


ensure_data_dirs()
