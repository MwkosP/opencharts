import unittest

import numpy as np

from opencandles.core.orderflow import synthetic_footprint


class SyntheticFootprintTests(unittest.TestCase):
    def test_preserves_total_volume_per_candle(self):
        volume = np.array([120.0, 75.0])
        prices, bid, ask, step = synthetic_footprint(
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
        _, bid, ask, _ = synthetic_footprint(
            np.array([10.0]),
            np.array([12.0]),
            np.array([9.0]),
            np.array([11.8]),
            np.array([100.0]),
        )

        self.assertGreater(float(ask.sum()), float(bid.sum()))


if __name__ == "__main__":
    unittest.main()
