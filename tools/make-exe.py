#!/usr/bin/env python3
"""Builds the single-file Windows installer-launcher, "Syncplay Marquee.exe": no Python needed on the user's PC.

    python tools/make-exe.py --build 1 [--defaults path/to/syncplay-defaults.json]

It bundles the official Windows embeddable Python + every library (downloaded here for win_amd64) + the app into one
.exe. On first run the exe unpacks itself under %LOCALAPPDATA%\\Syncplay Marquee and starts the app; the in-app Update
button then keeps the app files current (tools/make-release.py builds those updates).

Needs: python3 with pip, git, and mingw-w64 (apt install gcc-mingw-w64-x86-64). Downloads are cached in dist/cache."""
import argparse
import glob
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_VERSION = "3.11.9"
EMBED_URL = "https://www.python.org/ftp/python/{0}/python-{0}-embed-amd64.zip".format(PYTHON_VERSION)
REQUIREMENTS = ["twisted[tls]", "pem", "certifi", "PySide6-Essentials", "pywin32"]
NEVER = {"syncplay-defaults.json", "syncplay-secrets.json", "syncplay.log", "marquee.log"}

# Parts of the Qt wheel the app never uses (QML/Quick, designer, tools, software OpenGL, networking, printing, SQL, docs, stubs).
# The app only needs QtCore/Gui/Widgets/Svg, the Windows platform plugin and the image/icon/style plugins.
TRIM_DIRS = ["qml", "translations", "metatypes", "typesystems", "glue", "include", "scripts", "examples", "resources",
             "plugins/sqldrivers", "plugins/tls", "plugins/networkinformation", "plugins/qmltooling", "plugins/qmllint",
             "plugins/designer", "plugins/generic", "plugins/platforminputcontexts", "plugins/vectorimageformats"]
TRIM_GLOBS = ["Qt6Quick*.dll", "Qt6Qml*.dll", "Qt6Designer*.dll", "Qt6Help.dll", "Qt6Lottie*.dll", "Qt6Labs*.dll", "Qt6Pdf*.dll",
              "Qt6UiTools.dll", "Qt63D*.dll", "Qt6ShaderTools.dll", "Qt6Test.dll", "Qt6SpatialAudio.dll", "opengl32sw.dll",
              "d3dcompiler_*.dll", "Qt6OpenGL*.dll", "Qt6Network.dll", "Qt6PrintSupport.dll", "Qt6DBus.dll", "Qt6Concurrent.dll",
              "Qt6Sql.dll", "Qt6Xml.dll", "Qt6Svg*Widgets*.dll",
              "*.exe", "*.pyi", "Qt*Quick*.pyd", "Qt*Qml*.pyd", "QtDesigner.pyd", "QtHelp.pyd", "QtUiTools.pyd", "QtTest.pyd",
              "Qt3D*.pyd", "QtPdf*.pyd", "QtOpenGL*.pyd", "QtNetwork.pyd", "QtPrintSupport.pyd", "QtDBus.pyd", "QtConcurrent.pyd",
              "QtSql.pyd", "QtXml.pyd", "QtSvgWidgets.pyd", "plugins/platforms/qminimal.dll", "plugins/platforms/qdirect2d.dll",
              "plugins/platforms/qoffscreen.dll"]
# pywin32 is large; the app needs win32event (its Qt event loop on Windows) and, for the MPC-HC player, api/gui/con/process
PYWIN32_KEEP_PYD = {"_win32sysloader.pyd", "win32api.pyd", "win32event.pyd", "win32gui.pyd", "win32process.pyd", "win32file.pyd",
                    "win32pipe.pyd", "win32clipboard.pyd"}
PYWIN32_KEEP_LIB = {"pywintypes.py", "win32con.py", "winerror.py"}
PYWIN32_DROP = ["win32/pythonservice.exe", "win32/perfmondata.dll", "win32/winxpgui.py", "win32/License.txt", "pythonwin", "win32com", "win32comext", "adodbapi", "isapi", "PyWin32.chm", "pywin32.pth", "pythoncom.py",
                "win32/scripts", "win32/test", "win32/Demos", "win32/include", "win32/libs"]
