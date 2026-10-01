import base64
import io
import json
import os
import shutil
import struct
import tempfile
import unittest
import urllib.error
from urllib.parse import parse_qs, urlparse

from twisted.internet import defer
from twisted.python.failure import Failure

from syncplay import constants, opensubtitles, subtitles
from tests.test_subtitle_sharing import FakePlayer, FakeUI, SRT

SEARCH_PAYLOAD = {"data": [
    {"attributes": {"language": "en", "download_count": 10, "moviehash_match": False, "release": "Show.720p",
                    "feature_details": {"title": "Show"}, "files": [{"file_id": 111, "file_name": "a.srt"}]}},
    {"attributes": {"language": "en", "download_count": 5, "moviehash_match": True, "release": "Show.1080p",
                    "hearing_impaired": True, "files": [{"file_id": 222, "file_name": "b.srt"}]}},
    {"attributes": {"language": "en", "files": []}},  # No usable file - skipped
    {"attributes": {"language": "en", "download_count": 99, "files": [{"file_id": 333, "file_name": "c.srt"}]}},
]}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeApi(object):
    """Stands in for urlopen: records requests and replies from a route table."""

    def __init__(self, routes):
        self.routes, self.requests = routes, []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        path = urlparse(request.full_url).path
        reply = self.routes[(request.get_method(), path)]
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(reply if isinstance(reply, bytes) else json.dumps(reply).encode("utf-8"))


class MovieHashTests(unittest.TestCase):
    def test_hash_matches_reference_algorithm(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, "video.bin")
        data = bytes(range(256)) * 1024  # 256 KiB
        with open(path, "wb") as f:
            f.write(data)
        expected = len(data)
        for chunk in (data[:65536], data[-65536:]):
            expected = (expected + sum(struct.unpack("<8192Q", chunk))) & 0xFFFFFFFFFFFFFFFF
        self.assertEqual(opensubtitles.computeMovieHash(path), ("{:016x}".format(expected), len(data)))

    def test_small_files_have_no_hash(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, "tiny.bin")
        with open(path, "wb") as f:
            f.write(b"x" * 100)
        self.assertEqual(opensubtitles.computeMovieHash(path), (None, 100))


