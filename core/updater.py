"""
core/updater.py
Portable, user-controlled updater backed only by GitHub Releases.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from core.paths import APP_DIR, LOGS_DIR, TEMP_UPDATE_DIR
from core.version import APP_VERSION

REPO_OWNER = "Wolfyisdabest"
REPO_NAME = "Wolfys-media-downloader"
RELEASES_API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
RELEASES_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases"

INSTALLER_MARKERS = ("setup", "installer", "install", ".msi", "bootstrapper")
PORTABLE_MARKERS = ("portable", "wolfysmedia", "wolfys-media", "wolfys_media")
ASSET_EXTENSIONS = (".zip",)
REQUIRED_EXE = "WolfysMediaDownloader.exe"

ProgressCallback = Callable[[str, float, str], None]


@dataclass
class ReleaseAsset:
    name: str
    download_url: str
    size: int


@dataclass
class UpdateInfo:
    version: str
    tag: str
    html_url: str
    notes: str
    asset: Optional[ReleaseAsset]


def log_update(message: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGS_DIR / "updater.log"
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {message}\n")


def normalize_version(value: str) -> str:
    value = value.strip().lstrip("vV")
    match = re.search(r"\d+(?:\.\d+){0,3}(?:[-+][0-9A-Za-z.-]+)?", value)
    return match.group(0) if match else ""


def version_key(value: str) -> tuple:
    normalized = normalize_version(value)
    if not normalized:
        return ()
    main = re.split(r"[-+]", normalized, maxsplit=1)[0]
    parts = [int(p) for p in main.split(".") if p.isdigit()]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    r_key = version_key(remote)
    l_key = version_key(local)
    return bool(r_key and l_key and r_key > l_key)


def _request_json(url: str, timeout: int = 12) -> object:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"WolfysMediaDownloader/{APP_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def select_portable_asset(release: dict) -> Optional[ReleaseAsset]:
    candidates: list[tuple[int, dict]] = []
    for asset in release.get("assets", []) or []:
        name = str(asset.get("name", ""))
        lowered = name.lower()
        if not lowered.endswith(ASSET_EXTENSIONS):
            continue
        if any(marker in lowered for marker in INSTALLER_MARKERS):
            continue
        if "portable" not in lowered:
            continue

        score = 100
        if "win" in lowered or "windows" in lowered:
            score += 20
        if "x64" in lowered or "64" in lowered:
            score += 10
        if any(marker in lowered for marker in PORTABLE_MARKERS):
            score += 5
        candidates.append((score, asset))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    asset = candidates[0][1]
    return ReleaseAsset(
        name=str(asset.get("name", "")),
        download_url=str(asset.get("browser_download_url", "")),
        size=int(asset.get("size") or 0),
    )


def check_for_update(include_prerelease: bool = False) -> Optional[UpdateInfo]:
    try:
        releases = _request_json(RELEASES_API)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError("GitHub rate limit reached. Try again later.") from e
        raise RuntimeError(f"GitHub update check failed: HTTP {e.code}") from e
    except Exception as e:
        raise RuntimeError(f"Could not check GitHub Releases: {e}") from e

    if not isinstance(releases, list):
        raise RuntimeError("GitHub returned an unexpected release response.")

    for release in releases:
        if not isinstance(release, dict):
            continue
        if release.get("draft"):
            continue
        if release.get("prerelease") and not include_prerelease:
            continue
        tag = str(release.get("tag_name", ""))
        version = normalize_version(tag)
        if not version:
            continue
        if is_newer(version):
            return UpdateInfo(
                version=version,
                tag=tag,
                html_url=str(release.get("html_url") or RELEASES_URL),
                notes=str(release.get("body") or ""),
                asset=select_portable_asset(release),
            )
        return None
    return None


def _clean_update_workspace() -> tuple[Path, Path, Path]:
    TEMP_UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    archive = TEMP_UPDATE_DIR / "portable_update.zip"
    staging = TEMP_UPDATE_DIR / "staging"
    extracted = TEMP_UPDATE_DIR / "extracted"
    for path in (archive, staging, extracted):
        if path.is_file():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)
    staging.mkdir(parents=True, exist_ok=True)
    extracted.mkdir(parents=True, exist_ok=True)
    return archive, extracted, staging


def download_asset(asset: ReleaseAsset, target: Path, progress: ProgressCallback) -> None:
    req = urllib.request.Request(
        asset.download_url,
        headers={"User-Agent": f"WolfysMediaDownloader/{APP_VERSION}"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        total = int(response.headers.get("Content-Length") or asset.size or 0)
        downloaded = 0
        with open(target, "wb") as f:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                pct = (downloaded / total * 100) if total else 0
                progress("download", pct, f"Downloading {asset.name}")


def _find_payload_root(extracted: Path) -> Path:
    if (extracted / REQUIRED_EXE).exists():
        return extracted
    matches = [p.parent for p in extracted.rglob(REQUIRED_EXE)]
    if not matches:
        raise RuntimeError("Downloaded portable archive did not contain WolfysMediaDownloader.exe.")
    matches.sort(key=lambda p: len(p.parts))
    return matches[0]


def stage_update(archive: Path, extracted: Path, staging: Path, progress: ProgressCallback) -> Path:
    progress("extract", 0, "Extracting portable update")
    try:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extracted)
    except zipfile.BadZipFile as e:
        raise RuntimeError("Downloaded update is not a valid zip archive.") from e

    root = _find_payload_root(extracted)
    if (root / "Data").exists():
        log_update("Release archive contains Data folder; updater will ignore it.")

    progress("stage", 0, "Staging application files")
    for child in root.iterdir():
        if child.name.lower() == "data":
            continue
        dest = staging / child.name
        if child.is_dir():
            shutil.copytree(child, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(child, dest)

    if not (staging / REQUIRED_EXE).exists():
        raise RuntimeError("Staged update is missing WolfysMediaDownloader.exe.")
    return staging


def prepare_update(update: UpdateInfo, progress: ProgressCallback) -> Path:
    if not update.asset:
        raise RuntimeError("No portable release asset was found for the latest GitHub release.")

    archive, extracted, staging = _clean_update_workspace()
    log_update(f"Preparing update {update.tag} from {update.asset.name}")
    download_asset(update.asset, archive, progress)
    return stage_update(archive, extracted, staging, progress)


def _quote_ps(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def write_apply_script(staging: Path, current_pid: int) -> Path:
    script = TEMP_UPDATE_DIR / "apply_update.ps1"
    app_dir = APP_DIR.resolve()
    exe = app_dir / REQUIRED_EXE
    log = LOGS_DIR / "updater.log"

    body = f"""