# Test suites and docs inside the bundled libraries, and Python's own optional extras
TRIM_ANYWHERE = ["test", "tests", "testing", "__pycache__"]
_UNUSED_TRIM_PYTHON = ["sqlite3.dll", "_sqlite3.pyd", "_tkinter.pyd", "tcl86t.dll", "tk86t.dll", "_msi.pyd", "_lzma.pyd", "_bz2.pyd",
               "_decimal.pyd", "_multiprocessing.pyd", "_overlapped.pyd", "_zoneinfo.pyd", "_uuid.pyd", "_elementtree.pyd",
               "pyexpat.pyd", "_asyncio.pyd", "unicodedata.pyd", "winsound.pyd", "select.pyd"]


def download(url, path):
    if not os.path.isfile(path):
        print("Downloading", url)
        with urllib.request.urlopen(url) as response, open(path, "wb") as out:
            shutil.copyfileobj(response, out)
    return path


def fetchWheels(cache):
    wheels = os.path.join(cache, "wheels")
    os.makedirs(wheels, exist_ok=True)
    if True:
        subprocess.run([sys.executable, "-m", "pip", "download", "--dest", wheels, "--platform", "win_amd64",
                        "--python-version", "3.11", "--implementation", "cp", "--abi", "cp311", "--only-binary=:all:"]
                       + REQUIREMENTS, check=True)
    return sorted(glob.glob(os.path.join(wheels, "*.whl")))


def assembleRuntime(cache, work):
    runtime = os.path.join(work, "python")
    shutil.rmtree(runtime, ignore_errors=True)
    os.makedirs(runtime)
    zipfile.ZipFile(download(EMBED_URL, os.path.join(cache, "python-embed.zip"))).extractall(runtime)
    site = os.path.join(runtime, "Lib", "site-packages")
    os.makedirs(site)
    for wheel in fetchWheels(cache):
        zipfile.ZipFile(wheel).extractall(site)
    for name in PYWIN32_DROP:
        target = os.path.join(site, *name.split("/"))
        shutil.rmtree(target, ignore_errors=True) if os.path.isdir(target) else (os.path.exists(target) and os.remove(target))
    for path in glob.glob(os.path.join(site, "*pywin32*.data")):
        shutil.rmtree(path, ignore_errors=True)
    for path in glob.glob(os.path.join(site, "win32", "*.pyd")):
        if os.path.basename(path) not in PYWIN32_KEEP_PYD:
            os.remove(path)
    for path in glob.glob(os.path.join(site, "win32", "lib", "*")):
        if os.path.basename(path) not in PYWIN32_KEEP_LIB:
            shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)
    system32 = os.path.join(site, "pywin32_system32")
    if os.path.isdir(system32):  # Windows finds pywintypes311.dll next to python.exe (the wheel's .pth bootstrap isn't run here)
        shutil.copyfile(os.path.join(system32, "pywintypes311.dll"), os.path.join(runtime, "pywintypes311.dll"))
        try:
            os.remove(os.path.join(system32, "pythoncom311.dll"))
        except OSError:
            pass
    with open(os.path.join(runtime, "python311._pth"), "w") as f:  # Paths are relative to this file: ../app is the app folder
        f.write("python311.zip\n.\n../app\nLib/site-packages\nLib/site-packages/win32\nLib/site-packages/win32/lib\n")
    qt = os.path.join(site, "PySide6")
    for name in TRIM_DIRS:
        shutil.rmtree(os.path.join(qt, name), ignore_errors=True)
    for pattern in TRIM_GLOBS:
        for path in glob.glob(os.path.join(qt, pattern)):
            os.remove(path)
    for root, dirs, _ in os.walk(site, topdown=True):  # Bundled libraries' own test suites
        for name in list(dirs):
            if name in TRIM_ANYWHERE and "PySide6" not in root:
                shutil.rmtree(os.path.join(root, name), ignore_errors=True)
                dirs.remove(name)
    for path in glob.glob(os.path.join(site, "*.dist-info", "RECORD")):
        os.remove(path)
    return runtime


