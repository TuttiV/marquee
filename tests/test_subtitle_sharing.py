import base64
import json
import os
import shutil
import tempfile
import unittest

from twisted.test.proto_helpers import StringTransport

from syncplay import constants, subtitles
from syncplay.protocols import SyncServerProtocol
from syncplay.server import SyncFactory

SRT = b"1\n00:00:01,000 --> 00:00:02,000\nHello\n"


def encode(raw):
    return base64.b64encode(raw).decode("ascii")


class SubtitleModuleTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, name, raw=SRT):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as f:
            f.write(raw)
        return path

    def test_sanitize_strips_paths_and_checks_extension(self):
        self.assertEqual(subtitles.sanitizeSubtitleName("../../etc/Movie.SRT"), "Movie.SRT")
        self.assertEqual(subtitles.sanitizeSubtitleName("C:\\subs\\a.ass"), "a.ass")
        self.assertIsNone(subtitles.sanitizeSubtitleName("evil.exe"))
        self.assertIsNone(subtitles.sanitizeSubtitleName("noextension"))
        self.assertIsNone(subtitles.sanitizeSubtitleName(".srt"))
        self.assertIsNone(subtitles.sanitizeSubtitleName(None))

    def test_decode_roundtrip(self):
        name, raw = subtitles.decodeSubtitlePayload("a.srt", encode(SRT))
        self.assertEqual((name, raw), ("a.srt", SRT))

    def test_decode_rejects_bad_payloads(self):
        bad = [
            ("a.exe", encode(SRT)),
            ("a.srt", "not base64!!"),
            ("a.srt", ""),
            ("a.srt", 123),
            ("a.srt", encode(b"bin\x00ary")),
            ("a.srt", encode(b"x" * (constants.MAX_SHARED_SUBTITLE_BYTES + 1))),
        ]
        for name, data in bad:
            with self.assertRaises(subtitles.SubtitleShareError, msg=(name, str(data)[:20])):
                subtitles.decodeSubtitlePayload(name, data)

    def test_read_subtitle_file(self):
        name, data = subtitles.readSubtitleFile(self.write("Show.srt"))
        self.assertEqual(name, "Show.srt")
        self.assertEqual(base64.b64decode(data), SRT)

    def test_read_subtitle_file_errors(self):
        with self.assertRaises(subtitles.SubtitleShareError) as ctx:
            subtitles.readSubtitleFile(os.path.join(self.dir, "missing.srt"))
        self.assertEqual(ctx.exception.messageKey, "subtitle-file-not-found-error")
        big = self.write("big.srt", b"x" * 100)
        with self.assertRaises(subtitles.SubtitleShareError) as ctx:
            subtitles.readSubtitleFile(big, maxBytes=10)
        self.assertEqual(ctx.exception.messageKey, "subtitle-too-large-error")

    def test_find_sidecar(self):
        media = self.write("Show.S01E01.mkv", b"video")
        self.write("Other.srt")
        self.assertIsNone(subtitles.findSidecarSubtitle(media))
        self.write("Show.S01E01.en.srt")
        self.write("Show.S01E01.srt")
        self.assertEqual(os.path.basename(subtitles.findSidecarSubtitle(media)), "Show.S01E01.srt")
        self.assertIsNone(subtitles.findSidecarSubtitle(None))

    def test_store_saves_privately_and_cleans_up(self):
        store = subtitles.SharedSubtitleStore()
        first = store.save("bob", "a.srt", SRT)
        second = store.save("bob", "a.srt", SRT)
        self.assertNotEqual(first, second)
        with open(first, "rb") as f:
            self.assertEqual(f.read(), SRT)
        store.cleanup()
        self.assertFalse(os.path.exists(first))
        store.cleanup()  # Idempotent


class FakeClient(object):
    """A logged-in connection to a real SyncFactory, with a transport we can read."""

    def __init__(self, factory, username, features=None, room="room"):
        self.protocol = SyncServerProtocol(factory)
        self.transport = StringTransport()
        self.protocol.makeConnection(self.transport)
        hello = {"username": username, "room": {"name": room}, "version": "1.7.4"}
        hello["features"] = features if features is not None else {"subtitleSharing": True}
        self.send({"Hello": hello})

    def send(self, message):
        self.protocol.dataReceived(json.dumps(message).encode("utf-8") + b"\r\n")

    def received(self):
        messages = [json.loads(line) for line in self.transport.value().decode("utf-8").split("\r\n") if line]
        return messages

    def subtitlesReceived(self):
        return [m["Set"]["subtitle"] for m in self.received() if "Set" in m and "subtitle" in m["Set"]]


