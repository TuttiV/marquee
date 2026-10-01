import base64
import binascii
import os
import re
import shutil
import tempfile

from syncplay import constants


class SubtitleShareError(Exception):
    """Raised when a subtitle can't be shared or received; messageKey is a messages_*.py key."""

    def __init__(self, messageKey):
        super().__init__(messageKey)
        self.messageKey = messageKey


def sanitizeSubtitleName(name):
    """Return a bare, safe file name with an allowed subtitle extension, or None."""
    if not isinstance(name, str):
        return None
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", name).strip(" .")
    if not name or len(name) > constants.MAX_FILENAME_LENGTH:
        return None
    if os.path.splitext(name)[1].lower() not in constants.SHARED_SUBTITLE_EXTENSIONS:
        return None
    return name


def maxEncodedLength(maxBytes):
    return 4 * ((maxBytes + 2) // 3)


def decodeSubtitlePayload(name, data, maxBytes=None):
    """Validate an untrusted (name, base64 data) pair and return (safeName, rawBytes)."""
    maxBytes = maxBytes or constants.MAX_SHARED_SUBTITLE_BYTES
    safeName = sanitizeSubtitleName(name)
    if safeName is None:
        raise SubtitleShareError("subtitle-invalid-name-error")
    if not isinstance(data, str) or len(data) > maxEncodedLength(maxBytes):
        raise SubtitleShareError("subtitle-too-large-error")
    try:
        raw = base64.b64decode(data.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError):
        raise SubtitleShareError("subtitle-invalid-data-error")
    if not raw or len(raw) > maxBytes:
        raise SubtitleShareError("subtitle-too-large-error")
    if b"\x00" in raw:  # Subtitle formats we share are text-only
        raise SubtitleShareError("subtitle-invalid-data-error")
    return safeName, raw


def readSubtitleFile(path, maxBytes=None):
    """Read a local subtitle file and return (safeName, base64String) ready to send."""
    maxBytes = maxBytes or constants.MAX_SHARED_SUBTITLE_BYTES
    safeName = sanitizeSubtitleName(os.path.basename(path))
    if safeName is None:
        raise SubtitleShareError("subtitle-invalid-name-error")
    try:
        if os.path.getsize(path) > maxBytes:
            raise SubtitleShareError("subtitle-too-large-error")
        with open(path, "rb") as f:
            raw = f.read(maxBytes + 1)
    except OSError:
        raise SubtitleShareError("subtitle-file-not-found-error")
    encoded = base64.b64encode(raw).decode("ascii")
    decodeSubtitlePayload(safeName, encoded, maxBytes)  # Same checks the server and receivers will apply
    return safeName, encoded


def findSidecarSubtitle(mediaPath):
    """Find a subtitle next to a media file, e.g. Show.mkv -> Show.srt / Show.en.srt."""
    if not mediaPath or not os.path.isfile(mediaPath):
        return None
    directory, mediaName = os.path.split(mediaPath)
    stem = os.path.splitext(mediaName)[0].lower()
    candidates = []
    try:
        for entry in os.listdir(directory or "."):
            entryStem, extension = os.path.splitext(entry)
            if extension.lower() in constants.SHARED_SUBTITLE_EXTENSIONS and entryStem.lower().startswith(stem):
                candidates.append(entry)
    except OSError:
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda entry: (len(entry), entry.lower()))
    return os.path.join(directory, candidates[0])


class SharedSubtitleStore(object):
    """Keeps received subtitles in a private temp directory that is removed on shutdown."""

    def __init__(self):
        self._directory = None
        self._counter = 0

    def save(self, username, safeName, raw):
        if self._directory is None:
            self._directory = tempfile.mkdtemp(prefix="syncplay-subtitles-")
        self._counter += 1
        path = os.path.join(self._directory, "{}-{}".format(self._counter, safeName))
        with open(path, "wb") as f:
            f.write(raw)
        return path

    def cleanup(self):
        if self._directory is not None:
            shutil.rmtree(self._directory, ignore_errors=True)
            self._directory = None
