import unittest
from unittest.mock import MagicMock

from syncplay import subpresence
from syncplay.client import SyncplayClient


class LineTests(unittest.TestCase):
    def test_lines_round_trip_and_none_is_a_dash(self):
        self.assertEqual(subpresence.parse(subpresence.line("Show.S01E01.en.srt")), "Show.S01E01.en.srt")
        self.assertEqual(subpresence.line(None), "[subs] -")
        self.assertIsNone(subpresence.parse("[subs] -"))

    def test_other_text_is_not_a_subtitle_line(self):
        for text in ("hello", "[subs]", "[subs] ", "[subs] a\x00b", "[sync] 1:00 (in sync) #abcd", None, "[subs] " + "x" * 61):
            self.assertIs(subpresence.parse(text), False, text)

    def test_labels_are_cleaned_and_shortened(self):
        self.assertEqual(subpresence.clean("a\nb\x07c"), "abc")
        self.assertLessEqual(len(subpresence.clean("y" * 200)), subpresence.MAX_LENGTH)
        self.assertIsNone(subpresence.parse(subpresence.line("y" * 200)) and None)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.client = object.__new__(SyncplayClient)
        self.client.userSubtitles = {}
        self.client._mySubtitle = None
        self.client._running = True
        self.client.ui = MagicMock()
        self.client.userlist = MagicMock()
        self.client.userlist.currentUser.username = "Me"
        self.client._protocol = MagicMock()
        self.client._protocol.logged = True
        self.client.serverVersion = "1.7.3"
        self.client.serverFeatures = {"chat": True}
        self.sent = []
        self.client.sendChat = self.sent.append

    def test_a_friends_line_is_recorded_hidden_and_cleared(self):
        self.assertTrue(self.client.handleSubtitlePresenceChat("Ann", "[subs] Show.en.srt"))
        self.assertEqual(self.client.subtitleFor("Ann"), "Show.en.srt")
        self.client.ui.subtitleInfoChanged.assert_called()
        self.assertTrue(self.client.handleSubtitlePresenceChat("Ann", "[subs] -"))
        self.assertIsNone(self.client.subtitleFor("Ann"))

    def test_ordinary_chat_and_fake_lines_are_left_alone(self):
        self.assertFalse(self.client.handleSubtitlePresenceChat("Ann", "[subs] "))
        self.assertFalse(self.client.handleSubtitlePresenceChat("Ann", "hi [subs] x"))
        self.assertEqual(self.client.userSubtitles, {})

    def test_your_own_line_echoed_back_changes_nothing(self):
        self.assertTrue(self.client.handleSubtitlePresenceChat("Me", "[subs] mine.srt"))
        self.assertEqual(self.client.userSubtitles, {})

    def test_setting_your_subtitle_announces_it_once_and_a_new_video_clears_it(self):
        self.client._setMySubtitle("Show.en.srt")
        self.client._setMySubtitle("Show.en.srt")
        self.assertEqual(self.sent, ["[subs] Show.en.srt"])
        self.assertEqual(self.client.subtitleFor("Me"), "Show.en.srt")
        self.client._setMySubtitle(None)
        self.assertEqual(self.sent[-1], "[subs] -")
        self.assertIsNone(self.client.subtitleFor("Me"))
