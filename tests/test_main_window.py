import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from unittest.mock import MagicMock, patch
    from twisted.internet import defer
    from syncplay import updater
    from syncplay.vendor.Qt import QtWidgets
    from syncplay.client import SyncplayUser
    from syncplay.ui.gui import MainWindow
    HAVE_QT = True
except Exception:  # No Qt binding or system libraries available
    HAVE_QT = False

CONFIG = {"host": "example.org", "port": 8999, "password": "hashed", "sharedPlaylistEnabled": True,
          "mediaSearchDirectories": ["/x"], "readyAtStart": False, "alwaysReady": False, "autoplayInitialState": None,
          "autoplayMinUsers": -1, "roomList": [], "chatOutputEnabled": True, "checkForUpdatesAutomatically": False,
          "lastCheckedForUpdates": ""}


@unittest.skipUnless(HAVE_QT, "Qt not available")
class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        self.me = SyncplayUser("You", "room")
        self.me.setFile("a.mkv", 100.0, 10, path="/nonexistent/a.mkv")
        self.me.setReady(True)
        self.client = MagicMock()
        self.client.getConfig.return_value = dict(CONFIG)
        self.client.getRoom.return_value = "room"
        self.client.userlist.currentUser = self.me
        self.window.addClient(self.client)
        self.window.setFeatures({"readiness": True, "chat": True, "sharedPlaylists": True})

    def test_theme_is_applied(self):
        self.assertIn("readyButton", QtWidgets.QApplication.instance().styleSheet())  # Themed app-wide, so dialogs match
        self.assertEqual(self.window.readyPushButton.objectName(), "readyButton")

    def test_always_ready_button_drives_the_client(self):
        self.window.alwaysReadyButton.setChecked(True)
        self.client.setAlwaysReady.assert_called_with(True)
        self.window.alwaysReadyButton.setChecked(False)
        self.client.setAlwaysReady.assert_called_with(False)

    def test_client_notification_updates_buttons_and_menu(self):
        self.window.alwaysReadyChanged(True)
        self.assertTrue(self.window.alwaysReadyButton.isChecked())
        self.assertTrue(self.window.alwaysReadyAction.isChecked())
        self.assertTrue(self.window.readyPushButton.isChecked())
        self.assertFalse(self.window.readyPushButton.isEnabled())  # Locked on
        self.window.alwaysReadyChanged(False)
        self.assertTrue(self.window.readyPushButton.isEnabled())
        self.client.setAlwaysReady.assert_not_called()  # UI mirroring must not loop back into the client

    def test_server_without_readiness_disables_all_ready_controls(self):
        self.window.setFeatures({"readiness": False, "chat": True, "sharedPlaylists": True})
        self.window.alwaysReadyChanged(False)
        self.assertFalse(self.window.readyPushButton.isEnabled())
        self.assertFalse(self.window.alwaysReadyButton.isEnabled())

    def test_invite_copies_details_but_never_the_password(self):
        self.window.copyInvite()
        text = QtWidgets.QApplication.clipboard().text()
        self.assertIn("example.org", text)
        self.assertIn("Room: room", text)
        self.assertNotIn("hashed", text)
        self.assertIn("password", text.lower())

    def test_status_bar_and_room_card_show_server_room_and_counts(self):
        ann = SyncplayUser("Ann", "room")
        ann.setFile("a.mkv", 100.0, 10)
        ann.setReady(False)
        self.window.updateStatusBar(self.me, {"room": [self.me, ann]})
        self.assertIn("example.org:8999", self.window.statusServerLabel.toolTip())
        self.assertEqual(self.window.nowRoomLabel.text(), "room")
        self.assertEqual(self.window.nowPeoplePill.text(), "2 watching")
        self.assertEqual(self.window.nowReadyPill.text(), "1/2 ready")
        self.assertEqual(self.window.nowReadyPill.property("kind"), "waiting")
        self.assertIn("a.mkv", self.window.nowFileLabel.text())
        ann.setReady(True)
        self.window.updateStatusBar(self.me, {"room": [self.me, ann]})
        self.assertEqual(self.window.nowReadyPill.property("kind"), "ready")

    def test_user_rows_get_an_avatar_delegate_and_stable_colours(self):
        from syncplay.ui import theme
        from syncplay.ui.gui import ModernUserlistDelegate
        self.window.getFileSwitchState = lambda name: None
        self.window.showUserList(self.me, {"room": [self.me]})
        self.assertIsInstance(self.window.listTreeView.itemDelegate(), ModernUserlistDelegate)
        self.assertEqual(theme.userColor("Ann", True), theme.userColor("Ann", True))
        self.assertEqual(theme.initialOf("  ann"), "A")
        self.assertEqual(theme.initialOf(""), "?")

    def test_connection_states_banner_and_dot(self):
        self.assertTrue(self.window.connectionBanner.isHidden())
        self.window.connectionLost()
        self.assertFalse(self.window.connectionBanner.isHidden())
        self.assertIn("Reconnecting", self.window.statusServerLabel.text())
        self.assertTrue(self.window._dotTimer.isActive())
        before = self.window.statusDot.styleSheet()
        self.window._pulseStatusDot()
        self.assertNotEqual(before, self.window.statusDot.styleSheet())  # The dot pulses while waiting
        self.window.bannerButton.click()
        self.client.manualReconnect.assert_called_once()
        self.window.updateStatusBar(self.me, {"room": [self.me]})  # The user list arrives again: we're back
        self.assertTrue(self.window.connectionBanner.isHidden())
        self.assertFalse(self.window._dotTimer.isActive())
        self.assertIn("example.org", self.window.statusServerLabel.toolTip())

    def test_title_bar_shows_room_ready_count_and_build(self):
        from syncplay.private_build import BUILD
        ann = SyncplayUser("Ann", "room")
        ann.setFile("a.mkv", 100.0, 10)
        ann.setReady(False)
        self.window.updateNowCard(self.me, {"room": [self.me]})
        self.assertEqual(self.window.windowTitle(), "Syncplay Marquee \u00b7 room \u00b7 build {}".format(BUILD))
        self.window.updateNowCard(self.me, {"room": [self.me, ann]})
        self.assertEqual(self.window.windowTitle(), "Syncplay Marquee \u00b7 room \u00b7 1/2 ready \u00b7 build {}".format(BUILD))

    def test_every_replacement_icon_exists_and_the_menus_use_line_icons(self):
        from syncplay.ui import icons
        for stem, name in icons.LEGACY.items():
            self.assertIn(name, icons._PATHS, stem)
            self.assertFalse(icons.legacy(stem, "#ffffff").isNull(), stem)
        self.assertIsNone(icons.legacy("not_a_real_icon", "#ffffff"))
        for action in (self.window.openAction, self.window.reconnectAction, self.window.updateAction):
            self.assertFalse(action.icon().isNull())

    def test_icons_render_in_both_themes(self):
        from syncplay.ui import icons
        for name in ("send", "join", "subtitles", "invite", "library", "check", "refresh", "star"):
            for color in ("#ffffff", "#000000"):
                pm = icons.pixmap(name, color, 16)
                self.assertFalse(pm.isNull())
                self.assertTrue(any(pm.toImage().pixelColor(x, y).alpha() > 0 for x in range(pm.width()) for y in range(pm.height())), name)


