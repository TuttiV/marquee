import io
import json
import os
import unittest
import urllib.error
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from twisted.internet import defer

from syncplay import torbox

try:
    from syncplay.vendor.Qt import QtWidgets
    from syncplay.ui.TorBoxDialog import TorBoxDialog
    HAVE_QT = True
except Exception:
    HAVE_QT = False

GB = 1024 ** 3
TORRENTS = {"success": True, "data": [
    {"id": 1, "name": "Show.S01.2160p.WEB-DL.DV.HDR10.HEVC", "download_finished": True, "files": [
        {"id": 10, "name": "Show.S01/Show.S01E01.2160p.WEB-DL.HEVC.mkv", "size": 6 * GB},
        {"id": 11, "name": "Show.S01/Show.S01E02.2160p.WEB-DL.HEVC.mkv", "size": 6 * GB},
        {"id": 12, "name": "Show.S01/readme.txt", "size": 100}]},
    {"id": 2, "name": "Film.2019.1080p.BluRay.x264", "cached": True, "files": [
        {"id": 20, "name": "Film.2019.1080p.BluRay.x264.mkv", "size": 3 * GB}]},
    {"id": 3, "name": "Still.Downloading.720p", "download_finished": False, "files": [
        {"id": 30, "name": "a.mkv", "size": GB}]},
    {"id": 4, "name": "Docs", "download_finished": True, "files": [{"id": 40, "name": "notes.pdf", "size": 5}]},
]}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeApi(object):
    def __init__(self, routes):
        self.routes, self.requests = routes, []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        reply = self.routes[urlparse(request.full_url).path]
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(json.dumps(reply).encode("utf-8"))


class LibraryTests(unittest.TestCase):
    def library(self):
        return torbox.parseLibrary("torrents", TORRENTS)

    def test_only_finished_items_with_video_files_are_listed(self):
        items = self.library()
        self.assertEqual([i.name for i in items], ["Film.2019.1080p.BluRay.x264", "Show.S01.2160p.WEB-DL.DV.HDR10.HEVC"])
        self.assertEqual([f.shortName for f in items[1].files], ["Show.S01E01.2160p.WEB-DL.HEVC.mkv", "Show.S01E02.2160p.WEB-DL.HEVC.mkv"])

    def test_filters_combine_and_fall_back_to_the_item_name(self):
        items = self.library()
        count = lambda **kw: sum(len(f) for _, f in torbox.filterLibrary(items, torbox.LibraryFilters(**kw)))
        self.assertEqual(count(), 3)
        self.assertEqual(count(query="show e02"), 1)
        self.assertEqual(count(resolution="2160p"), 2)
        self.assertEqual(count(resolution="1080p", codec="H.264"), 1)
        self.assertEqual(count(hdr=True), 2)  # HDR tag only appears in the folder name
        self.assertEqual(count(hdr=False), 1)
        self.assertEqual(count(minSize=4 * GB), 2)
        self.assertEqual(count(maxSize=4 * GB), 1)
        self.assertEqual(count(codec="AV1"), 0)


class ClientTests(unittest.TestCase):
    def test_needs_a_key(self):
        with self.assertRaises(torbox.TorBoxError):
            torbox.TorBoxClient("  ")

    def test_library_uses_bearer_auth_and_only_talks_to_torbox(self):
        empty = {"success": True, "data": []}
        api = FakeApi({"/v1/api/torrents/mylist": TORRENTS, "/v1/api/usenet/mylist": empty, "/v1/api/webdl/mylist": empty})
        items = torbox.TorBoxClient("SECRET", urlopen=api).library()
        self.assertEqual(len(items), 2)
        self.assertTrue(all(r.headers["Authorization"] == "Bearer SECRET" for r in api.requests))
        self.assertTrue(all(urlparse(r.full_url).netloc == "api.torbox.app" for r in api.requests))
        self.assertTrue(all("SECRET" not in r.full_url for r in api.requests))  # Never in the URL for listing

    def test_stream_url_asks_for_a_json_link_with_the_file_name(self):
        api = FakeApi({"/v1/api/torrents/requestdl": {"success": True, "data": "https://cdn.example/f/Show.mkv"}})
        item = torbox.TorBoxItem("torrents", 1, "Show", [])
        url = torbox.TorBoxClient("KEY", urlopen=api).streamUrl(item, torbox.TorBoxFile(10, "a/b.mkv", 5))
        self.assertEqual(url, "https://cdn.example/f/Show.mkv")
        query = parse_qs(urlparse(api.requests[0].full_url).query)
        self.assertEqual((query["torrent_id"], query["file_id"], query["redirect"], query["append_name"]),
                         (["1"], ["10"], ["false"], ["true"]))

    def test_bad_key_and_bad_replies_are_friendly_errors(self):
        api = FakeApi({"/v1/api/torrents/mylist": urllib.error.HTTPError("u", 403, "no", {}, io.BytesIO(b""))})
        with self.assertRaises(torbox.TorBoxError) as ctx:
            torbox.TorBoxClient("BAD", urlopen=api)._get("/torrents/mylist")
        self.assertIn("API key", str(ctx.exception))
        api = FakeApi({"/v1/api/torrents/requestdl": {"success": True, "data": "http://insecure/x"}})
        with self.assertRaises(torbox.TorBoxError):
            torbox.TorBoxClient("K", urlopen=api).streamUrl(torbox.TorBoxItem("torrents", 1, "S", []), torbox.TorBoxFile(1, "a.mkv", 1))
        api = FakeApi({"/v1/api/torrents/mylist": {"success": False, "detail": "Slow down"}})
        with self.assertRaises(torbox.TorBoxError) as ctx:
            torbox.TorBoxClient("K", urlopen=api)._get("/torrents/mylist")
        self.assertEqual(str(ctx.exception), "Slow down")


