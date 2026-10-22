"""The Linux .deb package (tools/make-linux.py) and how the app behaves when it runs from it."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from syncplay import install, invite

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def loadMakeLinux():
    spec = importlib.util.spec_from_file_location("make_linux", os.path.join(ROOT, "tools", "make-linux.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageMode(unittest.TestCase):
    """A fake package (/opt/syncplay-marquee with its runtime) and this person's copy of the app files, as the package's
    start script leaves them: ~/.local/share/syncplay-marquee/app."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, True)
        self.package = os.path.join(self.base, "opt", "syncplay-marquee")
        os.makedirs(os.path.join(self.package, "runtime"))
        self.data = os.path.join(self.base, "share")
        self.root = os.path.join(self.data, "syncplay-marquee")
        self.app = os.path.join(self.root, "app")
        os.makedirs(os.path.join(self.app, "program"))
        self.desktop = os.path.join(self.base, "Desktop")
        os.makedirs(self.desktop)
        linux = install.LINUX
        install.LINUX = True
        self.addCleanup(setattr, install, "LINUX", linux)
        for key, value in (("XDG_DATA_HOME", self.data), (install.PACKAGE_ENV, self.package), ("HOME", self.base)):
            patcher = mock.patch.dict(os.environ, {key: value})
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(install, "appFolder", lambda: self.app)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = []

    def runner(self, command, **kw):
        self.calls.append(command)

        class Done(object):
            stdout = self.desktop + "\n" if command[:1] == ["xdg-user-dir"] else ""
        return Done()


class RecognisingThePackageTests(PackageMode):
    def test_the_persons_copy_is_the_installed_app(self):
        self.assertEqual(install.packageFolder(), self.package)
        self.assertEqual(install.rootFolder(), self.root)
        self.assertTrue(install.isPackaged())
        self.assertTrue(install.installedByPackage())

    def test_only_with_the_start_scripts_marker_and_only_for_its_own_copy(self):
        with mock.patch.dict(os.environ, {install.PACKAGE_ENV: ""}):
            self.assertIsNone(install.rootFolder())
            self.assertFalse(install.installedByPackage())
        with mock.patch.dict(os.environ, {install.PACKAGE_ENV: os.path.join(self.base, "missing")}):
            self.assertIsNone(install.packageFolder())
        elsewhere = os.path.join(self.base, "elsewhere", "syncplay-marquee", "app")
        self.assertIsNone(install.rootFolder(elsewhere))

    def test_never_on_windows(self):
        install.LINUX = False
        self.assertIsNone(install.packageFolder())


class PackageShortcutTests(PackageMode):
    def test_the_menu_entry_is_the_packages_and_the_desktop_one_starts_the_package(self):
        install.setShortcuts(self.root, True, True, runner=self.runner)
        self.assertFalse(os.path.exists(os.path.join(self.data, "applications", "syncplay-marquee.desktop")))  # Would hide the package's
        text = read(os.path.join(self.desktop, "syncplay-marquee.desktop"))
        self.assertIn('Exec="/usr/bin/syncplay-marquee" %u', text)
        self.assertIn("Icon=syncplay-marquee\n", text)
        self.assertEqual(install.existingShortcuts(runner=self.runner), {"menu": True, "desktop": True})

    def test_uninstall_tidies_this_persons_part(self):
        install.setShortcuts(self.root, True, True, runner=self.runner)
        cfg = os.path.join(self.base, "cfg")
        os.makedirs(cfg)
        with open(os.path.join(cfg, "syncplay.ini"), "w") as f:
            f.write("x")
        started = []
        install.uninstall(cfg, deleteSettings=True, launcher=lambda command, **k: started.append(command), runner=self.runner)
        self.assertFalse(os.path.exists(os.path.join(self.desktop, "syncplay-marquee.desktop")))
        self.assertFalse(os.path.exists(os.path.join(cfg, "syncplay.ini")))
        self.assertEqual(started[-1][-1], self.root)  # The copy of the app files, once the app has closed

    def test_only_its_own_copy_is_ever_deleted(self):
        stranger = os.path.join(self.base, "elsewhere", "syncplay-marquee")
        os.makedirs(os.path.join(stranger, "app"))
        with self.assertRaises(ValueError):
            install.removeFolderLater(stranger, popen=lambda *a, **k: None)

    def test_removing_the_package_asks_the_system(self):
        started = []
        install.removePackage(popen=lambda command, **k: started.append(command))
        self.assertEqual(started, [["pkexec", "apt-get", "remove", "-y", "syncplay-marquee"]])


