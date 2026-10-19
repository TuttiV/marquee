"""Making the app feel installed: choosing where it lives, Start menu / desktop shortcuts (or the Linux applications menu
and desktop), the invite-link handler on Linux, and a clean uninstall.

The packaged app always lives in a folder called "Syncplay Marquee" with the app files in its "app" subfolder:
- Windows: the .exe unpacks itself there (by default %LOCALAPPDATA%\\Syncplay Marquee; a folder chosen in the install window
  is remembered in the registry, which the .exe reads). The Python runtime sits in a "python-..." subfolder.
- Linux: the folder from the download (or the one it was installed to), with the Python runtime in "runtime" and a
  "Syncplay Marquee" start script.
Everything here only ever touches this app's own folder, its shortcuts and its link handler."""
import os
import shutil
import subprocess
import sys

from syncplay import invite

FOLDER_NAME = "Syncplay Marquee"
FLAG = "shortcutsAsked"     # Older builds asked about shortcuts once; anyone who saw that has been asked
INSTALL_FLAG = "installAsked"  # Saved once the install window has been shown, whatever the answer
EXE_NAME = "Syncplay Marquee.exe"
EXE_ENV = "MARQUEE_EXE"      # The .exe tells the app where it is, so an install can take a copy of it along
LAUNCHER_NAME = "Syncplay Marquee"  # The Linux start script in the install folder
REG_KEY = r"Software\Syncplay Marquee"
REG_VALUE = "InstallDir"
DESKTOP_ID = "syncplay-marquee"
LINUX = sys.platform.startswith("linux")
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def appFolder():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rootFolder(appDir=None):
    """The install folder (the parent of the app folder), or None when running some other way (e.g. from source)."""
    appDir = os.path.abspath(appDir or appFolder())
    root = os.path.dirname(appDir)
    if os.path.basename(appDir) == "app" and os.path.basename(root) == FOLDER_NAME:
        return root
    override = os.environ.get("MARQUEE_HOME")  # The .exe honours this too (used for testing)
    if override and os.path.basename(appDir) == "app" and os.path.abspath(override) == root:
        return root
    return None


def isPackaged(appDir=None):
    root = rootFolder(appDir)
    if root is None:
        return False
    if os.name == "nt":
        return True
    return LINUX and os.path.isdir(os.path.join(root, "runtime"))


# --- where to install --------------------------------------------------------------------------------------------------

def defaultParent():
    if os.name == "nt":
        return os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(os.path.expanduser("~"), ".local", "share")


def targetRoot(chosen):
    """The install folder for a folder the person picked: a "Syncplay Marquee" folder is made inside it (unless they picked
    one already called that), like any installer."""
    chosen = os.path.abspath(os.path.expanduser((chosen or "").strip()))
    return chosen if os.path.basename(chosen) == FOLDER_NAME else os.path.join(chosen, FOLDER_NAME)


