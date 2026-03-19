# WolfysMediaDownloader.spec
# PyInstaller build spec for Wolfy's Media Downloader V2.0
#
# Build with:   pyinstaller WolfysMediaDownloader.spec
# Or via uv:    uv run pyinstaller WolfysMediaDownloader.spec

import os
from pathlib import Path

ROOT = Path(SPECPATH)

block_cipher = None

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Bundle the logo so it's always available inside the exe
        (str(ROOT / 'Wolfysdownloaderlogo.png'), '.'),
        (str(ROOT / 'Wolfysdownloaderlogo.ico'), '.'),
        (str(ROOT / 'LICENSE'), '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'yt_dlp',
        'spotdl',
        'curl_cffi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WolfysMediaDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # No console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'Wolfysdownloaderlogo.ico'),
    # Windows version info — makes Windows treat it as a known app
    version='version_info.txt',
)
