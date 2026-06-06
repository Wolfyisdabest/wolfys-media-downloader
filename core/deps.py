"""
core/deps.py
Dependency management — detection, lazy install, minimal footprint.

Philosophy:
  - yt-dlp     → bundled in exe via PyInstaller. No install needed for exe users.
  - ffmpeg      → only hard external requirement. Auto-installed silently via winget.
  - spotdl      → lazy: only installed when user actually submits a Spotify URL.
  - deno        → optional: only suggested if a YouTube download fails.
  - Python/uv   → not needed by exe users at all.
"""

from __future__ import annotations
import os
import shutil
import subprocess
import sys
import platform
import logging
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("WMD")

IS_FROZEN = getattr(sys, "frozen", False)
_WINDOWS_NO_WINDOW = (
    subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
)


def _subprocess_kwargs() -> dict:
    if platform.system() != "Windows":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "creationflags": _WINDOWS_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def _app_dirs() -> list[Path]:
    dirs: list[Path] = []
    if IS_FROZEN:
        dirs.append(Path(sys.executable).resolve().parent)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(Path(meipass))
    dirs.append(Path(__file__).resolve().parent.parent)
    dirs.append(Path.cwd())
    return list(dict.fromkeys(dirs))


# ------------------------------------------------------------------ #
#  Python interpreter resolution                                       #
# ------------------------------------------------------------------ #

def _real_python() -> Optional[str]:
    """Find a real Python interpreter. When frozen, searches the system."""
    if not IS_FROZEN:
        return sys.executable

    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            try:
                if subprocess.run(
                    [found, "--version"],
                    capture_output=True,
                    timeout=5,
                    **_subprocess_kwargs(),
                ).returncode == 0:
                    return found
            except Exception:
                pass

    appdata = Path(os.environ.get("APPDATA", ""))
    for p in sorted((appdata / "uv" / "python").glob("cpython-3*"), reverse=True):
        candidate = p / "python.exe"
        if candidate.exists():
            try:
                if subprocess.run(
                    [str(candidate), "--version"],
                    capture_output=True,
                    timeout=5,
                    **_subprocess_kwargs(),
                ).returncode == 0:
                    return str(candidate)
            except Exception:
                pass
    return None


# ------------------------------------------------------------------ #
#  Tool path resolution                                                #
# ------------------------------------------------------------------ #

def _tool_dirs() -> list[Path]:
    home = Path.home()
    dirs = []
    for base in _app_dirs():
        dirs.extend([
            base,
            base / "tools",
            base / "_internal" / "tools",
        ])

    dirs += [
        home / ".local" / "bin",
        home / ".cargo" / "bin",
    ]
    if platform.system() == "Windows":
        appdata = Path(os.environ.get("APPDATA", ""))
        localappdata = Path(os.environ.get("LOCALAPPDATA", ""))
        programdata = Path(os.environ.get("PROGRAMDATA", ""))
        dirs += [
            appdata / "uv" / "bin",
            appdata / "Python" / "Scripts",
            localappdata / "uv" / "bin",
            localappdata / "Microsoft" / "WinGet" / "Packages",
            localappdata / "Programs" / "Python" / "Scripts",
            localappdata / "Programs" / "Python" / "Launcher",
            localappdata / "Programs" / "Microsoft VS Code" / "bin",
            home / "scoop" / "shims",
            programdata / "scoop" / "shims",
            programdata / "chocolatey" / "bin",
        ]
        for p in sorted((appdata / "Python").glob("Python3*"), reverse=True):
            dirs.append(p / "Scripts")
        for p in sorted((localappdata / "Programs" / "Python").glob("Python3*"), reverse=True):
            dirs.append(p / "Scripts")
    else:
        dirs += [Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path("/usr/bin")]
    return [d for d in dirs if d.exists()]


def _find_tool(name: str) -> Optional[str]:
    exe = f"{name}.exe" if platform.system() == "Windows" else name
    for d in _tool_dirs():
        c = d / exe
        if c.exists():
            return str(c)
    found = shutil.which(name)
    if found:
        return found
    return None


def _run_ok(args: list[str], timeout: int = 8) -> bool:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            **_subprocess_kwargs(),
        ).returncode == 0
    except Exception:
        return False


def _run_install_command(
    args: list[str],
    log: Optional[Callable[[str], None]] = None,
    timeout: Optional[int] = None,
) -> bool:
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **_subprocess_kwargs(),
        )
        try:
            for line in proc.stdout:  # type: ignore
                if log:
                    log(line.rstrip())
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            if log:
                log("✗ Install command timed out.")
            return False
        return proc.returncode == 0
    except Exception as e:
        if log:
            log(f"✗ {e}")
        return False


# ------------------------------------------------------------------ #
#  Check functions                                                     #
# ------------------------------------------------------------------ #

def check_ytdlp() -> bool:
    if IS_FROZEN:
        try:
            import yt_dlp  # noqa: F401 — bundled by PyInstaller
            return True
        except ImportError:
            return False
    tool = _find_tool("yt-dlp")
    if tool and _run_ok([tool, "--version"]):
        return True
    py = _real_python()
    return bool(py and _run_ok([py, "-m", "yt_dlp", "--version"]))


