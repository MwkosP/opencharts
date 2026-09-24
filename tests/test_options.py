"""Tests for the Options workspace helpers."""

import unittest

import numpy as np

from chartist.views.options_view import (
    UNDERLYINGS,
    buildChain,
    buildIvSmile,
    buildMetricSurface,
)


class OptionsHelpersTests(unittest.TestCase):
    def test_chain_builds_symmetric_quotes_around_spot(self):
        spot, quotes = buildChain("AAPL", "30D")
        self.assertEqual(spot, UNDERLYINGS["AAPL"]["spot"])
        self.assertEqual(len(quotes), 17)
        self.assertTrue(all(quote.call_ask >= quote.call_bid for quote in quotes))
        self.assertTrue(all(quote.put_ask >= quote.put_bid for quote in quotes))
        atm = min(quotes, key=lambda quote: abs(quote.strike - spot))
        self.assertGreater(atm.call_delta, 0.35)
        self.assertLess(atm.call_delta, 0.65)

    def test_metric_surfaces_for_iv_and_greeks(self):
        strikes, call_ivs, put_ivs = buildIvSmile("SPY", "60D")
        self.assertEqual(len(strikes), len(call_ivs))
        self.assertEqual(len(strikes), len(put_ivs))
        for metric in ("iv", "mid", "delta", "gamma", "theta", "vega"):
            expiries, surface_strikes, grid = buildMetricSurface(
                "NVDA", metric=metric, side="call"
            )
            self.assertEqual(len(expiries), 37)
            self.assertEqual(len(surface_strikes), 49)
            self.assertEqual(grid.shape, (37, 49))
            self.assertFalse(np.isnan(grid).any())

    def test_option_clusters_cover_chain(self):
        from chartist.views.options_view import buildOptionClusters

        clusters = buildOptionClusters("AAPL", "30D")
        self.assertEqual(len(clusters), 5)
        self.assertEqual(sum(cluster["count"] for cluster in clusters), 17)
        self.assertTrue(all(cluster["call_oi"] >= 0 for cluster in clusters))


if __name__ == "__main__":
    unittest.main()
