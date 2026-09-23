"""Application and chart settings."""

SYMBOL = "DUMMY/USD"
TIMEFRAMES = [("1s", 1), ("5s", 5), ("15s", 15), ("1m", 60), ("5m", 300), ("15m", 900)]
DEFAULT_TF = 5
TICK_MS = 100               # a new price tick every 100 ms
RENDER_MS = 200             # redraw rate
HISTORY_SEC = 900 * 300     # fake history: 300 candles of 15m
MAX_BARS = 2000             # candles kept per timeframe
VISIBLE_CANDLES = 120       # default zoom
MIN_VISIBLE = 10
START_PRICE = 65_000.0

CHART_TYPES = [
    "Candles",
    "Footprint",
    "Hollow candles",
    "Bars",
    "Line",
    "Area",
    "Heikin Ashi",
]
DEFAULT_OVERLAYS = ["sma", "ema"]
DEFAULT_PANES = ["vol", "rsi"]

VOLS = [0.00002, 0.00004, 0.00007, 0.00012]       # per-tick volatility regimes
