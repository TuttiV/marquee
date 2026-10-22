#!/usr/bin/env python3
"""Builds the Linux downloads: a folder with its own Python, every library and the app, packed as a .tar.xz, and the same
files as a .deb package for Linux Mint, Ubuntu and Debian (double-click it, Install, and it is in the applications menu).

    python tools/make-linux.py --build 27 [--defaults path/to/syncplay-defaults.json] [--out dist]

Nothing needs to be installed on the user's PC except a video player (mpv or VLC): the bundle carries a standalone
Python (python-build-standalone), PySide6 and the few X11 helper libraries Qt needs that a fresh Linux Mint may not have.
The person extracts the archive and opens "Syncplay Marquee"; the first start shows the install window (folder, menu and
desktop shortcuts). The in-app Update keeps the app files current, exactly like on Windows.

The .deb puts everything in /opt/syncplay-marquee with a menu entry, an icon and the invite-link handler in the system's
own places. Those files belong to the system, so its start script runs each person's own copy of the app files
(~/.local/share/syncplay-marquee/app, copied from the package on first start), which the in-app Update keeps current;
a newer package replaces that copy. It depends on the system libraries the bundle links to and on mpv or VLC.

Needs: python3, pip, binutils (readelf) and dpkg (dpkg-deb, dpkg -S). Downloads are cached in <out>/cache."""
import argparse
import glob
import hashlib
import importlib.util
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = "Syncplay Marquee"
LAUNCHER = "Syncplay Marquee"

PBS_RELEASE, PY_VERSION = "20250604", "3.11.13"
PBS_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/{0}/"
           "cpython-{1}%2B{0}-x86_64-unknown-linux-gnu-install_only.tar.gz").format(PBS_RELEASE, PY_VERSION)
REQUIREMENTS = ["twisted[tls]", "pem", "certifi", "PySide6-Essentials==6.11.2"]

# X11 helper libraries Qt's xcb platform plugin links to that are not part of a default Ubuntu/Mint install (the classic
# "could not load the Qt platform plugin xcb" error). Ubuntu 22.04 builds, so they run on Mint 21 and 22 alike.
UBUNTU = "https://archive.ubuntu.com/ubuntu/pool/"
XCB_DEBS = ["universe/x/xcb-util-cursor/libxcb-cursor0_0.1.1-4ubuntu1_amd64.deb",
            "main/x/xcb-util-image/libxcb-image0_0.4.0-2_amd64.deb",
            "main/x/xcb-util-renderutil/libxcb-render-util0_0.3.9-1build3_amd64.deb",
            "main/x/xcb-util-wm/libxcb-icccm4_0.4.1-1.1build2_amd64.deb",
            "main/x/xcb-util-keysyms/libxcb-keysyms1_0.4.0-1build3_amd64.deb",
            "main/x/xcb-util/libxcb-util1_0.4.0-1build2_amd64.deb",
            "main/libx/libxcb/libxcb-xkb1_1.14-3ubuntu3_amd64.deb",
            "main/libx/libxkbcommon/libxkbcommon-x11-0_1.4.0-1_amd64.deb"]

# Qt parts the app uses: these Python modules and plugins, plus whatever Qt libraries they need (found with readelf).
QT_MODULES = {"QtCore", "QtGui", "QtWidgets", "QtSvg"}
QT_PLUGINS = ["platforms/libqxcb.so", "xcbglintegrations/*.so", "imageformats/libqsvg.so", "imageformats/libqico.so",
              "imageformats/libqgif.so", "imageformats/libqjpeg.so", "iconengines/libqsvgicon.so", "platforminputcontexts/*.so",
              "platformthemes/libqxdgdesktopportal.so"]
QT_TRIM_DIRS = ["examples", "glue", "include", "typesystems", "scripts", "support", "Qt/qml", "Qt/translations", "Qt/metatypes",
                "Qt/resources", "Qt/libexec", "doc", "lib",
                # Qt's developer tools (they link to Qt parts that aren't kept, so they couldn't even start)
                "assistant", "designer", "linguist", "lrelease", "lupdate", "qmlformat", "qmllint", "qmlls", "svgtoqml"]
