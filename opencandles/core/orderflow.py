"""Order-flow aggregation helpers.

The current demo feed exposes OHLCV rather than individual bid/ask trades, so
``synthetic_footprint`` produces a deterministic visual approximation. A real
feed can replace this function while keeping the chart renderer unchanged.
"""

import numpy as np


def synthetic_footprint(o, h, l, c, volume, levels=8):
    """Split each candle's volume into deterministic bid/ask price rows."""
    o, h, l, c, volume = (
        np.asarray(values, dtype=float) for values in (o, h, l, c, volume)
    )
    if not (len(o) == len(h) == len(l) == len(c) == len(volume)):
        raise ValueError("OHLCV arrays must have the same length")
    if levels < 2:
        raise ValueError("levels must be at least 2")

    span = h - l
    fallback = np.maximum(np.abs(c) * 1e-6, 1e-9)
    safe_span = np.where(span > 0, span, fallback)
    step = safe_span / levels
    fractions = (np.arange(levels, dtype=float) + 0.5) / levels
    prices = l[:, None] + safe_span[:, None] * fractions

    # Concentrate activity near the middle while retaining volume at extremes.
    weights = np.exp(-2.4 * ((fractions - 0.5) / 0.5) ** 2)
    weights /= weights.sum()
    row_volume = np.maximum(volume, 0)[:, None] * weights[None, :]

    # Approximate aggressor balance from candle direction and location. This is
    # deliberately deterministic and must not be presented as exchange data.
    body_bias = np.clip((c - o) / safe_span, -1, 1)[:, None] * 0.28
    level_bias = (fractions[None, :] - 0.5) * 0.16
    ask_share = np.clip(0.5 + body_bias + level_bias, 0.08, 0.92)
    ask = row_volume * ask_share
    bid = row_volume - ask
    return prices, bid, ask, step
