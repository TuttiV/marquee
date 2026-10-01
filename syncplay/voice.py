"""Voice calls without any server of ours: a random, unguessable room on the public Jitsi Meet service (no account needed)."""
import re
import secrets as _secrets

_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_URL = re.compile(r"https://meet\.jit\.si/SyncplayMarquee-[A-Za-z0-9]{10,24}(?![A-Za-z0-9])")


def newUrl(length=14):
    return "https://meet.jit.si/SyncplayMarquee-" + "".join(_secrets.choice(_ALPHABET) for _ in range(length))


def find(text):
    """The voice-call link in a chat line, or None. Only links of exactly our own form are recognised."""
    match = _URL.search(text or "")
    return match.group(0) if match else None
