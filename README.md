# marquee

A private desktop app for watching videos together, in sync, with a clean look.

- Pick a room, share the invite link, press Ready.
- Shows who has which file and subtitle and notifies you when people join.
- Updates itself from the releases on this page (Help > Update).

## Install

- **Windows:** run the Setup `.exe`. It asks for the install folder and which shortcuts you want (Start menu,
  desktop), needs no administrator rights, and adds an uninstaller under Settings > Apps. The single `.exe` still works too.
- **Linux (Mint, Ubuntu and similar, 64-bit):** download `marquee-linux-x86_64-vN.tar.xz` from the Releases page, extract it,
  and open the launcher inside the extracted folder. You also need a video player: mpv or VLC.

Without Setup, the first start shows an install window where you pick the folder and the shortcuts you want.

## Build from source

```
pip install -r requirements.txt -r requirements_gui.txt
python tools/make-exe.py --build N
python tools/make-setup.py --build N
python tools/make-release.py --build N
python tools/make-linux.py --build N
```

`tools/make-exe.py` builds the single-file Windows app, `tools/make-setup.py` the Windows Setup wizard (needs NSIS, mingw-w64 and
ImageMagick), `tools/make-linux.py` the Linux download and `tools/make-release.py` the zip the in-app update installs.

## Licence

Apache License 2.0, see `LICENSE`.
