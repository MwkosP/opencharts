import unittest

import numpy as np

from opencandles.core.indicators import bollinger, heikin_ashi, sma


class IndicatorTests(unittest.TestCase):
    def test_sma_has_expected_warmup_and_values(self):
        actual = sma(np.array([1.0, 2.0, 3.0, 4.0]), 2)
        np.testing.assert_allclose(actual[1:], [1.5, 2.5, 3.5])
        self.assertTrue(np.isnan(actual[0]))

    def test_bollinger_is_flat_for_constant_prices(self):
        middle, upper, lower = bollinger(np.full(25, 5.0), n=20, k=2)
        np.testing.assert_allclose(middle[19:], 5.0)
        np.testing.assert_allclose(upper[19:], 5.0)
        np.testing.assert_allclose(lower[19:], 5.0)

    def test_heikin_ashi_does_not_mutate_raw_candles(self):
        raw = {
            "x": np.array([0.0, 1.0, 2.0]),
            "o": np.array([10.0, 12.0, 11.0]),
            "h": np.array([13.0, 14.0, 15.0]),
            "l": np.array([9.0, 10.0, 10.0]),
            "c": np.array([12.0, 11.0, 14.0]),
            "v": np.array([1.0, 2.0, 3.0]),
        }
        before = {name: values.copy() for name, values in raw.items()}

        display = heikin_ashi(raw)

        for name in raw:
            np.testing.assert_array_equal(raw[name], before[name])
        np.testing.assert_allclose(display["c"], [11.0, 11.75, 12.5])
        self.assertFalse(np.array_equal(display["o"], raw["o"]))


if __name__ == "__main__":
    unittest.main()
