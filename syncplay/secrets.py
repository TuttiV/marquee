"""Tiny store for API keys, kept in its own file next to the Syncplay config so a problem writing syncplay.ini
can never lose them. Plain JSON in the user's own config folder (owner-only permissions where the OS supports it)."""
import json
import os
import tempfile

FILE_NAME = "syncplay-secrets.json"


def _path(configDir):
    return os.path.join(configDir, FILE_NAME)


def load(name, configDir):
    """The stored value for name, or None (missing/unreadable files are treated as 'nothing saved')."""
    try:
        with open(_path(configDir), "r", encoding="utf-8") as f:
            data = json.load(f)
        value = data.get(name) if isinstance(data, dict) else None
        return value if isinstance(value, str) and value.strip() else None
    except (OSError, ValueError):
        return None


def save(name, value, configDir):
    """Store (or, when value is empty, remove) name. Raises OSError if it can't be written."""
    try:
        with open(_path(configDir), "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    if value and value.strip():
        data[name] = value.strip()
    else:
        data.pop(name, None)
    os.makedirs(configDir, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=configDir, prefix=".secrets-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(data, f)
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        os.replace(temp, _path(configDir))  # Atomic: never leaves a half-written file
    except BaseException:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise


DEFAULTS_FILE_NAME = "syncplay-defaults.json"


def bundledDefault(name, appDir=None):
    """A default shipped with a private build in syncplay-defaults.json next to syncplayClient.py (kept out of the
    source code and patches). None when the file or entry is missing or unreadable."""
    appDir = appDir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(appDir, DEFAULTS_FILE_NAME), "r", encoding="utf-8") as f:
            data = json.load(f)
        value = data.get(name) if isinstance(data, dict) else None
        return value.strip() if isinstance(value, str) and value.strip() else None
    except (OSError, ValueError):
        return None