@unittest.skipUnless(HAVE_QT, "Qt not available")
class OneClickUpdateTests(unittest.TestCase):
    """Clicking Update installs and restarts with no questions; only the startup check stays quiet."""

    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def release(self, build):
        return updater.ReleaseInfo("v{}".format(build), build, "Build {}".format(build), "notes", "https://github.com/o/r/a.zip", 10, "a" * 64)

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        self.client = MagicMock()
        self.client.getConfig.return_value = dict(CONFIG)
        self.client.getRoom.return_value = "room"
        self.window.addClient(self.client)
        self.client.privateUpdateRepo.return_value = "o/r"
        self.client.installPrivateUpdate.return_value = defer.succeed(5)
        self.window.showMessage = MagicMock()
        box = QtWidgets.QMessageBox
        self.box = {}
        for name in ("question", "information", "warning"):
            p = patch.object(box, name, return_value=box.Yes)
            self.box[name] = p.start()
            self.addCleanup(p.stop)

    def test_clicking_update_installs_and_restarts_without_asking_anything(self):
        self.client.checkPrivateUpdate.return_value = defer.succeed(self.release(updater.BUILD + 1))
        self.window.userCheckForUpdates()
        self.client.installPrivateUpdate.assert_called_once()
        self.client.restartSyncplay.assert_called_once()
        for mock in self.box.values():
            mock.assert_not_called()

    def test_the_startup_check_only_mentions_the_update_in_chat(self):
        self.client.checkPrivateUpdate.return_value = defer.succeed(self.release(updater.BUILD + 1))
        self.window.checkForUpdates(userInitiated=False)
        self.client.installPrivateUpdate.assert_not_called()
        self.client.restartSyncplay.assert_not_called()
        self.assertIn("Build {}".format(updater.BUILD + 1), self.window.showMessage.call_args[0][0])
        for mock in self.box.values():
            mock.assert_not_called()

    def test_up_to_date_says_so_and_does_not_install(self):
        self.client.checkPrivateUpdate.return_value = defer.succeed(self.release(updater.BUILD))
        self.window.userCheckForUpdates()
        self.client.installPrivateUpdate.assert_not_called()
        self.box["information"].assert_called_once()

    def test_failed_download_is_reported_and_nothing_restarts(self):
        self.client.checkPrivateUpdate.return_value = defer.succeed(self.release(updater.BUILD + 1))
        self.client.installPrivateUpdate.return_value = defer.fail(updater.UpdateError("The download was corrupted."))
        self.window.userCheckForUpdates()
        self.client.restartSyncplay.assert_not_called()
        self.assertIn("corrupted", self.box["warning"].call_args[0][2])

    def test_if_the_restart_cannot_start_the_user_is_told_to_reopen_manually(self):
        self.client.checkPrivateUpdate.return_value = defer.succeed(self.release(updater.BUILD + 1))
        self.client.restartSyncplay.side_effect = OSError("no")
        self.window.userCheckForUpdates()
        self.box["information"].assert_called_once()

    def test_without_an_update_source_the_first_click_asks_once_then_updates(self):
        self.client.privateUpdateRepo.return_value = None

        def saved(text):
            self.client.privateUpdateRepo.return_value = "me/app"
            return "me/app"
        self.client.saveUpdateRepo.side_effect = saved
        self.client.checkPrivateUpdate.return_value = defer.succeed(self.release(updater.BUILD + 1))
        with patch.object(QtWidgets.QInputDialog, "getText", return_value=("github.com/me/app", True)) as prompt:
            self.window.userCheckForUpdates()
        prompt.assert_called_once()
        self.client.saveUpdateRepo.assert_called_once_with("github.com/me/app")
        self.client.installPrivateUpdate.assert_called_once()
        self.client.restartSyncplay.assert_called_once()

    def test_cancelling_the_source_prompt_changes_nothing(self):
        self.client.privateUpdateRepo.return_value = None
        with patch.object(QtWidgets.QInputDialog, "getText", return_value=("", False)):
            self.window.userCheckForUpdates()
        self.client.saveUpdateRepo.assert_not_called()
        self.client.checkPrivateUpdate.assert_not_called()

    def test_a_bad_source_is_explained_not_saved(self):
        self.client.privateUpdateRepo.return_value = None
        self.client.saveUpdateRepo.side_effect = ValueError("That doesn't look like a GitHub repository.")
        with patch.object(QtWidgets.QInputDialog, "getText", return_value=("nope", True)):
            self.window.userCheckForUpdates()
        self.assertIn("GitHub", self.box["warning"].call_args[0][2])
        self.client.checkPrivateUpdate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
