import os
import shutil
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_subtitle_sharing import FakeUI


class FakeUserlist(object):
    class currentUser:
        username = "Me"
        file = {"name": "Show.mkv", "size": 10, "duration": 3000.0}

    def __init__(self):
        self._users = {"Ann": object(), "Bo": object()}

    def isUserInYourRoom(self, name):
        return name in self._users


class ClientTests(unittest.TestCase):
    def setUp(self):
        from syncplay.client import SyncplayClient
        self.client = object.__new__(SyncplayClient)
        self.client.ui = FakeUI()
        self.client.userlist = FakeUserlist()
        self.client._config = {"configDir": tempfile.mkdtemp()}
        self.addCleanup(shutil.rmtree, self.client._config["configDir"], True)
        self.client._player = object()
        self.client.serverFeatures = {"chat": True}
        self.client._lastGlobalUpdate = time.time()
        self.client._globalPosition = 10.0
        self.client._globalPaused = False
        self.client._running = True
        self.chat = []
        self.client.sendChat = self.chat.append
        self.client.getPlayerPosition = lambda: 105.0
        self.client.getGlobalPaused = lambda: False
        self.client.getGlobalPosition = lambda: 100.0
        self.offers = []
        self.client.ui.offerResume = self.offers.append

    def test_sync_status_reports_the_last_drift_only_while_it_is_fresh(self):
        self.assertIsNone(self.client.syncStatus()["offset"])
        self.client._lastSyncDiff, self.client._lastSyncAt = 1.4, time.time()
        self.assertEqual(self.client.syncStatus()["offset"], 1.4)
        self.client._lastSyncAt = time.time() - 30
        self.assertIsNone(self.client.syncStatus()["offset"])

    def test_sync_check_asks_the_room_and_answers_other_peoples_requests(self):
        from syncplay import synccheck
        self.client._lastSyncDiff, self.client._lastSyncAt = -2.0, time.time()
        self.client.startSyncCheck()
        self.assertEqual(len(self.chat), 1)
        self.assertTrue(synccheck.parseRequest(self.chat[0]))
        self.assertTrue(self.client.handleSyncCheckChat("Ann", synccheck.requestText("wxyz")))
        self.assertFalse(self.client.handleSyncCheckChat("Ann", "good evening"))
        self.assertFalse(self.client.handleSyncCheckChat("Ann", "[syncing soon] ok"))

    def test_sync_check_needs_chat(self):
        self.client.serverFeatures = {}
        self.client.startSyncCheck()
        self.assertEqual(self.chat, [])
        self.assertEqual(len(self.client.ui.errors), 1)

    def test_resume_is_offered_only_near_the_start_of_a_remembered_video(self):
        file_ = dict(FakeUserlist.currentUser.file)
        self.client._resumeStoreObject = lambda: type("S", (), {"get": staticmethod(lambda f: 1800.0)})()
        self.client.getGlobalPosition = lambda: 3.0
        self.client._offerResume(file_)
        self.assertEqual(self.offers, [1800.0])
        self.client.getGlobalPosition = lambda: 900.0  # The room is already well into it: don't interrupt
        self.client._offerResume(file_)
        self.assertEqual(self.offers, [1800.0])

    def test_positions_are_saved_and_finished_videos_forgotten(self):
        from syncplay import resume
        self.client.getGlobalPosition = lambda: 1200.0
        self.client._saveResume()
        self.assertEqual(resume.ResumeStore(self.client._config["configDir"]).get(FakeUserlist.currentUser.file), 1200.0)
        self.client.getGlobalPosition = lambda: 2990.0
        self.client._saveResume()
        self.assertIsNone(resume.ResumeStore(self.client._config["configDir"]).get(FakeUserlist.currentUser.file))

    def test_start_window_setting_and_reopen(self):
        from syncplay import updater
        from syncplay.ui import ConfigurationGetter as module
        saved, launched, stopped = [], [], []
        original = module.ConfigurationGetter.setConfigOption
        module.ConfigurationGetter.setConfigOption = lambda self, option, value: saved.append((option, value))
        self.addCleanup(setattr, module.ConfigurationGetter, "setConfigOption", original)
        originalRelaunch = updater.relaunch
        updater.relaunch = lambda *a, **k: launched.append((a, k))
        self.addCleanup(setattr, updater, "relaunch", originalRelaunch)
        self.client.stop = lambda *a, **k: stopped.append(1)
        self.assertFalse(self.client.skipStartWindowEnabled())
        self.client.setSkipStartWindow(True)
        self.assertTrue(self.client.skipStartWindowEnabled())
        self.assertEqual(saved, [("skipStartWindow", True)])
        self.client._config["skipStartWindow"] = "True"
        self.assertTrue(self.client.skipStartWindowEnabled())
        self.client.reopenWithStartWindow()
        self.assertEqual(len(launched), 1)
        self.assertIs(launched[0][1]["skipStartWindow"], False)
        self.assertEqual(stopped, [1])
        import sys
        self.assertEqual(launched[0][0][2].count("--force-gui-prompt"), 1)


if __name__ == "__main__":
    unittest.main()
