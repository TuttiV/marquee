import unittest

from syncplay.client import SyncplayClient


class FakeUser(object):
    def __init__(self, username="me", ready=None):
        self.username, self.ready = username, ready

    def isReady(self):
        return self.ready

    def setReady(self, ready):
        self.ready = ready


class FakeUserlist(object):
    def __init__(self, user):
        self.currentUser = user

    def isReady(self, username):
        return self.currentUser.ready if username == self.currentUser.username else False

    def setReady(self, username, ready):
        if username == self.currentUser.username:
            self.currentUser.setReady(ready)


class FakeProtocol(object):
    logged = True

    def __init__(self):
        self.ready = []

    def setReady(self, isReady, manuallyInitiated=True, username=None):
        self.ready.append((isReady, manuallyInitiated))


class FakeUI(object):
    def __init__(self):
        self.changed, self.messages = [], []

    def userListChange(self):
        pass

    def alwaysReadyChanged(self, enabled):
        self.changed.append(enabled)

    def showMessage(self, message, *args, **kwargs):
        self.messages.append(message)

    def showErrorMessage(self, *args, **kwargs):
        pass

    def showDebugMessage(self, *args, **kwargs):
        pass


class FakeWarnings(object):
    def checkReadyStates(self):
        pass


class AlwaysReadyTests(unittest.TestCase):
    def setUp(self):
        self.client = object.__new__(SyncplayClient)
        self.client._config = {"alwaysReady": True}
        self.client.serverFeatures = {"readiness": True}
        self.client.serverVersion = "1.7.7"
        self.client.ui = FakeUI()
        self.client._warnings = FakeWarnings()
        self.client._protocol = FakeProtocol()
        self.client.userlist = FakeUserlist(FakeUser(ready=True))
        self.client.autoplayCheck = lambda: None

    def sent(self):
        return self.client._protocol.ready

    def test_enabled_only_when_server_supports_readiness(self):
        self.assertTrue(self.client.alwaysReadyEnabled())
        self.client.serverFeatures = {"readiness": False}
        self.assertFalse(self.client.alwaysReadyEnabled())
        self.client.serverFeatures, self.client._config = {"readiness": True}, {"alwaysReady": False}
        self.assertFalse(self.client.alwaysReadyEnabled())

    def test_pausing_never_unreadies_us(self):
        self.client.toggleReady()
        self.client.changeReadyState(False, manuallyInitiated=False)
        self.assertEqual(self.sent(), [])

    def test_can_still_become_ready_and_toggle_when_feature_is_off(self):
        self.client.userlist.currentUser.ready = False
        self.client.changeReadyState(True)
        self.assertEqual(self.sent(), [(True, True)])
        self.client._config["alwaysReady"] = False
        self.client.userlist.currentUser.ready = True
        self.client.toggleReady()
        self.assertEqual(self.sent()[-1], (False, True))

    def test_being_unreadied_by_the_server_is_undone(self):
        self.client.setReady("me", False, manuallyInitiated=False)
        self.assertEqual(self.sent(), [(True, False)])

    def test_operator_override_is_respected(self):
        self.client.setReady("me", False, manuallyInitiated=True, setBy="operator")
        self.assertEqual(self.sent(), [])

    def test_other_users_unready_is_ignored(self):
        self.client.setReady("bob", False)
        self.assertEqual(self.sent(), [])

    def test_no_reassert_when_feature_off(self):
        self.client._config["alwaysReady"] = False
        self.client.setReady("me", False)
        self.assertEqual(self.sent(), [])

    def test_enabling_readies_immediately_and_notifies_ui(self):
        self.client._config["alwaysReady"] = False
        self.client.userlist.currentUser.ready = False
        self.client.setAlwaysReady(True, persist=False)
        self.assertEqual(self.sent(), [(True, False)])
        self.assertEqual(self.client.ui.changed, [True])
        self.client.setAlwaysReady(False, persist=False)
        self.assertEqual(self.client.ui.changed, [True, False])
        self.assertFalse(self.client.alwaysReadyEnabled())

    def test_connecting_starts_ready(self):
        self.client.userlist.currentUser.ready = None
        self.client._config["readyAtStart"] = False
        self.client.reIdentifyAsController = lambda: None
        self.client._config["loadPlaylistFromFile"] = None
        self.client.connected()
        self.assertEqual(self.sent(), [(True, False)])


if __name__ == "__main__":
    unittest.main()
