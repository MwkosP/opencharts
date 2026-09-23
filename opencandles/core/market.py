"""Dummy live market and history generation."""

import math
import random
import time

import numpy as np

from opencandles.config import HISTORY_SEC, START_PRICE, VOLS

class MarketSim:
    """Live ticks: random walk with volatility regimes, drift and rare jumps."""

    def __init__(self, price):
        self.price = price
        self.vol = VOLS[1]
        self.trend = 0.0

    def tick(self):
        if random.random() < 0.0005:
            self.vol = random.choice(VOLS)
        if random.random() < 0.001:
            self.trend = random.gauss(0, 2e-7)
        ret = self.trend + self.vol * random.gauss(0, 1)
        if random.random() < 0.0015:
            ret += random.choice([-1, 1]) * self.vol * random.uniform(5, 10)
        self.price *= math.exp(ret)
        size = abs(random.gauss(0, 1)) * (1 + self.vol * 10000) * random.uniform(0.01, 0.5)
        return self.price, size


def generate_history(n_sec, start, k=3):
    """Vectorised version of MarketSim: n_sec one-second candles, k ticks each."""
    rng = np.random.default_rng()
    total = n_sec * k
    s = 10 / k                                              # live runs 10 ticks/s
    vol = np.repeat(rng.choice(VOLS, total // 2000 + 1), 2000)[:total] * math.sqrt(s)
    trend = np.repeat(rng.normal(0, 2e-7, total // 1000 + 1), 1000)[:total] * s
    ret = trend + vol * rng.standard_normal(total)
    jumps = rng.random(total) < 0.0015 * s
    n = int(jumps.sum())
    ret[jumps] += rng.choice([-1, 1], n) * vol[jumps] * rng.uniform(5, 10, n)

    prices = (start * np.exp(np.cumsum(ret))).reshape(n_sec, k)
    c = prices[:, -1]
    o = np.concatenate([[start], c[:-1]])
    h = np.maximum(prices.max(axis=1), o)
    l = np.minimum(prices.min(axis=1), o)
    size = (np.abs(rng.standard_normal(total)) * (1 + vol / math.sqrt(s) * 10000)
            * rng.uniform(0.01, 0.5, total))
    v = size.reshape(n_sec, k).sum(axis=1)
    return o, h, l, c, v


class Market:
    """Stores 1-second base candles; any timeframe is aggregated from them."""

    def __init__(self):
        now = int(time.time())
        self.t0 = (now - HISTORY_SEC) // 900 * 900          # aligned to every timeframe
        n = now - self.t0
        o, h, l, c, v = generate_history(n, START_PRICE)
        cap = n + 100_000
        self.cols = {name: np.zeros(cap) for name in "xohlcv"}
        for name, arr in zip("xohlcv", (np.arange(n, dtype=float), o, h, l, c, v)):
            self.cols[name][:n] = arr
        self.n = n
        self.first_open = o[0]
        self.sim = MarketSim(c[-1])

    def base(self):
        return {k: a[:self.n] for k, a in self.cols.items()}

    def tick(self):
        price, size = self.sim.tick()
        sec = int(time.time()) - self.t0
        C = self.cols
        if sec > C["x"][self.n - 1]:                         # a new second starts
            if self.n == len(C["x"]):
                for k in C:
                    C[k] = np.resize(C[k], len(C[k]) * 2)
            i = self.n
            prev = C["c"][i - 1]
            C["x"][i], C["o"][i], C["h"][i], C["l"][i], C["c"][i], C["v"][i] = sec, prev, prev, prev, prev, 0
            self.n += 1
        i = self.n - 1
        C["h"][i] = max(C["h"][i], price)
        C["l"][i] = min(C["l"][i], price)
        C["c"][i] = price
        C["v"][i] += size
        return sec, price, size
