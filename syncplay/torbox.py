import json
import os
import urllib.error
import urllib.parse
import urllib.request

import syncplay
from syncplay.private_build import BUILD
from syncplay import constants
from syncplay.opensubtitles import OpenSubtitlesClient

API_URL = "https://api.torbox.app/v1/api"
VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".m4v", ".mov", ".webm", ".ts", ".m2ts", ".wmv", ".flv", ".mpg", ".mpeg")

# The three kinds of item in a TorBox account, and the request parameter each kind uses to identify itself
KINDS = {"torrents": "torrent_id", "usenet": "usenet_id", "webdl": "web_id"}


class TorBoxError(Exception):
    """Raised for API/network problems; the message is safe to show to the user."""


class TorBoxFile(object):
    def __init__(self, fileId, name, size):
        self.fileId, self.name, self.size = fileId, name, size

    @property
    def shortName(self):
        return os.path.basename(self.name.replace("\\", "/"))


class TorBoxItem(object):
    def __init__(self, kind, itemId, name, files):
        self.kind, self.itemId, self.name, self.files = kind, itemId, name, files


def parseLibrary(kind, payload):
    """Items in the user's own account that are ready to stream, keeping only their video files."""
    items = []
    data = payload.get("data") if isinstance(payload, dict) else None
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict) or entry.get("id") is None:
            continue
        if not (entry.get("download_finished") or entry.get("download_present") or entry.get("cached")):
            continue  # Still downloading, so there is nothing to stream yet
        files = [TorBoxFile(f.get("id"), f.get("name") or f.get("short_name") or "", int(f.get("size") or 0))
                 for f in entry.get("files") or [] if isinstance(f, dict) and f.get("id") is not None]
        files = [f for f in files if f.name.lower().endswith(VIDEO_EXTENSIONS)]
        if files:
            files.sort(key=lambda f: f.name.lower())
            items.append(TorBoxItem(kind, entry["id"], entry.get("name") or files[0].shortName, files))
    items.sort(key=lambda i: i.name.lower())
    return items


