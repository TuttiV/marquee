"""Help > Copy diagnostics: one block of plain text with the facts needed to find a problem, safe to paste into a chat.

It never contains passwords, API keys, the room name or user names: secrets are removed from the log lines, and only the
server's address and counts are included."""
import os
import platform
import re
import sys

LOG_LINES = 60
_SECRET_WORDS = re.compile(r"(?i)\b(password|passwd|api[-_ ]?key|apikey|token|secret|authorization)\b(\s*[:=]\s*|\s+)(\S+)")
_LONG_TOKEN = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")


def redact(text, secrets=()):
    """Remove known secret values and anything that looks like a key/password assignment or a long token."""
    for secret in secrets:
        if secret and len(str(secret)) >= 4:
            text = text.replace(str(secret), "<hidden>")
    text = _SECRET_WORDS.sub(lambda m: "{}{}<hidden>".format(m.group(1), m.group(2)), text)
    return _LONG_TOKEN.sub("<hidden>", text)


def logCandidates(appDir):
    return [os.path.join(appDir, name) for name in ("syncplay.log", "marquee.log")] + \
           [os.path.join(os.path.dirname(appDir), name) for name in ("syncplay.log", "marquee.log")] + \
           [os.path.join(appDir, "program", "syncplay.log")]


def tailOfLog(appDir, lines=LOG_LINES):
    for path in logCandidates(appDir):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return [line.rstrip("\n") for line in f.readlines()[-lines:]]
        except OSError:
            continue
    return []


def report(facts, logLines=(), secrets=()):
    """facts: ordered (label, value) pairs; returns the finished text."""
    out = ["Marquee diagnostics"]
    for label, value in facts:
        out.append("{}: {}".format(label, value))
    if logLines:
        out.append("")
        out.append("Recent log ({} lines):".format(len(logLines)))
        out.extend(logLines)
    return redact("\n".join(out), secrets)


def _packaged():
    try:
        from syncplay import install
        return install.isPackaged()
    except Exception:
        return False


def systemFacts():
    try:
        from syncplay.vendor.Qt import __binding__, __binding_version__
        qt = "{} {}".format(__binding__, __binding_version__)
    except Exception:
        qt = "unknown"
    return [("Python", platform.python_version()), ("Qt", qt), ("System", "{} {}".format(platform.system(), platform.release())),
            ("Packaged", "yes" if _packaged() else "no")]
