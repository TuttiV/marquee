"""Which shared links other people's apps open by themselves (trusted domains), TorBox's servers included."""
import unittest

from syncplay import constants
from syncplay.client import SyncplayClient


class Client(object):
    _isURITrustableAndTrusted = SyncplayClient._isURITrustableAndTrusted
    isURITrusted = SyncplayClient.isURITrusted
    isUntrustedTrustableURI = SyncplayClient.isUntrustedTrustableURI

    def __init__(self, trustedDomains=None, onlyTrusted=True):
        self._config = {"onlySwitchToTrustedDomains": onlyTrusted,
                        "trustedDomains": list(constants.DEFAULT_TRUSTED_DOMAINS if trustedDomains is None else trustedDomains)}


class TorBoxLinkTests(unittest.TestCase):
    def test_every_torbox_server_is_trusted_without_adding_it(self):
        client = Client()
        for url in ("https://nexus-280.weur.tb-cdn.st/dld/abc?token=x", "https://nexus-290.weur.tb-cdn.st/dld/def/Movie.mkv",
                    "https://store-031.eus.tb-cdn.st/zip/1", "https://NEXUS-12.WEUR.TB-CDN.ST/a", "https://cdn.torbox.app/x.mp4"):
            self.assertTrue(client.isURITrusted(url), url)
            self.assertFalse(client.isUntrustedTrustableURI(url), url)  # So no "Add ... as trusted domain" either

    def test_trusted_even_when_someone_emptied_their_list(self):
        self.assertTrue(Client(trustedDomains=[]).isURITrusted("https://nexus-280.weur.tb-cdn.st/dld/abc"))

    def test_lookalikes_are_not(self):
        client = Client()
        for url in ("https://tb-cdn.st.example.com/x.mkv", "https://eviltb-cdn.st/x.mkv", "https://torbox.app.example.org/x",
                    "https://example.com/nexus-280.weur.tb-cdn.st/x.mkv", "file:///home/x/nexus-1.weur.tb-cdn.st.mkv"):
            self.assertFalse(client.isURITrusted(url), url)


class UnchangedRulesTests(unittest.TestCase):
    def test_the_list_still_decides_for_everything_else(self):
        client = Client()
        self.assertTrue(client.isURITrusted("https://www.youtube.com/watch?v=1"))
        self.assertFalse(client.isURITrusted("https://example.com/video.mp4"))
        self.assertTrue(client.isUntrustedTrustableURI("https://example.com/video.mp4"))
        self.assertTrue(Client(trustedDomains=["*.example.com"]).isURITrusted("https://media.example.com/v.mp4"))

    def test_trusting_everything_still_trusts_everything(self):
        self.assertTrue(Client(onlyTrusted=False).isURITrusted("https://example.com/video.mp4"))


if __name__ == "__main__":
    unittest.main()
