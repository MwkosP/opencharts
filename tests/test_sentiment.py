import unittest

import numpy as np

from chartist.core.sentiment import (
    buildGauge,
    buildIndicators,
    buildPostsSentiment,
    buildSocial,
    postsInRange,
    rangeSentimentSummary,
)


class SentimentHelpersTests(unittest.TestCase):
    def test_gauge_score_in_range(self):
        snap = buildGauge(pulse=3)
        self.assertGreaterEqual(snap.score, 0.0)
        self.assertLessEqual(snap.score, 100.0)
        self.assertTrue(snap.label)
        self.assertEqual(len(snap.components), 6)
        self.assertEqual(len(snap.history), 90)

    def test_social_sorted_by_mentions(self):
        rows = buildSocial(pulse=1)
        self.assertGreaterEqual(len(rows), 5)
        mentions = [row.mentions for row in rows]
        self.assertEqual(mentions, sorted(mentions, reverse=True))
        for row in rows:
            self.assertGreaterEqual(row.bullish, 0.0)
            self.assertLessEqual(row.bullish, 1.0)

    def test_indicators_has_many_series(self):
        series = buildIndicators(pulse=0, days=60)
        self.assertGreaterEqual(len(series), 12)
        self.assertEqual(len(series[0].values), 60)

    def test_posts_sentiment_platform_and_range(self):
        snap = buildPostsSentiment(symbol="NVDA", platform="X", pulse=2, days=40)
        self.assertEqual(len(snap.history), 40)
        self.assertTrue(all(p.platform == "X" for p in snap.posts))
        selected = postsInRange(snap.posts, 10, 20)
        summary = rangeSentimentSummary(selected)
        self.assertIn("score", summary)
        self.assertGreaterEqual(summary["count"], 0)


if __name__ == "__main__":
    unittest.main()
