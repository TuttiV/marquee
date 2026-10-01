"""The release notes shown in Help > Update log: syncplay/CHANGELOG.md, one "## Build N - title" section per build."""
import html
import os
import re
import time

from syncplay.ui import theme

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CHANGELOG.md")
_HEADING = re.compile(r"^##\s*Build\s+(\d+)\s*(?:[-–—:]\s*(.*))?$", re.I)


def parse(text):
    """[(build, title, [bullet, ...])] in file order; anything that isn't a build section is ignored."""
    entries, current = [], None
    for line in (text or "").splitlines():
        line = line.strip()
        match = _HEADING.match(line)
        if match:
            current = (int(match.group(1)), (match.group(2) or "").strip(), [])
            entries.append(current)
        elif line.startswith("#"):
            current = None  # Some other heading: its bullets don't belong to the build above it
        elif current is not None and line[:1] in ("-", "*") and line[1:2] == " ":
            current[2].append(line[2:].strip())
    return entries


def load(path=PATH):
    try:
        with open(path, encoding="utf-8") as f:
            return parse(f.read())
    except OSError:
        return []


def _when(stamp):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(stamp)))
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _activity(entry):
    if entry.get("event") == "updated":
        text = "Updated to build {}".format(entry.get("to") or "?")
    elif entry.get("event") == "rolled-back":
        text = "Build {} didn't start properly, so the app went back to build {}".format(entry.get("to") or "?", entry.get("from") or "?")
    else:
        return None
    return "{} &middot; {}".format(html.escape(text), html.escape(_when(entry.get("time"))))


def render(entries, installedBuild, activity=(), newerThan=None, dark=False):
    """HTML for the update log window. Builds newer than `newerThan` (the build before the last update) get a NEW tag."""
    t = theme.tokens(dark)
    parts = ['<h2 style="margin:0 0 2px 0">Update log</h2>',
             '<p style="color:{};margin:0 0 10px 0">You\'re on build {}.</p>'.format(t["muted"], installedBuild)]
    lines = [line for line in (_activity(e) for e in reversed(list(activity)[-6:])) if line]
    if lines:
        parts.append('<p style="color:{};margin:0 0 4px 0"><b>RECENT ACTIVITY</b></p>'.format(t["muted"]))
        parts.append('<ul style="margin:0 0 12px -18px">{}</ul>'.format("".join("<li>{}</li>".format(l) for l in lines)))
    for build, title, bullets in sorted(entries, key=lambda e: -e[0]):
        tag = ""
        if newerThan is not None and newerThan < build <= installedBuild:
            tag = ' <span style="color:{}"><b>NEW</b></span>'.format(t["ready"])
        elif build > installedBuild:
            tag = ' <span style="color:{}">(not installed)</span>'.format(t["muted"])
        heading = "Build {}{}".format(build, " &middot; " + html.escape(title) if title else "")
        parts.append('<h3 style="margin:14px 0 4px 0">{}{}</h3>'.format(heading, tag))
        parts.append('<ul style="margin:0 0 0 -18px">{}</ul>'.format("".join("<li>{}</li>".format(html.escape(b)) for b in bullets)))
    if not entries:
        parts.append('<p style="color:{}">No release notes are available for this build.</p>'.format(t["muted"]))
    return "".join(parts)
