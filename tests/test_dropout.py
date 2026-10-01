import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_subtitle_sharing import FakeUI


class FakeUserlist(object):
    class currentUser:
        username = "Me"

    def __init__(self):
        self.inRoom, self.ready, self.files, self.removed = set(), {}, set(), []

    def isUserInYourRoom(self, name):
        return name in self.inRoom

    def isReadyWithFile(self, name):
        if name not in self.files:
            return None
        return self.ready.get(name)

    def hasFile(self, name):
        return name in self.files

    def removeUser(self, name):
        self.removed.append(name)
        self.inRoom.discard(name)


class DropoutTests(unittest.TestCase):
    def setUp(self):
        from syncplay.client import SyncplayClient
        self.client = object.__new__(SyncplayClient)
        self.client.ui = FakeUI()
        self.client._config = {"pauseOnLeave": True}
        self.client.userlist = FakeUserlist()
        self.client.serverFeatures = {"readiness": True}
        self.client.userlist.inRoom = {"Ann", "Bo"}
        self.client.userlist.files = {"Ann", "Bo"}
        self.client.userlist.ready = {"Ann": True, "Bo": True}
        self.paused = []
        self.client.setPaused = lambda value: self.paused.append(value)
        self.client._lastPlaylistUpdate = None

    def leave(self, name):
        self.client.removeUser(name)

    def come_back(self, name, ready):
        self.client.userlist.inRoom.add(name)
        self.client.userlist.files.add(name)
        self.client.userlist.ready[name] = ready
        self.client.checkDropoutResume()

    def test_someone_leaving_pauses_and_says_who_we_are_waiting_for(self):
        self.leave("Ann")
        self.assertEqual(self.paused, [True])
        self.assertIn("Ann dropped out", self.client.ui.messages[0])
        self.assertEqual(self.client.userlist.removed, ["Ann"])

    def test_playback_resumes_when_they_are_back_and_ready(self):
        self.leave("Ann")
        self.come_back("Ann", True)
        self.assertEqual(self.paused, [True, False])
        self.assertIn("Ann is back and ready", self.client.ui.messages[-1])
        self.client.checkDropoutResume()  # Nothing left to wait for
        self.assertEqual(self.paused, [True, False])

    def test_it_waits_for_ready_and_resumes_when_they_press_it(self):
        self.leave("Ann")
        self.come_back("Ann", False)
        self.assertEqual(self.paused, [True])
        self.assertIn("waiting for them to be ready", self.client.ui.messages[-1].lower().replace("...", ""))
        told = len(self.client.ui.messages)
        self.client.checkDropoutResume()  # Same state again: no repeated chatter
        self.assertEqual(len(self.client.ui.messages), told)
        self.client.userlist.ready["Ann"] = True
        self.client.checkDropoutResume()
        self.assertEqual(self.paused, [True, False])

    def test_with_two_dropouts_it_waits_for_both(self):
        self.leave("Ann")
        self.leave("Bo")
        self.come_back("Ann", True)
        self.assertEqual(self.paused, [True, True])
        self.come_back("Bo", True)
        self.assertEqual(self.paused, [True, True, False])

    def test_someone_pressing_play_themselves_cancels_the_wait(self):
        self.leave("Ann")
        self.client.cancelDropoutWait()
        self.come_back("Ann", True)
        self.assertEqual(self.paused, [True])  # We paused, but we never force play afterwards

    def test_switched_off_does_nothing_and_strangers_in_other_rooms_are_ignored(self):
        self.client._config["pauseOnLeave"] = False
        self.leave("Ann")
        self.assertEqual(self.paused, [])
        self.client._config["pauseOnLeave"] = True
        self.client.userlist.inRoom.discard("Bo")
        self.leave("Bo")  # Was in another room
        self.assertEqual(self.paused, [])
        self.assertEqual(getattr(self.client, "_dropoutWaiting", {}), {})

    def test_giving_up_after_the_wait_limit_and_string_true_from_the_ini(self):
        self.client._config["pauseOnLeave"] = "True"
        self.leave("Ann")
        self.client._dropoutWaiting["Ann"] -= self.client.DROPOUT_WAIT_LIMIT + 5
        self.come_back("Ann", True)
        self.assertEqual(self.paused, [True])

    def test_servers_without_readiness_resume_as_soon_as_a_file_is_open(self):
        self.client.serverFeatures = {}
        self.client.userlist.ready = {}
        self.leave("Ann")
        self.client.userlist.inRoom.add("Ann")
        self.client.userlist.files.discard("Ann")
        self.client.checkDropoutResume()
        self.assertEqual(self.paused, [True])
        self.client.userlist.files.add("Ann")
        self.client.checkDropoutResume()
        self.assertEqual(self.paused, [True, False])

    def test_the_setting_can_be_switched_and_is_saved(self):
        from syncplay.ui import ConfigurationGetter as module
        saved = []
        original = module.ConfigurationGetter.setConfigOption
        module.ConfigurationGetter.setConfigOption = lambda self, option, value: saved.append((option, value))
        self.addCleanup(setattr, module.ConfigurationGetter, "setConfigOption", original)
        self.leave("Ann")
        self.client.setPauseOnLeave(False)
        self.assertEqual(saved, [("pauseOnLeave", False)])
        self.assertFalse(self.client.pauseOnLeaveEnabled())
        self.assertEqual(self.client._dropoutWaiting, {})


if __name__ == "__main__":
    unittest.main()