PY_TRIM = ["lib/python3.11/test", "lib/python3.11/idlelib", "lib/python3.11/tkinter", "lib/python3.11/turtledemo",
           "lib/python3.11/lib2to3", "lib/python3.11/ensurepip", "lib/python3.11/lib-dynload/_tkinter*", "lib/python3.11/config-3.11*",
           "lib/libtcl*", "lib/libtk*", "lib/tcl8*", "lib/tk8*", "lib/itcl*", "lib/thread*", "lib/Tix*", "share", "include",
           "bin/idle3*", "bin/pydoc*", "bin/2to3*"]
TRIM_ANYWHERE = {"test", "tests", "testing"}


def download(url, path):
    if not os.path.isfile(path):
        print("Downloading", url)
        temporary = path + ".part"
        with urllib.request.urlopen(url) as response, open(temporary, "wb") as out:
            shutil.copyfileobj(response, out)
        os.replace(temporary, path)
    return path


def removeAny(path):
    for match in glob.glob(path):
        if os.path.islink(match) or os.path.isfile(match):
            os.remove(match)
        elif os.path.isdir(match):
            shutil.rmtree(match)


def needed(path):
    """The shared libraries an ELF file links to."""
    out = subprocess.run(["readelf", "-d", path], capture_output=True, text=True).stdout
    return [line.split("[", 1)[1].split("]", 1)[0] for line in out.splitlines() if "(NEEDED)" in line]


def assembleRuntime(cache, root):
    runtime = os.path.join(root, "runtime")
    archive = download(PBS_URL, os.path.join(cache, os.path.basename(PBS_URL).replace("%2B", "+")))
    with tarfile.open(archive) as tar:
        tar.extractall(root, filter="tar") if hasattr(tarfile, "data_filter") else tar.extractall(root)
    os.replace(os.path.join(root, "python"), runtime)
    python = os.path.join(runtime, "bin", "python3")
    isolated = dict(os.environ, PYTHONNOUSERSITE="1", PIP_USER="0")  # Never count the build machine's own packages
    isolated.pop("PYTHONPATH", None)
    subprocess.run([python, "-m", "pip", "install", "--ignore-installed", "--no-warn-script-location", "--disable-pip-version-check", "--no-compile",
                    "--cache-dir", os.path.join(cache, "pip")] + REQUIREMENTS, check=True, env=isolated)
    subprocess.run([python, "-m", "pip", "uninstall", "-y", "pip"], check=True, stdout=subprocess.DEVNULL, env=isolated)
    for pattern in PY_TRIM:
        removeAny(os.path.join(runtime, pattern))
    site = glob.glob(os.path.join(runtime, "lib", "python3.11", "site-packages"))[0]
    for folder, dirs, _ in os.walk(site, topdown=True):
        for name in list(dirs):
            if name in TRIM_ANYWHERE and "PySide6" not in folder:
                shutil.rmtree(os.path.join(folder, name), ignore_errors=True)
                dirs.remove(name)
    trimQt(os.path.join(site, "PySide6"))
    addXcbLibraries(cache, os.path.join(site, "PySide6", "Qt", "lib"))
    for path in glob.glob(os.path.join(site, "*.dist-info", "RECORD")):
        os.remove(path)
    return runtime


def trimQt(pyside):
    for name in QT_TRIM_DIRS:
        removeAny(os.path.join(pyside, name))
    for path in glob.glob(os.path.join(pyside, "*.pyi")):
        os.remove(path)
    for path in glob.glob(os.path.join(pyside, "Qt*.abi3.so")):  # Python bindings for Qt modules the app doesn't use
        if os.path.basename(path).split(".")[0] not in QT_MODULES:
            os.remove(path)
    for path in glob.glob(os.path.join(pyside, "*.so*")):
        if os.path.basename(path).startswith(("libpyside6qml",)):
            os.remove(path)
    plugins = os.path.join(pyside, "Qt", "plugins")
    keep = set()
    for pattern in QT_PLUGINS:
        keep.update(os.path.abspath(p) for p in glob.glob(os.path.join(plugins, pattern)))
    for folder, _, files in os.walk(plugins):
        for name in files:
            path = os.path.abspath(os.path.join(folder, name))
            if path not in keep:
                os.remove(path)
    for folder in sorted({os.path.join(plugins, d) for d in os.listdir(plugins)}):
        if os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)
    # Keep only the Qt libraries something we kept links to (directly or through another Qt library)
    lib = os.path.join(pyside, "Qt", "lib")
    roots = [p for p in glob.glob(os.path.join(pyside, "*.so*")) + list(keep)]
    wanted, queue = set(), list(roots)
    while queue:
        for dependency in needed(queue.pop()):
            candidate = os.path.join(lib, dependency)
            if dependency not in wanted and os.path.exists(candidate):
                wanted.add(dependency)
                queue.append(os.path.realpath(candidate))
    for path in glob.glob(os.path.join(lib, "*.so*")):
        name = os.path.basename(path)
        if name not in wanted and not any(name.startswith(w.split(".so")[0] + ".so") for w in wanted):
            os.remove(path)