class TorBoxClient(object):
    """Blocking client for the user's own TorBox account - call from a thread, not the reactor.

    The API key only ever goes to api.torbox.app; it is never logged or shared with other Syncplay users."""

    def __init__(self, apiKey, baseUrl=API_URL, urlopen=None):
        if not apiKey or not apiKey.strip():
            raise TorBoxError("No TorBox API key configured")
        self._apiKey = apiKey.strip()
        self._baseUrl = baseUrl
        self._urlopen = urlopen or OpenSubtitlesClient._defaultUrlopen

    def _get(self, path, params=None, authorized=True):
        query = "?" + urllib.parse.urlencode(params) if params else ""
        headers = {"User-Agent": "Syncplay-Marquee v{}".format(BUILD), "Accept": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer {}".format(self._apiKey)
        request = urllib.request.Request(self._baseUrl + path + query, headers=headers)
        try:
            with self._urlopen(request) as response:
                raw = response.read(constants.TORBOX_MAX_RESPONSE_BYTES)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise TorBoxError("TorBox rejected your API key - check it under Settings > API on torbox.app")
            raise TorBoxError("TorBox error {}".format(e.code))
        except (urllib.error.URLError, OSError) as e:
            raise TorBoxError("Could not reach TorBox: {}".format(getattr(e, "reason", e)))
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise TorBoxError("TorBox returned an unreadable response")
        if isinstance(payload, dict) and payload.get("success") is False:
            raise TorBoxError(payload.get("detail") or "TorBox reported an error")
        return payload

    def library(self):
        """Everything streamable in the account, across torrents, usenet and web downloads."""
        items = []
        for kind in KINDS:
            items.extend(parseLibrary(kind, self._get("/{}/mylist".format(kind), {"bypass_cache": "true"})))
        items.sort(key=lambda i: i.name.lower())
        return items

    def streamUrl(self, item, file_):
        """A direct https link to one file. append_name puts the file name in the URL so Syncplay can show it."""
        params = {"token": self._apiKey, KINDS[item.kind]: item.itemId, "file_id": file_.fileId,
                  "redirect": "false", "append_name": "true"}
        payload = self._get("/{}/requestdl".format(item.kind), params, authorized=False)
        link = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(link, str) or not link.startswith("https://"):
            raise TorBoxError("TorBox did not return a stream link")
        return link


# --- Searching and filtering the library ---------------------------------------------------------------------------

_RESOLUTIONS = (("2160p", r"2160p|4k|uhd"), ("1080p", r"1080[pi]"), ("720p", r"720p"), ("480p", r"480p|576p"))
_CODECS = (("AV1", r"av1"), ("HEVC", r"hevc|x265|h[. ]?265"), ("H.264", r"avc|x264|h[. ]?264"), ("VP9", r"vp9"),
           ("XviD", r"xvid|divx"))
_LANGUAGES = (("English", r"eng(?:lish)?"), ("German", r"ger(?:man)?|deu"), ("French", r"fre(?:nch)?|fra|vff"),
              ("Spanish", r"spa(?:nish)?|esp|latino"), ("Italian", r"ita(?:lian)?"), ("Japanese", r"jpn|jap(?:anese)?"),
              ("Swedish", r"swe(?:dish)?"), ("Multi", r"multi|dual"))

import re  # noqa: E402  (kept next to the patterns that use it)


def _tokenised(name):
    return " " + re.sub(r"[^a-z0-9]+", " ", name.lower()) + " "


def parseQuality(name):
    """Best-effort resolution/codec/HDR/language tags read from a file name (values are None/empty when unknown)."""
    text = _tokenised(name)
    resolution = next((label for label, pattern in _RESOLUTIONS if re.search(r" (?:%s) " % pattern, text)), None)
    codec = next((label for label, pattern in _CODECS if re.search(r" (?:%s) " % pattern, text)), None)
    hdr = bool(re.search(r" (?:hdr|hdr10|hdr10plus|dv|dovi|dolby vision) ", text) or "hdr10" in text.replace(" ", ""))
    languages = {label for label, pattern in _LANGUAGES if re.search(r" (?:%s) " % pattern, text)}
    return {"resolution": resolution, "codec": codec, "hdr": hdr, "languages": languages}


class LibraryFilters(object):
    """What to keep: text query plus the optional Stremio-style stream filters. None means 'Any'."""

    def __init__(self, query="", resolution=None, codec=None, hdr=None, language=None, minSize=None, maxSize=None):
        self.query, self.resolution, self.codec, self.hdr = query, resolution, codec, hdr
        self.language, self.minSize, self.maxSize = language, minSize, maxSize

    def accepts(self, item, file_):
        words = self.query.lower().split()
        haystack = (item.name + " " + file_.name).lower()
        if any(word not in haystack for word in words):
            return False
        quality = parseQuality(file_.name) if not item.name else _merge(parseQuality(item.name), parseQuality(file_.name))
        if self.resolution and quality["resolution"] != self.resolution:
            return False
        if self.codec and quality["codec"] != self.codec:
            return False
        if self.hdr is not None and quality["hdr"] != self.hdr:
            return False
        if self.language and self.language not in quality["languages"]:
            return False
        if self.minSize is not None and file_.size < self.minSize:
            return False
        if self.maxSize is not None and file_.size > self.maxSize:
            return False
        return True


def _merge(fromItem, fromFile):
    """File names often omit tags the torrent/folder name carries, so fall back to the item's."""
    return {"resolution": fromFile["resolution"] or fromItem["resolution"], "codec": fromFile["codec"] or fromItem["codec"],
            "hdr": fromFile["hdr"] or fromItem["hdr"], "languages": fromFile["languages"] | fromItem["languages"]}


def filterLibrary(items, filters):
    """[(item, [matching files])] for items with at least one matching file."""
    result = []
    for item in items:
        files = [f for f in item.files if filters.accepts(item, f)]
        if files:
            result.append((item, files))
    return result
