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


class ShortcutTests(unittest.TestCase):
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


class UninstallTests(unittest.TestCase):
    def setUp(self):
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
        window._offerShortcuts()  # Not packaged here: must return without opening a dialog


if __name__ == "__main__":
    unittest.main()
