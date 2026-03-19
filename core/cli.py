"""
core/cli.py
CLI fallback — used when customtkinter isn't installed or --cli flag is passed.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

from core.downloader import download, check_ytdlp, check_spotdl, check_ffmpeg, FormatType
from core.config import config

# ANSI colors (same aesthetic as V1)
DARK_RED = "\033[31m"
CRIMSON  = "\033[91m"
AMBER    = "\033[93m"
CYAN     = "\033[96m"
WHITE    = "\033[97m"
RESET    = "\033[0m"

BANNER = f"""
{DARK_RED}██╗    ██╗███╗   ███╗██████╗ {RESET}
{DARK_RED}██║    ██║████╗ ████║██╔══██╗{RESET}
{DARK_RED}██║ █╗ ██║██╔████╔██║██║  ██║{RESET}
{DARK_RED}██║███╗██║██║╚██╔╝██║██║  ██║{RESET}
{DARK_RED}╚███╔███╔╝██║ ╚═╝ ██║██████╔╝{RESET}
 {AMBER}Wolfy's Media Downloader V2.0{RESET}
"""


def print_status() -> None:
    ytdlp   = f"{AMBER}✓{RESET}" if check_ytdlp()   else f"{CRIMSON}✗{RESET}"
    spotdl  = f"{AMBER}✓{RESET}" if check_spotdl()  else f"{CRIMSON}✗{RESET}"
    ffmpeg  = f"{AMBER}✓{RESET}" if check_ffmpeg()  else f"{CRIMSON}✗{RESET}"
    print(f"  yt-dlp  {ytdlp}   spotdl  {spotdl}   ffmpeg  {ffmpeg}\n")


def run_cli(args: argparse.Namespace) -> None:
    print(BANNER)
    print_status()

    url = args.url
    if not url:
        url = input(f"{AMBER}URL{RESET} > ").strip()
    if not url:
        print(f"{CRIMSON}No URL provided. Exiting.{RESET}")
        sys.exit(1)

    dest_str = args.dest or config.get("default_destination", str(Path.home() / "Downloads"))
    dest_str = input(f"{AMBER}Destination{RESET} [{dest_str}] > ").strip() or dest_str
    dest = Path(dest_str).resolve()

    fmt_default = getattr(args, "format", config.get("default_format", "mp3"))
    fmt_input = input(f"{AMBER}Format{RESET} (mp3/flac/mp4/mkv) [{fmt_default}] > ").strip() or fmt_default
    if fmt_input not in ("mp3", "flac", "mp4", "mkv"):
        fmt_input = "mp3"
    fmt: FormatType = fmt_input  # type: ignore

    overwrite = args.overwrite

    po_token: str | None = config.get("po_token") or None

    print(f"\n{DARK_RED}▶{RESET} Downloading {CYAN}{url}{RESET} → {CYAN}{dest}{RESET} [{fmt}]\n")

    def on_progress(pct: float, fname: str) -> None:
        bar_len = 30
        filled  = int(bar_len * pct / 100)
        bar     = f"{DARK_RED}{'█' * filled}{'░' * (bar_len - filled)}{RESET}"
        print(f"\r  {bar} {AMBER}{pct:5.1f}%{RESET}  {fname[:40]:<40}", end="", flush=True)

    success = download(url, dest, fmt, overwrite, po_token, on_progress)
    print()  # newline after progress bar

    if success:
        print(f"\n{AMBER}✓ Done.{RESET} Saved to {CYAN}{dest}{RESET}")
        config.add_history({"url": url, "dest": str(dest), "fmt": fmt, "status": "DONE"})
    else:
        print(f"\n{CRIMSON}✗ Download failed.{RESET} Check logs above.")
        sys.exit(1)
