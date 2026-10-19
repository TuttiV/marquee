import os
import shutil
import subprocess
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from syncplay import install


def makeRoot():
    base = tempfile.mkdtemp()
    root = os.path.join(base, "Syncplay Marquee")
    os.makedirs(os.path.join(root, "app", "syncplay"))
    os.makedirs(os.path.join(root, "python-abc"))
    with open(os.path.join(root, "app", "syncplay", "x.py"), "w") as f:
        f.write("x")
    return base, root


class LocationTests(unittest.TestCase):
    def test_root_is_found_only_for_the_single_file_layout(self):
        base, root = makeRoot()
        self.addCleanup(shutil.rmtree, base, True)
        self.assertEqual(install.rootFolder(os.path.join(root, "app")), root)
        self.assertIsNone(install.rootFolder(os.path.join(base, "some", "checkout")))
        self.assertIsNone(install.rootFolder(os.path.join(base, "app")))  # Parent isn't called Syncplay Marquee
        self.assertFalse(install.isPackaged(os.path.join(base, "app")))


class WindowsMode(unittest.TestCase):
    """Runs a test as on Windows, whatever system the tests run on."""

    def setUp(self):
        self._linux = install.LINUX
        install.LINUX = False
        self.addCleanup(setattr, install, "LINUX", self._linux)


class ShortcutTests(WindowsMode):
    def test_shortcut_command_carries_values_in_the_environment_not_the_script(self):
        calls = []
        install.createShortcut("desktop", appDir=r"C:\Users\me\AppData\Local\Syncplay Marquee\app", python=r"C:\py\pythonw.exe",
                               runner=lambda command, **kw: calls.append((command, kw)))
        command, kw = calls[0]
        self.assertEqual(command[0], "powershell")
        self.assertNotIn("pythonw", " ".join(command))  # Paths never end up inside the script text
        env = kw["env"]
        self.assertEqual((env["MQ_ACTION"], env["MQ_KIND"], env["MQ_TARGET"]), ("create", "Desktop", r"C:\py\pythonw.exe"))
        self.assertIn("launch-syncplay.pyw", env["MQ_ARGS"])
        self.assertTrue(env["MQ_ARGS"].startswith('"') and env["MQ_ARGS"].endswith('"'))
        self.assertTrue(env["MQ_ICON"].endswith("icon.ico"))
        self.assertTrue(kw["check"])

    def test_start_menu_kind_and_removal_and_failures(self):
        calls = []
        install.createShortcut("startmenu", appDir="/a", python="/p", runner=lambda command, **kw: calls.append(kw["env"]))
        self.assertEqual(calls[0]["MQ_KIND"], "Programs")
        install.removeShortcut("desktop", runner=lambda command, **kw: calls.append(kw["env"]))
        self.assertEqual((calls[1]["MQ_ACTION"], calls[1]["MQ_KIND"]), ("remove", "Desktop"))

        def failing(command, **kw):
            raise subprocess.CalledProcessError(1, command)
        with self.assertRaises(OSError):
            install.createShortcut("desktop", appDir="/a", python="/p", runner=failing)
        install.removeShortcut("desktop", runner=failing)  # Removing quietly does nothing when it can't


