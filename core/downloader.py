"""
core/downloader.py
All download logic. Handles yt-dlp (YouTube/generic) and SpotDL (Spotify).
Designed to be called from both GUI and CLI without modification.
"""

from __future__ import annotations
import sys
import subprocess
import logging
from pathlib import Path
from typing import Callable, Literal, Optional

logger = logging.getLogger("WMD")

FormatType = Literal["mp3", "flac", "mp4", "mkv"]

# Re-export check functions from deps so existing callers don't break
from core.deps import check_ytdlp, check_spotdl, check_ffmpeg, check_deno


# ------------------------------------------------------------------ #
#  URL detection                                                       #
# ------------------------------------------------------------------ #

def is_spotify_url(url: str) -> bool:
    url = url.lower()
    return any(p in url for p in [
        "open.spotify.com/",
        "spotify.com/",
        "spotify.link",
        "spotify:track:",
        "spotify:album:",
        "spotify:playlist:",
    ])

def is_playlist_url(url: str) -> bool:
    return any(x in url for x in ["/playlist", "list=", "channel/", "/album/", "/user/"])


# ------------------------------------------------------------------ #
#  Progress hook factory                                               #
# ------------------------------------------------------------------ #

def make_progress_hook(
    on_progress: Optional[Callable[[float, str], None]] = None
) -> Callable:
    """
    Returns a yt-dlp progress hook.
    on_progress(percent: float, filename: str) is called on each update.
    """
    def hook(d: dict) -> None:
        if d.get("status") == "downloading" and on_progress:
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = (downloaded / total) * 100
                fname = Path(d.get("filename", "")).name
                on_progress(pct, fname)
        elif d.get("status") == "finished" and on_progress:
            fname = Path(d.get("filename") or d.get("filepath", "")).name
            on_progress(100.0, fname)
    return hook


# ------------------------------------------------------------------ #
#  yt-dlp download                                                     #
# ------------------------------------------------------------------ #

def download_ytdlp(
    url: str,
    dest: Path,
    fmt: FormatType = "mp3",
    overwrite: bool = False,
    po_token: Optional[str] = None,
    on_progress: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """
    Download via yt-dlp. Returns True on success, False on failure.
    Supports mp3, flac, mp4, mkv.
    """
    dest.mkdir(parents=True, exist_ok=True)

    # Detect playlist for subfolder organisation
    playlist_detected = False
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "ignoreerrors": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                if isinstance(info.get("entries"), list) or info.get("_type") in [
                    "playlist", "multi_video", "youtube_tab"
                ]:
                    playlist_detected = True
    except Exception:
        playlist_detected = is_playlist_url(url)

    outtmpl = (
        str(dest / "%(playlist_title)s" / "%(title)s.%(ext)s")
        if playlist_detected
        else str(dest / "%(title)s.%(ext)s")
    )

    # Base yt-dlp options
    ydl_opts: dict = {
        "outtmpl": outtmpl,
        "noplaylist": False,
        "ignoreerrors": True,
        "writethumbnail": True,
        "overwrites": overwrite,
        "progress_hooks": [make_progress_hook(on_progress)],
        "postprocessors": [],
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "ios", "mweb"],
            }
        },
        "js_runtimes": ["deno"] if check_deno() else [],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    }

    if po_token and po_token.strip():
        ydl_opts["extractor_args"]["youtube"]["po_token"] = po_token.strip()

    # Format-specific options
    if fmt in ("mp3", "flac"):
        ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
        ydl_opts["postprocessors"].extend([
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": fmt,
                "preferredquality": "320" if fmt == "mp3" else "0",
            },
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ])
    elif fmt in ("mp4", "mkv"):
        ydl_opts["format"] = "bestvideo+bestaudio/best"
        ydl_opts["merge_output_format"] = fmt
        ydl_opts["postprocessors"].extend([
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ])

    try:
        import yt_dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        logger.error(f"yt-dlp failed: {e}")
        return False


# ------------------------------------------------------------------ #
#  SpotDL download                                                     #
# ------------------------------------------------------------------ #

from core.config import config

def download_spotify(
    url: str,
    dest: Path,
    overwrite: bool = False,
    on_progress: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """
    Download via SpotDL. Returns True on success, False on failure.
    SpotDL doesn't expose per-track progress hooks easily, so we ping
    on_progress at start (0%) and end (100%).
    """
    dest.mkdir(parents=True, exist_ok=True)

    is_playlist = any(x in url.lower() for x in ["/playlist/", "/album/"])
    dest_posix = dest.as_posix()

    output_template = (
        f"{dest_posix}/{{list-name}}/{{title}}.{{output-ext}}"
        if is_playlist
        else f"{dest_posix}/{{title}}.{{output-ext}}"
    )

    cmd = [
        sys.executable, "-m", "spotdl", "download", url,
        "--output", output_template,
        "--format", "mp3",
    ]
    if overwrite:
        cmd.extend(["--overwrite", "force"])
    else:
        cmd.extend(["--overwrite", "skip"])

    client_id = config.get("spotify_client_id", "").strip()
    client_secret = config.get("spotify_client_secret", "").strip()
    if client_id and client_secret:
        cmd.extend(["--client-id", client_id, "--client-secret", client_secret])

    try:
        if on_progress:
            on_progress(0.0, "Starting SpotDL...")
        result = subprocess.run(cmd, check=False)
        if on_progress:
            on_progress(100.0, "SpotDL finished")
        return result.returncode == 0
    except Exception as e:
        logger.error(f"SpotDL failed: {e}")
        return False


# ------------------------------------------------------------------ #
#  Unified entry point                                                 #
# ------------------------------------------------------------------ #

def download(
    url: str,
    dest: Path,
    fmt: FormatType = "mp3",
    overwrite: bool = False,
    po_token: Optional[str] = None,
    on_progress: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """
    Route URL to correct downloader. Returns True on success.
    This is the single function GUI and CLI both call.
    """
    url = url.strip()
    if not url:
        logger.error("No URL provided.")
        return False

    if is_spotify_url(url):
        if not check_spotdl():
            logger.error("SpotDL not found. Install: pip install spotdl")
            return False
        return download_spotify(url, dest, overwrite, on_progress)
    else:
        if not check_ytdlp():
            logger.error("yt-dlp not found. Install: pip install yt-dlp")
            return False
        return download_ytdlp(url, dest, fmt, overwrite, po_token, on_progress)
