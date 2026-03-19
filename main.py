"""
Wolfy's Media Downloader - V2.0
================================
Entry point. Launches GUI or falls back to CLI.

Author: Wolfy (Sander Loenen)
"""

from __future__ import annotations
import sys
import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wolfy's Media Downloader V2.0",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--cli", action="store_true", help="Force CLI mode (no GUI)")
    parser.add_argument("--url", type=str, help="URL to download (CLI mode)")
    parser.add_argument("--dest", type=str, help="Destination folder (CLI mode)")
    parser.add_argument(
        "--format", type=str, choices=["mp3", "flac", "mp4", "mkv"], default="mp3",
        help="Output format (CLI mode, default: mp3)"
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.cli:
        from core.cli import run_cli
        run_cli(args)
        return

    # Try launching GUI
    try:
        import customtkinter  # noqa: F401
        from gui.app import WolfyApp
        app = WolfyApp()
        app.run()
    except ImportError:
        print("[WMD] customtkinter not found — falling back to CLI mode.")
        print("[WMD] Install it with: pip install customtkinter")
        print("[WMD] Or run with --cli flag for CLI mode.\n")
        from core.cli import run_cli
        run_cli(args)


if __name__ == "__main__":
    main()