class AdoptingAnOlderDownloadTests(PackageMode):
    """Someone who used the .tar.xz version installs the package."""

    def oldInstall(self, parent):
        old = os.path.join(parent, "Syncplay Marquee")
        os.makedirs(os.path.join(old, "runtime"))
        os.makedirs(os.path.join(old, "app", "program"))
        for path in (os.path.join(old, "app", "program", "launch-syncplay.pyw"), os.path.join(old, "Syncplay Marquee")):
            open(path, "w").close()
        with mock.patch.dict(os.environ, {install.PACKAGE_ENV: ""}):  # Written by the old version
            for kind in ("menu", "links", "desktop"):
                install.writeLinuxEntry(kind, old, runner=self.runner)
        return old

    def test_old_entries_go_the_desktop_icon_moves_over_and_the_old_folder_is_removed(self):
        old = self.oldInstall(os.path.join(self.base, "My apps $50%"))
        removed = []
        result = install.adoptPackage(runner=self.runner, popen=lambda command, **k: removed.append(command[-1]))
        applications = os.path.join(self.data, "applications")
        self.assertEqual(os.listdir(applications), [])
        text = read(os.path.join(self.desktop, "syncplay-marquee.desktop"))
        self.assertIn('Exec="/usr/bin/syncplay-marquee" %u', text)
        self.assertEqual(result, [old])
        self.assertEqual(removed, [old])
        self.assertIn(["xdg-mime", "default", "syncplay-marquee.desktop", "x-scheme-handler/" + invite.SCHEME], self.calls)

    def test_the_usual_folder_goes_even_without_shortcuts(self):
        old = os.path.join(self.base, ".local", "share", "Syncplay Marquee")  # Where the old install window put it
        os.makedirs(os.path.join(old, "runtime"))
        os.makedirs(os.path.join(old, "app", "program"))
        for path in (os.path.join(old, "app", "program", "launch-syncplay.pyw"), os.path.join(old, "Syncplay Marquee")):
            open(path, "w").close()
        removed = []
        self.assertEqual(install.adoptPackage(runner=self.runner, popen=lambda command, **k: removed.append(command[-1])), [old])

    def test_nothing_to_do_and_nothing_touched(self):
        install.setShortcuts(self.root, True, True, runner=self.runner)
        before = read(os.path.join(self.desktop, "syncplay-marquee.desktop"))
        self.calls[:] = []
        self.assertEqual(install.adoptPackage(runner=self.runner, popen=lambda *a, **k: self.fail("removed something")), [])
        self.assertEqual(read(os.path.join(self.desktop, "syncplay-marquee.desktop")), before)
        self.assertNotIn("xdg-mime", [c[0] for c in self.calls])

    def test_a_folder_that_only_looks_similar_is_left_alone(self):
        lookalike = os.path.join(self.base, "Projects", "Syncplay Marquee")
        os.makedirs(lookalike)
        entry = os.path.join(self.data, "applications", "syncplay-marquee.desktop")
        os.makedirs(os.path.dirname(entry))
        with open(entry, "w") as f:
            f.write('[Desktop Entry]\nExec="{}" %u\n'.format(os.path.join(lookalike, "Syncplay Marquee")))
        self.assertEqual(install.adoptPackage(runner=self.runner, popen=lambda *a, **k: self.fail("removed something")), [])
        self.assertTrue(os.path.isdir(lookalike))
        self.assertFalse(os.path.exists(entry))  # Its stale menu entry still goes: it would hide the package's

    def test_exec_lines_read_back_exactly(self):
        for path in ('/a "b"/$c/50%/Syncplay Marquee', "/plain/Syncplay Marquee", "/back\\slash/Syncplay Marquee"):
            line = "Exec={} %u".format(install._quoteExec(path))
            self.assertEqual(install._unquoteExec(line), path)
        self.assertIsNone(install._unquoteExec("Exec=syncplay-marquee %u"))