class UninstallTests(WindowsMode):
    def setUp(self):
        super().setUp()
        self.base, self.root = makeRoot()
        self.addCleanup(shutil.rmtree, self.base, True)

    def test_script_removes_the_app_folder_settings_and_itself(self):
        script = install.uninstallScript(self.root, ["/cfg/syncplay-secrets.json"], ["HKCU\\Software\\Syncplay"])
        self.assertIn('rmdir /s /q "{}"'.format(self.root), script)
        self.assertIn("syncplay-secrets.json", script)
        self.assertIn('reg delete "HKCU\\Software\\Syncplay" /f', script)
        self.assertIn('del "%~f0"', script)
        self.assertTrue(script.endswith("\r\n"))

    def test_it_refuses_folders_that_are_not_ours(self):
        for bad in (self.base, os.path.join(self.base, "Documents"), os.path.dirname(self.base), "/"):
            with self.assertRaises(ValueError):
                install.uninstallScript(bad)
        os.makedirs(os.path.join(self.base, "Other"))
        with self.assertRaises(ValueError):
            install.uninstallScript(os.path.join(self.base, "Other"))
        with self.assertRaises(ValueError):  # Right name but no app folder inside
            os.makedirs(os.path.join(self.base, "x", "Syncplay Marquee"))
            install.uninstallScript(os.path.join(self.base, "x", "Syncplay Marquee"))

    def test_uninstall_writes_the_script_and_starts_it_and_keeps_settings_unless_asked(self):
        started = []
        cfg = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, cfg, True)
        path = install.uninstall(cfg, deleteSettings=False, root=self.root, launcher=lambda cmd, **kw: started.append(cmd), tempDir=self.base)
        self.assertEqual(started, [["cmd", "/c", path]])
        text = open(path, newline="").read()
        self.assertNotIn("syncplay-secrets.json", text)
        path = install.uninstall(cfg, deleteSettings=True, root=self.root, launcher=lambda cmd, **kw: started.append(cmd), tempDir=self.base)
        text = open(path, newline="").read()
        self.assertIn(os.path.join(cfg, "syncplay-secrets.json"), text)
        self.assertIn("syncplay.ini", text)
        with self.assertRaises(ValueError):
            install.uninstall(cfg, root=None, launcher=lambda *a, **k: None)  # Not the single-file app

    @unittest.skipUnless(shutil.which("wine"), "Wine not available")
    def test_the_script_really_deletes_the_folder_under_wine(self):
        wineprefix = os.environ.get("WINEPREFIX")
        if not wineprefix or not os.path.isdir(wineprefix):
            self.skipTest("no prepared Wine prefix")
        script = install.uninstallScript(self.root)
        # Wine sees Linux paths as Z:\..., so translate the folder for the script only
        windowsRoot = "Z:" + self.root.replace("/", "\\")
        script = script.replace(self.root, windowsRoot)
        bat = os.path.join(self.base, "u.bat")
        with open(bat, "w", newline="") as f:
            f.write(script.replace('del "%~f0"', "rem"))
        env = dict(os.environ, WINEDEBUG="-all")
        subprocess.run(["wine", "cmd", "/c", "Z:" + bat.replace("/", "\\")], env=env, timeout=120, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 20
        while os.path.exists(self.root) and time.time() < deadline:
            time.sleep(0.3)
        self.assertFalse(os.path.exists(self.root))


try:
    from unittest.mock import MagicMock
    from syncplay.vendor.Qt import QtWidgets
    from syncplay.ui.gui import MainWindow
    HAVE_QT = True
except Exception:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "Qt not available")
class MenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_install_items_stay_hidden_outside_the_single_file_app_and_no_offer_is_made(self):
        window = MainWindow()
        self.addCleanup(window.close)
        self.assertEqual(window.shortcutsAction.isVisible(), install.isPackaged())
        self.assertEqual(window.uninstallAction.isVisible(), install.isPackaged())
        client = MagicMock()
        client.getConfig.return_value = {"host": "h", "port": 1, "password": "", "sharedPlaylistEnabled": True, "mediaSearchDirectories": ["/x"],
                                         "readyAtStart": False, "alwaysReady": False, "autoplayInitialState": None, "autoplayMinUsers": -1,
                                         "roomList": [], "chatOutputEnabled": True, "checkForUpdatesAutomatically": False,
                                         "lastCheckedForUpdates": "", "configDir": tempfile.mkdtemp()}
        client.getRoom.return_value = "r"
        window.addClient(client)
        self.assertFalse(hasattr(window, "_offerShortcuts"))  # Replaced by the install window, shown before the start window


if __name__ == "__main__":
    unittest.main()


