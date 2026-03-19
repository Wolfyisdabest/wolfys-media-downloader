"""
core/deps.py
Dependency checker and auto-installer.
Handles: yt-dlp, spotdl, ffmpeg, deno (JS runtime for yt-dlp EJS).
"""

from __future__ import annotations
import subprocess
import sys
import platform
import logging
from typing import Callable, Optional

logger = logging.getLogger("WMD")


# ------------------------------------------------------------------ #
#  Check functions                                                     #
# ------------------------------------------------------------------ #

def check_ytdlp() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


def check_spotdl() -> bool:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "spotdl", "--version"],
            capture_output=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def check_ffmpeg() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def check_deno() -> bool:
    try:
        r = subprocess.run(["deno", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def check_all() -> dict[str, bool]:
    return {
        "yt-dlp":  check_ytdlp(),
        "spotdl":  check_spotdl(),
        "ffmpeg":  check_ffmpeg(),
        "deno":    check_deno(),
    }


def any_missing() -> bool:
    return not all(check_all().values())


# ------------------------------------------------------------------ #
#  Install functions                                                   #
# ------------------------------------------------------------------ #

def install_ytdlp(log: Optional[Callable[[str], None]] = None) -> bool:
    return _pip_install("yt-dlp", log)


def install_spotdl(log: Optional[Callable[[str], None]] = None) -> bool:
    return _pip_install("spotdl", log)


def install_ffmpeg(log: Optional[Callable[[str], None]] = None) -> bool:
    """
    Try winget first (Windows), fallback to instructions.
    ffmpeg can't be pip installed so we use winget on Windows.
    """
    if platform.system() == "Windows":
        return _winget_install("ffmpeg", log)
    else:
        if log:
            log("FFmpeg must be installed manually on this platform.")
            log("Visit: https://ffmpeg.org/download.html")
        return False


def install_deno(log: Optional[Callable[[str], None]] = None) -> bool:
    """
    Install Deno via the official installer script.
    Windows: PowerShell one-liner
    Linux/Mac: curl shell script
    """
    if log:
        log("Installing Deno (JS runtime for yt-dlp)...")

    try:
        if platform.system() == "Windows":
            cmd = [
                "powershell", "-Command",
                "irm https://deno.land/install.ps1 | iex"
            ]
        else:
            cmd = ["sh", "-c", "curl -fsSL https://deno.land/install.sh | sh"]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:  # type: ignore
            if log:
                log(line.rstrip())
        proc.wait()

        if proc.returncode == 0:
            if log:
                log("✓ Deno installed. You may need to restart the app for it to be detected.")
            return True
        else:
            if log:
                log("✗ Deno install failed. Install manually: https://deno.com")
            return False
    except Exception as e:
        if log:
            log(f"✗ Deno install error: {e}")
        return False


def install_dep(name: str, log: Optional[Callable[[str], None]] = None) -> bool:
    """Install a dependency by name. Returns True on success."""
    installers = {
        "yt-dlp":  install_ytdlp,
        "spotdl":  install_spotdl,
        "ffmpeg":  install_ffmpeg,
        "deno":    install_deno,
    }
    fn = installers.get(name)
    if fn is None:
        if log:
            log(f"Unknown dependency: {name}")
        return False
    return fn(log)


def install_all_missing(log: Optional[Callable[[str], None]] = None) -> dict[str, bool]:
    """Install all missing dependencies. Returns dict of name -> success."""
    results = {}
    for name, ok in check_all().items():
        if not ok:
            if log:
                log(f"\n── Installing {name} ──")
            results[name] = install_dep(name, log)
        else:
            results[name] = True
    return results


# ------------------------------------------------------------------ #
#  Internal helpers                                                    #
# ------------------------------------------------------------------ #

def _pip_install(package: str, log: Optional[Callable[[str], None]] = None) -> bool:
    if log:
        log(f"Installing {package} via pip...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "-U", package],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:  # type: ignore
            if log:
                log(line.rstrip())
        proc.wait()
        success = proc.returncode == 0
        if log:
            log(f"{'✓' if success else '✗'} {package} {'installed.' if success else 'failed.'}")
        return success
    except Exception as e:
        if log:
            log(f"✗ {package} install error: {e}")
        return False


def _winget_install(package: str, log: Optional[Callable[[str], None]] = None) -> bool:
    if log:
        log(f"Installing {package} via winget...")
    try:
        proc = subprocess.Popen(
            ["winget", "install", "--id", package, "-e", "--accept-source-agreements",
             "--accept-package-agreements"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:  # type: ignore
            if log:
                log(line.rstrip())
        proc.wait()
        success = proc.returncode == 0
        if log:
            log(f"{'✓' if success else '✗'} {package} {'installed.' if success else 'failed.'}")
        return success
    except Exception as e:
        if log:
            log(f"✗ {package} winget error: {e}")
            log("Install FFmpeg manually: https://ffmpeg.org/download.html")
        return False