def _same(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def checkTarget(target, current):
    """None when the app can be installed into target, otherwise a short reason to show."""
    if not target:
        return "Choose a folder."
    if current and _same(target, current):
        return None
    if current:
        try:
            inside = os.path.commonpath([os.path.normcase(os.path.abspath(target)), os.path.normcase(os.path.abspath(current))])
        except ValueError:  # Different drives
            inside = None
        if inside and (_same(inside, current) or _same(inside, target)):
            return "That folder is inside the current installation (or the other way round). Pick another one."
    if os.path.isfile(target):
        return "There is a file with that name. Pick another folder."
    if os.path.isdir(target) and os.listdir(target) and not os.path.isdir(os.path.join(target, "app")):
        return "That folder already has other files in it. Pick an empty or new folder."
    parent = os.path.dirname(target)
    probe = parent
    while probe and not os.path.isdir(probe):
        nextUp = os.path.dirname(probe)
        if nextUp == probe:
            break
        probe = nextUp
    if not probe or not os.access(probe, os.W_OK):
        return "You can't write to that folder. Pick one in your own user folder."
    return None


def _plan(current, target, exePath=None):
    """(source, destination) pairs for every file and link in the install, plus the .exe when it is known."""
    plan = []
    for folder, dirs, files in os.walk(current):
        dirs.sort()
        relative = os.path.relpath(folder, current)
        for name in list(dirs):  # Symbolic links to folders are copied as links, not followed
            if os.path.islink(os.path.join(folder, name)):
                plan.append((os.path.join(folder, name), os.path.normpath(os.path.join(target, relative, name))))
                dirs.remove(name)
        for name in sorted(files):
            plan.append((os.path.join(folder, name), os.path.normpath(os.path.join(target, relative, name))))
    if exePath and os.path.isfile(exePath):
        plan.append((exePath, os.path.join(target, EXE_NAME)))
    return plan


def copyInstall(current, target, exePath=None, progress=None):
    """Copy the whole installation to target (keeping start-script permissions and the runtime's links). Returns the
    number of files copied; raises OSError (and leaves the current installation untouched) if it fails."""
    plan = _plan(current, target, exePath)
    total = len(plan)
    for done, (source, destination) in enumerate(plan, 1):
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        if os.path.islink(source):
            if os.path.lexists(destination):
                os.remove(destination)
            os.symlink(os.readlink(source), destination)
        else:
            shutil.copy2(source, destination)
        if progress and (done % 25 == 0 or done == total):
            progress(done, total)
    return total


# --- Windows: remembering the folder for the .exe --------------------------------------------------------------------

def _winreg(reg):
    if reg is not None:
        return reg
    import winreg
    return winreg


def writeInstallDir(root, reg=None):
    reg = _winreg(reg)
    with reg.CreateKeyEx(reg.HKEY_CURRENT_USER, REG_KEY, 0, reg.KEY_WRITE) as key:
        reg.SetValueEx(key, REG_VALUE, 0, reg.REG_SZ, os.path.abspath(root))


def readInstallDir(reg=None):
    try:
        reg = _winreg(reg)
        with reg.OpenKey(reg.HKEY_CURRENT_USER, REG_KEY) as key:
            return reg.QueryValueEx(key, REG_VALUE)[0] or None
    except (OSError, ImportError):
        return None


# --- Windows shortcuts -------------------------------------------------------------------------------------------------

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


def _runtimeFolder(root):
    """The python-... folder of a Windows install."""
    try:
        for name in sorted(os.listdir(root)):
            if name.startswith("python-") and os.path.isfile(os.path.join(root, name, "pythonw.exe")):
                return os.path.join(root, name)
    except OSError:
        pass
    return None


def createShortcut(kind, appDir=None, python=None, runner=subprocess.run, exe=None):
    """Put a 'Syncplay Marquee' shortcut in the Start menu (kind 'startmenu') or on the desktop ('desktop'). It opens the
    .exe when there is one in the install folder, otherwise the app's own Python and launcher. Raises OSError."""
    appDir = appDir or appFolder()
    if exe:
        extra = {"MQ_TARGET": exe, "MQ_ARGS": "", "MQ_DIR": os.path.dirname(exe), "MQ_ICON": exe + ",0"}
    else:
        launcher = os.path.join(appDir, "program", "launch-syncplay.pyw")
        icon = os.path.join(appDir, "syncplay", "resources", "icon.ico")
        extra = {"MQ_TARGET": python or sys.executable, "MQ_ARGS": '"{}"'.format(launcher), "MQ_DIR": appDir, "MQ_ICON": icon}
    try:
        _powershell("create", kind, extra, runner)
    except (subprocess.SubprocessError, OSError) as e:
        raise OSError("Couldn't create the shortcut: {}".format(e))


def removeShortcut(kind, runner=subprocess.run):
    try:
        _powershell("remove", kind, {}, runner)
    except (subprocess.SubprocessError, OSError):
        pass  # Already gone, or PowerShell isn't available: nothing more to do


# --- Linux menu entry, desktop launcher and link handler --------------------------------------------------------------

def _dataHome():
    return os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")


def desktopFolder(runner=subprocess.run):
    """The person's desktop folder (it has a translated name on many systems)."""
    try:
        done = runner(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=5)
        path = (done.stdout or "").strip()
        if path and path != os.path.expanduser("~") and os.path.isdir(path):
            return path
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def linuxEntryPath(kind, runner=subprocess.run):
    if kind == "desktop":
        return os.path.join(desktopFolder(runner), DESKTOP_ID + ".desktop")
    if kind == "links":
        return os.path.join(_dataHome(), "applications", DESKTOP_ID + "-links.desktop")
    return os.path.join(_dataHome(), "applications", DESKTOP_ID + ".desktop")


def launcherPath(root):
    return os.path.join(root, LAUNCHER_NAME)


def _quoteExec(path):
    """A path as one argument of a .desktop Exec line (always double-quoted, with the characters the spec reserves escaped)."""
    escaped = path.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return '"{}"'.format(escaped.replace("%", "%%"))


def desktopEntry(root, links=False):
    icon = os.path.join(root, "app", "syncplay", "resources", "syncplay.png")
    lines = ["[Desktop Entry]", "Type=Application", "Version=1.0", "Name=Syncplay Marquee",
             "Comment=Watch videos in sync with friends", "Exec={} %u".format(_quoteExec(launcherPath(root))),
             "Icon={}".format(icon), "Terminal=false", "Categories=AudioVideo;Video;Network;", "StartupNotify=true"]
    if links:
        lines += ["NoDisplay=true", "MimeType=x-scheme-handler/{};".format(invite.SCHEME)]
    return "\n".join(lines) + "\n"


def _refreshMenus(runner):
    try:
        runner(["update-desktop-database", os.path.join(_dataHome(), "applications")], timeout=20,
               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        pass


def writeLinuxEntry(kind, root, runner=subprocess.run):
    """Create the menu entry ('menu'), desktop launcher ('desktop') or hidden link handler ('links'). Raises OSError."""
    path = linuxEntryPath(kind, runner)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(desktopEntry(root, links=(kind == "links")))
    os.chmod(path, 0o755)  # Desktop launchers must be executable to be trusted
    if kind == "desktop":
        try:  # Nemo/Nautilus also want this mark before they run a launcher from the desktop
            runner(["gio", "set", path, "metadata::trusted", "true"], timeout=10,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        _refreshMenus(runner)
    return path


def removeLinuxEntry(kind, runner=subprocess.run):
    try:
        os.remove(linuxEntryPath(kind, runner))
    except OSError:
        return
    if kind != "desktop":
        _refreshMenus(runner)


def registerLinuxLinks(root, runner=subprocess.run):
    """Make syncplay-marquee:// links open this app. Raises OSError if the handler file can't be written."""
    path = writeLinuxEntry("links", root, runner)
    try:
        runner(["xdg-mime", "default", os.path.basename(path), "x-scheme-handler/{}".format(invite.SCHEME)], timeout=20,
               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        pass


def linuxLinksRegistered(root, runner=subprocess.run):
    try:
        with open(linuxEntryPath("links", runner), encoding="utf-8") as f:
            return f.read() == desktopEntry(root, links=True)
    except OSError:
        return False


# --- both systems --------------------------------------------------------------------------------------------------

def existingShortcuts(runner=subprocess.run):
    """{'menu': bool, 'desktop': bool} for the shortcuts that exist now (best effort; used to pre-tick the install window)."""
    if LINUX:
        return {"menu": os.path.exists(linuxEntryPath("menu", runner)), "desktop": os.path.exists(linuxEntryPath("desktop", runner))}
    appData, profile = os.environ.get("APPDATA", ""), os.environ.get("USERPROFILE", "")
    return {"menu": os.path.exists(os.path.join(appData, "Microsoft", "Windows", "Start Menu", "Programs", "Syncplay Marquee.lnk")),
            "desktop": os.path.exists(os.path.join(profile, "Desktop", "Syncplay Marquee.lnk"))}


def setShortcuts(root, menu, desktop, runner=subprocess.run):
    """Make the shortcuts match the two choices (creating or removing each). Raises OSError if one can't be created."""
    if LINUX:
        for kind, wanted in (("menu", menu), ("desktop", desktop)):
            if wanted:
                writeLinuxEntry(kind, root, runner)
            else:
                removeLinuxEntry(kind, runner)
        return
    exe = os.path.join(root, EXE_NAME)
    exe = exe if os.path.isfile(exe) else None
    runtime = _runtimeFolder(root)
    python = os.path.join(runtime, "pythonw.exe") if runtime else None
    for kind, wanted in (("startmenu", menu), ("desktop", desktop)):
        if wanted:
            createShortcut(kind, appDir=os.path.join(root, "app"), python=python, runner=runner, exe=exe)
        else:
            removeShortcut(kind, runner)


def startCommand(root, arguments=()):
    """The command that starts the copy installed in root."""
    if LINUX or os.name != "nt":
        return [launcherPath(root)] + list(arguments)
    exe = os.path.join(root, EXE_NAME)
    if os.path.isfile(exe):
        return [exe] + list(arguments)
    runtime = _runtimeFolder(root)
    return [os.path.join(runtime or root, "pythonw.exe"), os.path.join(root, "app", "program", "launch-syncplay.pyw")] + list(arguments)


def startInstalled(root, arguments=(), popen=subprocess.Popen):
    popen(startCommand(root, arguments), cwd=root, close_fds=True, creationflags=_NO_WINDOW,
          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def removeFolderLater(folder, pid=None, popen=subprocess.Popen, tempDir=None):
    """Delete an old install folder once this process (pid) has closed. Only ever a folder this app installed."""
    folder = os.path.abspath(folder)
    if os.path.basename(folder) != FOLDER_NAME or not os.path.isdir(os.path.join(folder, "app")):
        raise ValueError("Refusing to remove {!r}: not a Syncplay Marquee folder".format(folder))
    if os.name == "nt":
        script = uninstallScript(folder)
        path = os.path.join(tempDir or os.environ.get("TEMP") or os.path.dirname(folder), "syncplay-marquee-move.bat")
        with open(path, "w", encoding="ascii", errors="replace", newline="") as f:
            f.write(script)
        popen(["cmd", "/c", path], creationflags=_NO_WINDOW, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL)
        return path
    pid = pid or os.getpid()
    popen(["sh", "-c", 'while kill -0 "$1" 2>/dev/null; do sleep 1; done; rm -rf -- "$2"', "sh", str(pid), folder],
          close_fds=True, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return folder


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


SETTINGS_FILES = ("syncplay-secrets.json", "syncplay.ini", ".syncplay", "instance.json", "invite-inbox.txt", "resume-positions.json")


def uninstall(configDir, deleteSettings=False, root=None, launcher=subprocess.Popen, tempDir=None, runner=subprocess.run):
    """Remove the link handler and shortcuts now, and the app's folder once this process has exited.
    Returns the path of the Windows script that was started (or the folder on Linux)."""
    root = root or rootFolder()
    if not root:
        raise ValueError("This copy of the app isn't an installed one, so there is nothing to uninstall.")
    settings = [os.path.join(configDir, name) for name in SETTINGS_FILES] if (deleteSettings and configDir) else []
    if LINUX:
        if os.path.basename(os.path.abspath(root)) != FOLDER_NAME or not os.path.isdir(os.path.join(root, "app")):
            raise ValueError("Refusing to remove {!r}: not a Syncplay Marquee folder".format(root))
        for kind in ("menu", "desktop", "links"):
            removeLinuxEntry(kind, runner)
        for path in settings:
            try:
                os.remove(path)
            except OSError:
                pass
        return removeFolderLater(root, popen=launcher)
    try:
        invite.unregisterHandler()
    except Exception:
        pass
    for kind in KINDS:
        removeShortcut(kind)
    registry = ["HKCU\\" + REG_KEY]
    if deleteSettings and configDir:
        registry.append("HKCU\\Software\\Syncplay")
    script = uninstallScript(root, settings, registry)
    path = os.path.join(tempDir or os.environ.get("TEMP") or os.path.dirname(root), "syncplay-marquee-uninstall.bat")
    with open(path, "w", encoding="ascii", errors="replace", newline="") as f:
        f.write(script)
    launcher(["cmd", "/c", path], creationflags=_NO_WINDOW, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
             stderr=subprocess.DEVNULL)
    return path
