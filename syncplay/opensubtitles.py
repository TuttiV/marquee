import json
import os
import re
import ssl
import struct
import urllib.error
import urllib.parse
import urllib.request

import certifi

import syncplay
from syncplay.private_build import BUILD
from syncplay import constants

HASH_CHUNK_SIZE = 65536


class OpenSubtitlesError(Exception):
    """Raised for API/network problems; the message is safe to show to the user."""


class LoginRejected(OpenSubtitlesError):
    """OpenSubtitles refused the saved username/password."""


_REJECTED_LOGINS = set()  # Pairs refused this session: never retried, since repeated bad logins lock the account for a day


class SubtitleResult(object):
    def __init__(self, fileId, fileName, title, release, language, downloads, hashMatch, hearingImpaired, url=None):
        self.url = url  # Direct download link, for providers that don't need a separate download call
        self.fileId = fileId
        self.fileName = fileName
        self.title = title
        self.release = release
        self.language = language
        self.downloads = downloads
        self.hashMatch = hashMatch
        self.hearingImpaired = hearingImpaired

    def describe(self):
        tags = []
        if self.hashMatch:
            tags.append("exact match")
        if self.hearingImpaired:
            tags.append("HI")
        downloads = "{} downloads".format(self.downloads) if self.downloads else None
        details = ", ".join(filter(None, [self.language, downloads] + tags))
        label = self.release or self.fileName or self.title or str(self.fileId)
        return "{} ({})".format(label, details)


def computeMovieHash(path):
    """OpenSubtitles' hash: file size plus 64-bit little-endian sums of the first and last 64 KiB."""
    size = os.path.getsize(path)
    if size < HASH_CHUNK_SIZE * 2:
        return None, size
    value = size
    with open(path, "rb") as f:
        for offset in (0, size - HASH_CHUNK_SIZE):
            f.seek(offset)
            chunk = f.read(HASH_CHUNK_SIZE)
            for (word,) in struct.iter_unpack("<Q", chunk):
                value = (value + word) & 0xFFFFFFFFFFFFFFFF
    return "{:016x}".format(value), size


def parseSearchResults(payload, limit=constants.OPENSUBTITLES_MAX_RESULTS):
    results = []
    for item in payload.get("data", []) if isinstance(payload, dict) else []:
        attributes = item.get("attributes") or {}
        files = attributes.get("files") or []
        if not files or not files[0].get("file_id"):
            continue
        feature = attributes.get("feature_details") or {}
        results.append(SubtitleResult(
            fileId=files[0]["file_id"],
            fileName=files[0].get("file_name"),
            title=feature.get("title") or feature.get("movie_name"),
            release=attributes.get("release"),
            language=attributes.get("language"),
            downloads=int(attributes.get("download_count") or 0),
            hashMatch=bool(attributes.get("moviehash_match")),
            hearingImpaired=bool(attributes.get("hearing_impaired")),
        ))
    results.sort(key=lambda r: (not r.hashMatch, -r.downloads))
    return results[:limit]


