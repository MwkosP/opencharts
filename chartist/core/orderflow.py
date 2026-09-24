"""Order-flow aggregation helpers.

The current demo feed exposes OHLCV rather than individual bid/ask trades, so
these helpers produce deterministic visual approximations. A real feed can
replace them while keeping the chart renderers unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


EXCHANGES = (
    ("AGG", "Aggregated"),
    ("NASDAQ", "NASDAQ"),
    ("NYSE", "NYSE"),
    ("ARCA", "ARCA"),
    ("BATS", "BATS"),
    ("IEX", "IEX"),
)

# Per-venue size multipliers + microstructure bias for the demo book.
_EXCHANGE_PROFILE = {
    "AGG": {"size": 1.00, "spread": 1.00, "noise": 0.10},
    "NASDAQ": {"size": 0.42, "spread": 1.00, "noise": 0.16},
    "NYSE": {"size": 0.28, "spread": 1.05, "noise": 0.14},
    "ARCA": {"size": 0.18, "spread": 1.10, "noise": 0.20},
    "BATS": {"size": 0.14, "spread": 1.08, "noise": 0.22},
    "IEX": {"size": 0.08, "spread": 1.15, "noise": 0.12},
}


@dataclass(frozen=True)
class BookLevel:
    price: float
    size: float
    orders: int


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str
    exchange: str
    mid: float
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]

    @property
    def spread(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return self.asks[0].price - self.bids[0].price

    @property
    def imbalance(self) -> float:
        """Top-of-book size imbalance in [-1, 1], bid-heavy positive."""
        bid = self.bids[0].size if self.bids else 0.0
        ask = self.asks[0].size if self.asks else 0.0
        total = bid + ask
        if total <= 0:
            return 0.0
        return (bid - ask) / total


@dataclass(frozen=True)
class TapePrint:
    time_label: str
    price: float
    size: float
    side: str  # "buy" | "sell"
    exchange: str


def syntheticFootprint(o, h, l, c, volume, levels=8):
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


def _tickSize(mid: float) -> float:
    if mid >= 500:
        return 0.10
    if mid >= 100:
        return 0.05
    if mid >= 20:
        return 0.01
    return 0.005


def buildOrderBook(
    symbol: str,
    mid: float,
    exchange: str = "AGG",
    levels: int = 20,
    pulse: int = 0,
) -> OrderBookSnapshot:
    """
    L2 ladder with near-Gaussian size around mid (Binance-style depth shape).

    ``pulse`` nudges sizes so a timer can keep the book visually alive.
    """
    profile = _EXCHANGE_PROFILE.get(exchange, _EXCHANGE_PROFILE["AGG"])
    tick = _tickSize(mid) * profile["spread"]
    rng = np.random.default_rng(
        (abs(hash((symbol, exchange))) + int(pulse) * 9973) % (2**32)
    )

    # Half-normal from the touch: densest at best bid/ask, thinning outward.
    # Shape matches a normal distribution sliced at mid.
    indices = np.arange(levels, dtype=float)
    sigma = max(levels * 0.28, 1.5)
    shape = np.exp(-0.5 * (indices / sigma) ** 2)
    shape /= shape.max()

    # Live flutter + occasional larger clips/refills.
    flutter = 1.0 + profile["noise"] * rng.normal(0.0, 1.0, size=levels)
    flutter = np.clip(flutter, 0.45, 1.75)
    wave = 1.0 + 0.16 * np.sin(pulse * 0.85 + indices * 0.65)
    # Rare liquidity spikes a few levels deep (iceberg / wall feel).
    spikes = np.ones(levels)
    if levels >= 4:
        spike_at = int(rng.integers(2, min(levels, 12)))
        spikes[spike_at] = 1.0 + float(rng.uniform(0.8, 2.2))

    base = 9_500.0 * profile["size"]
    bid_sizes = np.maximum(12.0, base * shape * flutter * wave * spikes)
    # Ask side: correlated but not identical.
    ask_flutter = 1.0 + profile["noise"] * rng.normal(0.0, 1.0, size=levels)
    ask_flutter = np.clip(ask_flutter, 0.45, 1.75)
    ask_wave = 1.0 + 0.16 * np.sin(pulse * 0.85 + 1.7 + indices * 0.65)
    ask_spikes = np.ones(levels)
    if levels >= 4:
        spike_at = int(rng.integers(2, min(levels, 12)))
        ask_spikes[spike_at] = 1.0 + float(rng.uniform(0.8, 2.2))
    ask_sizes = np.maximum(12.0, base * 0.96 * shape * ask_flutter * ask_wave * ask_spikes)

    bids = []
    asks = []
    for index in range(levels):
        bid_size = round(float(bid_sizes[index]), 3)
        ask_size = round(float(ask_sizes[index]), 3)
        bids.append(
            BookLevel(
                price=round(mid - tick * (index + 1), 4),
                size=bid_size,
                orders=max(1, int(bid_size / 140)),
            )
        )
        asks.append(
            BookLevel(
                price=round(mid + tick * (index + 1), 4),
                size=ask_size,
                orders=max(1, int(ask_size / 140)),
            )
        )
    return OrderBookSnapshot(
        symbol=symbol,
        exchange=exchange,
        mid=float(mid),
        bids=tuple(bids),
        asks=tuple(asks),
    )



def buildTape(
    symbol: str,
    mid: float,
    exchange: str = "AGG",
    count: int = 80,
    pulse: int = 0,
) -> list[TapePrint]:
    """Synthetic time & sales prints clustered around mid."""
    profile = _EXCHANGE_PROFILE.get(exchange, _EXCHANGE_PROFILE["AGG"])
    tick = _tickSize(mid)
    rng = np.random.default_rng(
        (abs(hash((symbol, exchange, "tape"))) + int(pulse) * 7919) % (2**32)
    )
    venues = [code for code, _ in EXCHANGES if code != "AGG"]
    prints: list[TapePrint] = []
    price = mid
    seconds = 9 * 3600 + 31 * 60 + int(pulse)  # session clock drifts with pulse
    for _ in range(count):
        side = "buy" if rng.random() > 0.48 else "sell"
        jump = tick * int(rng.integers(0, 3))
        price = price + jump if side == "buy" else price - jump
        price = float(np.clip(price, mid - 12 * tick, mid + 12 * tick))
        size = float(
            max(1, int(rng.lognormal(mean=4.2, sigma=0.55) * profile["size"]))
        )
        venue = (
            exchange
            if exchange != "AGG"
            else venues[int(rng.integers(0, len(venues)))]
        )
        seconds += int(rng.integers(1, 4))
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        prints.append(
            TapePrint(
                time_label=f"{hours:02d}:{mins:02d}:{secs:02d}",
                price=round(price, 4),
                size=size,
                side=side,
                exchange=venue,
            )
        )
    prints.reverse()  # newest first
    return prints


def nextTapePrints(
    symbol: str,
    mid: float,
    exchange: str = "AGG",
    pulse: int = 0,
    count: int = 2,
) -> list[TapePrint]:
    """A few fresh prints for a live tape tick."""
    return buildTape(symbol, mid, exchange=exchange, count=count, pulse=pulse)


def buildFlowSeries(bars: int = 60, levels: int = 12):
    """Synthetic OHLCV + footprint rows + cumulative delta for Orderflow tab."""
    rng = np.random.default_rng(42)
    mid = 198.4
    closes = mid + np.cumsum(rng.normal(0, 0.35, size=bars))
    opens = np.roll(closes, 1)
    opens[0] = mid
    highs = np.maximum(opens, closes) + rng.uniform(0.05, 0.55, size=bars)
    lows = np.minimum(opens, closes) - rng.uniform(0.05, 0.55, size=bars)
    volume = rng.integers(8_000, 45_000, size=bars).astype(float)
    prices, bid, ask, step = syntheticFootprint(
        opens, highs, lows, closes, volume, levels=levels
    )
    delta = ask.sum(axis=1) - bid.sum(axis=1)
    cvd = np.cumsum(delta)
    return {
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volume,
        "prices": prices,
        "bid": bid,
        "ask": ask,
        "step": step,
        "delta": delta,
        "cvd": cvd,
    }


__all__ = [
    "BookLevel",
    "EXCHANGES",
    "OrderBookSnapshot",
    "TapePrint",
    "buildFlowSeries",
    "buildOrderBook",
    "buildTape",
    "nextTapePrints",
    "syntheticFootprint",
]
