# marquee

A private desktop app for watching videos together, in sync, with a clean look.

- Pick a room, share the invite link, press Ready.
- Shows who has which file and subtitle, notifies you when people join, and can start a voice call for the room.
- Updates itself from the releases on this page (Help > Update).

## Install

- **Windows:** run the `.exe`. Nothing else needs to be installed.
- **Linux (Mint, Ubuntu and similar, 64-bit):** download `marquee-linux-x86_64-vN.tar.xz` from the Releases page, extract it,
  and open the launcher inside the extracted folder. You also need a video player: mpv or VLC.

The first start shows an install window where you pick the folder and the shortcuts you want.

## Build from source

```
pip install -r requirements.txt -r requirements_gui.txt
python tools/make-exe.py --build N
python tools/make-release.py --build N
python tools/make-linux.py --build N
```

`tools/make-exe.py` builds the Windows app, `tools/make-linux.py` the Linux download and `tools/make-release.py` the zip the in-app update installs.

## Licence

Apache License 2.0, see `LICENSE`.