class WhereToInstallTests(unittest.TestCase):
    def setUp(self):
        self.base, self.root = makeRoot()
        self.addCleanup(shutil.rmtree, self.base, True)

    def test_a_marquee_folder_is_made_inside_the_chosen_folder(self):
        self.assertEqual(install.targetRoot("/opt/apps"), os.path.join("/opt/apps", "Syncplay Marquee"))
        self.assertEqual(install.targetRoot("/opt/apps/Syncplay Marquee"), "/opt/apps/Syncplay Marquee")
        self.assertEqual(install.targetRoot("~/x"), os.path.join(os.path.expanduser("~"), "x", "Syncplay Marquee"))

    def test_folder_checks(self):
        other = os.path.join(self.base, "new", "Syncplay Marquee")
        self.assertIsNone(install.checkTarget(other, self.root))  # New folder: fine
        self.assertIsNone(install.checkTarget(self.root, self.root))  # Same folder: shortcuts only
        self.assertIn("inside", install.checkTarget(os.path.join(self.root, "app", "Syncplay Marquee"), self.root))
        busy = os.path.join(self.base, "busy", "Syncplay Marquee")
        os.makedirs(busy)
        with open(os.path.join(busy, "photo.jpg"), "w") as f:
            f.write("x")
        self.assertIn("other files", install.checkTarget(busy, self.root))
        os.makedirs(os.path.join(busy, "app"))  # An earlier install of ours there: may be installed over
        self.assertIsNone(install.checkTarget(busy, self.root))
        self.assertTrue(install.checkTarget("", self.root))
        if os.geteuid() != 0:
            locked = os.path.join(self.base, "locked")
            os.makedirs(locked)
            os.chmod(locked, 0o555)
            self.addCleanup(os.chmod, locked, 0o755)
            self.assertIn("can't write", install.checkTarget(os.path.join(locked, "Syncplay Marquee"), self.root))

    def test_copy_keeps_links_permissions_and_takes_the_exe_along(self):
        runtime = os.path.join(self.root, "runtime", "bin")
        os.makedirs(runtime)
        with open(os.path.join(runtime, "python3.11"), "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(os.path.join(runtime, "python3.11"), 0o755)
        os.symlink("python3.11", os.path.join(runtime, "python3"))
        exe = os.path.join(self.base, "Downloads", "Syncplay Marquee.exe")
        os.makedirs(os.path.dirname(exe))
        with open(exe, "w") as f:
            f.write("MZ")
        target = os.path.join(self.base, "elsewhere", "Syncplay Marquee")
        seen = []
        count = install.copyInstall(self.root, target, exe, lambda done, total: seen.append((done, total)))
        self.assertEqual(seen[-1], (count, count))
        self.assertTrue(os.path.islink(os.path.join(target, "runtime", "bin", "python3")))
        self.assertTrue(os.access(os.path.join(target, "runtime", "bin", "python3.11"), os.X_OK))
        self.assertTrue(os.path.isfile(os.path.join(target, "app", "syncplay", "x.py")))
        self.assertTrue(os.path.isfile(os.path.join(target, "Syncplay Marquee.exe")))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "app")))  # The original is left alone
        install.copyInstall(self.root, target)  # Installing over an earlier copy works too

    def test_start_command_per_system(self):
        linux = install.LINUX
        self.addCleanup(setattr, install, "LINUX", linux)
        install.LINUX = True
        self.assertEqual(install.startCommand("/x/Syncplay Marquee", ["link"]), ["/x/Syncplay Marquee/Syncplay Marquee", "link"])

    def test_old_folders_are_only_removed_when_they_are_ours(self):
        started = []
        with self.assertRaises(ValueError):
            install.removeFolderLater(self.base, popen=lambda *a, **k: started.append(a))
        if os.name != "nt":
            install.removeFolderLater(self.root, pid=12345, popen=lambda command, **k: started.append(command))
            self.assertEqual(started[-1][-2:], ["12345", self.root])


