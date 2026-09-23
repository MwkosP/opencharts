import unittest

import numpy as np

from opencandles.core.series import Series


class FakeMarket:
    def base(self):
        return {
            "x": np.array([0.0, 1.0, 2.0, 3.0]),
            "o": np.array([10.0, 11.0, 12.0, 13.0]),
            "h": np.array([11.0, 12.0, 13.0, 14.0]),
            "l": np.array([9.0, 10.0, 11.0, 12.0]),
            "c": np.array([10.5, 11.5, 12.5, 13.5]),
            "v": np.array([1.0, 2.0, 3.0, 4.0]),
        }


class SeriesTests(unittest.TestCase):
    def test_aggregates_base_candles_by_timeframe(self):
        data = Series(FakeMarket(), tf=2).data()

        np.testing.assert_array_equal(data["x"], [0.0, 2.0])
        np.testing.assert_array_equal(data["o"], [10.0, 12.0])
        np.testing.assert_array_equal(data["h"], [12.0, 14.0])
        np.testing.assert_array_equal(data["l"], [9.0, 11.0])
        np.testing.assert_array_equal(data["c"], [11.5, 13.5])
        np.testing.assert_array_equal(data["v"], [3.0, 7.0])

    def test_updates_current_bucket_then_appends_next(self):
        series = Series(FakeMarket(), tf=2)

        series.update(sec=3, price=15.0, size=2.0)
        self.assertEqual(series.h[-1], 15.0)
        self.assertEqual(series.c[-1], 15.0)
        self.assertEqual(series.v[-1], 9.0)

        series.update(sec=4, price=16.0, size=3.0)
        self.assertEqual(series.x[-1], 4.0)
        self.assertEqual(series.o[-1], 16.0)
        self.assertEqual(series.c[-1], 16.0)
        self.assertEqual(series.v[-1], 3.0)


if __name__ == "__main__":
    unittest.main()