class FakeUI(object):
    def __init__(self):
        self.messages, self.playlist = [], []

    def showMessage(self, message, *a, **k):
        self.messages.append(message)

    def addFileToPlaylist(self, url):
        self.playlist.append(url)


class PlayTests(unittest.TestCase):
    def setUp(self):
        from syncplay.client import SyncplayClient
        self.client = object.__new__(SyncplayClient)
        self.client.ui = FakeUI()
        self.client.playlist = type("P", (), {"switchToNewPlaylistItem": False})()
        self.opened = []
        self.client.openFile = lambda url, resetPosition=False, fromUser=False: self.opened.append((url, fromUser))
        self.client.sharedPlaylistIsEnabled = lambda: True

    def test_for_me_opens_directly_and_for_room_uses_the_shared_playlist(self):
        self.assertEqual(self.client._playTorBoxLink("https://cdn/x.mkv", "x.mkv", False), "x.mkv")
        self.assertEqual(self.opened, [("https://cdn/x.mkv", True)])
        self.client._playTorBoxLink("https://cdn/y.mkv", "y.mkv", True)
        self.assertEqual(self.client.ui.playlist, ["https://cdn/y.mkv"])
        self.assertTrue(self.client.playlist.switchToNewPlaylistItem)

    def test_room_falls_back_to_solo_when_playlists_are_off(self):
        self.client.sharedPlaylistIsEnabled = lambda: False
        self.client._playTorBoxLink("https://cdn/z.mkv", "z.mkv", True)
        self.assertEqual(self.opened, [("https://cdn/z.mkv", True)])
        self.assertTrue(self.client.ui.messages)

    def test_no_key_fails_without_touching_the_network(self):
        self.client._config = {}
        result = []
        self.client.torboxLibrary().addErrback(lambda f: result.append(f.value))
        self.assertIsInstance(result[0], torbox.TorBoxError)


class FakeDialogClient(object):
    def __init__(self, key=True):
        self.key, self.saved, self.played = key, [], []

    def hasTorBoxKey(self):
        return self.key

    def saveTorBoxKey(self, key):
        self.saved.append(key)
        self.key = True

    def torboxLibrary(self):
        return defer.succeed(torbox.parseLibrary("torrents", TORRENTS))

    def openTorBoxFile(self, item, file_, forRoom=False):
        self.played.append((file_.fileId, forRoom))
        return defer.succeed(file_.shortName)


@unittest.skipUnless(HAVE_QT, "Qt not available")
class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make(self, **kw):
        client = FakeDialogClient(**kw)
        dialog = TorBoxDialog(client)
        self.addCleanup(dialog.close)
        return client, dialog

    def files(self, dialog):
        rows = []
        for i in range(dialog._tree.topLevelItemCount()):
            parent = dialog._tree.topLevelItem(i)
            rows += [parent.child(j).text(0) for j in range(parent.childCount())]
        return rows

    def test_loads_lists_and_selects_first_file(self):
        client, dialog = self.make()
        self.assertEqual(len(self.files(dialog)), 3)
        self.assertTrue(dialog._playButton.isEnabled())

    def test_search_and_filters_narrow_the_tree(self):
        _, dialog = self.make()
        dialog._searchEdit.setText("e02")
        self.assertEqual(len(self.files(dialog)), 1)
        dialog._searchEdit.setText("")
        dialog._resolution.setCurrentIndex(dialog._resolution.findData("1080p"))
        self.assertEqual(self.files(dialog), ["Film.2019.1080p.BluRay.x264.mkv"])
        dialog._codec.setCurrentIndex(dialog._codec.findData("AV1"))
        self.assertTrue(dialog._tree.isHidden())
        self.assertIn("No files match", dialog._empty.text())

    def test_play_buttons_pass_the_room_flag(self):
        client, dialog = self.make()
        dialog._playButton.click()
        dialog._roomButton.click()
        self.assertEqual(client.played, [(20, False), (20, True)])  # Library is sorted by name, Film first
        self.assertIn("room playlist", dialog._status.text())

    def test_no_key_shows_setup_and_saving_loads_the_library(self):
        client, dialog = self.make(key=False)
        self.assertFalse(dialog._setupCard.isHidden())
        self.assertTrue(dialog._libraryCard.isHidden())
        dialog._saveKey()  # Empty
        self.assertEqual(client.saved, [])
        dialog._keyEdit.setText(" KEY ")
        dialog._saveKey()
        self.assertEqual(client.saved, ["KEY"])
        self.assertEqual(len(self.files(dialog)), 3)


if __name__ == "__main__":
    unittest.main()