$ErrorActionPreference = 'Stop'
$pidToWait = {current_pid}
$appDir = {_quote_ps(str(app_dir))}
$staging = {_quote_ps(str(staging.resolve()))}
$exe = {_quote_ps(str(exe))}
$log = {_quote_ps(str(log))}

function Write-UpdateLog($Message) {{
  $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  Add-Content -LiteralPath $log -Value "[$stamp] $Message"
}}

try {{
  Write-UpdateLog "Waiting for app process $pidToWait to exit."
  try {{ Wait-Process -Id $pidToWait -Timeout 120 }} catch {{ Start-Sleep -Seconds 3 }}

  if (-not (Test-Path -LiteralPath (Join-Path $staging 'WolfysMediaDownloader.exe'))) {{
    throw 'Staging folder is missing WolfysMediaDownloader.exe.'
  }}

  Write-UpdateLog 'Applying staged update.'
  Get-ChildItem -LiteralPath $staging -Force | ForEach-Object {{
    $dest = Join-Path $appDir $_.Name
    if ($_.PSIsContainer) {{
      Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force
    }} else {{
      Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
    }}
  }}

  Write-UpdateLog 'Cleaning temporary update files.'
  Remove-Item -LiteralPath (Split-Path -Parent $staging) -Recurse -Force -ErrorAction SilentlyContinue
  Write-UpdateLog 'Restarting application.'
  Start-Process -FilePath $exe -WorkingDirectory $appDir
}} catch {{
  Write-UpdateLog ("Update failed: " + $_.Exception.Message)
  Start-Process -FilePath $exe -WorkingDirectory $appDir
  exit 1
}}
"""
    script.write_text(body.strip() + "\n", encoding="utf-8")
    return script


def launch_apply_script(staging: Path) -> None:
    script = write_apply_script(staging, os.getpid())
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(script),
        ],
        cwd=str(APP_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