class ClientTests(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(opensubtitles.OpenSubtitlesError):
            opensubtitles.OpenSubtitlesClient(None)

    def test_search_sends_key_and_hash_and_ranks_results(self):
        api = FakeApi({("GET", "/api/v1/subtitles"): SEARCH_PAYLOAD})
        client = opensubtitles.OpenSubtitlesClient("KEY", urlopen=api)
        results = client.search(movieHash="abc", byteSize=42, languages="en,sv")
        request = api.requests[0]
        query = parse_qs(urlparse(request.full_url).query)
        self.assertEqual(request.headers["Api-key"], "KEY")
        self.assertIn("Syncplay", request.headers["User-agent"])
        self.assertEqual((query["moviehash"], query["moviebytesize"], query["languages"]), (["abc"], ["42"], ["en,sv"]))
        self.assertEqual([r.fileId for r in results], [222, 333, 111])  # Hash match first, then by downloads
        self.assertIn("exact match", results[0].describe())

    def test_search_needs_something_to_search(self):
        client = opensubtitles.OpenSubtitlesClient("KEY", urlopen=FakeApi({}))
        with self.assertRaises(opensubtitles.OpenSubtitlesError):
            client.search()

    def test_download_logs_in_then_fetches_link(self):
        api = FakeApi({
            ("POST", "/api/v1/login"): {"token": "TOK", "base_url": "api.opensubtitles.com"},
            ("POST", "/api/v1/download"): {"link": "https://dl.example/file.srt", "file_name": "x.srt"},
            ("GET", "/file.srt"): SRT,
        })
        client = opensubtitles.OpenSubtitlesClient("KEY", "me", "pw", urlopen=api)
        self.assertEqual(client.download(222), ("x.srt", SRT))
        download = [r for r in api.requests if r.full_url.endswith("/download")][0]
        self.assertEqual(download.headers["Authorization"], "Bearer TOK")
        self.assertEqual(json.loads(download.data)["file_id"], 222)

    def test_a_rejected_saved_login_falls_back_to_the_key_alone_and_is_not_retried(self):
        from syncplay import opensubtitles as module
        module._REJECTED_LOGINS.clear()
        self.addCleanup(module._REJECTED_LOGINS.clear)
        bad = urllib.error.HTTPError("u", 401, "no", {}, io.BytesIO(b'{"message": "invalid username/password"}'))
        api = FakeApi({("POST", "/api/v1/login"): bad, ("POST", "/api/v1/download"): {"link": "https://dl.example/f.srt"}, ("GET", "/f.srt"): SRT})
        self.assertEqual(opensubtitles.OpenSubtitlesClient("KEY", "me", "wrong", urlopen=api).download(222)[1], SRT)
        download = [r for r in api.requests if r.full_url.endswith("/download")][0]
        self.assertNotIn("Authorization", download.headers)
        again = FakeApi({("POST", "/api/v1/download"): {"link": "https://dl.example/f.srt"}, ("GET", "/f.srt"): SRT})
        opensubtitles.OpenSubtitlesClient("KEY", "me", "wrong", urlopen=again).download(222)
        self.assertFalse([r for r in again.requests if r.full_url.endswith("/login")])  # No second login attempt

    def test_download_without_credentials_skips_login(self):
        api = FakeApi({
            ("POST", "/api/v1/download"): {"link": "https://dl.example/f.srt"},
            ("GET", "/f.srt"): SRT,
        })
        opensubtitles.OpenSubtitlesClient("KEY", urlopen=api).download(1)
        self.assertFalse(any(r.full_url.endswith("/login") for r in api.requests))

    def test_http_and_link_errors_become_friendly_errors(self):
        error = urllib.error.HTTPError("u", 406, "quota", {}, io.BytesIO(b'{"message": "Quota exceeded"}'))
        api = FakeApi({("POST", "/api/v1/download"): error})
        with self.assertRaises(opensubtitles.OpenSubtitlesError) as ctx:
            opensubtitles.OpenSubtitlesClient("KEY", urlopen=api).download(1)
        self.assertIn("Quota exceeded", str(ctx.exception))
        api = FakeApi({("POST", "/api/v1/download"): {"link": "http://insecure/f.srt"}})
        with self.assertRaises(opensubtitles.OpenSubtitlesError):
            opensubtitles.OpenSubtitlesClient("KEY", urlopen=api).download(1)

    def test_network_failure(self):
        api = FakeApi({("GET", "/api/v1/subtitles"): urllib.error.URLError("offline")})
        with self.assertRaises(opensubtitles.OpenSubtitlesError):
            opensubtitles.OpenSubtitlesClient("KEY", urlopen=api).search(query="x")


class ParseFileNameTests(unittest.TestCase):
    def test_parses_common_release_names(self):
        cases = {
            "Game.of.Thrones.S01E01.720p.HDTV.DD5.1.x264-EbP.mkv": ("Game of Thrones", None, 1, 1),
            "The.Matrix.1999.1080p.BluRay.x264.mkv": ("The Matrix", 1999, None, None),
            "Show Name - 2x05 - Title.mkv": ("Show Name", None, 2, 5),
            "[SubsPlease] Frieren - 12 (1080p).mkv": ("Frieren", None, 1, 12),
            "Movie Title (2019).mp4": ("Movie Title", 2019, None, None),
            "Some.Film.2160p.WEB-DL.DDP5.1.mkv": ("Some Film", None, None, None),
            "Show.Name.2020.S03E10.1080p.mkv": ("Show Name", 2020, 3, 10),
        }
        for name, (title, year, season, episode) in cases.items():
            info = opensubtitles.parseFileName(name)
            self.assertEqual((info["title"], info["year"], info["season"], info["episode"]), (title, year, season, episode), name)


PUBLIC_SUBS = {"subtitles": [
    {"id": "1", "url": "https://subs.example/en/1", "lang": "eng", "subtitleFileName": "Show.S01E02.720p.HDTV.srt"},
    {"id": "2", "url": "https://subs.example/en/2", "lang": "eng", "subtitleFileName": "Show.S01E02.HI.srt"},
    {"id": "3", "url": "https://subs.example/de/3", "lang": "ger", "subtitleFileName": "Show.S01E02.de.srt"},
    {"id": "4", "url": "http://insecure.example/4", "lang": "eng", "subtitleFileName": "bad.srt"},
]}


class PublicClientTests(unittest.TestCase):
    def routes(self, **extra):
        routes = {
            ("GET", "/catalog/series/top/search=Show.json"): {"metas": [{"imdb_id": "tt123", "name": "Show", "releaseInfo": "2011-"}]},
            ("GET", "/subtitles/series/tt123:1:2/filename=Show.S01E02.720p.HDTV.mkv.json"): PUBLIC_SUBS,
            ("GET", "/en/1"): SRT,
        }
        routes.update(extra)
        return routes

    def test_search_resolves_title_then_filters_language_and_insecure_links(self):
        api = FakeApi(self.routes())
        results = opensubtitles.PublicSubtitleClient(urlopen=api).search("Show.S01E02.720p.HDTV.mkv", languages="en")
        self.assertEqual([r.fileId for r in results], ["1", "2"])
        self.assertEqual(results[0].language, "en")
        self.assertTrue(results[1].hearingImpaired)
        self.assertFalse(results[0].hearingImpaired)
        self.assertNotIn("0 downloads", results[0].describe())  # The public catalogue has no download counts
        self.assertIn("HI", results[1].describe())

    def test_other_languages_map_to_catalogue_codes(self):
        api = FakeApi(self.routes())
        results = opensubtitles.PublicSubtitleClient(urlopen=api).search("Show.S01E02.720p.HDTV.mkv", languages="de")
        self.assertEqual([(r.fileId, r.language) for r in results], [("3", "de")])

    def test_hash_and_size_are_sent_when_known(self):
        routes = self.routes()
        routes[("GET", "/subtitles/series/tt123:1:2/filename=Show.S01E02.720p.HDTV.mkv&videoHash=abc&videoSize=5.json")] = PUBLIC_SUBS
        api = FakeApi(routes)
        results = opensubtitles.PublicSubtitleClient(urlopen=api).search("Show.S01E02.720p.HDTV.mkv", "abc", 5, "en")
        self.assertEqual(len(results), 2)

    def test_unknown_title_is_a_friendly_error(self):
        api = FakeApi({("GET", "/catalog/series/top/search=Show.json"): {"metas": []}})
        with self.assertRaises(opensubtitles.OpenSubtitlesError):
            opensubtitles.PublicSubtitleClient(urlopen=api).search("Show.S01E02.mkv")

    def test_download_uses_the_result_url(self):
        api = FakeApi(self.routes())
        client = opensubtitles.PublicSubtitleClient(urlopen=api)
        result = client.search("Show.S01E02.720p.HDTV.mkv", languages="en")[0]
        self.assertEqual(client.download(result), ("Show.S01E02.720p.HDTV.srt", SRT))
        with self.assertRaises(opensubtitles.OpenSubtitlesError):
            client.download(opensubtitles.SubtitleResult(9, "x.srt", "t", "r", "en", 0, False, False))  # No url


class FakeProtocol(object):
    logged = True

    def __init__(self):
        self.sent = []

    def sendSubtitle(self, name, data, autoLoad=False):
        self.sent.append((name, data, autoLoad))


class PickFlowTests(unittest.TestCase):
    def setUp(self):
        from syncplay.client import SyncplayClient
        self.client = object.__new__(SyncplayClient)
        self.client.ui = FakeUI()
        self.client._subtitleStore = subtitles.SharedSubtitleStore()
        self.addCleanup(self.client._subtitleStore.cleanup)
        self.client.lastSharedSubtitle = None
        self.client.subtitleSearchResults = opensubtitles.parseSearchResults(SEARCH_PAYLOAD)
        self.client._player = FakePlayer(True)
        self.client._protocol = FakeProtocol()
        self.client.serverFeatures = {"subtitleSharing": True}
        self.client.getUsername = lambda: "me"

    def test_downloaded_subtitle_loads_locally_and_is_shared_with_autoload(self):
        self.client._subtitleDownloaded(("Show.srt", SRT))
        self.assertEqual(len(self.client._player.loaded), 1)
        name, data, autoLoad = self.client._protocol.sent[0]
        self.assertEqual((name, base64.b64decode(data), autoLoad), ("Show.srt", SRT, True))

    def test_wrong_extension_becomes_srt(self):
        self.client._subtitleDownloaded(("Show.txt", SRT))
        self.assertEqual(self.client._protocol.sent[0][0], "Show.srt")

    def test_server_without_feature_loads_locally_only(self):
        self.client.serverFeatures = {}
        self.client._subtitleDownloaded(("Show.srt", SRT))
        self.assertEqual(len(self.client._player.loaded), 1)
        self.assertEqual(self.client._protocol.sent, [])

    def test_received_picked_subtitle_autoloads_but_manual_share_does_not(self):
        data = base64.b64encode(SRT).decode()
        self.client.receivedSharedSubtitle("bob", "a.srt", data, autoLoad=True)
        self.assertEqual(len(self.client._player.loaded), 1)
        self.client.receivedSharedSubtitle("bob", "b.srt", data)
        self.assertEqual(len(self.client._player.loaded), 1)

    def test_autoload_can_be_switched_off(self):
        constants.AUTO_LOAD_PICKED_SUBTITLES = False
        self.addCleanup(setattr, constants, "AUTO_LOAD_PICKED_SUBTITLES", True)
        self.client.receivedSharedSubtitle("bob", "a.srt", base64.b64encode(SRT).decode(), autoLoad=True)
        self.assertEqual(self.client._player.loaded, [])

    def test_pick_rejects_bad_numbers(self):
        for bad in ("0", "99", "abc", None):
            self.client.pickSubtitle(bad)
        self.assertEqual(len(self.client.ui.errors), 4)

    def test_results_are_listed_and_lookup_errors_reported(self):
        self.client._subtitleResultsFound(self.client.subtitleSearchResults)
        self.assertIn("1:", self.client.ui.messages[0])
        self.client._subtitleLookupFailed(Failure(opensubtitles.OpenSubtitlesError("nope")))
        self.assertEqual(self.client.ui.errors, ["nope"])


if __name__ == "__main__":
    unittest.main()


class ChatReferenceTests(unittest.TestCase):
    PUBLIC = opensubtitles.SubtitleResult("7", "Show.S01E02.720p.HDTV.srt", "t", "r", "en", 0, False, False,
                                          url="https://subs5.strem.io/en/download/subencoding-stremio-utf8/src-api/file/1952846466")

    def test_public_result_round_trips_through_a_chat_line(self):
        line = opensubtitles.buildChatReference(self.PUBLIC, 150)
        self.assertEqual(line, "Subtitle picked: Show.S01E02.720p.HDTV.srt (Syncplay sub: st:1952846466)")
        name, source, refId = opensubtitles.parseChatReference(line)
        result = opensubtitles.resultFromReference(name, source, refId)
        self.assertEqual(result.url, self.PUBLIC.url)  # Rebuilt from the strict template, not taken from the message

    def test_opensubtitles_com_result_uses_its_file_id(self):
        result = opensubtitles.SubtitleResult(4242, "a.srt", "t", "r", "en", 5, True, False)
        line = opensubtitles.buildChatReference(result, 150)
        self.assertTrue(line.endswith("(Syncplay sub: os:4242)"))
        rebuilt = opensubtitles.resultFromReference(*opensubtitles.parseChatReference(line))
        self.assertEqual((rebuilt.fileId, rebuilt.url), (4242, None))

    def test_long_names_are_trimmed_to_fit_and_still_parse(self):
        result = opensubtitles.SubtitleResult(1, "N" * 300 + ".srt", "t", "r", "en", 0, False, False)
        line = opensubtitles.buildChatReference(result, 100)
        self.assertLessEqual(len(line), 100)
        self.assertIsNotNone(opensubtitles.parseChatReference(line))

    def test_too_short_chat_limit_or_unshareable_result_gives_none(self):
        self.assertIsNone(opensubtitles.buildChatReference(self.PUBLIC, 50))
        odd = opensubtitles.SubtitleResult("x", "a.srt", "t", "r", "en", 0, False, False, url="https://evil.example/f")
        self.assertIsNone(opensubtitles.buildChatReference(odd, 150))

    def test_ordinary_chat_and_forged_references_are_not_matched(self):
        for text in ("hello", "Subtitle picked: x (Syncplay sub: st:abc)", "Subtitle picked: x (Syncplay sub: zz:1)",
                     "hey Subtitle picked: x (Syncplay sub: st:1)"):
            self.assertIsNone(opensubtitles.parseChatReference(text))


class ChatDeliveryTests(unittest.TestCase):
    def setUp(self):
        from syncplay.client import SyncplayClient
        self.client = object.__new__(SyncplayClient)
        self.client.ui = FakeUI()
        self.client._subtitleStore = subtitles.SharedSubtitleStore()
        self.addCleanup(self.client._subtitleStore.cleanup)
        self.client.lastSharedSubtitle = None
        self.client._player = FakePlayer(True)
        self.client._config = {}
        self.client.getUsername = lambda: "me"
        self.chat = []
        proto = FakeProtocol()
        proto.sendChatMessage = self.chat.append
        self.client._protocol = proto
        self.client.serverFeatures = {"chat": True, "subtitleSharing": False}
        from syncplay.client import SyncplayUser
        self.client.userlist = type("UL", (), {"currentUser": SyncplayUser("me", "room")})()
        self.result = ChatReferenceTests.PUBLIC

    def test_pick_on_a_stock_server_announces_in_chat_and_loads_locally(self):
        self.assertTrue(self.client.canShareSubtitles())
        self.client._subtitleDownloaded(("Show.srt", SRT), True, self.result)
        self.assertEqual(len(self.client._player.loaded), 1)
        self.assertEqual(self.chat, ["Subtitle picked: Show.S01E02.720p.HDTV.srt (Syncplay sub: st:1952846466)"])

    def test_server_side_file_relay_is_preferred_when_available(self):
        self.client.serverFeatures = {"chat": True, "subtitleSharing": True}
        self.client._subtitleDownloaded(("Show.srt", SRT), True, self.result)
        self.assertEqual(self.chat, [])
        self.assertEqual(len(self.client._protocol.sent), 1)

    def test_no_chat_and_no_relay_means_solo(self):
        self.client.serverFeatures = {"chat": False}
        self.assertFalse(self.client.canShareSubtitles())
        self.client._subtitleDownloaded(("Show.srt", SRT), True, self.result)
        self.assertEqual(self.chat, [])
        self.assertIn("only", self.client.ui.messages[-1].lower() + "only")

    def test_incoming_reference_is_consumed_downloaded_and_loaded(self):
        downloads = []
        self.client.downloadSubtitle = lambda result, share=True, load=True: (
            downloads.append((result.url, share, load)) or defer.succeed("x"))
        line = opensubtitles.buildChatReference(self.result, 150)
        self.assertTrue(self.client.handleSubtitleChatReference("bob", line))
        self.assertEqual(downloads, [(self.result.url, False, True)])

    def test_own_echo_ordinary_chat_and_keyless_os_refs(self):
        downloads = []
        self.client.downloadSubtitle = lambda *a, **k: downloads.append(a) or defer.succeed("x")
        line = opensubtitles.buildChatReference(self.result, 150)
        self.assertTrue(self.client.handleSubtitleChatReference("me", line))
        self.assertFalse(self.client.handleSubtitleChatReference("bob", "just chatting"))
        os_line = "Subtitle picked: a.srt (Syncplay sub: os:42)"
        self.assertTrue(self.client.handleSubtitleChatReference("bob", os_line))
        self.assertEqual(downloads, [])
        self.assertIn("API key", self.client.ui.messages[-1])

    def test_auto_load_off_downloads_but_does_not_load(self):
        calls = []
        self.client.downloadSubtitle = lambda result, share=True, load=True: calls.append(load) or defer.succeed("x")
        constants.AUTO_LOAD_PICKED_SUBTITLES = False
        self.addCleanup(setattr, constants, "AUTO_LOAD_PICKED_SUBTITLES", True)
        self.client.handleSubtitleChatReference("bob", opensubtitles.buildChatReference(self.result, 150))
        self.assertEqual(calls, [False])
