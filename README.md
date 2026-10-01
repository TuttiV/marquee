# marquee

A private desktop app for watching videos together, in sync, with a clean look.

- Pick a room, share the invite link, press Ready.
- Shows who has which file and subtitle, notifies you when people join, and can start a voice call for the room.
- Updates itself from the releases on this page (Help > Update).

## Install

Download the latest `.exe` from the Releases page and run it. Nothing else needs to be installed.

## Build from source

```
pip install -r requirements.txt -r requirements_gui.txt
python tools/make-exe.py --build N
python tools/make-release.py --build N
```

`tools/make-exe.py` builds the single-file app and `tools/make-release.py` builds the zip the in-app update installs.

## Licence

Apache License 2.0, see `LICENSE`.
