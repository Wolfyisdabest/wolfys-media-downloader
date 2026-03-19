# 🐺 Wolfy's Media Downloader — V2.0

A clean, expandable media downloader for YouTube, Spotify, and more.
Built from the ground up as a proper Python project — not Copilot spaghetti.

---

## ✨ What's new in V2.0

| Feature | V1 | V2 |
|---|---|---|
| GUI layout | `.pack()` soup | Tabbed, modular |
| Download queue | ❌ | ✅ Multi-URL queue |
| Progress bar | ❌ | ✅ Per-download |
| Download history | ❌ | ✅ Last 100 entries |
| CLI fallback | ❌ | ✅ Full `--cli` mode |
| Code structure | Single 500-line file | Split modules |
| Config | ✅ | ✅ Improved |

---

## 🚀 Quick Start

### Requirements
- Python 3.10+
- FFmpeg in PATH ([download](https://ffmpeg.org/download.html) or `winget install ffmpeg`)

```bash
# Clone
git clone https://github.com/wolfy213/wolfys-media-downloader.git
cd wolfys-media-downloader

# Install deps
pip install -r requirements.txt

# Run
python main.py
```

### CLI Mode
```bash
# Interactive CLI
python main.py --cli

# Direct download
python main.py --cli --url "https://youtube.com/..." --dest "C:/Downloads" --format mp3
```

---

## 📁 Project Structure

```
wmd_v2/
├── main.py                   # Entry point
├── requirements.txt
├── core/
│   ├── config.py             # Persistent settings
│   ├── downloader.py         # yt-dlp + SpotDL logic
│   ├── queue_manager.py      # Thread-safe download queue
│   └── cli.py                # CLI fallback
└── gui/
    ├── app.py                # Main window + theme
    └── tabs/
        ├── download_tab.py   # URL input + add to queue
        ├── queue_tab.py      # Live queue with progress bars
        ├── history_tab.py    # Download history
        └── settings_tab.py   # Theme, defaults, dep status
```

---

## ⚙️ Supported Formats

| Format | Source | Notes |
|--------|--------|-------|
| MP3 | YouTube / generic | 320kbps, metadata + thumbnail embedded |
| FLAC | YouTube / generic | Lossless |
| MP4 | YouTube / generic | Best quality video |
| MKV | YouTube / generic | Best quality video |
| MP3 | Spotify | Via SpotDL |

---

## 🔧 YouTube PO Tokens

If YouTube starts blocking downloads, you may need a PO token.
Enter it in the Download tab or Settings. It's saved locally.

Guide: https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide

---

## 🏗️ Building an .exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "WolfysMediaDownloader" main.py
```

---

## ⚠️ Disclaimer

Personal use only. Respect copyright laws and platform ToS.
