import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from twisted.internet import defer

from syncplay import opensubtitles, utils
from syncplay.players.vlc import VlcPlayer
from tests.test_subtitle_sharing import FakePlayer, FakeUI
from tests.test_invite import FakeWinreg


class PlayerPathTests(unittest.TestCase):
    def test_vlc_comes_first_and_the_order_is_stable(self):
        paths = [r"C:\mpv\mpv.exe", r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\mpv\mpv.exe", r"D:\Other\mpc-hc.exe",
                 r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]
        expected = [r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe", r"C:\mpv\mpv.exe", r"D:\Other\mpc-hc.exe"]
        for _ in range(5):
            self.assertEqual(utils.orderPlayerPaths(paths), expected)
        self.assertEqual(utils.orderPlayerPaths([]), [])

    def test_vlc_install_folder_is_read_from_the_registry(self):
        class Reg(FakeWinreg):
            HKEY_LOCAL_MACHINE = "HKLM"

            def OpenKey(self, root, path):
                if (root, path) not in self.values_by_key:
                    raise FileNotFoundError(path)
                return self._Key((root, path))

            def QueryValueEx(self, key, name):
                return (self.values_by_key[key.path], 1)

        reg = Reg()
        reg.values_by_key = {("HKLM", "SOFTWARE\\WOW6432Node\\VideoLAN\\VLC"): r"D:\Apps\VLC", ("HKCU", "SOFTWARE\\VideoLAN\\VLC"): r"E:\Portable\VLC"}
        self.assertEqual(VlcPlayer.registryPaths(reg), [os.path.join(r"D:\Apps\VLC", "vlc.exe"), os.path.join(r"E:\Portable\VLC", "vlc.exe")])
        reg.values_by_key = {}
        self.assertEqual(VlcPlayer.registryPaths(reg), [])
        if os.name != "nt":
            self.assertEqual(VlcPlayer.registryPaths(), [])


def result(fileId, language="en", release="Show.1080p", hashMatch=False):
    return opensubtitles.SubtitleResult(fileId, "f.srt", "Show", release, language, 10, hashMatch, False)


class AutoSubtitleTests(unittest.TestCase):
    def setUp(self):
        from syncplay.client import SyncplayClient
        self.client = object.__new__(SyncplayClient)
        self.client.ui = FakeUI()
        self.client._config = {"autoSubtitles": True, "subtitleLanguages": "sv,en"}
        self.client._running = True
        self.client._player = FakePlayer(True)
        self.client.lastSharedSubtitle = None
        self.saved = []
        self.searches, self.downloads = [], []

        class User(object):
            file = {"name": "Show.S01E01.mkv", "path": None}

        class Userlist(object):
            currentUser = User()
        self.client.userlist = Userlist()
        self.client.searchSubtitles = lambda languages=None: (self.searches.append(languages), defer.succeed(self.found))[1]
        self.client.downloadSubtitle = lambda r, share=True, load=True: (self.downloads.append((r.fileId, share, load)), defer.succeed("x.srt"))[1]
        self.found = [result(1, "sv", hashMatch=True), result(2, "en")]
        from syncplay import client as clientModule
        self.scheduled = []
        original = clientModule.reactor.callLater
        clientModule.reactor.callLater = lambda delay, fn, *a: self.scheduled.append((delay, fn, a))
        self.addCleanup(setattr, clientModule.reactor, "callLater", original)

    def test_opening_a_video_schedules_one_automatic_search_for_it(self):
        self.client._scheduleAutoSubtitles("Show.S01E01.mkv")
        self.client._scheduleAutoSubtitles("Show.S01E01.mkv")  # Same video again: nothing new
        self.assertEqual(len(self.scheduled), 1)
        self.client._scheduleAutoSubtitles("Show.S01E02.mkv")
        self.assertEqual(len(self.scheduled), 2)

    def test_switched_off_or_no_video_schedules_nothing(self):
        self.client._config["autoSubtitles"] = False
        self.client._scheduleAutoSubtitles("a.mkv")
        self.client._config["autoSubtitles"] = "True"  # As read back from the ini file
        self.client._scheduleAutoSubtitles(None)
        self.assertEqual(self.scheduled, [])
        self.client._scheduleAutoSubtitles("a.mkv")
        self.assertEqual(len(self.scheduled), 1)

    def test_the_best_result_loads_for_me_only_and_says_so(self):
        self.client._autoSubtitles("Show.S01E01.mkv")
        self.assertEqual(self.downloads, [(1, False, True)])  # share=False: nothing goes to the room
        self.assertEqual(len(self.client.ui.messages), 1)
        self.assertIn("SV", self.client.ui.messages[0])
        self.assertNotIn("matched by name", self.client.ui.messages[0])

    def test_a_name_only_match_is_labelled_as_a_guess(self):
        self.found = [result(2, "en")]
        self.client._autoSubtitles("Show.S01E01.mkv")
        self.assertIn("matched by name", self.client.ui.messages[0])

    def test_it_stands_down_when_the_video_changed_or_someone_already_shared_subtitles(self):
        self.client._autoSubtitles("Some.Other.mkv")
        self.client._subtitleAppliedFor = "Show.S01E01.mkv"
        self.client._autoSubtitles("Show.S01E01.mkv")
        self.assertEqual((self.searches, self.downloads), ([], []))

    def test_no_results_or_a_failed_search_is_quiet(self):
        self.found = []
        self.client._autoSubtitles("Show.S01E01.mkv")
        self.assertEqual((self.downloads, self.client.ui.messages, self.client.ui.errors), ([], [], []))
        self.client.searchSubtitles = lambda languages=None: defer.fail(opensubtitles.OpenSubtitlesError("nope"))
        self.client._autoSubtitles("Show.S01E01.mkv")
        self.assertEqual((self.client.ui.messages, self.client.ui.errors), ([], []))

    def test_loading_any_subtitle_marks_the_video_as_done(self):
        from syncplay import subtitles
        self.client._subtitleStore = subtitles.SharedSubtitleStore()
        self.addCleanup(self.client._subtitleStore.cleanup)
        self.client.lastSharedSubtitle = ("a.srt", "/tmp/a.srt")
        self.client.loadSharedSubtitle()
        self.assertEqual(self.client._subtitleAppliedFor, "Show.S01E01.mkv")

    def test_language_choice_is_cleaned_and_remembered_once(self):
        calls = []
        from syncplay.ui import ConfigurationGetter as module
        original = module.ConfigurationGetter.setConfigOption
        module.ConfigurationGetter.setConfigOption = lambda self, option, value: calls.append((option, value))
        self.addCleanup(setattr, module.ConfigurationGetter, "setConfigOption", original)
        self.client.saveSubtitleLanguages(" SV, en-US ,, <x>")
        self.assertEqual(self.client._config["subtitleLanguages"], "sv,en-us,x")
        self.client.saveSubtitleLanguages("sv,en-us,x")  # Unchanged: nothing to write
        self.client.saveSubtitleLanguages("")  # Empty: ignored
        self.assertEqual(calls, [("subtitleLanguages", "sv,en-us,x")])

    def test_turning_it_on_mid_video_starts_looking_now(self):
        calls = []
        from syncplay.ui import ConfigurationGetter as module
        original = module.ConfigurationGetter.setConfigOption
        module.ConfigurationGetter.setConfigOption = lambda self, option, value: calls.append((option, value))
        self.addCleanup(setattr, module.ConfigurationGetter, "setConfigOption", original)
        self.client._config["autoSubtitles"] = False
        self.client.setAutoSubtitles(True)
        self.assertEqual(calls, [("autoSubtitles", True)])
        self.assertEqual(len(self.scheduled), 1)
        self.assertLess(self.scheduled[0][0], 1)


try:
    from unittest.mock import MagicMock
    from syncplay.vendor.Qt import QtWidgets
    from syncplay.ui.gui import MainWindow
    HAVE_QT = True
except Exception:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "Qt not available")
class StartupWarningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_no_media_directories_is_not_shouted_at_every_new_user(self):
        window = MainWindow()
        self.addCleanup(window.close)
        client = MagicMock()
        client.getConfig.return_value = {"host": "h", "port": 1, "password": "", "sharedPlaylistEnabled": True, "mediaSearchDirectories": [],
                                         "readyAtStart": False, "alwaysReady": False, "autoplayInitialState": None, "autoplayMinUsers": -1,
                                         "roomList": [], "chatOutputEnabled": True, "checkForUpdatesAutomatically": False, "lastCheckedForUpdates": ""}
        client.getRoom.return_value = "room"
        window.addClient(client)
        client.ui.showErrorMessage.assert_not_called()


if __name__ == "__main__":
    unittest.main()
