Place portable command-line tools here.

The build script downloads these files automatically when needed:

- ffmpeg.exe
- ffprobe.exe

When present, PyInstaller bundles this folder into the application. The app checks
this folder before looking at system PATH, so the built exe can run without a
machine-wide FFmpeg install.
