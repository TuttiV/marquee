"""Invite links (syncplay-marquee://host:port/room), random private room names, and the Windows link registration."""
import os
import re
import secrets
import sys
import urllib.parse
from collections import namedtuple

from syncplay import constants

SCHEME = "syncplay-marquee"
SETTING = "inviteLinks"  # Saved as "off" when the user turns link handling off
Invite = namedtuple("Invite", "host port room")

_HOST = re.compile(r"^(?:[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?|\[[0-9A-Fa-f:.]{2,45}\])$")
_ROOM_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # No look-alikes (0/o, 1/l/i)


def randomRoomName(length=10):
    """An unguessable room name (about 50 bits): on a public server, the name is the only thing keeping strangers out."""
    return "room-" + "".join(secrets.choice(_ROOM_ALPHABET) for _ in range(length))


def make(host, port, room):
    host = str(host or "").strip()
    if ":" in host and not host.startswith("["):
        host = "[{}]".format(host)  # IPv6
    return "{}://{}:{}/{}".format(SCHEME, host, int(port), urllib.parse.quote(room, safe=""))


def parse(text):
    """Invite(host, port, room) for a well-formed invite link, else None. Nothing else in the text is trusted."""
    text = (text or "").strip()
    if not text.lower().startswith(SCHEME + "://") or len(text) > 400 or any(ord(c) < 32 or ord(c) == 127 for c in text):
        return None
    try:
        parts = urllib.parse.urlsplit(text)
        host, port = parts.hostname, parts.port
    except ValueError:
        return None
    if not host or not _HOST.match("[{}]".format(host) if ":" in host else host):
        return None
    room = urllib.parse.unquote(parts.path[1:]).strip()
    if not room or len(room) > constants.MAX_ROOM_NAME_LENGTH or any(ord(c) < 32 or ord(c) == 127 for c in room):
        return None
    return Invite(host, port or constants.DEFAULT_PORT, room)


def hostArgument(invite):
    """host:port as the -a/--host argument expects it."""
    return "{}:{}".format("[{}]".format(invite.host) if ":" in invite.host else invite.host, invite.port)


def sameServer(invite, host, port):
    try:
        return bool(host) and invite.host.lower() == str(host).strip().lower() and int(invite.port) == int(port)
    except (TypeError, ValueError):
        return False


def fitsSavedSetup(invite, savedName, savedHost, savedPort):
    """Can the app go straight into the invite's room? Only with a user name already set and the same server as last time;
    otherwise the start dialog opens pre-filled so the person can check the details first."""
    return bool(savedName) and sameServer(invite, savedHost, savedPort)


# --- Windows: make syncplay-marquee:// links open this app -----------------------------------------------------------

_KEY = r"Software\Classes\{}".format(SCHEME)


def _appFolder():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def handlerCommand(python=None, launcher=None):
    """The command Windows runs for a link: the app's own Python and launcher, so it keeps working if the .exe is moved."""
    python = python or sys.executable
    launcher = launcher or os.path.join(_appFolder(), "program", "launch-syncplay.pyw")
    return '"{}" "{}" "%1"'.format(python, launcher)


def handlerAvailable(launcher=None, reg=None):
    launcher = launcher or os.path.join(_appFolder(), "program", "launch-syncplay.pyw")
    if reg is None:
        if os.name != "nt":
            return False
        try:
            import winreg as reg  # noqa: F401
        except ImportError:
            return False
    return os.path.isfile(launcher)


def _winreg(reg):
    if reg is not None:
        return reg
    import winreg
    return winreg


def isHandlerRegistered(command, reg=None):
    reg = _winreg(reg)
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, _KEY + r"\shell\open\command") as key:
            return reg.QueryValueEx(key, "")[0] == command
    except OSError:
        return False


def registerHandler(command, iconPath=None, reg=None):
    """Per-user (no admin needed). Raises OSError if the registry can't be written."""
    reg = _winreg(reg)
    entries = [(_KEY, "", "URL:Syncplay Marquee invite"), (_KEY, "URL Protocol", ""), (_KEY + r"\shell\open\command", "", command)]
    if iconPath:
        entries.append((_KEY + r"\DefaultIcon", "", '"{}",0'.format(iconPath)))
    for path, name, value in entries:
        with reg.CreateKeyEx(reg.HKEY_CURRENT_USER, path, 0, reg.KEY_WRITE) as key:
            reg.SetValueEx(key, name, 0, reg.REG_SZ, value)


def unregisterHandler(reg=None):
    reg = _winreg(reg)
    for path in (_KEY + r"\shell\open\command", _KEY + r"\shell\open", _KEY + r"\shell", _KEY + r"\DefaultIcon", _KEY):
        try:
            reg.DeleteKey(reg.HKEY_CURRENT_USER, path)
        except OSError:
            pass
