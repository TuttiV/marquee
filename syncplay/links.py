"""Turns web addresses in chat into clickable links. Works on text that has ALREADY been HTML-escaped."""
import re

_URL = re.compile(r"(https?://[^\s<>\"']+)")
_TRAILING = ".,;:!?)]}"


def linkify(escapedHtml):
    def replace(match):
        url = match.group(1)
        tail = ""
        while url and url[-1] in _TRAILING:
            tail = url[-1] + tail
            url = url[:-1]
        if not re.match(r"https?://[^\s/]+", url):
            return match.group(0)
        return '<a href="{0}">{0}</a>{1}'.format(url, tail)
    return _URL.sub(replace, escapedHtml)
