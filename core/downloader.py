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
from core.config import config
from core.deps import check_ytdlp, check_spotdl, check_ffmpeg, check_deno, get_spotdl_cmd


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
    Download via yt-dlp.
    When frozen (exe): uses yt-dlp Python API directly — no external binary needed.
    When from source: uses CLI subprocess via get_ytdlp_cmd().
    """
    dest.mkdir(parents=True, exist_ok=True)

    from core.deps import IS_FROZEN, get_ytdlp_cmd, check_deno, get_deno_path

    if IS_FROZEN:
        return _download_ytdlp_api(url, dest, fmt, overwrite, po_token, on_progress)
    else:
        return _download_ytdlp_subprocess(url, dest, fmt, overwrite, po_token, on_progress)


def _build_ydl_opts(
    url: str,
    dest: Path,
    fmt: FormatType,
    overwrite: bool,
    po_token: Optional[str],
    on_progress: Optional[Callable[[float, str], None]],
) -> dict:
    """Shared yt-dlp options used by both API and subprocess paths."""
    # Detect playlist
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

    opts: dict = {
        "outtmpl": outtmpl,
        "noplaylist": False,
        "ignoreerrors": True,
        "writethumbnail": True,
        "overwrites": overwrite,
        "progress_hooks": [make_progress_hook(on_progress)],
        "postprocessors": [],
        "extractor_args": {"youtube": {"player_client": ["web", "ios", "mweb"]}},
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        },
    }

    if po_token and po_token.strip():
        opts["extractor_args"]["youtube"]["po_token"] = po_token.strip()

    if fmt in ("mp3", "flac"):
        opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
        opts["postprocessors"].extend([
            {"key": "FFmpegExtractAudio", "preferredcodec": fmt,
             "preferredquality": "320" if fmt == "mp3" else "0"},
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ])
    elif fmt in ("mp4", "mkv"):
        opts["format"] = "bestvideo+bestaudio/best"
        opts["merge_output_format"] = fmt
        opts["postprocessors"].extend([
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ])

    return opts


def _download_ytdlp_api(
    url: str,
    dest: Path,
    fmt: FormatType,
    overwrite: bool,
    po_token: Optional[str],
    on_progress: Optional[Callable[[float, str], None]],
) -> bool:
    """yt-dlp via Python API — used when running as frozen exe (yt-dlp is bundled)."""
    try:
        import yt_dlp
        opts = _build_ydl_opts(url, dest, fmt, overwrite, po_token, on_progress)

        from core.deps import check_deno, get_deno_path
        if check_deno():
            deno = get_deno_path()
            if deno:
                opts["extractor_args"]["youtube"]["player_client"] = ["web", "ios", "mweb"]

        if on_progress:
            on_progress(0.0, "Starting...")

        with yt_dlp.YoutubeDL(opts) as ydl:
            ret = ydl.download([url])

        if on_progress:
            on_progress(100.0, "Done")

        return ret == 0
    except Exception as e:
        logger.error(f"yt-dlp API failed: {e}")
        return False


def _download_ytdlp_subprocess(
    url: str,
    dest: Path,
    fmt: FormatType,
    overwrite: bool,
    po_token: Optional[str],
    on_progress: Optional[Callable[[float, str], None]],
) -> bool:
    """yt-dlp via subprocess — used when running from source."""
    from core.deps import get_ytdlp_cmd, check_deno, get_deno_path

    opts = _build_ydl_opts(url, dest, fmt, overwrite, po_token, on_progress)
    outtmpl = opts["outtmpl"]

    base_cmd = get_ytdlp_cmd()
    args = base_cmd + [
        "-o", outtmpl,
        "--ignore-errors",
        "--write-thumbnail",
        "--add-metadata",
        "--extractor-args", "youtube:player_client=web,ios,mweb",
    ]

    deno = get_deno_path()
    if check_deno() and deno:
        args += ["--remote-components", "ejs:github", "--js-runtimes", f"deno:{deno}"]

    if po_token and po_token.strip():
        args += ["--extractor-args", f"youtube:po_token={po_token.strip()}"]

    if not overwrite:
        args.append("--no-overwrites")

    if fmt == "mp3":
        args += ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "320", "--embed-thumbnail"]
    elif fmt == "flac":
        args += ["--extract-audio", "--audio-format", "flac", "--audio-quality", "0", "--embed-thumbnail"]
    elif fmt in ("mp4", "mkv"):
        args += ["-f", "bestvideo+bestaudio/best", "--merge-output-format", fmt, "--embed-thumbnail"]

    args.append(url)

    try:
        if on_progress:
            on_progress(0.0, "Starting...")

        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:  # type: ignore
            line = line.rstrip()
            logger.debug(f"[yt-dlp] {line}")
            if on_progress and "%" in line and "[download]" in line:
                try:
                    pct = float(line.split("%")[0].split()[-1])
                    fname = line.split("of")[0].replace("[download]", "").strip()
                    on_progress(pct, fname)
                except Exception:
                    pass
        proc.wait()

        if on_progress:
            on_progress(100.0, "Done")

        return proc.returncode == 0
    except Exception as e:
        logger.error(f"yt-dlp subprocess failed: {e}")
        return False


# ------------------------------------------------------------------ #
#  SpotDL download                                                     #
# ------------------------------------------------------------------ #

from core.config import config

# Spotify-specific error types
class SpotifyRateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        hours = retry_after // 3600
        mins  = (retry_after % 3600) // 60
        super().__init__(
            f"Spotify API rate limit hit. Retry after {hours}h {mins}m. "
            f"Fix: Add your own Spotify API credentials in Settings → Spotify API Credentials "
            f"(get them free at developer.spotify.com)."
        )

class SpotifyNoCredsWarning(Exception):
    pass


def download_spotify(
    url: str,
    dest: Path,
    overwrite: bool = False,
    on_progress: Optional[Callable[[float, str], None]] = None,
) -> bool:
    """
    Download via SpotDL. Returns True on success, False on failure.
    Raises SpotifyRateLimitError if Spotify API rate limit is hit.
    """
    dest.mkdir(parents=True, exist_ok=True)

    # Lazy install — only installs spotdl the first time a Spotify URL is used
    from core.deps import ensure_spotdl
    if not ensure_spotdl(log=lambda m: logger.info(m)):
        raise RuntimeError(
            "SpotDL could not be installed automatically. "
            "Install manually: uv tool install spotdl"
        )

    client_id     = config.get("spotify_client_id", "").strip()
    client_secret = config.get("spotify_client_secret", "").strip()
    has_creds     = bool(client_id and client_secret)

    if not has_creds:
        logger.warning(
            "No Spotify API credentials set. Using SpotDL shared credentials — "
            "rate limits are more likely. Add your own in Settings → Spotify API Credentials."
        )

    is_playlist = any(x in url.lower() for x in ["/playlist/", "/album/"])
    dest_posix  = dest.as_posix()

    output_template = (
        f"{dest_posix}/{{list-name}}/{{title}}.{{output-ext}}"
        if is_playlist
        else f"{dest_posix}/{{title}}.{{output-ext}}"
    )

    cmd = get_spotdl_cmd() + [
        "download", url,
        "--output", output_template,
        "--format", "mp3",
    ]
    if overwrite:
        cmd.extend(["--overwrite", "force"])
    else:
        cmd.extend(["--overwrite", "skip"])

    if has_creds:
        cmd.extend(["--client-id", client_id, "--client-secret", client_secret])

    try:
        if on_progress:
            on_progress(0.0, "Starting SpotDL...")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        output_lines: list[str] = []
        for line in proc.stdout:  # type: ignore
            line = line.rstrip()
            output_lines.append(line)
            logger.debug(f"[spotdl] {line}")

            # Detect rate limit in real-time
            if "rate/request limit" in line.lower() or "retry will occur after" in line.lower():
                retry_after = 86400  # default 24h
                import re
                match = re.search(r"after[:\s]+(\d+)\s*s", line, re.IGNORECASE)
                if match:
                    retry_after = int(match.group(1))
                proc.kill()
                raise SpotifyRateLimitError(retry_after)

        proc.wait()

        # Check output for rate limit even if it didn't raise mid-stream
        full_output = "\n".join(output_lines)
        if "rate/request limit" in full_output.lower():
            import re
            match = re.search(r"after[:\s]+(\d+)\s*s", full_output, re.IGNORECASE)
            retry_after = int(match.group(1)) if match else 86400
            raise SpotifyRateLimitError(retry_after)

        if on_progress:
            on_progress(100.0, "SpotDL finished")

        return proc.returncode == 0

    except SpotifyRateLimitError:
        raise  # Re-raise so queue_manager can surface it properly
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