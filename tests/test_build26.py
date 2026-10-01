import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from syncplay import diagnostics, emoji, subdelay
from syncplay.client import SyncplayClient


class SubDelayLineTests(unittest.TestCase):
    def test_lines_round_trip_and_are_limited(self):
        self.assertEqual(subdelay.line(0.4), "[subdelay] +0.4")
        self.assertEqual(subdelay.parse("[subdelay] +0.4"), 0.4)
        self.assertEqual(subdelay.parse("[subdelay] -2"), -2.0)
        self.assertEqual(subdelay.parse(subdelay.line(99)), subdelay.LIMIT)

    def test_other_text_is_not_a_delay(self):
        for text in ("hello", "[subdelay]", "[subdelay] abc", "[subdelay] 1e9", "[subdelay] 123", "x [subdelay] +1", None):
            self.assertIs(subdelay.parse(text), False, text)

    def test_description(self):
        self.assertEqual(subdelay.describe(0), "0 s")
        self.assertEqual(subdelay.describe(0.3), "+0.3 s")
        self.assertEqual(subdelay.describe(-1), "-1.0 s")


class FakeClient(object):
    def make(self):
        client = object.__new__(SyncplayClient)
        client.ui = MagicMock()
        client.userlist = MagicMock()
        client.userlist.currentUser.username = "Me"
        client._player = MagicMock()
        client._player.setSubtitleDelay.return_value = True
        client._protocol = MagicMock()
        client._protocol.logged = True
        client.serverVersion = "1.7.3"
        client.serverFeatures = {"chat": True}
        client._running = True
        self.sent = []
        client.sendChat = self.sent.append
        return client


class SharedSubtitleDelayTests(unittest.TestCase):
    def setUp(self):
        self.helper = FakeClient()
        self.client = self.helper.make()

    def test_nudging_applies_here_and_tells_the_room(self):
        self.client.changeSharedSubtitleDelay(by=0.1)
        self.client.changeSharedSubtitleDelay(by=0.1)
        self.client._player.setSubtitleDelay.assert_called_with(0.2)
        self.assertEqual(self.helper.sent, ["[subdelay] +0.1", "[subdelay] +0.2"])
        self.assertEqual(self.client.subtitleDelay(), 0.2)
        self.client.changeSharedSubtitleDelay(seconds=0.0)
        self.assertEqual(self.helper.sent[-1], "[subdelay] +0.0")

    def test_a_friends_change_is_applied_and_hidden_but_your_own_echo_is_not_applied_twice(self):
        self.assertTrue(self.client.handleSubtitleDelayChat("Ann", "[subdelay] -0.5"))
        self.client._player.setSubtitleDelay.assert_called_once_with(-0.5)
        self.assertIn("Ann", self.client.ui.showMessage.call_args[0][0])
        self.client._player.setSubtitleDelay.reset_mock()
        self.assertTrue(self.client.handleSubtitleDelayChat("Me", "[subdelay] +9"))
        self.client._player.setSubtitleDelay.assert_not_called()
        self.assertFalse(self.client.handleSubtitleDelayChat("Ann", "[subdelay] nonsense"))

    def test_a_player_that_cannot_do_it_says_so(self):
        self.client._player.setSubtitleDelay.return_value = False
        self.client.changeSharedSubtitleDelay(by=0.1)
        self.assertIn("can't", self.client.ui.showMessage.call_args[0][0])
        self.assertEqual(self.helper.sent, ["[subdelay] +0.1"])  # The others still get it

    def test_newcomers_hear_a_nonzero_delay(self):
        self.client._subDelay = 0.3
        with patch("syncplay.client.reactor.callLater") as later:
            self.client.announceSubtitleToNewcomer()
        later.assert_called_once()
        self.client._announceMyState()
        self.assertEqual(self.helper.sent, ["[subdelay] +0.3"])


