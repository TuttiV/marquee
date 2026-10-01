"""Finding out whether another copy of the app is already running, and handing it an invite link to open.

A running copy touches instance.json every couple of seconds. When an invite link starts a second copy, that copy drops the
link into invite-inbox.txt and exits instead; the running copy picks it up within a moment and joins the room."""
import json
import os
import time

HEARTBEAT_SECONDS = 2
STALE_SECONDS = 8


def _lock(configDir):
    return os.path.join(configDir, "instance.json")


def _inbox(configDir):
    return os.path.join(configDir, "invite-inbox.txt")


def beat(configDir, now=None):
    """I'm running (call every HEARTBEAT_SECONDS)."""
    temporary = _lock(configDir) + ".tmp"
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "time": time.time() if now is None else now}, f)
    os.replace(temporary, _lock(configDir))


def primaryRunning(configDir, now=None):
    """Is a different copy alive right now (its heartbeat is recent)?"""
    try:
        with open(_lock(configDir), encoding="utf-8") as f:
            data = json.load(f)
        age = (time.time() if now is None else now) - float(data["time"])
        return int(data["pid"]) != os.getpid() and -STALE_SECONDS < age < STALE_SECONDS
    except (OSError, ValueError, KeyError, TypeError):
        return False


def release(configDir):
    try:
        with open(_lock(configDir), encoding="utf-8") as f:
            if int(json.load(f).get("pid")) != os.getpid():
                return
        os.remove(_lock(configDir))
    except (OSError, ValueError, TypeError, AttributeError):
        pass


def handOff(configDir, link):
    with open(_inbox(configDir), "a", encoding="utf-8") as f:
        f.write(link.strip().replace("\n", " ") + "\n")


def takeInbox(configDir):
    """Links waiting for this copy (each is returned once)."""
    inbox = _inbox(configDir)
    if not os.path.exists(inbox):
        return []
    taking = "{}.{}.taking".format(inbox, os.getpid())
    try:
        os.replace(inbox, taking)
        with open(taking, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()][:5]
    except OSError:
        return []
    finally:
        try:
            os.remove(taking)
        except OSError:
            pass
