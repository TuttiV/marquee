"""The on-demand "who's behind?" check, done entirely with chat lines so it works on any Syncplay server.

The requester posts one line; every Syncplay Marquee in the room answers with its own position a moment later; the requester
then shows one summary line. Copies of Marquee hide these control lines (people on stock Syncplay simply see a few short
lines). Nothing is sent unless somebody asks."""
import random
import re
import string
import time

from syncplay.utils import formatTime

_REQUEST = re.compile(r"^\[sync check\] .{0,60} #([a-z0-9]{4})$")
_REPLY = re.compile(r"^\[sync\] (?:(?P<pos>\d+:\d\d(?::\d\d)?) \((?:(?P<secs>\d{1,5}(?:\.\d)?)s (?P<dir>ahead|behind)|in sync)\)|no video) #(?P<id>[a-z0-9]{4})$")
IN_SYNC_SECONDS = 0.5      # Closer than this counts as in sync
REPLY_WINDOW = 3.5         # Seconds the requester waits for answers
MIN_REQUEST_GAP = 8.0      # A copy answers a given person at most this often (keeps the room from being flooded)


def newId():
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))


def requestText(checkId):
    return "[sync check] where is everyone? #{}".format(checkId)


def parseRequest(text):
    match = _REQUEST.match(text or "")
    return match.group(1) if match else None


def replyText(checkId, position=None, offset=None):
    """position/offset in seconds; offset > 0 means ahead of the room. No position means no video is open."""
    if position is None:
        return "[sync] no video #{}".format(checkId)
    if offset is None or abs(offset) < IN_SYNC_SECONDS:
        state = "in sync"
    else:
        state = "{:.1f}s {}".format(abs(offset), "ahead" if offset > 0 else "behind")
    return "[sync] {} ({}) #{}".format(formatTime(position), state, checkId)


def parseReply(text):
    """(checkId, offsetSeconds or None, hasVideo) for a reply line, else None. Offset is 0.0 when in sync."""
    match = _REPLY.match(text or "")
    if not match:
        return None
    if match.group("pos") is None:
        return match.group("id"), None, False
    seconds = float(match.group("secs")) if match.group("secs") else 0.0
    return match.group("id"), (seconds if match.group("dir") == "ahead" else -seconds), True


def describe(offset):
    if offset is None:
        return "no video open"
    if abs(offset) < IN_SYNC_SECONDS:
        return "in sync"
    return "{:.1f} s {}".format(abs(offset), "ahead" if offset > 0 else "behind")


class SyncCheck(object):
    """Keeps track of one check at a time. The client supplies the pieces that touch the network and the player."""

    def __init__(self, me, sendChat, myState, roomUsers, say, later, clock=time.time):
        self._me, self._send, self._myState, self._roomUsers = me, sendChat, myState, roomUsers
        self._say, self._later, self._clock = say, later, clock
        self._pending = {}       # id -> {username: offset or None}
        self._lastRequestFrom = {}
        self._answered = set()

    def start(self):
        """Ask the room. Returns the id."""
        checkId = newId()
        self._pending[checkId] = {}
        self._send(requestText(checkId))
        self._later(REPLY_WINDOW, self._finish, checkId)
        return checkId

    def handle(self, username, text):
        """True if the chat line was part of a check (so it shouldn't be shown as ordinary chat)."""
        checkId = parseRequest(text)
        if checkId:
            self._handleRequest(username, checkId)
            return True
        reply = parseReply(text)
        if reply:
            replyId, offset, hasVideo = reply
            if replyId in self._pending:
                self._pending[replyId][username] = offset
            return True
        return False

    def _handleRequest(self, username, checkId):
        if username == self._me or checkId in self._answered:
            return
        now = self._clock()
        if now - self._lastRequestFrom.get(username, -1e9) < MIN_REQUEST_GAP:
            return
        self._lastRequestFrom[username] = now
        self._answered.add(checkId)
        if len(self._answered) > 50:
            self._answered.clear()
        position, offset = self._myState()
        self._later(random.uniform(0.0, 0.6), self._send, replyText(checkId, position, offset))  # Staggered so replies don't collide

    def _finish(self, checkId):
        replies = self._pending.pop(checkId, {})
        position, offset = self._myState()
        parts = ["You: " + describe(offset if position is not None else None)]
        for name in sorted(replies):
            parts.append("{}: {}".format(name, describe(replies[name])))
        silent = sorted(u for u in self._roomUsers() if u != self._me and u not in replies)
        text = "Sync check: " + "; ".join(parts) + "."
        if silent:
            text += " No answer from {} (probably not using Syncplay Marquee).".format(", ".join(silent))
        self._say(text)