class DiagnosticsTests(unittest.TestCase):
    def test_secrets_and_tokens_are_removed(self):
        text = diagnostics.redact("login password=hunter2 api_key: ABCDEF123456 token xyz and " + "k" * 40 + " plus Room123", ["Room123"])
        self.assertNotIn("hunter2", text)
        self.assertNotIn("ABCDEF123456", text)
        self.assertNotIn("k" * 40, text)
        self.assertNotIn("Room123", text)
        self.assertIn("<hidden>", text)

    def test_the_report_lists_facts_and_the_log_tail(self):
        text = diagnostics.report([("Build", 26), ("Server", "x:1")], ["line one", "password=abc"], [])
        self.assertTrue(text.startswith("Marquee diagnostics"))
        self.assertIn("Build: 26", text)
        self.assertIn("line one", text)
        self.assertNotIn("abc", text)

    def test_the_log_tail_is_read_from_the_app_folder(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        self.assertEqual(diagnostics.tailOfLog(folder), [])
        with open(os.path.join(folder, "syncplay.log"), "w") as f:
            f.write("\n".join("row %d" % i for i in range(200)))
        tail = diagnostics.tailOfLog(folder)
        self.assertEqual(len(tail), diagnostics.LOG_LINES)
        self.assertEqual(tail[-1], "row 199")

    def test_the_client_report_has_no_secrets_names_or_rooms(self):
        helper = FakeClient()
        client = helper.make()
        client._config = {"host": "example.org", "port": 8999, "password": "pw-secret", "name": "Gustav", "room": "private-room-1",
                          "playerPath": "C:\\Program Files\\VLC\\vlc.exe", "openSubtitlesApiKey": "KEY-123456"}
        client.userlist._users = {}
        client.userlist.currentUser.file = {"name": "Private Movie.mkv"}
        client._mySubtitle = None
        text = client.diagnosticsText()
        for secret in ("pw-secret", "Gustav", "private-room-1", "KEY-123456"):
            self.assertNotIn(secret, text)
        self.assertIn("example.org:8999", text)
        self.assertIn("vlc.exe", text)
        self.assertNotIn("Private Movie", text)


class EmojiTests(unittest.TestCase):
    def test_shortcodes_expand_and_unknown_ones_stay(self):
        self.assertEqual(emoji.expand("nice :fire: :+1:"), "nice 🔥 👍")
        self.assertEqual(emoji.expand("at 10:30:45 or :nope:"), "at 10:30:45 or :nope:")
        self.assertEqual(emoji.expand(""), "")

    def test_a_line_of_only_emoji_counts_as_a_reaction(self):
        self.assertTrue(emoji.isOnlyEmoji("🔥"))
        self.assertTrue(emoji.isOnlyEmoji("😂 😂 😂"))
        self.assertTrue(emoji.isOnlyEmoji("❤️"))
        self.assertFalse(emoji.isOnlyEmoji("great 🔥"))
        self.assertFalse(emoji.isOnlyEmoji("hello"))
        self.assertFalse(emoji.isOnlyEmoji(""))

    def test_every_picker_emoji_is_emoji_only(self):
        for symbol in emoji.PICKER:
            self.assertTrue(emoji.isOnlyEmoji(symbol), symbol)


class ReopenPlayerTests(unittest.TestCase):
    def test_it_restarts_with_the_same_video_and_room(self):
        helper = FakeClient()
        client = helper.make()
        client.userlist.currentUser.file = {"name": "Show.mkv", "path": "/videos/Show.mkv"}
        client.getRoom = lambda: "room-x"
        client._saveResume = MagicMock()
        client.stop = MagicMock()
        with patch("syncplay.client.updater.relaunch") as relaunch:
            client.reopenPlayer()
        argv = relaunch.call_args[0][2]
        self.assertEqual(argv[1:], ["/videos/Show.mkv", "-r", "room-x"])
        client._saveResume.assert_called_once()
        client.stop.assert_called_once()

    def test_with_no_video_it_refuses(self):
        helper = FakeClient()
        client = helper.make()
        client.userlist.currentUser.file = None
        with self.assertRaises(OSError):
            client.reopenPlayer()


try:
    from syncplay.vendor.Qt import QtWidgets
    HAVE_QT = True
except Exception:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "Qt not available")
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from syncplay.ui.gui import MainWindow
        from tests.test_release2_window import CONFIG
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
        self.window.showMessage = MagicMock()

    def test_menus_reach_the_new_features(self):
        self.window.subDelayLaterAction.trigger()
        self.client.changeSharedSubtitleDelay.assert_called_with(by=0.1)
        self.window.subDelayEarlierAction.trigger()
        self.client.changeSharedSubtitleDelay.assert_called_with(by=-0.1)
        self.window.subDelayResetAction.trigger()
        self.client.changeSharedSubtitleDelay.assert_called_with(seconds=0.0)
        self.window.reopenPlayerAction.trigger()
        self.client.reopenPlayer.assert_called_once()

    def test_copy_diagnostics_puts_the_report_on_the_clipboard(self):
        self.client.diagnosticsText.return_value = "Marquee diagnostics\nBuild: 26"
        self.window.diagnosticsAction.trigger()
        self.assertEqual(QtWidgets.QApplication.clipboard().text(), "Marquee diagnostics\nBuild: 26")
        self.assertIn("2", self.window.showMessage.call_args[0][0])

    def test_emoji_button_inserts_into_the_message_and_shortcodes_are_expanded_on_send(self):
        self.window._insertEmoji("🔥")
        self.assertEqual(self.window.chatInput.text(), "🔥")
        self.window.chatInput.setText("great :tada:")
        self.window.sendChatMessage()
        self.client.sendChat.assert_called_with("great 🎉")

    def test_a_lone_emoji_is_shown_large(self):
        self.window.showMessage = type(self.window).showMessage.__get__(self.window)
        self.window.showMessage("<Ann> 🔥")
        self.assertIn("font-size", self.window.outputbox.toHtml().replace("font-size:26px", "font-size: 26px"))

    def test_the_picker_lists_every_emoji(self):
        self.window.showEmojiPicker()
        self.assertEqual(len(self.window._emojiPicker.buttons), len(emoji.PICKER))
        self.window._emojiPicker.close()

    def test_you_are_welcomed_once_with_who_is_here(self):
        class U(object):
            def __init__(self, name):
                self.username = name
        me, ann, bo = U("Me"), U("Ann"), U("Bo")
        me.room = "room"
        self.window._welcomeNote(me, {"room": [me, ann, bo]})
        self.assertIn("Ann, Bo", self.window.showMessage.call_args[0][0])
        self.window.showMessage.reset_mock()
        self.window._welcomeNote(me, {"room": [me, ann, bo]})
        self.window.showMessage.assert_not_called()
