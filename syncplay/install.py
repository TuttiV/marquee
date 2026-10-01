"""Making the single-file .exe feel installed: Start menu / desktop shortcuts and a clean uninstall.

Everything here only ever touches this app's own folder, its shortcuts and its link handler. The runtime lives in
%LOCALAPPDATA%\\Syncplay Marquee (the folder above the app folder), which is what an uninstall removes."""
import os
import subprocess
import sys

from syncplay import invite

FOLDER_NAME = "Syncplay Marquee"
FLAG = "shortcutsAsked"  # Saved once the person has been asked about shortcuts, whatever they answered
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def appFolder():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rootFolder(appDir=None):
    """The folder the single-file app unpacked itself into (the parent of the app folder), or None when running some other way."""
    appDir = os.path.abspath(appDir or appFolder())
    root = os.path.dirname(appDir)
    if os.path.basename(appDir) == "app" and os.path.basename(root) == FOLDER_NAME:
        return root
    override = os.environ.get("MARQUEE_HOME")  # The stub honours this too (used for testing)
    if override and os.path.basename(appDir) == "app" and os.path.abspath(override) == root:
        return root
    return None


def isPackaged(appDir=None):
    return os.name == "nt" and rootFolder(appDir) is not None


# --- shortcuts --------------------------------------------------------------------------------------------------------

_SHORTCUT_SCRIPT = (
    "$dir = [Environment]::GetFolderPath($env:MQ_KIND); $path = Join-Path $dir 'Syncplay Marquee.lnk'; "
    "if ($env:MQ_ACTION -eq 'remove') { if (Test-Path $path) { Remove-Item $path -Force }; exit 0 }; "
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($path); $s.TargetPath = $env:MQ_TARGET; $s.Arguments = $env:MQ_ARGS; "
    "$s.WorkingDirectory = $env:MQ_DIR; $s.IconLocation = $env:MQ_ICON; $s.Description = 'Syncplay Marquee'; $s.Save()")
KINDS = {"startmenu": "Programs", "desktop": "Desktop"}


def _powershell(action, kind, extra, runner):
    env = dict(os.environ, MQ_ACTION=action, MQ_KIND=KINDS[kind], **extra)
    runner(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _SHORTCUT_SCRIPT],
           env=env, creationflags=_NO_WINDOW, timeout=40, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def createShortcut(kind, appDir=None, python=None, runner=subprocess.run):
    """Put a 'Syncplay Marquee' shortcut in the Start menu (kind 'startmenu') or on the desktop ('desktop'). Raises OSError."""
    appDir = appDir or appFolder()
    launcher = os.path.join(appDir, "program", "launch-syncplay.pyw")
    icon = os.path.join(appDir, "syncplay", "resources", "icon.ico")
    try:
        _powershell("create", kind, {"MQ_TARGET": python or sys.executable, "MQ_ARGS": '"{}"'.format(launcher), "MQ_DIR": appDir, "MQ_ICON": icon}, runner)
    except (subprocess.SubprocessError, OSError) as e:
        raise OSError("Couldn't create the shortcut: {}".format(e))


def removeShortcut(kind, runner=subprocess.run):
    try:
        _powershell("remove", kind, {}, runner)
    except (subprocess.SubprocessError, OSError):
        pass  # Already gone, or PowerShell isn't available: nothing more to do


# --- uninstall --------------------------------------------------------------------------------------------------------

def uninstallScript(root, settingsFiles=(), registryKeys=()):
    """The .bat that finishes an uninstall once the app has closed: it keeps trying to delete the app's folder (Windows
    won't delete files that are still in use), then the settings the person chose to remove, then itself."""
    root = os.path.abspath(root)
    if os.path.basename(root) != FOLDER_NAME or not os.path.isdir(os.path.join(root, "app")):
        raise ValueError("Refusing to remove {!r}: not a Syncplay Marquee folder".format(root))
    lines = ["@echo off", "for /l %%i in (1,1,60) do (", '  rmdir /s /q "{}" >nul 2>&1'.format(root),
             '  if not exist "{}" goto done'.format(root), "  ping -n 2 127.0.0.1 >nul", ")", ":done"]
    for path in settingsFiles:
        lines.append('del /f /q "{}" >nul 2>&1'.format(os.path.abspath(path)))
    for key in registryKeys:
        lines.append('reg delete "{}" /f >nul 2>&1'.format(key))
    lines.append('del "%~f0"')
    return "\r\n".join(lines) + "\r\n"


def uninstall(configDir, deleteSettings=False, root=None, launcher=subprocess.Popen, tempDir=None):
    """Remove the link handler and shortcuts now, and schedule the removal of the app folder for after this process exits.
    Returns the path of the script that was started."""
    root = root or rootFolder()
    if not root:
        raise ValueError("This copy of the app isn't the single-file version, so there is nothing to uninstall.")
    try:
        invite.unregisterHandler()
    except Exception:
        pass
    for kind in KINDS:
        removeShortcut(kind)
    settings, registry = [], []
    if deleteSettings and configDir:
        for name in ("syncplay-secrets.json", "syncplay.ini", ".syncplay", "instance.json", "invite-inbox.txt"):
            settings.append(os.path.join(configDir, name))
        registry.append("HKCU\\Software\\Syncplay")
    script = uninstallScript(root, settings, registry)
    path = os.path.join(tempDir or os.environ.get("TEMP") or os.path.dirname(root), "syncplay-marquee-uninstall.bat")
    with open(path, "w", encoding="ascii", errors="replace", newline="") as f:
        f.write(script)
    launcher(["cmd", "/c", path], creationflags=_NO_WINDOW, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
             stderr=subprocess.DEVNULL)
    return path
