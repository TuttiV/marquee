"""Playlist text files: one link or file path per line (.m3u8 comments are skipped). Kept separate so the menu can say how
many entries a file holds without touching Syncplay's own loader."""
import os

SETTING = "lastPlaylistFile"  # Remembered so File > Reload playlist file works after a restart


def entries(path):
    """The entries in a playlist file, or None if it can't be read."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    if path.lower().endswith(".m3u8"):
        lines = [line for line in lines if line.strip() and not line.startswith("#")]
    return [line for line in lines if line.strip()]
