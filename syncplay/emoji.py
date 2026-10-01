"""Emoji for the chat: a small picker list, ":shortcodes:" that turn into emoji as you send, and a test for lines that
are only emoji (those are shown larger, like a reaction)."""
import re

PICKER = ("😀", "😂", "🤣", "😍", "🥹", "😭", "😮", "😱", "🤯", "😬", "😴", "🙄", "😏", "🥳", "😎", "🤔",
          "👍", "👎", "👏", "🙌", "🙏", "💪", "👀", "🤝", "❤️", "💔", "🔥", "✨", "💀", "🎉", "🍿", "🎬",
          "😅", "😆", "😉", "😊", "😢", "😡", "🤮", "🤢", "🫡", "🫠", "💯", "✅", "❌", "⏸️", "▶️", "⏪")

SHORTCODES = {
    "smile": "😊", "grin": "😀", "joy": "😂", "lol": "🤣", "love": "😍", "heart": "❤️", "cry": "😭", "sob": "😭", "wow": "😮",
    "scream": "😱", "mindblown": "🤯", "grimace": "😬", "sleep": "😴", "eyeroll": "🙄", "party": "🥳", "cool": "😎", "think": "🤔",
    "thumbsup": "👍", "+1": "👍", "thumbsdown": "👎", "-1": "👎", "clap": "👏", "pray": "🙏", "eyes": "👀", "fire": "🔥",
    "skull": "💀", "tada": "🎉", "popcorn": "🍿", "movie": "🎬", "100": "💯", "check": "✅", "x": "❌", "pause": "⏸️",
    "play": "▶️", "rewind": "⏪", "wink": "😉", "sweat": "😅", "rage": "😡", "salute": "🫡", "sparkles": "✨",
}
_CODE = re.compile(r":([a-z0-9+\-]{1,12}):")
_EMOJI_ONLY = re.compile(r"^[\s\u200d\ufe0f\u20e3\u23e9-\u23ff\u25a0-\u25ff\u2600-\u27bf\u2b00-\u2bff\U0001F000-\U0001FAFF]+$")


def expand(text):
    """Replace known :shortcodes: with emoji; unknown ones are left exactly as typed."""
    return _CODE.sub(lambda m: SHORTCODES.get(m.group(1), m.group(0)), text or "")


def isOnlyEmoji(text):
    text = (text or "").strip()
    return bool(text) and len(text) <= 24 and bool(_EMOJI_ONLY.match(text))