class OpenSubtitlesClient(object):
    """Blocking client for the OpenSubtitles.com REST API - call from a thread, not the reactor."""

    def __init__(self, apiKey, username=None, password=None, baseUrl=constants.OPENSUBTITLES_API_URL, urlopen=None):
        if not apiKey:
            raise OpenSubtitlesError("No OpenSubtitles API key configured")
        self._apiKey = apiKey
        self._username = username
        self._password = password
        self._baseUrl = baseUrl
        self._token = None
        self._urlopen = urlopen or self._defaultUrlopen

    @staticmethod
    def _defaultUrlopen(request, timeout=constants.OPENSUBTITLES_TIMEOUT):
        context = ssl.create_default_context(cafile=certifi.where())
        return urllib.request.urlopen(request, timeout=timeout, context=context)

    def _headers(self, authorized=False):
        headers = {
            "Api-Key": self._apiKey,
            "User-Agent": "Syncplay-Marquee v{}".format(BUILD),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if authorized and self._token:
            headers["Authorization"] = "Bearer {}".format(self._token)
        return headers

    def _request(self, method, url, body=None, authorized=False, decodeJson=True):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(url, data=data, headers=self._headers(authorized), method=method)
        try:
            with self._urlopen(request) as response:
                raw = response.read(constants.MAX_SHARED_SUBTITLE_BYTES * 4)
        except urllib.error.HTTPError as e:
            raise OpenSubtitlesError(self._errorMessage(e))
        except (urllib.error.URLError, OSError) as e:
            raise OpenSubtitlesError("Could not reach OpenSubtitles: {}".format(getattr(e, "reason", e)))
        if not decodeJson:
            return raw
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise OpenSubtitlesError("OpenSubtitles returned an unreadable response")

    @staticmethod
    def _errorMessage(error):
        try:
            message = json.loads(error.read().decode("utf-8")).get("message")
        except (ValueError, AttributeError, OSError):
            message = None
        return "OpenSubtitles error {}{}".format(error.code, ": {}".format(message) if message else "")

    def login(self):
        if self._token or not (self._username and self._password):
            return
        if (self._username, self._password) in _REJECTED_LOGINS:
            raise LoginRejected("OpenSubtitles refused the saved username or password")
        try:
            payload = self._request("POST", self._baseUrl + "/login",
                                    {"username": self._username, "password": self._password})
        except OpenSubtitlesError as e:
            if "error 401" in str(e) or "error 403" in str(e):
                _REJECTED_LOGINS.add((self._username, self._password))
                raise LoginRejected(str(e))
            raise
        self._token = payload.get("token")
        host = payload.get("base_url")
        if host and "/" not in host:  # Logged-in accounts may be served from a different host
            self._baseUrl = "https://{}/api/v1".format(host)

    def search(self, query=None, movieHash=None, byteSize=None, languages="en"):
        params = {"languages": languages, "order_by": "download_count", "order_direction": "desc"}
        if movieHash:
            params["moviehash"] = movieHash
        if byteSize:
            params["moviebytesize"] = byteSize
        if query:
            params["query"] = query
        if not (movieHash or query):
            raise OpenSubtitlesError("Nothing to search for")
        url = "{}/subtitles?{}".format(self._baseUrl, urllib.parse.urlencode(sorted(params.items())))
        return parseSearchResults(self._request("GET", url))

    def download(self, result):
        """Return (file name, raw bytes) for a search result (or a bare file id)."""
        fileId = getattr(result, "fileId", result)
        try:
            self.login()
        except LoginRejected:
            self._username = self._password = None  # A wrong saved password must not block downloads: use the key alone
            self.loginRejected = True
        info = self._request("POST", self._baseUrl + "/download", {"file_id": fileId, "sub_format": "srt"},
                             authorized=True)
        link = info.get("link")
        if not link or not link.startswith("https://"):
            raise OpenSubtitlesError(info.get("message") or "OpenSubtitles did not provide a download link")
        raw = self._request("GET", link, decodeJson=False)
        return info.get("file_name") or "subtitle.srt", raw


# --- Keyless provider ---------------------------------------------------------------------------------------------
# Uses the public, keyless OpenSubtitles catalogue that Stremio exposes (plus Stremio's public Cinemeta title search
# to turn a file name into an IMDb id). It is an unofficial endpoint, so it is only the fallback for users who haven't
# configured their own OpenSubtitles.com API key.

LANGUAGE_CODES = {  # ISO 639-1 -> the ISO 639-2 codes the public catalogue uses
    "ar": "ara", "bg": "bul", "bn": "ben", "ca": "cat", "cs": "cze", "da": "dan", "de": "ger", "el": "ell", "en": "eng",
    "es": "spa", "et": "est", "fa": "per", "fi": "fin", "fr": "fre", "he": "heb", "hi": "hin", "hr": "hrv", "hu": "hun",
    "id": "ind", "is": "ice", "it": "ita", "ja": "jpn", "ko": "kor", "lt": "lit", "lv": "lav", "nl": "dut", "no": "nor",
    "pl": "pol", "pt": "por", "pt-br": "pob", "ro": "rum", "ru": "rus", "sk": "slo", "sl": "slv", "sr": "scc", "sv": "swe",
    "th": "tha", "tr": "tur", "uk": "ukr", "vi": "vie", "zh": "chi", "zh-cn": "chi", "zh-tw": "zht",
}
_CODE_TO_SHORT = {}
for _short, _long in LANGUAGE_CODES.items():
    _CODE_TO_SHORT.setdefault(_long, _short)

_EPISODE_RE = re.compile(r"[\s._-]s(\d{1,2})[\s._-]?e(\d{1,3})|[\s._-](\d{1,2})x(\d{2,3})(?=[\s._-]|$)", re.I)
_YEAR_RE = re.compile(r"[\s._(\[-]((?:19|20)\d\d)(?=[\s._)\]-]|$)")
_JUNK_RE = re.compile(r"[\s._-](?:480p|576p|720p|1080p|2160p|4k|web[-.]?dl|webrip|bluray|brrip|bdrip|hdtv|dvdrip|remux|x26[45]|h[.]?26[45]|hevc|xvid|aac|ddp?\d|dts|hdr)\b.*$", re.I)


def parseFileName(fileName):
    """Guess {title, year, season, episode} from a media file name (season/episode are None for movies)."""
    stem = os.path.splitext(os.path.basename(fileName or ""))[0]
    hadGroupTag = bool(re.match(r"\s*\[[^\]]*\]", stem))
    stem = re.sub(r"\[[^\]]*\]|\((?:480|576|720|1080|2160)p[^)]*\)", " ", stem)  # [Group] tags, "(1080p)"
    season = episode = year = None
    match = _EPISODE_RE.search(stem)
    if not match and hadGroupTag:  # Fansub style "Title - 12": absolute episode number, treated as season 1
        match = re.search(r"\s-\s(\d{1,3})(?:v\d)?\s*$", stem)
        if match:
            stem = stem[:match.start()] + " S01E{:02d}".format(int(match.group(1)))
            match = _EPISODE_RE.search(stem)
    if match:
        season = int(match.group(1) or match.group(3))
        episode = int(match.group(2) or match.group(4))
        title = stem[:match.start()]
        yearMatch = _YEAR_RE.search(" " + title)
    else:
        yearMatch = _YEAR_RE.search(stem)
        title = stem[:yearMatch.start()] if yearMatch else _JUNK_RE.sub("", stem)
    if yearMatch:
        year = int(yearMatch.group(1))
        title = title[:max(title.find(yearMatch.group(1)) - 1, 0)] if title.find(yearMatch.group(1)) > 0 else title
    title = re.sub(r"[._]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" -")
    return {"title": title, "year": year, "season": season, "episode": episode}


class PublicSubtitleClient(object):
    """Blocking, keyless subtitle search - call from a thread, not the reactor."""

    CINEMETA_URL = "https://v3-cinemeta.strem.io"
    SUBTITLES_URL = "https://opensubtitles-v3.strem.io/subtitles"

    def __init__(self, urlopen=None):
        self._urlopen = urlopen or OpenSubtitlesClient._defaultUrlopen

    def _get(self, url, decodeJson=True):
        request = urllib.request.Request(url, headers={"User-Agent": "Syncplay-Marquee v{}".format(BUILD),
                                                       "Accept": "application/json"})
        try:
            with self._urlopen(request) as response:
                raw = response.read(constants.MAX_SHARED_SUBTITLE_BYTES * 4)
        except urllib.error.HTTPError as e:
            raise OpenSubtitlesError("Subtitle service error {}".format(e.code))
        except (urllib.error.URLError, OSError) as e:
            raise OpenSubtitlesError("Could not reach the subtitle service: {}".format(getattr(e, "reason", e)))
        if not decodeJson:
            return raw
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise OpenSubtitlesError("The subtitle service returned an unreadable response")

    def _findImdbId(self, info):
        kind = "series" if info["season"] is not None else "movie"
        url = "{}/catalog/{}/top/search={}.json".format(self.CINEMETA_URL, kind, urllib.parse.quote(info["title"]))
        metas = [m for m in self._get(url).get("metas", []) if str(m.get("imdb_id", "")).startswith("tt")]
        if info["year"]:
            metas.sort(key=lambda m: not str(m.get("releaseInfo") or "").startswith(str(info["year"])))
        if not metas:
            raise OpenSubtitlesError("Couldn't work out which title '{}' is".format(info["title"]))
        return kind, metas[0]["imdb_id"]

    def search(self, fileName, movieHash=None, byteSize=None, languages="en"):
        info = parseFileName(fileName)
        if not info["title"]:
            raise OpenSubtitlesError("Couldn't read a title from the file name")
        kind, imdbId = self._findImdbId(info)
        if kind == "series":
            imdbId = "{}:{}:{}".format(imdbId, info["season"], info["episode"])
        extras = {"filename": os.path.basename(fileName)}
        if movieHash and byteSize:
            extras.update({"videoHash": movieHash, "videoSize": byteSize})
        extra = "&".join("{}={}".format(k, urllib.parse.quote(str(v), safe="")) for k, v in extras.items())
        payload = self._get("{}/{}/{}/{}.json".format(self.SUBTITLES_URL, kind, urllib.parse.quote(imdbId, safe=":"), extra))
        wanted = {LANGUAGE_CODES.get(code.strip().lower(), code.strip().lower()) for code in languages.split(",") if code.strip()}
        results = []
        for item in payload.get("subtitles", []) if isinstance(payload, dict) else []:
            url = item.get("url") or ""
            if not url.startswith("https://") or (wanted and item.get("lang") not in wanted):
                continue
            results.append(SubtitleResult(
                fileId=item.get("id"), fileName=item.get("subtitleFileName"), title=item.get("movieReleaseName"),
                release=item.get("subtitleFileName") and os.path.splitext(item["subtitleFileName"])[0],
                language=_CODE_TO_SHORT.get(item.get("lang"), item.get("lang")), downloads=0, hashMatch=False,
                hearingImpaired=bool(re.search(r"(?:^|[.\s_-])(?:hi|sdh)(?:[.\s_-]|$)", item.get("subtitleFileName") or "", re.I)),
                url=url))
        return results[:constants.OPENSUBTITLES_MAX_RESULTS]

    def download(self, result):
        if not getattr(result, "url", None):
            raise OpenSubtitlesError("No download link for this subtitle")
        return result.fileName or "subtitle.srt", self._get(result.url, decodeJson=False)


# --- Subtitle references sent over chat --------------------------------------------------------------------------
# Stock Syncplay servers only relay chat, so a picked subtitle is announced as a short chat line naming where to
# fetch it. Receivers rebuild the download link themselves from a strict template - a chat message can never make a
# client fetch an arbitrary URL.

PUBLIC_DOWNLOAD_URL = "https://subs5.strem.io/en/download/subencoding-stremio-utf8/src-api/file/{}"
_PUBLIC_URL_RE = re.compile(r"^https://subs\d*\.strem\.io/[a-z]{2}/download/subencoding-stremio-utf8/src-api/file/(\d+)$")
_REFERENCE_RE = re.compile(r"^Subtitle picked: (?P<name>.{1,200}?) \(Syncplay sub: (?P<source>st|os):(?P<id>\d{1,12})\)$")


def referenceFor(result):
    """('st'|'os', numeric id) that lets another client fetch this result, or None."""
    if result.url:
        match = _PUBLIC_URL_RE.match(result.url)
        return ("st", match.group(1)) if match else None
    return ("os", str(result.fileId)) if str(result.fileId).isdigit() else None


def buildChatReference(result, maxLength):
    """The chat line announcing a pick, with the name trimmed so the whole line fits maxLength (or None)."""
    reference = referenceFor(result)
    if reference is None:
        return None
    suffix = " (Syncplay sub: {}:{})".format(*reference)
    prefix = "Subtitle picked: "
    room = maxLength - len(prefix) - len(suffix)
    if room < 8:
        return None
    name = (result.fileName or result.release or "subtitle.srt").replace("\n", " ").strip()
    if len(name) > room:
        name = name[:room - 1] + "\u2026"
    return prefix + name + suffix


def parseChatReference(message):
    """(name, source, id) if the chat line is a subtitle announcement, else None."""
    match = _REFERENCE_RE.match(message or "")
    return (match.group("name"), match.group("source"), match.group("id")) if match else None


def resultFromReference(name, source, refId):
    """Rebuild a downloadable SubtitleResult from a chat reference."""
    if source == "st":
        return SubtitleResult(refId, name, None, name, None, 0, False, False, url=PUBLIC_DOWNLOAD_URL.format(refId))
    return SubtitleResult(int(refId), name, None, name, None, 0, False, False)