def zipTree(sourceDir, zipPath, prefix=""):
    with zipfile.ZipFile(zipPath, "w", zipfile.ZIP_LZMA) as z:  # LZMA packs DLLs ~25% tighter than deflate; the stub decodes it
        for root, dirs, files in os.walk(sourceDir):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(root, name)
                z.write(full, os.path.join(prefix, os.path.relpath(full, sourceDir)).replace(os.sep, "/"))


def buildApp(work, build, defaults):
    app = os.path.join(work, "app")
    shutil.rmtree(app, ignore_errors=True)
    tracked = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.split("\n")
    for path in filter(None, tracked):
        top = path.split("/")[0]
        if top == "syncplay" or (("/" not in path) and re.match(r"^(?:syncplay(?:Client|Server)\.py|requirements.*\.txt|LICENSE)$", path)):
            target = os.path.join(app, *path.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, path), target)
    os.makedirs(os.path.join(app, "program"))
    shutil.copyfile(os.path.join(ROOT, "bundle", "program", "launch-syncplay.pyw"), os.path.join(app, "program", "launch-syncplay.pyw"))
    with open(os.path.join(app, "syncplay", "private_build.py"), "w") as f:
        f.write("# Written by tools/make-exe.py\nBUILD = {}\n".format(build))
    if defaults:
        shutil.copyfile(defaults, os.path.join(app, "syncplay-defaults.json"))
    return app


# Import names the app mentions that only matter on other systems (macOS, other Qt bindings) or are never used at runtime
NOT_NEEDED_ON_WINDOWS = {"Cocoa", "Foundation", "PyQt4", "PyQt5", "PySide", "PySide2", "QtSiteConfig", "appnope", "darkdetect",
                         "requests", "setuptools", "shiboken", "shiboken2", "sip"}
# Parts of the standard library the official embeddable Python does not include
NOT_IN_EMBEDDABLE_PYTHON = {"tkinter", "idlelib", "turtle", "turtledemo", "ensurepip", "lib2to3", "distutils", "venv", "test", "pydoc_data"}
REQUIRED_FILES = ["pythonw.exe", "python311.dll", "pywintypes311.dll", "libssl-3.dll", "libcrypto-3.dll",
                  "Lib/site-packages/win32/win32event.pyd", "Lib/site-packages/win32/win32api.pyd",
                  "Lib/site-packages/win32/lib/pywintypes.py", "Lib/site-packages/win32/lib/win32con.py",
                  "Lib/site-packages/PySide6/QtCore.pyd", "Lib/site-packages/PySide6/QtGui.pyd",
                  "Lib/site-packages/PySide6/QtWidgets.pyd", "Lib/site-packages/PySide6/QtSvg.pyd",
                  "Lib/site-packages/PySide6/Qt6Core.dll", "Lib/site-packages/PySide6/plugins/platforms/qwindows.dll",
                  "Lib/site-packages/PySide6/plugins/imageformats/qsvg.dll", "Lib/site-packages/shiboken6/shiboken6.abi3.dll",
                  "Lib/site-packages/twisted/__init__.py", "Lib/site-packages/OpenSSL/__init__.py",
                  "Lib/site-packages/certifi/cacert.pem", "python311._pth"]


