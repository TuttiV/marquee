"""A shared subtitle delay, sent as one short chat line so it works on any server.

Anyone nudges the delay ("[subdelay] +0.4") and every copy of Marquee in the room applies it to its own player and hides the
line. People on other clients see the line as ordinary chat. The delay belongs to the video: a new video starts at zero."""
import re

STEP = 0.1
LIMIT = 10.0
_LINE = re.compile(r"^\[subdelay\] (?P<value>[+-]?\d{1,2}(?:\.\d{1,2})?)$")


def clamp(seconds):
    return max(-LIMIT, min(LIMIT, round(float(seconds), 2)))


def line(seconds):
    return "[subdelay] {:+.1f}".format(clamp(seconds))


def parse(text):
    """The delay in a "[subdelay] ..." line (seconds), or False if the text isn't one."""
    match = _LINE.match(text or "")
    if not match:
        return False
    try:
        return clamp(float(match.group("value")))
    except ValueError:
        return False


def describe(seconds):
    seconds = clamp(seconds)
    return "0 s" if seconds == 0 else "{:+.1f} s".format(seconds)
