import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from syncplay import playlistfile

try:
    from unittest.mock import MagicMock
    from syncplay.vendor.Qt import QtWidgets
    from syncplay.ui.gui import MainWindow
    HAVE_QT = True
except Exception:
    HAVE_QT = False


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_plain_text_keeps_every_non_blank_line(self):
        path = self.write("p.txt", "https://a.example/1.mp4\n\n  \nC:\\videos\\two.mkv\n")
        self.assertEqual(playlistfile.entries(path), ["https://a.example/1.mp4", "C:\\videos\\two.mkv"])

    def test_m3u8_skips_comment_lines(self):
        path = self.write("p.m3u8", "#EXTM3U\n#EXTINF:1,x\nhttps://a.example/1.mp4\n\nhttps://a.example/2.mp4\n")
        self.assertEqual(playlistfile.entries(path), ["https://a.example/1.mp4", "https://a.example/2.mp4"])

    def test_missing_files_are_none_and_empty_files_are_empty(self):
        self.assertIsNone(playlistfile.entries(os.path.join(self.dir, "nope.txt")))
        self.assertEqual(playlistfile.entries(self.write("e.txt", "\n\n")), [])


CONFIG = {"host": "h", "port": 1, "password": "", "sharedPlaylistEnabled": True, "mediaSearchDirectories": ["/x"], "readyAtStart": False,
          "alwaysReady": False, "autoplayInitialState": None, "autoplayMinUsers": -1, "roomList": [], "chatOutputEnabled": True,
          "checkForUpdatesAutomatically": False, "lastCheckedForUpdates": "", "pauseOnLeave": False}


@unittest.skipUnless(HAVE_QT, "Qt not available")
class MenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        self.client = MagicMock()

    def start(self, **extra):
        self.client.getConfig.return_value = dict(CONFIG, configDir=self.dir, **extra)
        self.client.getRoom.return_value = "r"
        self.window.addClient(self.client)
        self.window.showMessage = MagicMock()

    def playlist(self, text="https://a.example/1.mp4\nhttps://a.example/2.mp4\n"):
        path = os.path.join(self.dir, "playlist.txt")
        with open(path, "w") as f:
            f.write(text)
        return path

    def test_file_menu_has_both_items_and_reload_starts_disabled(self):
        self.start()
        self.assertEqual(self.window.openPlaylistAction.text().replace("&", ""), "Open playlist file...")
        self.assertEqual(self.window.reloadPlaylistAction.text().replace("&", ""), "Reload playlist file")
        self.assertFalse(self.window.reloadPlaylistAction.isEnabled())

    def test_reload_says_so_when_there_is_nothing_to_reload(self):
        self.start()
        self.window.reloadPlaylistFile()
        self.assertIn("no playlist file to reload", self.window.showMessage.call_args[0][0])
        self.client.playlist.loadPlaylistFromFile.assert_not_called()

    def test_a_file_given_on_the_command_line_can_be_reloaded(self):
        path = self.playlist()
        self.start(loadPlaylistFromFile=path)
        self.assertTrue(self.window.reloadPlaylistAction.isEnabled())
        self.window.reloadPlaylistFile()
        self.client.playlist.loadPlaylistFromFile.assert_called_once_with(path)
        self.assertIn("2 entries from playlist.txt", self.window.showMessage.call_args[0][0])

    def test_reload_sees_changes_made_by_another_program(self):
        path = self.playlist("https://a.example/1.mp4\n")
        self.start(loadPlaylistFromFile=path)
        self.playlist("https://a.example/1.mp4\nhttps://a.example/2.mp4\nhttps://a.example/3.mp4\n")
        self.window.reloadPlaylistFile()
        self.assertIn("3 entries", self.window.showMessage.call_args[0][0])

    def test_missing_and_empty_files_leave_the_playlist_alone(self):
        path = self.playlist()
        self.start(loadPlaylistFromFile=path)
        self.playlist("\n\n")
        self.window.reloadPlaylistFile()
        self.assertIn("no entries", self.window.showMessage.call_args[0][0])
        os.remove(path)
        self.window.reloadPlaylistFile()
        self.assertIn("Couldn't read", self.window.showMessage.call_args[0][0])
        self.client.playlist.loadPlaylistFromFile.assert_not_called()

    def test_the_last_file_is_remembered_between_runs(self):
        path = self.playlist()
        self.start()
        self.window._rememberPlaylistFile(path)
        self.assertTrue(self.window.reloadPlaylistAction.isEnabled())
        second = MainWindow()
        self.addCleanup(second.close)
        client = MagicMock()
        client.getConfig.return_value = dict(CONFIG, configDir=self.dir)
        client.getRoom.return_value = "r"
        second.addClient(client)
        self.assertTrue(second.reloadPlaylistAction.isEnabled())
        self.assertEqual(second._lastPlaylistFile, path)

    def test_the_dropout_switch_mirrors_and_drives_the_setting(self):
        self.start(pauseOnLeave=True)
        self.assertTrue(self.window.dropoutSwitch.isChecked())
        self.window.dropoutSwitch.setChecked(False)
        self.client.setPauseOnLeave.assert_called_with(False)
        self.window.pauseOnDropoutChanged(True)
        self.assertTrue(self.window.dropoutSwitch.isChecked())


if __name__ == "__main__":
    unittest.main()
