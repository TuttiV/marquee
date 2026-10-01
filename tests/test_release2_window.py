import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from unittest.mock import MagicMock, patch
    from syncplay.vendor.Qt import QtGui, QtWidgets
    from syncplay.ui.gui import MainWindow
    HAVE_QT = True
except Exception:
    HAVE_QT = False

CONFIG = {"host": "h", "port": 1, "password": "", "sharedPlaylistEnabled": True, "mediaSearchDirectories": ["/x"], "readyAtStart": False,
          "alwaysReady": False, "autoplayInitialState": None, "autoplayMinUsers": -1, "roomList": [], "chatOutputEnabled": True,
          "checkForUpdatesAutomatically": False, "lastCheckedForUpdates": "", "pauseOnLeave": False}


@unittest.skipUnless(HAVE_QT, "Qt not available")
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        self.client = MagicMock()
        self.client.getConfig.return_value = dict(CONFIG, configDir=self.dir)
        self.client.getRoom.return_value = "room"
        self.client.getUsername.return_value = "Me"
        self.client.syncStatus.return_value = {"offset": None, "rtt": None, "paused": True}
        self.window.addClient(self.client)
        self.window.resize(MainWindow.NARROW_WIDTH + 200, 700)
        self.app.processEvents()

    def test_the_theme_menu_lists_every_theme_and_switching_changes_the_look_and_the_ticks(self):
        from syncplay.ui import theme
        self.addCleanup(theme.chooseTheme, "system", False)
        self.addCleanup(theme.applyApplicationTheme, self.app)
        self.assertEqual(list(self.window.themeActions), list(theme.THEME_ORDER))
        self.window.themeActions["cinema"].trigger()
        self.assertTrue(self.window._dark)
        self.assertIn(theme.CINEMA["accent"], self.app.styleSheet())
        self.assertTrue(self.window.themeActions["cinema"].isChecked())
        self.assertFalse(self.window.themeActions["system"].isChecked())
        self.window.themeActions["sand"].trigger()
        self.assertFalse(self.window._dark)
        self.window.grab()  # Paints in the new colours without error

    # --- look
    def test_tray_menu_items_have_icons(self):
        menu = self.window._buildTrayMenu()
        self.assertEqual(len(menu.actions()), 2)
        self.assertTrue(all(not a.icon().isNull() for a in menu.actions()))

    def test_message_boxes_get_the_line_icons(self):
        box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "t", "text", QtWidgets.QMessageBox.Ok, self.window)
        self.addCleanup(box.close)
        box.show()
        self.app.processEvents()
        self.assertTrue(box.property("themedIcon"))

    # --- resume bar
    def test_resume_bar_offers_continues_and_dismisses(self):
        self.assertTrue(self.window.resumeBar.isHidden())
        self.window.offerResume(1930.0)
        self.assertFalse(self.window.resumeBar.isHidden())
        self.assertIn("32:10", self.window.resumeLabel.text())
        self.window.resumeContinue.click()
        self.client.setPosition.assert_called_once_with(1930.0)
        self.assertTrue(self.window.resumeBar.isHidden())
        self.window.offerResume(500.0)
        self.window.resumeStartOver.click()
        self.assertTrue(self.window.resumeBar.isHidden())
        self.client.setPosition.assert_called_once()

    # --- sync note
    def test_sync_note_in_the_status_bar_and_click_runs_the_check(self):
        self.client.syncStatus.return_value = {"offset": 0.2, "rtt": 41, "paused": False}
        self.window._tickProgress()
        self.assertEqual(self.window.statusSyncLabel.text(), "In sync · 41 ms")
        self.assertEqual(self.window.statusSyncLabel.property("kind"), "ok")
        self.client.syncStatus.return_value = {"offset": -2.46, "rtt": 41, "paused": False}
        self.window._tickProgress()
        self.assertEqual(self.window.statusSyncLabel.text(), "2.5 s behind")
        self.assertEqual(self.window.statusSyncLabel.property("kind"), "warn")
        self.client.syncStatus.return_value = {"offset": 1.04, "rtt": None, "paused": False}
        self.window._tickProgress()
        self.assertEqual(self.window.statusSyncLabel.text(), "1.0 s ahead")
        self.client.syncStatus.return_value = {"offset": None, "rtt": 41, "paused": True}
        self.window._tickProgress()
        self.assertEqual(self.window.statusSyncLabel.text(), "")
        self.window.statusSyncLabel.clicked.emit()
        self.window.syncCheckAction.trigger()
        self.assertEqual(self.client.startSyncCheck.call_count, 2)

    # --- voice
    def test_voice_button_starts_a_call_then_joins_it(self):
        opened = []
        with patch.object(QtGui.QDesktopServices, "openUrl", side_effect=lambda url: opened.append(url.toString())):
            self.window.showMessage = MagicMock()
            self.assertEqual(self.window.voiceChip.text(), "Voice")
            self.window.voiceChip.click()
            line = self.client.sendChat.call_args[0][0]
            self.assertTrue(line.startswith("Voice call: https://meet.jit.si/SyncplayMarquee-"))
            self.assertEqual(opened[0], line.split(": ", 1)[1])
            self.assertEqual(self.window.voiceChip.text(), "Join voice")
            self.window.voiceChip.click()  # Joins the same call instead of starting another
            self.assertEqual(self.client.sendChat.call_count, 1)
            self.assertEqual(opened[1], opened[0])

    def test_a_voice_link_from_a_friend_turns_the_button_into_join(self):
        self.window.showMessage("<Ann> Voice call: https://meet.jit.si/SyncplayMarquee-abcdefghijkl")
        self.assertEqual(self.window.voiceChip.text(), "Join voice")
        self.client.getRoom.return_value = "another-room"  # A call belongs to its room
        self.window._updateVoiceChip()
        self.assertEqual(self.window.voiceChip.text(), "Voice")

    # --- chat links
    def test_links_in_chat_are_clickable_and_escaped(self):
        self.window.showMessage("<Ann> look https://a.example/x?a=1&b=2 <b>bold</b>")
        html = self.window.outputbox.toHtml()
        self.assertIn('href="https://a.example/x?a=1&amp;b=2"', html)
        self.assertNotIn("<b>bold</b>", html)

    # --- notifications
    def test_mentions_notify_but_your_own_words_and_substrings_do_not(self):
        self.window.notifyEvent = MagicMock()
        self.window.showMessage("<Ann> hey Me, ready?")
        self.window.notifyEvent.assert_called_once()
        self.assertEqual(self.window.notifyEvent.call_args[0][0], "mention")
        self.window.showMessage("<Ann> awesome homemade stuff")
        self.window.showMessage("<Me> @Me talking to myself")
        self.assertEqual(self.window.notifyEvent.call_count, 1)

    def test_toasts_only_when_inactive_enabled_throttled(self):
        self.window._tray = MagicMock()
        self.window._notificationsOn = True
        with patch.object(MainWindow, "isActiveWindow", return_value=True):
            self.window.notifyEvent("joined", "Ann joined the room")
        self.window._tray.showMessage.assert_not_called()  # You're looking at it
        with patch.object(MainWindow, "isActiveWindow", return_value=False):
            self.window.notifyEvent("joined", "Ann joined the room")
            self.window.notifyEvent("joined", "Bo joined the room")  # Within 3 s: skipped
            self.window.notifyEvent("left", "Ann left the room")
            self.assertEqual(self.window._tray.showMessage.call_count, 2)
            self.window.setNotifications(False)
            self.window._lastNotified.clear()
            self.window.notifyEvent("mention", "x")
            self.assertEqual(self.window._tray.showMessage.call_count, 2)

    def test_the_notification_choice_is_remembered(self):
        self.window.notificationsAction.setChecked(False)
        second = MainWindow()
        self.addCleanup(second.close)
        client = MagicMock()
        client.getConfig.return_value = dict(CONFIG, configDir=self.dir)
        client.getRoom.return_value = "room"
        client.syncStatus.return_value = {"offset": None, "rtt": None, "paused": True}
        second.addClient(client)
        self.assertFalse(second.notificationsAction.isChecked())

    # --- start window
    def test_menu_items_for_the_start_window(self):
        self.assertFalse(self.window.skipStartAction.isChecked())
        self.window.skipStartAction.setChecked(True)
        self.client.setSkipStartWindow.assert_called_with(True)
        self.window.connectionSettingsAction.trigger()
        self.client.reopenWithStartWindow.assert_called_once()

    def test_a_first_setup_tells_you_the_window_will_be_skipped_from_now_on(self):
        second = MainWindow()
        self.addCleanup(second.close)
        client = MagicMock()
        client.getConfig.return_value = dict(CONFIG, configDir=self.dir, skipStartWindow=True, startWindowNowSkipped=True)
        client.getRoom.return_value = "room"
        client.syncStatus.return_value = {"offset": None, "rtt": None, "paused": True}
        second.showMessage = MagicMock()
        second.addClient(client)
        self.assertTrue(second.skipStartAction.isChecked())
        self.assertIn("opens straight into this room", second.showMessage.call_args_list[0][0][0])


