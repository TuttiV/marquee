"""Remembers where each video was left, so it can be offered again ("Continue from 32:10")."""
import hashlib
import json
import os
import time

FILE_NAME = "resume-positions.json"
MAX_ENTRIES = 200
MIN_SECONDS = 60           # Not worth resuming before this
FINISHED_MARGIN = 90       # Within this of the end counts as finished
START_WINDOW = 15          # Only offer when the room is (still) near the beginning


def key(file_):
    """A stable id for a video: name, size and length (or just the address for a stream)."""
    name = (file_.get("name") or "").strip().lower()
    if name.startswith(("http://", "https://")):
        return hashlib.sha1(name.encode("utf-8")).hexdigest()
    raw = "{}|{}|{}".format(name, int(file_.get("size") or 0), int(round(file_.get("duration") or 0)))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class ResumeStore(object):
    def __init__(self, configDir):
        self._path = os.path.join(configDir, FILE_NAME)
        self._data = None

    def _load(self):
        if self._data is None:
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._data = data if isinstance(data, dict) else {}
            except (OSError, ValueError):
                self._data = {}
        return self._data

    def _save(self):
        data = self._load()
        if len(data) > MAX_ENTRIES:
            for old in sorted(data, key=lambda k: data[k].get("at", 0))[:len(data) - MAX_ENTRIES]:
                del data[old]
        temporary = self._path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(temporary, self._path)

    def get(self, file_):
        """Seconds to resume from, or None."""
        entry = self._load().get(key(file_))
        try:
            position = float(entry["position"]) if entry else None
        except (KeyError, TypeError, ValueError):
            return None
        return position if position and position >= MIN_SECONDS else None

    def remember(self, file_, position, now=None):
        """Record the position (or forget the video if it is finished or barely started)."""
        duration = float(file_.get("duration") or 0)
        k = key(file_)
        data = self._load()
        if position is None or position < MIN_SECONDS or (duration and position > duration - FINISHED_MARGIN):
            if k in data:
                del data[k]
                self._save()
            return
        if k in data and abs(float(data[k].get("position", 0)) - position) < 5:
            return  # Barely moved: don't rewrite the file every few seconds
        data[k] = {"position": round(float(position), 1), "at": now if now is not None else time.time(), "name": (file_.get("name") or "")[:120]}
        self._save()
