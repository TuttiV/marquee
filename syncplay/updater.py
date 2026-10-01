"""Self-update from the GitHub releases of the repo named in syncplay-defaults.json ("updateRepo": "owner/repo").

Flow: latestRelease() -> download() (https, GitHub hosts only, size-capped, SHA-256 checked) -> stage() (safe extract of
allowed files into update-staging/) -> applyStaged() on the next start, before Syncplay's modules are loaded, so no file
is ever replaced while in use. The user's key/config/virtualenv are never touched."""
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from syncplay import secrets
from syncplay.private_build import BUILD

STAGING = "update-staging"
READY_MARKER = "READY"
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
ALLOWED_HOSTS = ("github.com", "api.github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
API = "https://api.github.com/repos/{}/releases?per_page=20"

# Only these parts of a release are ever installed. Everything else in the zip is ignored.
ALLOWED_DIRS = ("syncplay", "program", "launcher", "tests")
ALLOWED_FILE_RE = re.compile(r"^[^/\\]+\.(?:py|pyw|bat|sh|txt|md|in|json)$|^LICENSE$|^Makefile$|^GNUmakefile$", re.I)
# ...and these are never overwritten, whatever a release contains: the user's own data, setup and the running launcher.
BACKUP = "update-backup"
PENDING = "update-pending.json"
HISTORY = "update-history.json"
BLOCKED = "update-blocked.json"
PROTECTED = {".venv", "syncplay-defaults.json", "syncplay-secrets.json", "syncplay.log", "marquee.log", STAGING,
             "syncplay.exe", "syncplay marquee.exe", BACKUP, PENDING, HISTORY, BLOCKED, ".marquee-build"}
SETTLE_SECONDS = 60  # A start that has run this long without confirming it works is treated as a failed start


class UpdateError(Exception):
    """Safe to show to the user."""


def validRepo(text):
    """'owner/repo' if text is a valid GitHub repository name (a github.com/owner/repo link is accepted too), else None."""
    text = (text or "").strip()
    text = re.sub(r"^(?:https?://)?(?:www\.)?github\.com/", "", text).rstrip("/")
    text = re.sub(r"\.git$", "", text)
    # GitHub rules: owners are letters/digits/hyphens; repo names may also use _ and . but are never "." or ".."
    return text if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/(?!\.{1,2}$)[A-Za-z0-9_.-]{1,100}", text) else None


def configuredRepo(appDir=None, configDir=None):
    """The repo updates come from: the one the user entered in the app (secrets file) or the build's default."""
    saved = secrets.load("updateRepo", configDir) if configDir else None
    return validRepo(saved) or validRepo(secrets.bundledDefault("updateRepo", appDir))


def parseBuild(tag):
    match = re.search(r"(\d+)\s*$", tag or "")
    return int(match.group(1)) if match else None


class ReleaseInfo(object):
    def __init__(self, tag, build, name, notes, assetUrl, size, sha256):
        self.tag, self.build, self.name, self.notes = tag, build, name, notes
        self.assetUrl, self.size, self.sha256 = assetUrl, size, sha256


def _hostAllowed(url):
    parts = urllib.parse.urlparse(url)
    return parts.scheme == "https" and (parts.hostname or "").lower() in ALLOWED_HOSTS


def _open(url, urlopen=None, accept="application/vnd.github+json"):
    if not _hostAllowed(url):
        raise UpdateError("Refusing to download from an untrusted address.")
    request = urllib.request.Request(url, headers={"User-Agent": "Syncplay-Marquee-updater", "Accept": accept})
    try:
        response = (urlopen or urllib.request.urlopen)(request, timeout=30)
    except urllib.error.HTTPError as e:
        raise UpdateError("GitHub said {}{}".format(e.code, " (no release published yet?)" if e.code == 404 else ""))
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError("Could not reach GitHub: {}".format(getattr(e, "reason", e)))
    final = getattr(response, "geturl", lambda: url)()
    if not _hostAllowed(final):
        raise UpdateError("The download was redirected to an untrusted address.")
    return response


def latestRelease(repo, urlopen=None):
    """The published release of repo with the highest build number, as ReleaseInfo (raises UpdateError).

    GitHub's own "latest" answer is not used: it orders releases by the date of the commit they are tagged on, so a repo
    where every release sits on the same commit can keep answering with an old one. The tag's number decides instead."""
    with _open(API.format(repo), urlopen) as response:
        try:
            listing = json.loads(response.read(4 * 1024 * 1024).decode("utf-8"))
        except ValueError:
            raise UpdateError("GitHub returned an unreadable answer.")
    listing = listing if isinstance(listing, list) else [listing]
    published = [r for r in listing if isinstance(r, dict) and not r.get("draft") and not r.get("prerelease")]
    numbered = [(parseBuild(r.get("tag_name")), r) for r in published]
    numbered = [(build, r) for build, r in numbered if build is not None]
    if not numbered:
        tag = published[0].get("tag_name") if published else ""
        raise UpdateError("The latest release tag ('{}') doesn't end in a number.".format(tag or "none"))
    build, data = max(numbered, key=lambda pair: pair[0])
    tag = data.get("tag_name")
    notes = data.get("body") or ""
    asset = next((a for a in data.get("assets", []) if str(a.get("name", "")).lower().endswith(".zip")), None)
    if not asset or not _hostAllowed(asset.get("browser_download_url", "")):
        raise UpdateError("The latest release has no .zip file attached.")
    # GitHub records a SHA-256 for every uploaded file ("digest"); fall back to a "sha256: ..." line in the description
    digest = re.fullmatch(r"sha256:([0-9a-fA-F]{64})", str(asset.get("digest") or ""))
    match = re.search(r"sha-?256\s*[:=]\s*([0-9a-fA-F]{64})", notes)
    checksum = (digest or match).group(1).lower() if (digest or match) else None
    return ReleaseInfo(tag, build, data.get("name") or tag, notes, asset["browser_download_url"],
                       int(asset.get("size") or 0), checksum)


def isNewer(release, currentBuild=BUILD, appDir=None):
    """Newer than what's installed, and not a build that was already tried on this PC and rolled back."""
    if appDir is not None and release.build <= blockedBuild(appDir):
        return False
    return release.build > currentBuild


def download(release, destination, progress=None, urlopen=None):
    """Download the release zip to destination and verify its SHA-256. Raises UpdateError on any problem."""
    if not release.sha256:
        raise UpdateError("GitHub didn't provide a checksum for this release file, so it can't be verified.")
    digest, total = hashlib.sha256(), 0
    with _open(release.assetUrl, urlopen, accept="application/octet-stream") as response, open(destination, "wb") as out:
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise UpdateError("The download is larger than expected.")
            digest.update(chunk)
            out.write(chunk)
            if progress:
                progress(total, release.size)
    if digest.hexdigest() != release.sha256:
        os.remove(destination)
        raise UpdateError("The download's checksum doesn't match the release, so it was discarded.")


def _wanted(relative):
    """Is this path (relative to the app folder, forward slashes) something a release may install?"""
    parts = relative.split("/")
    if not relative or relative.startswith("/") or ".." in parts or ":" in parts[0] or "\\" in relative:
        return False
    if parts[0].lower() in PROTECTED:
        return False
    if len(parts) == 1:
        return bool(ALLOWED_FILE_RE.match(parts[0]))
    return parts[0] in ALLOWED_DIRS


def stage(zipPath, appDir):
    """Safely extract the allowed files of a release zip into appDir/update-staging and mark it ready. Returns count."""
    staging = os.path.join(appDir, STAGING)
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    count = 0
    try:
        with zipfile.ZipFile(zipPath) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            tops = {n.split("/")[0] for n in names}
            prefix = (tops.pop() + "/") if len(tops) == 1 and all("/" in n for n in names) else ""
            total = 0
            for info in z.infolist():
                if info.filename.endswith("/"):
                    continue
                relative = info.filename[len(prefix):] if prefix and info.filename.startswith(prefix) else info.filename
                if not _wanted(relative):
                    continue
                total += info.file_size
                if total > 4 * MAX_DOWNLOAD_BYTES:
                    raise UpdateError("The update is unexpectedly large.")
                target = os.path.normpath(os.path.join(staging, relative))
                if os.path.commonpath([staging, target]) != staging:
                    continue  # Zip-slip guard
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
    except zipfile.BadZipFile:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError("The downloaded file isn't a valid zip.")
    if not count or not os.path.isfile(os.path.join(staging, "syncplay", "__init__.py")):
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError("The release doesn't look like a Syncplay bundle.")
    broken = brokenPythonFile(staging)
    if broken:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError("The release contains a broken file ({}), so it wasn't installed.".format(broken))
    with open(os.path.join(staging, READY_MARKER), "w") as marker:
        marker.write("ok")
    return count


def hasStagedUpdate(appDir):
    return os.path.isfile(os.path.join(appDir, STAGING, READY_MARKER))


def stagedBuild(appDir):
    """The build number of the update waiting in the staging folder, or 0 if there isn't a complete one."""
    if not hasStagedUpdate(appDir):
        return 0
    try:
        with open(os.path.join(appDir, STAGING, "syncplay", "private_build.py"), encoding="utf-8") as f:
            match = re.search(r"^BUILD\s*=\s*(\d+)", f.read(), re.M)
        return int(match.group(1)) if match else 0
    except (OSError, ValueError):
        return 0


def brokenPythonFile(root):
    """The first .py/.pyw file under root that isn't valid Python (a typo shipped by mistake must never be installed)."""
    for folder, _, files in os.walk(root):
        for name in files:
            if name.endswith((".py", ".pyw")):
                path = os.path.join(folder, name)
                try:
                    with open(path, "rb") as f:
                        compile(f.read(), path, "exec")
                except (SyntaxError, ValueError):
                    return os.path.relpath(path, root).replace(os.sep, "/")
    return None


def _now():
    import time
    return time.time()


def _readJson(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _writeJson(path, data):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(temporary, path)


def _buildOf(appDir):
    match = re.search(rb"BUILD\s*=\s*(\d+)", _read(os.path.join(appDir, "syncplay", "private_build.py")) or b"")
    return int(match.group(1)) if match else None


def applyStaged(appDir, pip=None, log=None):
    """Copy the staged files over the app folder. Run before Syncplay's modules are imported. Returns files copied.

    Every file that gets replaced is first copied to update-backup/, and update-pending.json records the change, so
    rollBack() can put the previous version back if the new one doesn't start."""
    staging = os.path.join(appDir, STAGING)
    if not hasStagedUpdate(appDir):
        return 0
    if brokenPythonFile(staging):
        shutil.rmtree(staging, ignore_errors=True)
        return 0
    oldRequirements = _read(os.path.join(appDir, "requirements.txt"))
    plan = []  # (relative, source, target)
    for root, _, files in os.walk(staging):
        for name in files:
            source = os.path.join(root, name)
            relative = os.path.relpath(source, staging).replace(os.sep, "/")
            if relative == READY_MARKER or not _wanted(relative):
                continue
            plan.append((relative, source, os.path.join(appDir, *relative.split("/"))))
    rollBack(appDir, "superseded by a newer update", record=False)  # Never stack an update on an unconfirmed one
    backup = os.path.join(appDir, BACKUP)
    shutil.rmtree(backup, ignore_errors=True)
    replaced = [relative for relative, _, target in plan if os.path.isfile(target)]
    created = [relative for relative, _, target in plan if not os.path.isfile(target)]
    for relative in replaced:
        destination = os.path.join(backup, *relative.split("/"))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(os.path.join(appDir, *relative.split("/")), destination)
    pending = {"state": "applying", "from": _buildOf(appDir), "to": None, "replaced": replaced, "created": created,
               "started": None}
    _writeJson(os.path.join(appDir, PENDING), pending)
    copied = 0
    for relative, source, target in plan:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        temporary = target + ".updating"
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)  # Atomic per file
        _dropCompiledCopies(target)
        copied += 1
    shutil.rmtree(staging, ignore_errors=True)
    pending.update(state="applied", to=_buildOf(appDir))
    _writeJson(os.path.join(appDir, PENDING), pending)
    _recordInstalledBuild(appDir)
    if _read(os.path.join(appDir, "requirements.txt")) != oldRequirements:
        (pip or _pipInstall)(appDir, log)
    return copied


def appFolder():
    """The folder Syncplay is running from (the one updates are installed into)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pendingUpdate(appDir):
    """The record of an update that has been applied but not yet confirmed working, or None."""
    data = _readJson(os.path.join(appDir, PENDING), None)
    return data if isinstance(data, dict) else None


def markStarted(appDir):
    """The launcher calls this just before running the app for the first time after an update."""
    pending = pendingUpdate(appDir)
    if pending and pending.get("state") == "applied" and not pending.get("started"):
        pending["started"] = _now()
        _writeJson(os.path.join(appDir, PENDING), pending)


def _addHistory(appDir, event, before, after, detail=""):
    history = _readJson(os.path.join(appDir, HISTORY), [])
    history = history if isinstance(history, list) else []
    history.append({"time": _now(), "event": event, "from": before, "to": after, "detail": detail, "seen": False})
    try:
        _writeJson(os.path.join(appDir, HISTORY), history[-50:])
    except OSError:
        pass


def confirmHealthy(appDir):
    """The new version's window is up: the update is kept, and the backup is no longer needed."""
    pending = pendingUpdate(appDir)
    if not pending:
        return False
    if pending.get("state") == "applied":
        _addHistory(appDir, "updated", pending.get("from"), pending.get("to"))
    shutil.rmtree(os.path.join(appDir, BACKUP), ignore_errors=True)
    try:
        os.remove(os.path.join(appDir, PENDING))
    except OSError:
        pass
    return True


def rollBack(appDir, reason, record=True, block=False):
    """Put the version from before the pending update back. True if something was rolled back."""
    pending = pendingUpdate(appDir)
    if not pending:
        return False
    backup = os.path.join(appDir, BACKUP)
    for relative in pending.get("replaced") or []:
        source = os.path.join(backup, *relative.split("/"))
        if _wanted(relative) and os.path.isfile(source):
            target = os.path.join(appDir, *relative.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(source, target + ".updating")
            os.replace(target + ".updating", target)
            _dropCompiledCopies(target)
    for relative in pending.get("created") or []:
        if _wanted(relative):
            target = os.path.join(appDir, *relative.split("/"))
            try:
                os.remove(target)
            except OSError:
                pass
            _dropCompiledCopies(target)
    marker = os.path.join(appDir, ".marquee-build")
    if _read(marker) is not None and pending.get("from") is not None:
        try:
            with open(marker, "w") as f:
                f.write(str(pending["from"]))
        except OSError:
            pass
    shutil.rmtree(backup, ignore_errors=True)
    try:
        os.remove(os.path.join(appDir, PENDING))
    except OSError:
        pass
    if block and pending.get("to"):
        _writeJson(os.path.join(appDir, BLOCKED), {"build": pending["to"]})
    if record:
        _addHistory(appDir, "rolled-back", pending.get("from"), pending.get("to"), reason)
    return True


def blockedBuild(appDir):
    """The highest build that was rolled back on this PC (0 if none): it isn't offered again."""
    data = _readJson(os.path.join(appDir, BLOCKED), {})
    try:
        return int(data.get("build") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def recoverFromFailedUpdate(appDir):
    """Launcher, first thing: if the previous start after an update never got as far as a working window, undo the
    update. Returns True when a rollback happened."""
    pending = pendingUpdate(appDir)
    if not pending:
        return False
    if pending.get("state") == "applying":  # Interrupted half way: files may be a mix of old and new
        return rollBack(appDir, "The update was interrupted.")
    started = pending.get("started")
    if started and _now() - float(started) > SETTLE_SECONDS:
        return rollBack(appDir, "The new version didn't start properly.", block=True)
    return False


def unseenHistory(appDir):
    """History entries the user hasn't been told about yet (each is returned once)."""
    history = _readJson(os.path.join(appDir, HISTORY), [])
    if not isinstance(history, list):
        return []
    fresh = [h for h in history if isinstance(h, dict) and not h.get("seen")]
    if fresh:
        for h in fresh:
            h["seen"] = True
        try:
            _writeJson(os.path.join(appDir, HISTORY), history)
        except OSError:
            pass
    return fresh


def history(appDir):
    data = _readJson(os.path.join(appDir, HISTORY), [])
    return [h for h in data if isinstance(h, dict)] if isinstance(data, list) else []


def _dropCompiledCopies(target):
    """Python trusts a cached .pyc whose recorded time and size match the source, so a same-size file replaced in the
    same second could keep running as the old code. Deleting the cache makes the new source the only truth."""
    if not target.endswith((".py", ".pyw")):
        return
    cache = os.path.join(os.path.dirname(target), "__pycache__")
    stem = os.path.splitext(os.path.basename(target))[0] + "."
    try:
        for name in os.listdir(cache):
            if name.startswith(stem) and name.endswith(".pyc"):
                os.remove(os.path.join(cache, name))
    except OSError:
        pass


def _recordInstalledBuild(appDir):
    """The single-file .exe re-unpacks its bundled app when this marker is older than the exe's own build, so record the
    build just installed: otherwise opening an older .exe later would silently roll the update back."""
    marker = os.path.join(appDir, ".marquee-build")
    current = _read(marker)
    installed = re.search(rb"BUILD\s*=\s*(\d+)", _read(os.path.join(appDir, "syncplay", "private_build.py")) or b"")
    if current is None or not installed:
        return  # Not the single-file edition (or nothing readable): nothing to keep in step
    try:
        if int(installed.group(1)) > int(current.strip() or 0):
            with open(marker, "wb") as f:
                f.write(installed.group(1))
    except (OSError, ValueError):
        pass


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def _pipInstall(appDir, log=None):
    """The release changed requirements.txt: install them into the private environment (best effort)."""
    python = os.path.join(appDir, ".venv", "Scripts" if os.name == "nt" else "bin", "python" + (".exe" if os.name == "nt" else ""))
    if not os.path.isfile(python):
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.run([python, "-m", "pip", "install", "-r", os.path.join(appDir, "requirements.txt")],
                       cwd=appDir, check=False, timeout=600, creationflags=flags,
                       stdout=log or subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except (OSError, subprocess.SubprocessError):
        pass


def forgetLoadedModules():
    """After applying an update, drop the old modules from memory so the new code is what gets imported."""
    for name in [n for n in sys.modules if n == "syncplay" or n.startswith("syncplay.")]:
        del sys.modules[name]
    importlib.invalidate_caches()  # A release can add modules that didn't exist when Python listed the folder


# --- Restarting after an update -------------------------------------------------------------------------------------

RESTARTED_ENV = "MARQUEE_RESTARTED"      # Set on the fresh copy: it reconnects straight away instead of showing the start dialog
UPDATED_FROM_ENV = "MARQUEE_UPDATED_FROM"  # The build number the previous copy was running

# Runs in its own tiny process: waits until the old copy has really exited (so nothing it had open can block the
# update, and the two never run side by side), then starts the new one.
_RELAUNCH_HELPER = r"""
import os, subprocess, sys, time
pid, appDir, fromBuild, skipWindow, command = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
def alive(pid):
    if os.name == "nt":
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258  # WAIT_TIMEOUT: still running
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
deadline = time.time() + 30
while alive(pid) and time.time() < deadline:
    time.sleep(0.2)
time.sleep(0.5)
env = dict(os.environ, MARQUEE_UPDATED_FROM=fromBuild)
if skipWindow == "1":
    env["MARQUEE_RESTARTED"] = "1"
subprocess.Popen(command, cwd=appDir, env=env, close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
"""


def relaunch(pid, python, argv, appDir, fromBuild=BUILD, skipStartWindow=True):
    """Start a helper that launches a fresh copy of the app once process pid has exited. Raises OSError if it can't.

    skipStartWindow=False brings the start (connection) window back on the new copy."""
    subprocess.Popen([python, "-c", _RELAUNCH_HELPER, str(pid), appDir, str(fromBuild), "1" if skipStartWindow else "0", python] + list(argv), cwd=appDir,
                     close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def restartedWithoutPrompt(environ=None):
    """True (once) when this copy was started by relaunch(), so it should skip the start dialog."""
    environ = os.environ if environ is None else environ
    return environ.pop(RESTARTED_ENV, None) == "1"


def consumeUpdateResult(appDir, environ=None, currentBuild=BUILD):
    """After a restart for an update: ("updated", fromBuild, toBuild), ("failed", fromBuild, toBuild) if the copy is
    still the old build with an update waiting, or None when this start wasn't an update restart."""
    environ = os.environ if environ is None else environ
    previous = environ.pop(UPDATED_FROM_ENV, None)
    try:
        previous = int(previous)
    except (TypeError, ValueError):
        return None
    if previous != currentBuild:
        return ("updated", previous, currentBuild)
    return ("failed", previous, currentBuild) if hasStagedUpdate(appDir) else None