class LinuxShortcutTests(unittest.TestCase):
    def setUp(self):
        self.base, self.root = makeRoot()
        self.addCleanup(shutil.rmtree, self.base, True)
        self.linux = install.LINUX
        install.LINUX = True
        self.addCleanup(setattr, install, "LINUX", self.linux)
        self.data = os.path.join(self.base, "share")
        self.desktop = os.path.join(self.base, "Desktop")
        os.makedirs(self.desktop)
        self.env = {k: os.environ.get(k) for k in ("XDG_DATA_HOME",)}
        os.environ["XDG_DATA_HOME"] = self.data
        self.addCleanup(self._restore)
        self.calls = []

    def _restore(self):
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def runner(self, command, **kw):
        self.calls.append(command)

        class Done(object):
            pass
        done = Done()
        done.stdout = self.desktop + "\n" if command[:1] == ["xdg-user-dir"] else ""
        return done

    def test_menu_and_desktop_entries_follow_the_two_choices(self):
        install.setShortcuts(self.root, True, False, runner=self.runner)
        menu = os.path.join(self.data, "applications", "syncplay-marquee.desktop")
        desktop = os.path.join(self.desktop, "syncplay-marquee.desktop")
        self.assertTrue(os.path.isfile(menu))
        self.assertFalse(os.path.exists(desktop))
        text = open(menu).read()
        self.assertIn('Exec="{}" %u'.format(os.path.join(self.root, "Syncplay Marquee")), text)
        self.assertIn("Icon=" + os.path.join(self.root, "app", "syncplay", "resources", "syncplay.png"), text)
        self.assertNotIn("NoDisplay", text)
        install.setShortcuts(self.root, False, True, runner=self.runner)  # Only the desktop one now
        self.assertFalse(os.path.exists(menu))
        self.assertTrue(os.path.isfile(desktop))
        self.assertTrue(os.access(desktop, os.X_OK))
        self.assertIn(["gio", "set", desktop, "metadata::trusted", "true"], self.calls)
        self.assertEqual(install.existingShortcuts(runner=self.runner), {"menu": False, "desktop": True})

    def test_paths_with_quotes_dollars_and_percent_are_escaped_in_exec(self):
        self.assertEqual(install._quoteExec('/a "b"/$c/50%'), '"/a \\"b\\"/\\$c/50%%"')

    def test_invite_links_get_a_hidden_handler(self):
        install.registerLinuxLinks(self.root, runner=self.runner)
        links = os.path.join(self.data, "applications", "syncplay-marquee-links.desktop")
        text = open(links).read()
        self.assertIn("NoDisplay=true", text)
        self.assertIn("MimeType=x-scheme-handler/syncplay-marquee;", text)
        self.assertIn(["xdg-mime", "default", "syncplay-marquee-links.desktop", "x-scheme-handler/syncplay-marquee"], self.calls)
        self.assertTrue(install.linuxLinksRegistered(self.root, runner=self.runner))
        self.assertFalse(install.linuxLinksRegistered(os.path.join(self.base, "elsewhere"), runner=self.runner))

    def test_linux_uninstall_removes_entries_settings_and_then_the_folder(self):
        install.setShortcuts(self.root, True, True, runner=self.runner)
        install.registerLinuxLinks(self.root, runner=self.runner)
        cfg = os.path.join(self.base, "cfg")
        os.makedirs(cfg)
        with open(os.path.join(cfg, "syncplay.ini"), "w") as f:
            f.write("x")
        started = []
        install.uninstall(cfg, deleteSettings=True, root=self.root, launcher=lambda command, **k: started.append(command), runner=self.runner)
        for name in ("syncplay-marquee.desktop", "syncplay-marquee-links.desktop"):
            self.assertFalse(os.path.exists(os.path.join(self.data, "applications", name)))
        self.assertFalse(os.path.exists(os.path.join(self.desktop, "syncplay-marquee.desktop")))
        self.assertFalse(os.path.exists(os.path.join(cfg, "syncplay.ini")))
        self.assertEqual(started[-1][-1], self.root)
        with self.assertRaises(ValueError):
            install.uninstall(cfg, root=self.base, launcher=lambda *a, **k: None, runner=self.runner)


class WindowsShortcutTargetTests(WindowsMode):
    def test_shortcuts_open_the_exe_in_the_install_folder_when_there_is_one(self):
        base, root = makeRoot()
        self.addCleanup(shutil.rmtree, base, True)
        calls = []
        install.setShortcuts(root, True, False, runner=lambda command, **kw: calls.append(kw["env"]))
        self.assertEqual([(c["MQ_ACTION"], c["MQ_KIND"]) for c in calls], [("create", "Programs"), ("remove", "Desktop")])
        self.assertIn("launch-syncplay.pyw", calls[0]["MQ_ARGS"])  # No .exe yet: Python and the launcher
        with open(os.path.join(root, "Syncplay Marquee.exe"), "w") as f:
            f.write("MZ")
        calls.clear()
        install.setShortcuts(root, False, True, runner=lambda command, **kw: calls.append(kw["env"]))
        self.assertEqual([(c["MQ_ACTION"], c["MQ_KIND"]) for c in calls], [("remove", "Programs"), ("create", "Desktop")])
        self.assertEqual(calls[1]["MQ_TARGET"], os.path.join(root, "Syncplay Marquee.exe"))
        self.assertEqual(calls[1]["MQ_ARGS"], "")

    def test_the_chosen_folder_is_kept_in_the_registry(self):
        store = {}

        class Key(object):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class Reg(object):
            HKEY_CURRENT_USER, KEY_WRITE, REG_SZ = "HKCU", 2, 1

            def CreateKeyEx(self, root, path, reserved, access):
                store["path"] = path
                return Key()

            def SetValueEx(self, key, name, reserved, kind, value):
                store[name] = value

            def OpenKey(self, root, path):
                if path != store.get("path"):
                    raise OSError("no key")
                return Key()

            def QueryValueEx(self, key, name):
                return (store[name], 1)
        reg = Reg()
        self.assertIsNone(install.readInstallDir(reg))
        install.writeInstallDir(r"D:\Apps\Syncplay Marquee", reg)
        self.assertEqual(store["path"], r"Software\Syncplay Marquee")
        self.assertTrue(install.readInstallDir(reg).endswith("Syncplay Marquee"))


