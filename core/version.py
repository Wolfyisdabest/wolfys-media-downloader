"""
core/version.py
Single source for the local application version.
"""

from __future__ import annotations

APP_VERSION = "2.0.0"


def normalized_app_version() -> str:
    return APP_VERSION.lstrip("vV")
