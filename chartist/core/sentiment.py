"""Synthetic market-sentiment series for the Sentiment workspace.

Demo approximations only — replace with real feeds when available.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


TICKERS = (
    ("SPY", "S&P 500"),
    ("QQQ", "Nasdaq 100"),
    ("IWM", "Russell 2000"),
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("NVDA", "NVIDIA"),
    ("TSLA", "Tesla"),
    ("META", "Meta"),
    ("AMZN", "Amazon"),
    ("BTC", "Bitcoin"),
)

PLATFORMS = (
    ("ALL", "All platforms"),
    ("X", "X (Twitter)"),
    ("REDDIT", "Reddit"),
    ("STOCKTWITS", "StockTwits"),
    ("YOUTUBE", "YouTube"),
    ("NEWS", "News comments"),
)

GAUGE_COMPONENTS = (
    ("Momentum", 0.22),
    ("Put / Call", 0.18),
    ("Breadth", 0.20),
    ("Volatility", 0.18),
    ("Safe haven", 0.12),
    ("Junk spread", 0.10),
)

# Very slow live pulse — sentiment “time” crawls.
LIVE_MS = 12_000


@dataclass(frozen=True)
class GaugeSnapshot:
    score: float  # 0..100
    label: str
    components: tuple[tuple[str, float], ...]  # name, 0..100
    history: np.ndarray  # recent daily scores


@dataclass(frozen=True)
class SocialRow:
    symbol: str
    name: str
    bullish: float  # 0..1
    mentions: int
    change_1h: float  # percentage points
    buzz: float  # relative volume 0..1


@dataclass(frozen=True)
class IndicatorSeries:
    """Named time series for the Indicators tab."""

    key: str
    title: str
    dates: np.ndarray
    values: np.ndarray
    secondary: np.ndarray | None = None
    secondary_title: str | None = None
    y_min: float | None = None
    y_max: float | None = None


@dataclass(frozen=True)
class SocialPost:
    post_id: str
    platform: str
    symbol: str
    time_index: float  # aligns with chart / series x
    time_label: str
    author: str
    text: str
    sentiment: float  # 0..100 fear/greed style
    likes: int


@dataclass(frozen=True)
class PostsSentimentSnapshot:
    score: float
    label: str
    history: np.ndarray  # 0..100 series
    dates: np.ndarray
    posts: tuple[SocialPost, ...]
    volume: np.ndarray  # post volume per day


def _gaugeLabel(score: float) -> str:
    if score < 20:
        return "Extreme Fear"
    if score < 40:
        return "Fear"
    if score < 60:
        return "Neutral"
    if score < 80:
        return "Greed"
    return "Extreme Greed"


def buildGauge(pulse: int = 0) -> GaugeSnapshot:
    """Fear & Greed–style composite with component breakdown + history."""
    rng = np.random.default_rng((4_201 + int(pulse) * 17) % (2**32))
    base = 48.0 + 18.0 * np.sin(pulse * 0.07) + rng.normal(0, 2.2)
    components = []
    weighted = 0.0
    for name, weight in GAUGE_COMPONENTS:
        value = float(
            np.clip(
                base
                + rng.normal(0, 9)
                + 6.0 * np.sin(pulse * 0.11 + weight * 20),
                4,
                96,
            )
        )
        components.append((name, value))
        weighted += value * weight
    score = float(np.clip(weighted, 0, 100))

    days = 90
    t = np.arange(days, dtype=float)
    history = (
        50
        + 22 * np.sin((t + pulse) * 0.08)
        + 8 * np.sin((t + pulse) * 0.21)
        + rng.normal(0, 3.5, size=days)
    )
    history = np.clip(history, 5, 95)
    history[-1] = score
    return GaugeSnapshot(
        score=score,
        label=_gaugeLabel(score),
        components=tuple(components),
        history=history.astype(float),
    )


def buildSocial(pulse: int = 0) -> list[SocialRow]:
    """Per-ticker social / retail sentiment board (Mentions tab)."""
    rng = np.random.default_rng((9_101 + int(pulse) * 41) % (2**32))
    rows: list[SocialRow] = []
    for index, (symbol, name) in enumerate(TICKERS):
        bias = 0.12 * np.sin(pulse * 0.13 + index * 0.7)
        bullish = float(np.clip(0.52 + bias + rng.normal(0, 0.06), 0.12, 0.92))
        mentions = int(
            max(
                40,
                rng.lognormal(mean=6.2, sigma=0.55)
                * (1.0 + 0.25 * np.sin(pulse * 0.2 + index)),
            )
        )
        change = float(rng.normal(0, 2.8) + 4.0 * bias)
        buzz = float(np.clip(mentions / 12_000.0, 0.05, 1.0))
        rows.append(
            SocialRow(
                symbol=symbol,
                name=name,
                bullish=bullish,
                mentions=mentions,
                change_1h=change,
                buzz=buzz,
            )
        )
    rows.sort(key=lambda row: row.mentions, reverse=True)
    return rows


def buildIndicators(pulse: int = 0, days: int = 120) -> list[IndicatorSeries]:
    """Many market-sentiment / internals indicators."""
    rng = np.random.default_rng((3_307 + int(pulse) * 13) % (2**32))
    dates = np.arange(days, dtype=float)
    drift = np.cumsum(rng.normal(0.02, 0.9, size=days))

    def series(base, amp, speed, noise, lo=None, hi=None):
        vals = (
            base
            + amp * np.sin((dates + pulse) * speed)
            + rng.normal(0, noise, size=days)
        )
        if lo is not None or hi is not None:
            vals = np.clip(vals, lo if lo is not None else -1e9, hi if hi is not None else 1e9)
        return vals.astype(float)

    ad = 1000 + drift * 40 + 80 * np.sin((dates + pulse) * 0.05)
    pct50 = series(55, 18, 0.06, 4, 8, 92)
    pct200 = series(52, 14, 0.04, 3, 12, 88)
    nh = series(80, 50, 0.07, 18, 5, 220)
    nl = series(55, 40, 0.065, 14, 3, 180)
    mcclellan = series(0, 120, 0.09, 25)
    tick = series(200, 400, 0.12, 80)
    trin = series(1.0, 0.35, 0.08, 0.08, 0.4, 2.4)
    vix = series(18, 7, 0.05, 1.2, 10, 45)
    skew = series(125, 12, 0.04, 3, 100, 160)
    put_call = series(0.95, 0.18, 0.11, 0.04, 0.55, 1.45)
    aaii_bull = series(38, 12, 0.09, 3.5, 15, 65)
    aaii_bear = series(32, 10, 0.09, 3.0, 12, 60)
    cot = series(0, 20, 0.07, 4)
    flows = series(0, 2.2, 0.13, 1.4)
    rsi_spy = series(52, 16, 0.07, 4, 15, 85)
    credit = series(320, 60, 0.05, 12, 180, 520)  # HY OAS bp
    cnn_fg = series(50, 22, 0.08, 3.5, 5, 95)

    return [
        IndicatorSeries("ad", "Advance / Decline", dates, ad),
        IndicatorSeries(
            "ma",
            "% stocks above MA",
            dates,
            pct50,
            secondary=pct200,
            secondary_title="200-day",
            y_min=0,
            y_max=100,
        ),
        IndicatorSeries(
            "nhl",
            "New highs / new lows",
            dates,
            nh,
            secondary=nl,
            secondary_title="New lows",
        ),
        IndicatorSeries("mcclellan", "McClellan Oscillator", dates, mcclellan),
        IndicatorSeries("tick", "NYSE TICK", dates, tick),
        IndicatorSeries("trin", "TRIN (Arms)", dates, trin, y_min=0.3, y_max=2.5),
        IndicatorSeries("vix", "VIX", dates, vix, y_min=8, y_max=50),
        IndicatorSeries("skew", "CBOE SKEW", dates, skew, y_min=95, y_max=165),
        IndicatorSeries("pc", "Equity put / call", dates, put_call, y_min=0.5, y_max=1.5),
        IndicatorSeries(
            "aaii",
            "AAII bull %",
            dates,
            aaii_bull,
            secondary=aaii_bear,
            secondary_title="Bear %",
            y_min=0,
            y_max=80,
        ),
        IndicatorSeries("cot", "COT net speculative", dates, cot),
        IndicatorSeries("flows", "Equity ETF flows ($B)", dates, flows),
        IndicatorSeries("rsi", "SPY RSI(14)", dates, rsi_spy, y_min=0, y_max=100),
        IndicatorSeries("credit", "HY OAS (bp)", dates, credit),
        IndicatorSeries("cnn", "Fear & Greed (hist.)", dates, cnn_fg, y_min=0, y_max=100),
    ]


def _postTexts(symbol: str, bullish: bool, rng: np.random.Generator) -> str:
    bull = (
        f"${symbol} looking strong into close",
        f"Loading more ${symbol} here — momentum intact",
        f"${symbol} breakout watch, volume confirming",
        f"Crowd long ${symbol}, dip buyers active",
    )
    bear = (
        f"${symbol} fading hard, sellers in control",
        f"Cutting ${symbol} — sentiment flipping risk-off",
        f"${symbol} rejection at highs, careful",
        f"Heavy ${symbol} chatter turning bearish",
    )
    pool = bull if bullish else bear
    return pool[int(rng.integers(0, len(pool)))]


def buildPostsSentiment(
    symbol: str = "SPY",
    platform: str = "ALL",
    pulse: int = 0,
    days: int = 90,
) -> PostsSentimentSnapshot:
    """Overall posts sentiment + fear/greed-like series for a platform/asset."""
    rng = np.random.default_rng(
        (abs(hash((symbol, platform, "posts"))) + int(pulse) * 7919) % (2**32)
    )
    dates = np.arange(days, dtype=float)
    bias = 0.08 * np.sin(pulse * 0.05 + abs(hash(symbol)) % 7)
    history = np.clip(
        50
        + 20 * np.sin((dates + pulse) * 0.09 + bias * 10)
        + 8 * np.sin((dates + pulse) * 0.22)
        + rng.normal(0, 4, size=days),
        5,
        95,
    )
    volume = np.clip(
        80 + 60 * np.sin((dates + pulse) * 0.07) + rng.normal(0, 15, size=days),
        10,
        None,
    )
    score = float(history[-1])

    platforms = [code for code, _ in PLATFORMS if code != "ALL"]
    authors = ("alpha_desk", "flow_hawk", "retail_rip", "macro_mike", "opts_owl", "tape_reader")
    posts: list[SocialPost] = []
    for day in range(days):
        n = int(max(1, rng.integers(1, 4)))
        for k in range(n):
            plat = (
                platform
                if platform != "ALL"
                else platforms[int(rng.integers(0, len(platforms)))]
            )
            sent = float(
                np.clip(history[day] + rng.normal(0, 12), 0, 100)
            )
            bullish = sent >= 50
            hour = int(rng.integers(8, 20))
            minute = int(rng.integers(0, 60))
            posts.append(
                SocialPost(
                    post_id=f"{symbol}-{plat}-{day}-{k}-{pulse}",
                    platform=plat,
                    symbol=symbol,
                    time_index=float(day) + hour / 24.0,
                    time_label=f"D{day:02d} {hour:02d}:{minute:02d}",
                    author=authors[int(rng.integers(0, len(authors)))],
                    text=_postTexts(symbol, bullish, rng),
                    sentiment=sent,
                    likes=int(rng.integers(2, 900)),
                )
            )
    posts.sort(key=lambda p: p.time_index, reverse=True)
    return PostsSentimentSnapshot(
        score=score,
        label=_gaugeLabel(score),
        history=history.astype(float),
        dates=dates,
        posts=tuple(posts[:220]),
        volume=volume.astype(float),
    )


def postsInRange(
    posts: tuple[SocialPost, ...] | list[SocialPost],
    x0: float,
    x1: float,
) -> list[SocialRow] | list[SocialPost]:
    """Filter posts whose time_index lies inside [x0, x1]."""
    lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
    return [p for p in posts if lo <= p.time_index <= hi]


def rangeSentimentSummary(posts: list[SocialPost]) -> dict:
    """Aggregate sentiment stats for a selected backtest window."""
    if not posts:
        return {
            "count": 0,
            "score": 50.0,
            "label": "Neutral",
            "bullish_pct": 50.0,
            "avg_likes": 0.0,
            "by_platform": {},
        }
    scores = np.array([p.sentiment for p in posts], dtype=float)
    score = float(scores.mean())
    bullish_pct = float((scores >= 50).mean() * 100.0)
    by_platform: dict[str, int] = {}
    for post in posts:
        by_platform[post.platform] = by_platform.get(post.platform, 0) + 1
    return {
        "count": len(posts),
        "score": score,
        "label": _gaugeLabel(score),
        "bullish_pct": bullish_pct,
        "avg_likes": float(np.mean([p.likes for p in posts])),
        "by_platform": by_platform,
    }


__all__ = [
    "GAUGE_COMPONENTS",
    "LIVE_MS",
    "PLATFORMS",
    "GaugeSnapshot",
    "IndicatorSeries",
    "PostsSentimentSnapshot",
    "SocialPost",
    "SocialRow",
    "TICKERS",
    "buildGauge",
    "buildIndicators",
    "buildPostsSentiment",
    "buildSocial",
    "postsInRange",
    "rangeSentimentSummary",
]