@unittest.skipUnless(HAVE_QT, "Qt not available")
class InstallDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from syncplay.ui.InstallDialog import InstallDialog
        self.Dialog = InstallDialog
        self.base, self.root = makeRoot()
        self.addCleanup(shutil.rmtree, self.base, True)
        self.copies, self.shortcuts = [], []

    def make(self, **kw):
        dialog = self.Dialog(self.root, copier=lambda *a: self.copies.append(a), shortcutSetter=lambda *a: self.shortcuts.append(a), **kw)
        self.addCleanup(dialog.close)
        return dialog

    def test_defaults_are_menu_on_desktop_off_and_same_folder_only_sets_shortcuts(self):
        dialog = self.make()
        self.assertTrue(dialog.menuCheck.isChecked())
        self.assertFalse(dialog.desktopCheck.isChecked())
        self.assertEqual(dialog.installButton.text(), "Install")
        dialog.desktopCheck.setChecked(True)
        dialog.menuCheck.setChecked(False)
        dialog.install()
        self.assertEqual(dialog.outcome, "here")
        self.assertEqual(self.copies, [])
        self.assertEqual(self.shortcuts, [(self.root, False, True)])

    def test_a_new_folder_copies_the_install_there(self):
        dialog = self.make(suggested=os.path.join(self.base, "Apps"))
        self.assertEqual(dialog.target(), os.path.join(self.base, "Apps", "Syncplay Marquee"))
        if os.name == "nt":
            self.skipTest("writes the registry on Windows")
        dialog.install()
        self.assertEqual(dialog.outcome, "moved")
        self.assertEqual(dialog.chosenRoot, os.path.join(self.base, "Apps", "Syncplay Marquee"))
        self.assertEqual(self.copies[0][:2], (self.root, dialog.chosenRoot))
        self.assertEqual(self.shortcuts, [(dialog.chosenRoot, True, False)])

    def test_bad_folders_disable_install_and_failures_are_shown_without_closing(self):
        dialog = self.make()
        busy = os.path.join(self.base, "busy")
        os.makedirs(os.path.join(busy, "Syncplay Marquee"))
        with open(os.path.join(busy, "Syncplay Marquee", "notes.txt"), "w") as f:
            f.write("x")
        dialog.folderEdit.setText(busy)
        self.assertFalse(dialog.installButton.isEnabled())
        self.assertFalse(dialog.problem.isHidden())
        dialog.folderEdit.setText(self.root)
        self.assertTrue(dialog.installButton.isEnabled())

        def failing(*a):
            raise OSError("disk full")
        dialog._setShortcuts = failing
        dialog.install()
        self.assertEqual(dialog.outcome, "skipped")
        self.assertIn("disk full", dialog.problem.text())
        self.assertTrue(dialog.installButton.isEnabled())

    def test_reopened_from_help_it_says_save(self):
        dialog = self.make(firstRun=False)
        self.assertEqual(dialog.installButton.text(), "Save")

    def test_the_player_note_shows_only_when_no_player_was_found(self):
        self.assertTrue(self.make(playerFound=True).playerNote.isHidden())
        self.assertFalse(self.make(playerFound=False).playerNote.isHidden())


