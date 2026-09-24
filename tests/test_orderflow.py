import unittest

import numpy as np

from chartist.core.orderflow import (
    buildFlowSeries,
    buildOrderBook,
    buildTape,
    syntheticFootprint,
)


class SyntheticFootprintTests(unittest.TestCase):
    def test_preserves_total_volume_per_candle(self):
        volume = np.array([120.0, 75.0])
        prices, bid, ask, step = syntheticFootprint(
            np.array([10.0, 11.0]),
            np.array([12.0, 12.5]),
            np.array([9.0, 10.0]),
            np.array([11.5, 10.5]),
            volume,
            levels=6,
        )

        self.assertEqual(prices.shape, (2, 6))
        self.assertEqual(step.shape, (2,))
        np.testing.assert_allclose((bid + ask).sum(axis=1), volume)
        self.assertTrue(np.all(bid >= 0))
        self.assertTrue(np.all(ask >= 0))

    def test_up_candle_has_more_ask_than_bid_volume(self):
        _, bid, ask, _ = syntheticFootprint(
            np.array([10.0]),
            np.array([12.0]),
            np.array([9.0]),
            np.array([11.8]),
            np.array([100.0]),
        )

        self.assertGreater(float(ask.sum()), float(bid.sum()))


class OrderBookHelpersTests(unittest.TestCase):
    def test_aggregated_book_default_has_bids_and_asks(self):
        book = buildOrderBook("AAPL", 198.4, exchange="AGG", levels=12)
        self.assertEqual(book.exchange, "AGG")
        self.assertEqual(len(book.bids), 12)
        self.assertEqual(len(book.asks), 12)
        self.assertGreater(book.asks[0].price, book.bids[0].price)
        self.assertGreater(book.spread, 0.0)

    def test_venue_books_are_smaller_than_aggregated(self):
        agg = buildOrderBook("SPY", 560.0, exchange="AGG")
        iex = buildOrderBook("SPY", 560.0, exchange="IEX")
        agg_depth = sum(level.size for level in agg.bids)
        iex_depth = sum(level.size for level in iex.bids)
        self.assertGreater(agg_depth, iex_depth)

    def test_book_sizes_peak_near_touch_like_normal(self):
        book = buildOrderBook("AAPL", 198.4, exchange="AGG", levels=20, pulse=0)
        near = book.bids[0].size + book.asks[0].size
        far = book.bids[-1].size + book.asks[-1].size
        self.assertGreater(near, far * 1.5)

    def test_tape_and_flow_series(self):
        prints = buildTape("NVDA", 118.5, exchange="AGG", count=40)
        self.assertEqual(len(prints), 40)
        self.assertTrue(all(print_.side in {"buy", "sell"} for print_ in prints))
        series = buildFlowSeries(bars=30, levels=8)
        self.assertEqual(len(series["delta"]), 30)
        self.assertEqual(len(series["cvd"]), 30)


if __name__ == "__main__":
    unittest.main()
