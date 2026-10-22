"""The Windows Setup wizard (tools/make-setup.py) and how the app behaves once Setup installed it."""
import importlib.util
import os
import re
import shutil
import tempfile
import unittest
from unittest import mock

from syncplay import install

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def loadMakeSetup():
    spec = importlib.util.spec_from_file_location("make_setup", os.path.join(ROOT, "tools", "make-setup.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setupRoot():
    base = tempfile.mkdtemp()
    root = os.path.join(base, "Syncplay Marquee")
    os.makedirs(os.path.join(root, "app", "program"))
    with open(os.path.join(root, install.SETUP_UNINSTALLER), "wb") as f:
        f.write(b"MZ")
    return base, root


class ScriptTests(unittest.TestCase):
    """The wizard and the app must agree on names, or uninstalling and the app's own checks would miss each other."""

    @classmethod
    def setUpClass(cls):
        cls.module = loadMakeSetup()
        cls.script = cls.module.nsisScript(BUILD=31, STAMP="0123456789abcdef", OUTFILE="/tmp/out.exe", STAGE="/tmp/stage",
                                           SIDE="/tmp/side.bmp", HEADER="/tmp/header.bmp", ICON="/tmp/icon.ico")

    def test_names_match_the_app(self):
        self.assertEqual(self.module.UNINSTALLER, install.SETUP_UNINSTALLER)
        self.assertEqual(self.module.UNINSTALL_KEY, install.SETUP_UNINSTALL_KEY)
        self.assertEqual(self.module.APP_KEY, install.REG_KEY)
        self.assertEqual(self.module.EXE, install.EXE_NAME)
        self.assertEqual(tuple(self.module.SETTINGS_FILES), tuple(install.SETTINGS_FILES))

    def test_a_per_user_64_bit_wizard_with_the_usual_pages(self):
        script = self.script
        self.assertIsNone(re.search(r"@[A-Z_]+@", script))
        self.assertIn("Target amd64-unicode", script)
        self.assertIn("RequestExecutionLevel user", script)  # No administrator rights, so the app can update its own folder
        self.assertIn('InstallDir "$LOCALAPPDATA\\Programs\\${APP}"', script)
        for page in ("MUI_PAGE_WELCOME", "MUI_PAGE_DIRECTORY", "Page custom ShortcutsShow", "MUI_PAGE_INSTFILES", "MUI_PAGE_FINISH"):
            self.assertIn(page, script)
        self.assertLess(script.index("MUI_PAGE_DIRECTORY"), script.index("Page custom ShortcutsShow"))
        self.assertIn('"Add to the Start menu"', script)
        self.assertIn('"Add a shortcut on the desktop"', script)
        self.assertIn("StrCpy $WantMenu ${BST_CHECKED}", script)    # Start menu on by default
        self.assertIn("StrCpy $WantDesktop ${BST_UNCHECKED}", script)  # Desktop off by default

    def test_reinstalling_starts_from_a_fresh_app_folder_and_drops_old_runtimes(self):
        install_section = self.script.split('Section "Install"', 1)[1].split("SectionEnd", 1)[0]
        self.assertLess(install_section.index('RMDir /r "$INSTDIR\\app"'), install_section.index("File /r"))
        self.assertIn('!insertmacro RemoveRuntimes "$INSTDIR" "python-${STAMP}"', install_section)
        self.assertIn("!insertmacro WaitUntilClosed", install_section)

    def test_only_a_real_old_copy_is_tidied_away(self):
        install_section = self.script.split('Section "Install"', 1)[1].split("SectionEnd", 1)[0]
        guard = install_section[install_section.index("$OldRoot != $INSTDIR"):install_section.index('RMDir /r "$OldRoot.old"')]
        self.assertIn('${FileExists} "$OldRoot\\app\\program\\launch-syncplay.pyw"', guard)
        self.assertIn('Rename "$OldRoot" "$OldRoot.old"', guard)  # Fails while the old copy is open: then it is left alone

    def test_uninstalling_removes_only_its_own_files_and_asks_about_settings(self):
        section = self.script.split('Section "Uninstall"', 1)[1].split("SectionEnd", 1)[0]
        self.assertNotIn('RMDir /r "$INSTDIR"\n', section)  # Never the whole folder blindly
        self.assertIn('RMDir "$INSTDIR"', section)          # Only once it is empty
        self.assertIn("/SD IDNO IDNO keepSettings", section)  # Silent uninstalls keep the settings
        for name in install.SETTINGS_FILES:
            self.assertIn('Delete "$APPDATA\\{}"'.format(name), section)


class InstalledBySetupTests(unittest.TestCase):
    def test_recognised_by_its_uninstaller(self):
        base, root = setupRoot()
        self.addCleanup(shutil.rmtree, base, True)
        self.assertTrue(install.installedBySetup(root))
        os.remove(os.path.join(root, install.SETUP_UNINSTALLER))
        self.assertFalse(install.installedBySetup(root))
        self.assertFalse(install.installedBySetup(None))

    def test_help_uninstall_hands_over_to_setups_uninstaller(self):
        base, root = setupRoot()
        self.addCleanup(shutil.rmtree, base, True)
        started = []
        install.runSetupUninstaller(root, popen=lambda args, **k: started.append(args))
        self.assertEqual(started, [[os.path.join(root, install.SETUP_UNINSTALLER)]])

    def test_the_version_in_apps_and_features_follows_in_app_updates(self):
        values = {"DisplayVersion": "Build 31"}

        class Key(object):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class Reg(object):
            HKEY_CURRENT_USER, KEY_READ, KEY_WRITE, REG_SZ = "HKCU", 1, 2, 1

            def OpenKey(self, root, path, reserved=0, access=0):
                assert path == install.SETUP_UNINSTALL_KEY
                return Key()

            def QueryValueEx(self, key, name):
                return values[name], 1

            def SetValueEx(self, key, name, reserved, kind, value):
                values[name] = value
        install.refreshSetupEntry(32, Reg())
        self.assertEqual(values["DisplayVersion"], "Build 32")

    def test_the_apps_own_install_window_stays_away(self):
        from syncplay.ui.ConfigurationGetter import ConfigurationGetter
        from syncplay.ui import ConfigurationGetter as module
        base, root = setupRoot()
        self.addCleanup(shutil.rmtree, base, True)
        getter = object.__new__(ConfigurationGetter)
        getter._config = {"configDir": base, "playerPath": "/usr/bin/true"}
        shown = []
        with mock.patch("syncplay.install.isPackaged", lambda *a: True), \
                mock.patch("syncplay.install.rootFolder", lambda *a: root), \
                mock.patch("syncplay.install.refreshSetupEntry", lambda build, reg=None: None), \
                mock.patch("syncplay.ui.InstallDialog.InstallDialog", lambda *a, **k: shown.append(a)), \
                mock.patch.object(module.os, "name", "nt"):
            self.assertFalse(getter._offerInstall())
        self.assertEqual(shown, [])


try:
    from syncplay.vendor.Qt import QtWidgets
    HAVE_QT = True
except Exception:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "Qt not available")
class InstallDialogUnderSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_the_folder_is_setups_to_move_but_shortcuts_can_still_change(self):
        from syncplay.ui.InstallDialog import InstallDialog
        from syncplay.messages import getMessage
        base, root = setupRoot()
        self.addCleanup(shutil.rmtree, base, True)
        dialog = InstallDialog(root, None, True, firstRun=False, shortcutSetter=lambda *a: None)
        self.addCleanup(dialog.close)
        self.assertFalse(dialog.canMove)
        self.assertFalse(dialog.folderEdit.isEnabled())
        self.assertFalse(dialog.browseButton.isEnabled())
        self.assertEqual(dialog.folderHint.text(), getMessage("install-folder-setup"))
        self.assertTrue(dialog.menuCheck.isEnabled())
        self.assertTrue(dialog.desktopCheck.isEnabled())


if __name__ == "__main__":
    unittest.main()
