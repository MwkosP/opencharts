"""Timeframe aggregation for market candles."""

import numpy as np

from opencandles.config import MAX_BARS

class Series:
    """Candles of one timeframe (last MAX_BARS), kept up to date tick by tick."""

    def __init__(self, market, tf):
        self.tf = tf
        B = market.base()
        bucket = B["x"] // tf * tf
        starts = np.flatnonzero(np.r_[True, bucket[1:] != bucket[:-1]])[-MAX_BARS:]
        off = starts[0]
        rel = starts - off
        ends = np.r_[starts[1:] - 1, len(bucket) - 1]
        self.x = bucket[starts].astype(float)
        self.o = B["o"][starts].copy()
        self.h = np.maximum.reduceat(B["h"][off:], rel)
        self.l = np.minimum.reduceat(B["l"][off:], rel)
        self.c = B["c"][ends].copy()
        self.v = np.add.reduceat(B["v"][off:], rel)

    def update(self, sec, price, size):
        bucket = sec // self.tf * self.tf
        if bucket > self.x[-1]:
            trim = len(self.x) >= MAX_BARS
            for name, val in zip("xohlcv", (bucket, price, price, price, price, size)):
                arr = np.append(getattr(self, name), val)
                setattr(self, name, arr[1:] if trim else arr)
        else:
            self.h[-1] = max(self.h[-1], price)
            self.l[-1] = min(self.l[-1], price)
            self.c[-1] = price
            self.v[-1] += size

    def data(self):
        return {"x": self.x, "o": self.o, "h": self.h, "l": self.l, "c": self.c, "v": self.v}
