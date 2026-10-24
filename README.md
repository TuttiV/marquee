# marquee

A private desktop app for watching videos together, in sync, with a clean look.

- Pick a room, share the invite link, press Ready.
- Shows who has which file and subtitle and notifies you when people join.
- Updates itself from the releases on this page (Help > Update).

## Install

- **Windows:** download `marquee-setup-vN.exe` from the Releases page and run it. It asks for the install folder and which
  shortcuts you want (Start menu, desktop), needs no administrator rights, and adds an uninstaller under Settings > Apps.
  Windows may warn that the file is unrecognised: choose More info > Run anyway.
- **Linux Mint, Ubuntu (64-bit):** download `marquee_N_amd64.deb` from the Releases page and open it. The package installer
  asks for your password once, adds mpv if you have no video player, and puts the app in the applications menu. Remove it
  with Help > Uninstall or like any other package.
- **Other Linux (64-bit):** download `marquee-linux-x86_64-vN.tar.xz`, extract it and open the launcher inside the extracted
  folder. You also need a video player: mpv or VLC.

Without Setup or the package, the first start shows an install window where you pick the folder and the shortcuts you want.

## Build from source

```
pip install -r requirements.txt -r requirements_gui.txt
python tools/make-exe.py --build N
python tools/make-setup.py --build N
python tools/make-release.py --build N
python tools/make-linux.py --build N
```

`tools/make-exe.py` builds the single-file Windows app, `tools/make-setup.py` the Windows Setup wizard (needs NSIS, mingw-w64 and
ImageMagick), `tools/make-linux.py` the Linux downloads (.tar.xz and .deb) and `tools/make-release.py` the zip the in-app update installs.

## Licence

Apache License 2.0, see `LICENSE`.