if __name__ == "__main__":
    unittest.main()



@unittest.skipUnless(HAVE_QT, "Qt not available")
class ReadyButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_state_changes_glide_and_always_end_on_the_right_look(self):
        from syncplay.ui.panels import ReadyButton
        button = ReadyButton("Not ready")
        button.setCheckable(True)
        self.addCleanup(button.close)
        button.resize(300, 40)
        button.show()
        self.app.processEvents()
        button.grab()
        self.assertEqual(button._t, 0.0)
        button.blockSignals(True)  # The room changes it without a click
        button.setChecked(True)
        button.blockSignals(False)
        button.grab()
        self.assertTrue(button.animating())
        button._animation.setCurrentTime(button.DURATION)
        self.assertEqual(button._t, 1.0)
        pixmap = button.grab()  # Fully ready: paints without error
        self.assertFalse(pixmap.isNull())
        button.setChecked(False)
        button.grab()
        button._animation.setCurrentTime(button.DURATION)
        self.assertEqual(button._t, 0.0)

    def test_nothing_animates_before_the_button_is_on_screen(self):
        from syncplay.ui.panels import ReadyButton
        button = ReadyButton("x")
        button.setCheckable(True)
        button.setChecked(True)
        button.grab()
        self.assertFalse(button.animating())
        self.assertEqual(button._t, 1.0)