def check_ffmpeg() -> bool:
    tool = _find_tool("ffmpeg")
    return bool(tool and _run_ok([tool, "-version"]))


def check_spotdl() -> bool:
    if IS_FROZEN:
        return True
    tool = _find_tool("spotdl")
    if tool and _run_ok([tool, "--version"], timeout=15):
        return True
    py = _real_python()
    return bool(py and _run_ok([py, "-m", "spotdl", "--version"], timeout=15))


def check_deno() -> bool:
    tool = _find_tool("deno")
    return bool(tool and _run_ok([tool, "--version"]))


def check_uv() -> bool:
    tool = _find_tool("uv")
    return bool(tool and _run_ok([tool, "--version"]))


def check_python() -> bool:
    return _real_python() is not None


# ------------------------------------------------------------------ #
#  Startup check — mandatory only                                      #
# ------------------------------------------------------------------ #

def check_mandatory() -> dict[str, bool]:
    """
    Only what's truly needed to run the app at all.
    yt-dlp is bundled in exe, so always True when frozen.
    ffmpeg is the only hard external requirement.
    """
    return {
        "yt-dlp": check_ytdlp(),
        "ffmpeg":  check_ffmpeg(),
    }


def check_all() -> dict[str, bool]:
    return {
        "yt-dlp":  check_ytdlp(),
        "ffmpeg":  check_ffmpeg(),
        "spotdl":  check_spotdl(),
        "deno":    check_deno(),
    }


def any_missing() -> bool:
    return not all(check_mandatory().values())


# ------------------------------------------------------------------ #
#  Command resolvers                                                   #
# ------------------------------------------------------------------ #

def get_ytdlp_cmd() -> list[str]:
    """
    Returns ["__api__"] when frozen (caller uses yt_dlp Python API directly).
    Returns CLI command when running from source.
    """
    if IS_FROZEN:
        return ["__api__"]
    tool = _find_tool("yt-dlp")
    if tool and _run_ok([tool, "--version"]):
        return [tool]
    py = _real_python()
    if py and _run_ok([py, "-m", "yt_dlp", "--version"]):
        return [py, "-m", "yt_dlp"]
    raise RuntimeError("yt-dlp not found.")


def get_spotdl_cmd() -> list[str]:
    if IS_FROZEN:
        return [sys.executable, "--internal-spotdl"]
    tool = _find_tool("spotdl")
    if tool and _run_ok([tool, "--version"], timeout=15):
        return [tool]
    py = _real_python()
    if py and _run_ok([py, "-m", "spotdl", "--version"], timeout=15):
        return [py, "-m", "spotdl"]
    raise RuntimeError("spotdl not found.")


def get_ffmpeg_path() -> Optional[str]:
    return _find_tool("ffmpeg")


def get_deno_path() -> Optional[str]:
    return _find_tool("deno")


# ------------------------------------------------------------------ #
#  Auto-install ffmpeg silently on first run                          #
# ------------------------------------------------------------------ #

def ensure_ffmpeg(log: Optional[Callable[[str], None]] = None) -> bool:
    """
    Auto-install ffmpeg via winget if missing.
    Called on startup — user never has to think about it.
    """
    if check_ffmpeg():
        return True

    if platform.system() != "Windows":
        if log:
            log("ffmpeg missing. Install: https://ffmpeg.org/download.html")
        return False

    winget = _find_tool("winget")
    if not winget or not _run_ok([winget, "--version"]):
        if log:
            log("✗ winget was not found. Install ffmpeg manually: winget install Gyan.FFmpeg")
        return False

    if log:
        log("Installing ffmpeg automatically via winget (one time only)...")

    installed = _run_install_command([
        winget, "install", "--id", "Gyan.FFmpeg", "-e",
        "--accept-source-agreements", "--accept-package-agreements", "--silent",
    ], log)
    _refresh_path()
    ok = check_ffmpeg()
    if log:
        if ok:
            log("✓ ffmpeg ready.")
        elif installed:
            log("✗ ffmpeg installed but was not detected. Restart the app or add ffmpeg to PATH.")
        else:
            log("✗ ffmpeg auto-install failed.")
            log("  Manual: winget install Gyan.FFmpeg")
    return ok


def ensure_ytdlp(log: Optional[Callable[[str], None]] = None) -> bool:
    """Install yt-dlp when running from source and it is missing."""
    if check_ytdlp():
        return True
    if IS_FROZEN:
        if log:
            log("✗ yt-dlp is missing from the bundled app.")
        return False
    if check_uv():
        ok = _uv_tool_install("yt-dlp", log)
    else:
        ok = _pip_install("yt-dlp", _real_python(), log)
    if ok:
        _refresh_path()
    return check_ytdlp()


def _refresh_path() -> None:
    if platform.system() != "Windows":
        return
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "[System.Environment]::GetEnvironmentVariable('PATH','Machine') + ';' + "
            "[System.Environment]::GetEnvironmentVariable('PATH','User')"],
            capture_output=True, text=True, timeout=5, **_subprocess_kwargs()
        )
        if r.returncode == 0 and r.stdout.strip():
            path_parts = [r.stdout.strip(), *[str(d) for d in _tool_dirs()]]
            os.environ["PATH"] = ";".join(dict.fromkeys(path_parts))
    except Exception:
        pass