@unittest.skipUnless(HAVE_QT, "Qt not available")
class FirstStartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from unittest.mock import patch
        from syncplay.ui.ConfigurationGetter import ConfigurationGetter
        self.base, self.root = makeRoot()
        self.addCleanup(shutil.rmtree, self.base, True)
        self.cfg = os.path.join(self.base, "cfg")
        os.makedirs(self.cfg)
        self.getter = object.__new__(ConfigurationGetter)
        self.getter._config = {"configDir": self.cfg, "playerPath": "/usr/bin/true"}
        self.started, self.removed, self.shown = [], [], []
        test = self

        class FakeDialog(object):
            outcome = "moved"

            def __init__(self, current, exePath, playerFound, suggested=None):
                test.shown.append((current, suggested))
                self.chosenRoot = os.path.join(test.base, "new", "Syncplay Marquee")

            def exec_(self):
                return 1
        self.FakeDialog = FakeDialog
        for target, value in (("syncplay.install.isPackaged", lambda *a: True), ("syncplay.install.rootFolder", lambda *a: self.root),
                              ("syncplay.install.startInstalled", lambda root, args: self.started.append((root, list(args)))),
                              ("syncplay.install.removeFolderLater", lambda folder, **k: self.removed.append(folder)),
                              ("syncplay.ui.InstallDialog.InstallDialog", FakeDialog),
                              ("syncplay.vendor.Qt.QtWidgets.QMessageBox.information", lambda *a, **k: None)):
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)

    def test_shown_once_and_a_moved_install_starts_the_new_copy(self):
        self.assertTrue(self.getter._offerInstall())
        self.assertEqual(len(self.shown), 1)
        self.assertEqual(self.started[0][0], os.path.join(self.base, "new", "Syncplay Marquee"))
        if os.name == "nt":
            self.assertEqual(self.removed, [self.root])
        else:
            self.assertEqual(self.removed, [])  # On Linux the downloaded folder is the person's to delete
        self.assertFalse(self.getter._offerInstall())  # Asked once, never again
        self.assertEqual(len(self.shown), 1)

    def test_not_now_or_same_folder_carries_on_starting(self):
        self.FakeDialog.outcome = "skipped"
        self.addCleanup(setattr, self.FakeDialog, "outcome", "moved")
        self.assertFalse(self.getter._offerInstall())
        self.assertEqual(self.started, [])

    def test_people_who_were_asked_about_shortcuts_before_are_not_asked_again(self):
        from syncplay import secrets
        secrets.save(install.FLAG, "yes", self.cfg)
        self.assertFalse(self.getter._offerInstall())
        self.assertEqual(self.shown, [])

    def test_linux_suggests_the_usual_place_instead_of_the_download_folder(self):
        linux = install.LINUX
        self.addCleanup(setattr, install, "LINUX", linux)
        install.LINUX = True
        self.getter._offerInstall()
        self.assertEqual(self.shown[0], (self.root, install.targetRoot(install.defaultParent())))


@unittest.skipUnless(HAVE_QT, "Qt not available")
class WindowsInstallDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from unittest.mock import patch
        from syncplay.ui import InstallDialog as module
        self.module = module
        self.base, self.root = makeRoot()
        self.addCleanup(shutil.rmtree, self.base, True)
        linux = install.LINUX
        install.LINUX = False
        self.addCleanup(setattr, install, "LINUX", linux)
        self.patch = patch
        self.shortcuts = []

    def make(self, exePath):
        with self.patch.object(self.module.os, "name", "nt"):
            dialog = self.module.InstallDialog(self.root, exePath, True, copier=lambda *a: None,
                                               shortcutSetter=lambda *a: self.shortcuts.append(a))
        self.addCleanup(dialog.close)
        return dialog

    def test_an_older_exe_cannot_move_the_install(self):
        dialog = self.make(None)
        self.assertFalse(dialog.canMove)
        self.assertFalse(dialog.folderEdit.isEnabled())
        self.assertFalse(dialog.browseButton.isEnabled())
        self.assertIn("newest", dialog.folderHint.text())

    def test_installing_in_place_keeps_a_copy_of_the_exe_for_the_shortcuts(self):
        exe = os.path.join(self.base, "Downloads", "Syncplay Marquee.exe")
        os.makedirs(os.path.dirname(exe))
        with open(exe, "w") as f:
            f.write("MZ")
        dialog = self.make(exe)
        self.assertTrue(dialog.canMove)
        with self.patch.object(self.module.os, "name", "nt"):
            dialog.install()
        self.assertEqual(dialog.outcome, "here")
        self.assertTrue(os.path.isfile(os.path.join(self.root, "Syncplay Marquee.exe")))
        self.assertEqual(self.shortcuts, [(self.root, True, False)])
