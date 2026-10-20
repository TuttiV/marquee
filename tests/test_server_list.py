"""The server box in the start window is a drop-down list of the public servers, and it looks like one."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from syncplay.vendor.Qt import QtCore, QtWidgets
    HAVE_QT = True
except Exception:
    HAVE_QT = False

from syncplay import constants


@unittest.skipUnless(HAVE_QT, "Qt not available")
class ServerListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def open(self, checkForUpdates, liveList=None):
        from syncplay.ui import GuiConfiguration
        from syncplay.ui.ConfigurationGetter import ConfigurationGetter
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        settingsFile = os.path.join(folder, "settings.ini")  # Nothing saved yet, like a fresh install
        patchers = [mock.patch.object(GuiConfiguration, "QSettings", lambda *a: QtCore.QSettings(settingsFile, QtCore.QSettings.IniFormat)),
                    mock.patch.object(GuiConfiguration.utils, "getListOfPublicServers", lambda: liveList)]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        config = ConfigurationGetter()._config
        config.update({"host": "syncplay.pl:8996", "name": "Tutti", "room": "room", "playerPath": "/usr/bin/vlc",
                       "checkForUpdatesAutomatically": checkForUpdates})
        dialog = GuiConfiguration.ConfigDialog(config, [], None, dict(config))
        self.addCleanup(dialog.hide)  # Closing the start window quits the app, by design
        box = dialog.hostCombobox
        return box, [box.itemText(i) for i in range(box.count())]

    def test_without_update_checks_the_built_in_public_servers_are_listed(self):
        box, items = self.open(checkForUpdates=False)
        self.assertEqual(items, [address for _, address in constants.FALLBACK_PUBLIC_SYNCPLAY_SERVERS])
        self.assertEqual(box.currentText(), "syncplay.pl:8996")  # The saved server stays chosen
        self.assertTrue(box.isEditable())  # Any other server can still be typed in

    def test_with_update_checks_the_current_list_from_syncplay_pl_is_used(self):
        live = [["syncplay.pl:8995 (France)", "syncplay.pl:8995"], ["example.org:8999 (Elsewhere)", "example.org:8999"]]
        box, items = self.open(checkForUpdates=True, liveList=live)
        self.assertEqual(items, ["syncplay.pl:8995", "example.org:8999"])

    def test_drop_down_boxes_show_an_arrow(self):
        from syncplay.ui import theme
        theme.applyApplicationTheme(self.app)
        css = self.app.styleSheet()
        self.assertIn("QComboBox::down-arrow { image: url(", css)
        arrow = css.split("QComboBox::down-arrow { image: url(\"", 1)[1].split("\"", 1)[0]
        self.assertTrue(os.path.isfile(arrow), arrow)


if __name__ == "__main__":
    unittest.main()
