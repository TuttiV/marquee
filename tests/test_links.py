import unittest

from syncplay import links


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
