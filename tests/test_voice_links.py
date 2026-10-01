import unittest

from syncplay import links, voice


class VoiceTests(unittest.TestCase):
    def test_new_links_are_unguessable_and_recognised(self):
        urls = {voice.newUrl() for _ in range(500)}
        self.assertEqual(len(urls), 500)
        for url in list(urls)[:50]:
            self.assertTrue(url.startswith("https://meet.jit.si/SyncplayMarquee-"))
            self.assertEqual(voice.find("Voice call: " + url + " see you"), url)

    def test_only_our_own_kind_of_link_is_picked_up(self):
        for text in (None, "", "https://meet.jit.si/SomethingElse", "https://evil.example/SyncplayMarquee-abcdefghijkl",
                     "http://meet.jit.si/SyncplayMarquee-abcdefghijkl", "https://meet.jit.si.evil.example/SyncplayMarquee-abcdefghijkl",
                     "https://meet.jit.si/SyncplayMarquee-short"):
            self.assertIsNone(voice.find(text), text)


class LinkTests(unittest.TestCase):
    def test_addresses_become_links_and_trailing_punctuation_stays_outside(self):
        self.assertEqual(links.linkify("see https://a.example/x?y=1&amp;z=2, ok"),
                         'see <a href="https://a.example/x?y=1&amp;z=2">https://a.example/x?y=1&amp;z=2</a>, ok')
        self.assertEqual(links.linkify("(http://b.example/p)."), '(<a href="http://b.example/p">http://b.example/p</a>).')

    def test_nothing_else_is_turned_into_a_link(self):
        for text in ("no links here", "javascript:alert(1)", "ftp://x.example/f", "file:///etc/passwd", "https://", "www.example.com"):
            self.assertEqual(links.linkify(text), text)

    def test_already_escaped_quotes_cannot_break_out_of_the_attribute(self):
        out = links.linkify("https://a.example/&quot;onmouseover=&quot;x")
        self.assertEqual(out.count('href="'), 1)
        self.assertNotIn('" onmouseover', out)


if __name__ == "__main__":
    unittest.main()