class ServerRelayTests(unittest.TestCase):
    def setUp(self):
        self.factory = SyncFactory(port="0", salt="test-salt")

    def share(self, client, name="a.srt", raw=SRT):
        client.send({"Set": {"subtitle": {"name": name, "data": encode(raw)}}})

    def test_advertises_feature(self):
        features = self.factory.getFeatures()
        self.assertTrue(features["subtitleSharing"])
        self.assertEqual(features["maxSharedSubtitleBytes"], constants.MAX_SHARED_SUBTITLE_BYTES)
        self.assertFalse(SyncFactory(port="0", salt="s", disableSubtitleSharing=True).getFeatures()["subtitleSharing"])

    def test_relays_to_room_but_not_sender_or_other_rooms(self):
        alice = FakeClient(self.factory, "alice")
        bob = FakeClient(self.factory, "bob")
        carol = FakeClient(self.factory, "carol", room="elsewhere")
        self.share(alice)
        self.assertEqual(bob.subtitlesReceived(), [{"user": "alice", "name": "a.srt", "data": encode(SRT)}])
        self.assertEqual(alice.subtitlesReceived(), [])
        self.assertEqual(carol.subtitlesReceived(), [])

    def test_not_sent_to_clients_without_the_feature(self):
        alice = FakeClient(self.factory, "alice")
        old = FakeClient(self.factory, "old", features={})
        self.share(alice)
        self.assertEqual(old.subtitlesReceived(), [])

    def test_invalid_payload_is_dropped_and_connection_survives(self):
        alice = FakeClient(self.factory, "alice")
        bob = FakeClient(self.factory, "bob")
        self.share(alice, name="evil.exe")
        alice.send({"Set": {"subtitle": "not a dict"}})
        self.assertEqual(bob.subtitlesReceived(), [])
        self.assertFalse(alice.transport.disconnecting)

    def test_name_is_sanitized_before_relay(self):
        alice = FakeClient(self.factory, "alice")
        bob = FakeClient(self.factory, "bob")
        self.share(alice, name="../../x.srt")
        self.assertEqual(bob.subtitlesReceived()[0]["name"], "x.srt")

    def test_rate_limited(self):
        alice = FakeClient(self.factory, "alice")
        bob = FakeClient(self.factory, "bob")
        self.share(alice)
        self.share(alice)
        self.assertEqual(len(bob.subtitlesReceived()), 1)

    def test_disabled_server_relays_nothing(self):
        factory = SyncFactory(port="0", salt="s", disableSubtitleSharing=True)
        alice = FakeClient(factory, "alice")
        bob = FakeClient(factory, "bob")
        self.share(alice)
        self.assertEqual(bob.subtitlesReceived(), [])

    def test_large_subtitle_fits_after_login_only(self):
        alice = FakeClient(self.factory, "alice")
        bob = FakeClient(self.factory, "bob")
        self.share(alice, raw=b"a" * constants.MAX_SHARED_SUBTITLE_BYTES)
        self.assertEqual(len(bob.subtitlesReceived()), 1)
        prelogin = SyncServerProtocol(self.factory)
        prelogin.makeConnection(StringTransport())
        self.assertLess(prelogin.MAX_LENGTH, constants.LOGGED_IN_MAX_LINE_LENGTH)


if __name__ == "__main__":
    unittest.main()


class FakeUI(object):
    def __init__(self):
        self.messages, self.errors = [], []

    def showMessage(self, message, *args, **kwargs):
        self.messages.append(message)

    def showErrorMessage(self, message, *args, **kwargs):
        self.errors.append(message)

    def showDebugMessage(self, message):
        pass


class FakePlayer(object):
    def __init__(self, canLoad):
        self.canLoad, self.loaded = canLoad, []

    def loadSubtitle(self, path):
        self.loaded.append(path)
        return self.canLoad


class ClientHandlingTests(unittest.TestCase):
    """Exercises SyncplayClient's subtitle methods without starting a real client."""

    def setUp(self):
        from syncplay.client import SyncplayClient
        self.client = object.__new__(SyncplayClient)
        self.client.ui = FakeUI()
        self.client._subtitleStore = subtitles.SharedSubtitleStore()
        self.client.lastSharedSubtitle = None
        self.client._player = FakePlayer(True)
        self.addCleanup(self.client._subtitleStore.cleanup)

    def test_received_subtitle_is_stored_but_not_auto_loaded(self):
        self.client.receivedSharedSubtitle("bob", "a.srt", encode(SRT))
        name, path = self.client.lastSharedSubtitle
        self.assertEqual(name, "a.srt")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self.client._player.loaded, [])
        self.assertIn("/loadsub", self.client.ui.messages[0])

    def test_invalid_received_subtitle_is_ignored(self):
        self.client.receivedSharedSubtitle("bob", "evil.exe", encode(SRT))
        self.assertIsNone(self.client.lastSharedSubtitle)
        self.assertEqual(self.client.ui.messages, [])

    def test_load_without_any_received_subtitle_errors(self):
        self.client.loadSharedSubtitle()
        self.assertEqual(len(self.client.ui.errors), 1)

    def test_load_uses_player_or_reports_saved_path(self):
        self.client.receivedSharedSubtitle("bob", "a.srt", encode(SRT))
        path = self.client.lastSharedSubtitle[1]
        self.client.loadSharedSubtitle()
        self.assertEqual(self.client._player.loaded, [path])
        self.client._player = FakePlayer(False)
        self.client.loadSharedSubtitle()
        self.assertIn(path, self.client.ui.messages[-1])