try:
    from syncplay.vendor.Qt import QtWidgets
    HAVE_QT = True
except Exception:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "Qt not available")
class PackageWindowTests(PackageMode):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_install_window_shows_where_the_package_is_and_keeps_its_menu_entry(self):
        from syncplay.ui.InstallDialog import InstallDialog
        from syncplay.messages import getMessage
        saved, errors = [], []
        with mock.patch.object(install, "existingShortcuts", lambda *a, **k: {"menu": True, "desktop": False}), \
                mock.patch.object(sys, "excepthook", lambda *e: errors.append(e[1])):  # Where Qt reports errors in its handlers
            dialog = InstallDialog(self.root, None, True, firstRun=False, shortcutSetter=lambda *a: saved.append(a))
        self.addCleanup(dialog.close)
        self.assertEqual(errors, [])
        self.assertEqual(dialog.folderEdit.text(), self.package)
        self.assertFalse(dialog.folderEdit.isEnabled())
        self.assertEqual(dialog.folderHint.text(), getMessage("install-folder-package"))
        self.assertTrue(dialog.menuCheck.isChecked())
        self.assertFalse(dialog.menuCheck.isEnabled())
        self.assertTrue(dialog.desktopCheck.isEnabled())
        self.assertEqual(dialog.target(), self.root)
        self.assertFalse(dialog.moving())
        dialog.desktopCheck.setChecked(True)
        dialog.install()
        self.assertEqual(saved, [(self.root, True, True)])
        self.assertEqual(dialog.outcome, "here")

    def test_uninstall_removes_the_package_and_says_why_not_when_it_cant(self):
        from syncplay.ui import gui

        class Process(object):
            def __init__(self, code):
                self.code, self.returncode, self.polls = code, None, 0

            def poll(self):  # Still running for a moment, as while the password window is up
                self.polls += 1
                if self.polls > 2:
                    self.returncode = self.code
                return self.returncode

        def missing():
            raise OSError("pkexec not found")
        warnings = []
        widget = QtWidgets.QWidget()
        self.addCleanup(widget.close)
        with mock.patch.object(QtWidgets.QMessageBox, "warning", lambda *a: warnings.append(a[2])):
            for code, removed in ((0, True), (126, False), (127, False), (100, False)):  # 127: not allowed; 100: apt failed
                with mock.patch.object(install, "removePackage", lambda code=code: Process(code)):
                    self.assertEqual(gui.MainWindow._removePackage(widget), removed)
            with mock.patch.object(install, "removePackage", missing):
                self.assertFalse(gui.MainWindow._removePackage(widget))
        self.assertEqual(len(warnings), 3)  # Closing the password window (126) says enough on its own
        self.assertTrue(all("sudo apt remove syncplay-marquee" in text for text in warnings))

    def test_first_start_retires_old_leftovers_instead_of_asking_where_to_install(self):
        from syncplay.ui.ConfigurationGetter import ConfigurationGetter
        getter = object.__new__(ConfigurationGetter)
        getter._config = {"configDir": self.base, "playerPath": "/usr/bin/true"}
        adopted, shown = [], []
        with mock.patch.object(install, "adoptPackage", lambda *a, **k: adopted.append(True)), \
                mock.patch("syncplay.ui.InstallDialog.InstallDialog", lambda *a, **k: shown.append(a)):
            self.assertFalse(getter._offerInstall())
        self.assertEqual((adopted, shown), ([True], []))
        self.assertEqual(getter._desktopFileName(), "syncplay-marquee")
        self.assertEqual(getter._windowClassArguments(), ["-name", "syncplay-marquee"])


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = loadMakeLinux()

    def test_names_match_the_app(self):
        m = self.module
        self.assertEqual(m.PACKAGE, install.PACKAGE_NAME)
        self.assertEqual(m.PACKAGE, install.PACKAGE_DATA)
        self.assertEqual(os.path.join(m.PACKAGE_DIR, m.PACKAGE).replace(m.PACKAGE_DIR, "/usr/bin"), install.PACKAGE_COMMAND)
        self.assertIn("MimeType=x-scheme-handler/{};".format(invite.SCHEME), m.DESKTOP_ENTRY)
        self.assertIn("Icon={}\n".format(install.DESKTOP_ID), m.DESKTOP_ENTRY)
        self.assertIn("StartupWMClass={}\n".format(install.DESKTOP_ID), m.DESKTOP_ENTRY)
        self.assertIn('export PYTHONNOUSERSITE=1 {}="$base"'.format(install.PACKAGE_ENV), m.PACKAGE_LAUNCHER)

    def test_dependencies_use_the_names_every_supported_release_knows(self):
        found = {"libglib-2.0.so.0": "libglib2.0-0t64:amd64: /usr/lib/x86_64-linux-gnu/libglib-2.0.so.0",
                 "libEGL.so.1": "libegl1:amd64: /usr/lib/x86_64-linux-gnu/libEGL.so.1",
                 "libc.so.6": "libc6:amd64: /usr/lib/x86_64-linux-gnu/libc.so.6",
                 "libmystery.so.3": ""}

        def run(command, **kw):
            class Done(object):
                stdout = found[command[-1][2:]]
            return Done()
        with mock.patch.object(self.module, "systemLibraries", lambda root: (sorted(found), (2, 34))), \
                mock.patch.object(self.module.subprocess, "run", run):
            depends = self.module.debianDepends("/x")
        self.assertEqual(depends, "libc6 (>= 2.34), libegl1, libglib2.0-0, mpv | vlc")


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("sh"), "needs a Linux shell")
class StartScriptTests(unittest.TestCase):
    """The package's start script, run for real against a fake package whose "python" only reports how it was started."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, True)
        self.package = os.path.join(self.base, "opt", "syncplay-marquee")
        python = os.path.join(self.package, "runtime", "bin", "python3")
        os.makedirs(os.path.dirname(python))
        with open(python, "w") as f:
            f.write('#!/bin/sh\necho "$MARQUEE_PACKAGE|$PYTHONNOUSERSITE|$*"\n')
        os.chmod(python, 0o755)
        self.writeApp(os.path.join(self.package, "app"), 32)
        self.script = os.path.join(self.package, "syncplay-marquee")
        with open(self.script, "w") as f:
            f.write(loadMakeLinux().PACKAGE_LAUNCHER)
        os.chmod(self.script, 0o755)
        self.data = os.path.join(self.base, "home", ".local", "share")
        self.copy = os.path.join(self.data, "syncplay-marquee", "app")

    @staticmethod
    def writeApp(app, build):
        os.makedirs(os.path.join(app, "program"), exist_ok=True)
        os.makedirs(os.path.join(app, "syncplay"), exist_ok=True)
        open(os.path.join(app, "program", "launch-syncplay.pyw"), "w").close()
        with open(os.path.join(app, "syncplay", "private_build.py"), "w") as f:
            f.write("# Build number\nBUILD = {}\n".format(build))

    def start(self, *arguments):
        env = dict(os.environ, HOME=os.path.join(self.base, "home"), XDG_DATA_HOME="")
        return subprocess.run([self.script] + list(arguments), env=env, capture_output=True, text=True, check=True).stdout.strip()

    def build(self):
        return read(os.path.join(self.copy, "syncplay", "private_build.py")).split("BUILD = ")[1].strip()

    def test_first_start_makes_this_persons_copy_and_runs_it(self):
        out = self.start("syncplay-marquee://join/x")
        self.assertEqual(out, "{}|1|{} syncplay-marquee://join/x".format(self.package, os.path.join(self.copy, "program", "launch-syncplay.pyw")))
        self.assertEqual(self.build(), "32")

    def test_an_update_installed_in_the_app_is_kept_and_a_newer_package_replaces_an_older_copy(self):
        self.start()
        self.writeApp(self.copy, 33)  # The in-app Update installed build 33
        open(os.path.join(self.copy, "kept"), "w").close()
        self.start()
        self.assertEqual(self.build(), "33")
        self.assertTrue(os.path.exists(os.path.join(self.copy, "kept")))
        self.writeApp(os.path.join(self.package, "app"), 34)  # Then a newer package was installed
        self.start()
        self.assertEqual(self.build(), "34")
        self.assertFalse(os.path.exists(os.path.join(self.copy, "kept")))


if __name__ == "__main__":
    unittest.main()