def verifyBundle(runtime, app):
    """Fail the build (instead of shipping an exe that silently falls back to text mode) if anything the app needs is missing."""
    import ast
    problems = [name for name in REQUIRED_FILES if not os.path.exists(os.path.join(runtime, *name.split("/")))]
    site = os.path.join(runtime, "Lib", "site-packages")
    installed = set()
    for entry in os.listdir(site):
        installed.add(entry.split(".")[0])
    stdlib = set(sys.stdlib_module_names)
    zipped = set()
    with zipfile.ZipFile(os.path.join(runtime, "python311.zip")) as z:
        zipped = {n.split("/")[0].split(".")[0] for n in z.namelist()}
    dlls = {f.split(".")[0].lstrip("_") for f in os.listdir(runtime) if f.endswith(".pyd")} | {f.split(".")[0] for f in os.listdir(runtime) if f.endswith(".pyd")}
    site_win32 = {f.split(".")[0] for f in os.listdir(os.path.join(site, "win32")) if f.endswith((".pyd", ".py"))}
    site_win32 |= {f.split(".")[0] for f in os.listdir(os.path.join(site, "win32", "lib"))}
    unresolved = {}
    for root, _, files in os.walk(os.path.join(app, "syncplay")):
        for name in files:
            if not name.endswith(".py") or name.startswith("messages_"):
                continue
            path = os.path.join(root, name)
            for node in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split(".")[0]]
                else:
                    continue
                for n in names:
                    if n in ("syncplay", "__future__") or n in NOT_NEEDED_ON_WINDOWS:
                        continue
                    if n in stdlib:  # Python's own modules ship in the embeddable package, except these few
                        if n in NOT_IN_EMBEDDABLE_PYTHON:
                            unresolved.setdefault(n, os.path.relpath(path, app))
                        continue
                    if n in installed or n in site_win32 or n in dlls:
                        continue
                    unresolved.setdefault(n, os.path.relpath(path, app))
    if problems or unresolved:
        for name in problems:
            print("MISSING FILE in runtime:", name)
        for name, where in sorted(unresolved.items()):
            print("UNRESOLVED IMPORT:", name, "(used in {})".format(where))
        sys.exit("Build stopped: the bundle would not work on Windows (see above).")
    print("Bundle check passed: all required files present, every app import resolves.")


def compileStub(work):
    sfx = os.path.join(ROOT, "bundle", "sfx")
    resource = os.path.join(work, "stub.res.o")
    stub = os.path.join(work, "stub.exe")
    subprocess.run(["x86_64-w64-mingw32-windres", os.path.join(sfx, "stub.rc"), "-O", "coff", "-o", resource], cwd=sfx, check=True)
    subprocess.run(["x86_64-w64-mingw32-gcc", "-O2", "-Wall", "-mwindows", "-municode", "-static", "-o", stub,
                    os.path.join(sfx, "stub.c"), resource, "-lgdi32", "-luser32", "-ladvapi32"], check=True)
    subprocess.run(["x86_64-w64-mingw32-strip", stub], check=True)
    return stub


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", type=int, required=True)
    parser.add_argument("--defaults", help="syncplay-defaults.json to ship inside (your API key / update repo)")
    parser.add_argument("--out", default=os.path.join(ROOT, "dist"))
    args = parser.parse_args()
    cache = os.path.join(args.out, "cache")
    work = os.path.join(args.out, "work")
    os.makedirs(cache, exist_ok=True)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)

    runtime = assembleRuntime(cache, work)
    runtimeZip = os.path.join(work, "runtime.zip")
    zipTree(runtime, runtimeZip)
    stamp = hashlib.sha256(open(runtimeZip, "rb").read()).hexdigest()[:16]
    app = buildApp(work, args.build, args.defaults)
    verifyBundle(runtime, app)
    appZip = os.path.join(work, "app.zip")
    zipTree(app, appZip)
    stub = compileStub(work)

    exe = os.path.join(args.out, "Syncplay Marquee.exe")
    stubBytes = open(stub, "rb").read()
    runtimeBytes = open(runtimeZip, "rb").read()
    appBytes = open(appZip, "rb").read()
    runtimeOffset = len(stubBytes)
    appOffset = runtimeOffset + len(runtimeBytes)
    trailer = struct.pack("<8sQQQQII16s", b"MARQSFX2", runtimeOffset, len(runtimeBytes), appOffset, len(appBytes),
                          args.build, 0, stamp.encode("ascii"))
    with open(exe, "wb") as f:
        f.write(stubBytes + runtimeBytes + appBytes + trailer)
    print("Built {} - {:.1f} MB (runtime {:.1f} MB, app {:.1f} MB), build {}".format(
        exe, os.path.getsize(exe) / 1e6, len(runtimeBytes) / 1e6, len(appBytes) / 1e6, args.build))


if __name__ == "__main__":
    main()