def addXcbLibraries(cache, lib):
    """Put the X11 helper libraries next to Qt's own: Qt looks there first, so they are used only by Qt, not by the
    video player the app starts (unlike LD_LIBRARY_PATH)."""
    debs = os.path.join(cache, "debs")
    os.makedirs(debs, exist_ok=True)
    for path in XCB_DEBS:
        deb = download(UBUNTU + path, os.path.join(debs, os.path.basename(path)))
        unpacked = os.path.join(debs, os.path.basename(path) + ".d")
        if not os.path.isdir(unpacked):
            subprocess.run(["dpkg-deb", "-x", deb, unpacked], check=True)
        for so in glob.glob(os.path.join(unpacked, "usr", "lib", "x86_64-linux-gnu", "*.so.*")):
            target = os.path.join(lib, os.path.basename(so))
            if os.path.islink(so):
                if not os.path.lexists(target):
                    os.symlink(os.readlink(so), target)
            else:
                shutil.copyfile(so, target)


def loadMakeExe():
    spec = importlib.util.spec_from_file_location("make_exe", os.path.join(ROOT, "tools", "make-exe.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LAUNCHER_SCRIPT = """#!/bin/sh
# Starts Syncplay Marquee with the Python that came with it (nothing from the system is needed).
here="$(cd "$(dirname "$0")" && pwd)"
export PYTHONNOUSERSITE=1
unset PYTHONHOME PYTHONPATH
exec "$here/runtime/bin/python3" "$here/app/program/launch-syncplay.pyw" "$@"
"""

README = """Syncplay Marquee for Linux
==========================

1. Install a video player if you don't have one: mpv or VLC (Software Manager, or `sudo apt install mpv`).
   Celluloid, the default player on Linux Mint, can't be used.
2. Open "Syncplay Marquee" in this folder (if your file manager asks, choose Run).
3. The install window asks where to install and whether you want a menu entry and/or a desktop shortcut.
   After installing you can delete this downloaded folder.

Help > Install and shortcuts changes those later; Help > Uninstall removes the app again.
Updates install themselves from inside the app (Help > Update, or the bar that appears when one is ready).
"""


PACKAGE = "syncplay-marquee"
PACKAGE_DIR = "/opt/" + PACKAGE

PACKAGE_LAUNCHER = """#!/bin/sh
# Starts Syncplay Marquee from the .deb package. The package's files belong to the system and can't change, so each person
# runs their own copy of the app files, which the in-app Update keeps current. A newer package replaces that copy.
base="$(dirname "$(readlink -f "$0")")"
data="${XDG_DATA_HOME:-$HOME/.local/share}/syncplay-marquee"
build() { sed -n 's/^BUILD *= *\\([0-9][0-9]*\\).*/\\1/p' "$1/syncplay/private_build.py" 2>/dev/null | head -n 1; }
have="$(build "$data/app")"
want="$(build "$base/app")"
if [ ! -f "$data/app/program/launch-syncplay.pyw" ] || [ "${have:-0}" -lt "${want:-0}" ]; then
    rm -rf "$data/app.new"
    if mkdir -p "$data" && cp -R "$base/app" "$data/app.new"; then
        rm -rf "$data/app" && mv "$data/app.new" "$data/app"
    fi
fi
app="$data/app"
[ -f "$app/program/launch-syncplay.pyw" ] || app="$base/app"  # No writable home folder: run the package's own copy
export PYTHONNOUSERSITE=1 MARQUEE_PACKAGE="$base"
unset PYTHONHOME PYTHONPATH
exec "$base/runtime/bin/python3" "$app/program/launch-syncplay.pyw" "$@"
"""

DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Version=1.0
Name=Syncplay Marquee
GenericName=Watch together
Comment=Watch videos in sync with friends
Exec=syncplay-marquee %u
Icon=syncplay-marquee
Terminal=false
Categories=AudioVideo;Video;Network;
Keywords=sync;watch;together;video;mpv;vlc;
MimeType=x-scheme-handler/syncplay-marquee;
StartupNotify=true
StartupWMClass=syncplay-marquee
"""

COPYRIGHT = """Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Syncplay Marquee
Source: https://github.com/TuttiV/marquee

Files: *
License: Apache-2.0
 On Debian systems the full text of the Apache License 2.0 is in /usr/share/common-licenses/Apache-2.0.
 The bundled components (Python, Qt for Python, Twisted and their dependencies) keep their own licences,
 which are included with each of them under /opt/syncplay-marquee/runtime.
"""

CONTROL = """Package: {package}
Version: {build}
Architecture: amd64
Maintainer: TuttiV <TuttiV@users.noreply.github.com>
Installed-Size: {size}
Depends: {depends}
Section: video
Priority: optional
Homepage: https://github.com/TuttiV/marquee
Description: Watch videos in sync with friends
 Syncplay Marquee keeps everyone's video player (mpv or VLC) at the same
 moment: play, pause and seek together, with chat, invite links and shared
 subtitles. It keeps itself up to date from inside the app.
"""


def isElf(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


def systemLibraries(root):
    """(sonames, glibc) the bundle needs from the system: what its programs and libraries link to that it doesn't carry
    itself, and the newest C library version any of them asks for."""
    provided, wanted, glibc = set(), set(), (2, 17)
    for folder, _, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            if ".so" in name:
                provided.add(name)
            if os.path.islink(path) or not isElf(path):
                continue
            wanted.update(os.path.basename(name) for name in needed(path))  # Some name a path ($ORIGIN/../lib/...)
            versions = subprocess.run(["readelf", "-V", path], capture_output=True, text=True).stdout
            for major, minor in re.findall(r"Name: GLIBC_(\d+)\.(\d+)", versions):
                glibc = max(glibc, (int(major), int(minor)))
    return sorted(wanted - provided), glibc


def debianDepends(root):
    """The Depends line: the packages that hold the system libraries the bundle links to, looked up on this (Debian or
    Ubuntu) build machine. Ubuntu 24.04 renamed some for its 64-bit time change ("...t64"); those still answer to the
    old names, which Ubuntu 22.04 and Linux Mint 21 use, so the old names are used."""
    sonames, glibc = systemLibraries(root)
    packages, unknown = set(), []
    for soname in sonames:
        out = subprocess.run(["dpkg", "-S", "*/" + soname], capture_output=True, text=True).stdout
        found = None
        for line in out.splitlines():
            owners, _, path = line.partition(": ")
            if os.path.basename(path.strip()) == soname and "/lib" in path:
                found = owners.split(",")[0].strip().split(":")[0]
                break
        if found:
            packages.add(re.sub(r"t64$", "", found))
        else:
            unknown.append(soname)
    if unknown:
        print("No package found on this machine for:", ", ".join(unknown))
    packages.discard("libc6")
    # A video player is part of what it needs: the system's installer adds mpv when neither is there
    return ", ".join(["libc6 (>= {}.{})".format(*glibc)] + sorted(packages) + ["mpv | vlc"])


def normalisePermissions(top):
    for folder, dirs, files in os.walk(top):
        os.chmod(folder, 0o755)
        for name in files:
            path = os.path.join(folder, name)
            if not os.path.islink(path):
                os.chmod(path, 0o755 if os.stat(path).st_mode & 0o111 else 0o644)


def buildDeb(root, build, out):
    """Package the finished folder as a .deb. Returns its path."""
    stage = os.path.join(os.path.dirname(root), "deb")
    shutil.rmtree(stage, ignore_errors=True)
    target = os.path.join(stage, PACKAGE_DIR.lstrip("/"))
    os.makedirs(target)
    for part in ("runtime", "app"):
        shutil.copytree(os.path.join(root, part), os.path.join(target, part), symlinks=True)
    # The package's files can't be written to later, so compile the Python files now (or every start would)
    subprocess.run([os.path.join(target, "runtime", "bin", "python3"), "-m", "compileall", "-q", "-j0", "-s", stage, "-p", "/",
                    os.path.join(target, "runtime", "lib")], check=True, env=dict(os.environ, PYTHONNOUSERSITE="1"))
    launcher = os.path.join(target, PACKAGE)
    with open(launcher, "w") as f:
        f.write(PACKAGE_LAUNCHER)
    os.chmod(launcher, 0o755)
    files = {"usr/share/applications/{}.desktop".format(PACKAGE): DESKTOP_ENTRY, "usr/share/doc/{}/copyright".format(PACKAGE): COPYRIGHT}
    for relative, text in files.items():
        path = os.path.join(stage, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
    icon = os.path.join(stage, "usr", "share", "icons", "hicolor", "256x256", "apps", PACKAGE + ".png")
    os.makedirs(os.path.dirname(icon))
    shutil.copyfile(os.path.join(root, "app", "syncplay", "resources", "syncplay.png"), icon)
    os.makedirs(os.path.join(stage, "usr", "bin"))
    os.symlink(os.path.join(PACKAGE_DIR, PACKAGE), os.path.join(stage, "usr", "bin", PACKAGE))
    normalisePermissions(stage)

    size = sum(os.lstat(os.path.join(folder, name)).st_size for folder, _, names in os.walk(stage) for name in names)
    debian = os.path.join(stage, "DEBIAN")
    os.makedirs(debian)
    with open(os.path.join(debian, "control"), "w") as f:
        f.write(CONTROL.format(package=PACKAGE, build=build, size=(size + 1023) // 1024, depends=debianDepends(target)))
    os.chmod(os.path.join(debian, "control"), 0o644)
    deb = os.path.join(out, "marquee_{}_amd64.deb".format(build))
    subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "-z9", "--build", stage, deb], check=True, stdout=subprocess.DEVNULL)
    return deb


def verify(root):
    python = os.path.join(root, "runtime", "bin", "python3")
    env = dict(os.environ, PYTHONNOUSERSITE="1", QT_QPA_PLATFORM="xcb")
    env.pop("PYTHONPATH", None)
    check = ("import sys; sys.path.insert(0, %r); import PySide6.QtWidgets, PySide6.QtSvg, twisted.internet, OpenSSL, certifi;"
             "from syncplay.ui import gui; print('imports ok')") % os.path.join(root, "app")
    subprocess.run([python, "-c", check], check=True, env=env, cwd=root)
    xcb = glob.glob(os.path.join(root, "runtime", "lib", "python3.11", "site-packages", "PySide6", "Qt", "plugins", "platforms", "libqxcb.so"))
    if not xcb:
        sys.exit("Build stopped: the xcb platform plugin is missing.")
    missing = []
    lib = os.path.dirname(os.path.dirname(os.path.dirname(xcb[0]))) + "/lib"
    out = subprocess.run(["ldd", xcb[0]], capture_output=True, text=True, env=dict(os.environ, LD_LIBRARY_PATH=lib)).stdout
    missing = [line.split()[0] for line in out.splitlines() if "not found" in line]
    print("xcb plugin libraries not found on this build machine:", ", ".join(missing) or "none")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", type=int, required=True)
    parser.add_argument("--defaults", help="syncplay-defaults.json to ship inside (update source; never put private keys in a public build)")
    parser.add_argument("--out", default=os.path.join(ROOT, "dist"))
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)  # Later steps run tools from other folders
    cache = os.path.join(args.out, "cache-linux")
    work = os.path.join(args.out, "work-linux")
    os.makedirs(cache, exist_ok=True)
    shutil.rmtree(work, ignore_errors=True)
    root = os.path.join(work, FOLDER)
    os.makedirs(root)

    assembleRuntime(cache, root)
    app = loadMakeExe().buildApp(work, args.build, args.defaults)
    os.replace(app, os.path.join(root, "app"))
    launcher = os.path.join(root, LAUNCHER)
    with open(launcher, "w") as f:
        f.write(LAUNCHER_SCRIPT)
    os.chmod(launcher, 0o755)
    with open(os.path.join(root, "README.txt"), "w") as f:
        f.write(README)
    verify(root)

    archive = os.path.join(args.out, "marquee-linux-x86_64-v{}.tar.xz".format(args.build))
    with tarfile.open(archive, "w:xz", preset=9) as tar:
        tar.add(root, arcname=FOLDER)
    deb = buildDeb(root, args.build, args.out)
    for path in (archive, deb):
        digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
        print("Built {} - {:.1f} MB, build {} (sha256 {})".format(path, os.path.getsize(path) / 1e6, args.build, digest))


if __name__ == "__main__":
    main()