# ------------------------------------------------------------------ #
#  Lazy spotdl install                                                 #
# ------------------------------------------------------------------ #

def ensure_spotdl(log: Optional[Callable[[str], None]] = None) -> bool:
    """
    Install spotdl only when a Spotify URL is actually submitted.
    Returns True if spotdl is available after this call.
    """
    if check_spotdl():
        return True
    if log:
        log("Installing SpotDL for Spotify support...")
    if check_uv():
        ok = _uv_tool_install("spotdl", log)
    else:
        ok = _pip_install("spotdl", _real_python(), log)
    if ok and check_spotdl():
        if log:
            log("✓ SpotDL ready.")
        return True
    if log:
        log("✗ SpotDL install failed.")
    return False


# ------------------------------------------------------------------ #
#  On-demand dep install (from dep dialog / settings)                  #
# ------------------------------------------------------------------ #

def install_dep(name: str, log: Optional[Callable[[str], None]] = None) -> bool:
    if name == "yt-dlp":
        return ensure_ytdlp(log)
    elif name == "ffmpeg":
        return ensure_ffmpeg(log)
    elif name == "spotdl":
        return ensure_spotdl(log)
    elif name == "deno":
        return _install_deno(log)
    elif name == "uv":
        return _install_uv(log)
    if log:
        log(f"Unknown dependency: {name}")
    return False


def prefetch_remote_components() -> None:
    """Pre-fetch yt-dlp EJS solver if Deno is available."""
    if not check_deno():
        return
    cmd = get_ytdlp_cmd()
    if cmd == ["__api__"]:
        return
    deno = get_deno_path()
    if not deno:
        return
    try:
        subprocess.run(
            cmd + ["--remote-components", "ejs:github",
                   "--js-runtimes", f"deno:{deno}",
                   "--simulate", "--quiet",
                   "https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            capture_output=True, timeout=30, **_subprocess_kwargs()
        )
    except Exception:
        pass


# ------------------------------------------------------------------ #
#  Internal installers                                                 #
# ------------------------------------------------------------------ #

def _uv_tool_install(package: str, log: Optional[Callable[[str], None]] = None) -> bool:
    uv = _find_tool("uv")
    if not uv or not _run_ok([uv, "--version"]):
        if log:
            log("✗ uv was not found.")
        return False
    if log:
        log(f"Installing {package} via uv...")
    ok = _run_install_command([uv, "tool", "install", package, "--upgrade"], log)
    _refresh_path()
    if log:
        log(f"{'✓' if ok else '✗'} {package} {'installed.' if ok else 'failed.'}")
    return ok


def _pip_install(package: str, py: Optional[str], log: Optional[Callable[[str], None]] = None) -> bool:
    if not py:
        if log:
            log("✗ No Python interpreter found.")
        return False
    if log:
        log(f"Installing {package} via pip...")
    ok = _run_install_command([py, "-m", "pip", "install", "-U", "--user", package], log)
    _refresh_path()
    if log:
        log(f"{'✓' if ok else '✗'} {package} {'installed.' if ok else 'failed.'}")
    return ok


def _install_deno(log: Optional[Callable[[str], None]] = None) -> bool:
    if log:
        log("Installing Deno (optional — improves YouTube compatibility)...")
    try:
        if platform.system() == "Windows":
            cmd = ["powershell", "-Command", "irm https://deno.land/install.ps1 | iex"]
        else:
            cmd = ["sh", "-c", "curl -fsSL https://deno.land/install.sh | sh"]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **_subprocess_kwargs(),
        )
        for line in proc.stdout:  # type: ignore
            if log:
                log(line.rstrip())
        proc.wait()
        ok = proc.returncode == 0
        _refresh_path()
        if log:
            if ok and check_deno():
                log("✓ Deno installed.")
            elif ok:
                log("✓ Deno installed. Restart app if it is not detected yet.")
            else:
                log("✗ Failed. Try: https://deno.com")
        return check_deno() if ok else False
    except Exception as e:
        if log:
            log(f"✗ {e}")
        return False


def _install_uv(log: Optional[Callable[[str], None]] = None) -> bool:
    if log:
        log("Installing uv...")
    try:
        if platform.system() == "Windows":
            cmd = ["powershell", "-Command", "irm https://astral.sh/uv/install.ps1 | iex"]
        else:
            cmd = ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **_subprocess_kwargs(),
        )
        for line in proc.stdout:  # type: ignore
            if log:
                log(line.rstrip())
        proc.wait()
        ok = proc.returncode == 0
        _refresh_path()
        if log:
            if ok and check_uv():
                log("✓ uv installed.")
            elif ok:
                log("✓ uv installed. Restart app if it is not detected yet.")
            else:
                log("✗ Failed. Try: https://docs.astral.sh/uv/")
        return check_uv() if ok else False
    except Exception as e:
        if log:
            log(f"✗ {e}")
        return False
