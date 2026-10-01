"""Who has which subtitle on, shared through one short chat line so it works on any Syncplay server.

A copy of Marquee says "[subs] <name>" when it puts a subtitle on (and "[subs] -" when that stops applying); other copies
keep the latest line per person for the people table and hide the line from the chat."""
import re

_LINE = re.compile(r"^\[subs\] (?P<name>[^\x00-\x1f]{1,60})$")
NONE = "-"
MAX_LENGTH = 60


def clean(name):
    """A short, single-line label (control characters dropped, long names cut in the middle)."""
    text = "".join(ch for ch in (name or "") if ch >= " " and ch != "\x7f").strip()
    if len(text) > MAX_LENGTH:
        text = text[:MAX_LENGTH // 2 - 1] + "…" + text[-(MAX_LENGTH // 2 - 1):]
    return text


def line(name):
    text = clean(name)
    return "[subs] {}".format(text) if text else "[subs] {}".format(NONE)


def parse(text):
    """The label in a subtitle line: a string, None for "no subtitle", or False if this isn't a subtitle line."""
    match = _LINE.match(text or "")
    if not match:
        return False
    name = match.group("name").strip()
    return None if name == NONE else name
