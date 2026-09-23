"""Pure NumPy chart indicators and candle transformations."""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def sma(a, n):
    out = np.full(len(a), np.nan)
    ok = ~np.isnan(a)
    if not ok.any():
        return out
    s = int(np.argmax(ok))
    b = a[s:]
    if len(b) >= n:
        cs = np.cumsum(np.insert(b, 0, 0.0))
        out[s + n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def ema(a, n=None, alpha=None, seed=None):
    """Exponential moving average, vectorised in chunks (fast and numerically safe)."""
    k = alpha if alpha is not None else 2 / (n + 1)
    q = 1 - k
    a = np.asarray(a, dtype=float)
    out = np.empty(len(a))
    prev = a[0] if seed is None else seed
    for s in range(0, len(a), 256):
        chunk = a[s:s + 256]
        pw = q ** np.arange(1, len(chunk) + 1)
        out[s:s + len(chunk)] = pw * (prev + k * np.cumsum(chunk / pw))
        prev = out[s + len(chunk) - 1]
    return out


def rma(a, n):                          # Wilder's smoothing (RSI, ATR)
    return ema(a, n, alpha=1 / n)


def rolling(a, n, fn):
    out = np.full(len(a), np.nan)
    if len(a) >= n:
        out[n - 1:] = fn(sliding_window_view(a, n), axis=1)
    return out


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up, dn = rma(np.clip(d, 0, None), n), rma(np.clip(-d, 0, None), n)
    return 100 - 100 / (1 + up / np.where(dn == 0, 1e-12, dn))


def macd(c, fast=12, slow=26, signal=9):
    m = ema(c, fast) - ema(c, slow)
    s = ema(m, signal)
    return m, s, m - s


def stochastic(h, l, c, n=14, k=3, d=3):
    hh, ll = rolling(h, n, np.max), rolling(l, n, np.min)
    raw = 100 * (c - ll) / np.where(hh - ll == 0, 1e-12, hh - ll)
    K = sma(raw, k)
    return K, sma(K, d)


def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return rma(tr, n)


def obv(c, v):
    return np.cumsum(np.sign(np.diff(c, prepend=c[0])) * v)


def bollinger(c, n=20, k=2):
    mid = sma(c, n)
    sd = rolling(c, n, np.std)
    return mid, mid + k * sd, mid - k * sd


def heikin_ashi(d):
    o, h, l, c = d["o"], d["h"], d["l"], d["c"]
    hc = (o + h + l + c) / 4
    ho0 = (o[0] + c[0]) / 2                  # ho[i] = (ho[i-1] + hc[i-1]) / 2
    ho = np.r_[ho0, ema(hc, alpha=0.5, seed=ho0)[:-1]]
    return {"x": d["x"], "o": ho, "h": np.maximum(h, np.maximum(ho, hc)),
            "l": np.minimum(l, np.minimum(ho, hc)), "c": hc, "v": d["v"]}
