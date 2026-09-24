import unittest

from chartist.views.news_view import parseFeed


class NewsFeedTests(unittest.TestCase):
    def test_parses_rss_article(self):
        payload = b"""
            <rss><channel><item>
                <title>Stocks rise after earnings beat</title>
                <link>https://example.com/story</link>
                <description><![CDATA[<b>Markets</b> moved higher.]]></description>
                <pubDate>Wed, 23 Sep 2026 12:00:00 GMT</pubDate>
            </item></channel></rss>
        """
        articles = parseFeed(payload, "Example", "Markets")

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].source, "Example")
        self.assertEqual(articles[0].category, "Earnings")
        self.assertEqual(articles[0].summary, "Markets moved higher.")
        self.assertEqual(articles[0].url, "https://example.com/story")

    def test_parses_atom_link_and_crypto_category(self):
        payload = b"""
            <feed xmlns="http://www.w3.org/2005/Atom">
                <entry>
                    <title>Bitcoin tests resistance</title>
                    <link href="https://example.com/bitcoin"/>
                    <summary>Digital assets update</summary>
                    <updated>2026-09-23T12:00:00Z</updated>
                </entry>
            </feed>
        """
        articles = parseFeed(payload, "Example", "Markets")

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].category, "Crypto")
        self.assertEqual(articles[0].url, "https://example.com/bitcoin")


if __name__ == "__main__":
    unittest.main()
