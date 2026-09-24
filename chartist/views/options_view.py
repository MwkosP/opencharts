"""Options workspace with Chain, Volatility, Surfaces, and Strategies tabs."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from chartist.theme import BORDER, DRAW, FG, MUTED, UP, DOWN

# Options content chrome — Surfaces must match the tab, never a darker inset.
_TAB_BG = "#090c12"


UNDERLYINGS = {
    "AAPL": {"name": "Apple Inc.", "spot": 198.40, "iv": 0.28},
    "MSFT": {"name": "Microsoft Corp.", "spot": 428.10, "iv": 0.24},
    "NVDA": {"name": "NVIDIA Corp.", "spot": 118.55, "iv": 0.42},
    "SPY": {"name": "SPDR S&P 500 ETF", "spot": 562.80, "iv": 0.15},
    "TSLA": {"name": "Tesla Inc.", "spot": 248.90, "iv": 0.51},
}

EXPIRIES = ("7D", "14D", "30D", "60D", "90D")
EXPIRY_YEARS = {"7D": 7 / 365, "14D": 14 / 365, "30D": 30 / 365, "60D": 60 / 365, "90D": 90 / 365}
RATE = 0.045


@dataclass(frozen=True)
class OptionQuote:
    strike: float
    call_bid: float
    call_ask: float
    call_mid: float
    call_iv: float
    call_delta: float
    call_gamma: float
    call_theta: float
    call_vega: float
    put_bid: float
    put_ask: float
    put_mid: float
    put_iv: float
    put_delta: float
    put_gamma: float
    put_theta: float
    put_vega: float
    call_oi: int
    put_oi: int
    call_volume: int
    put_volume: int


def _normCdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _normPdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _blackScholes(spot, strike, years, rate, iv, call=True):
    if years <= 1e-8 or iv <= 1e-8:
        intrinsic = max(0.0, spot - strike) if call else max(0.0, strike - spot)
        delta = 1.0 if (call and spot > strike) else (-1.0 if (not call and spot < strike) else 0.0)
        return intrinsic, delta, 0.0, 0.0, 0.0
    sqrt_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * years) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t
    discount = math.exp(-rate * years)
    if call:
        price = spot * _normCdf(d1) - strike * discount * _normCdf(d2)
        delta = _normCdf(d1)
        theta = (
            -(spot * _normPdf(d1) * iv) / (2 * sqrt_t)
            - rate * strike * discount * _normCdf(d2)
        ) / 365.0
    else:
        price = strike * discount * _normCdf(-d2) - spot * _normCdf(-d1)
        delta = _normCdf(d1) - 1.0
        theta = (
            -(spot * _normPdf(d1) * iv) / (2 * sqrt_t)
            + rate * strike * discount * _normCdf(-d2)
        ) / 365.0
    gamma = _normPdf(d1) / (spot * iv * sqrt_t)
    vega = spot * _normPdf(d1) * sqrt_t / 100.0
    return max(0.01, price), delta, gamma, theta, vega


def _skewedIv(base_iv: float, spot: float, strike: float, years: float) -> float:
    moneyness = math.log(strike / spot)
    # Stronger smile/skew so the 3D surface reads like a Bloomberg vol surface.
    skew = -0.35 * moneyness
    smile = 1.35 * moneyness * moneyness
    term = 0.08 * (0.35 - years)
    wings = 0.45 * abs(moneyness) ** 1.35
    return max(0.08, base_iv + skew + smile + term + wings)


def buildChain(symbol: str, expiry: str) -> tuple[float, list[OptionQuote]]:
    meta = UNDERLYINGS[symbol]
    spot = meta["spot"]
    years = EXPIRY_YEARS[expiry]
    base_iv = meta["iv"]
    step = 5.0 if spot >= 200 else (2.5 if spot >= 80 else 1.0)
    center = round(spot / step) * step
    strikes = [center + step * offset for offset in range(-8, 9)]
    quotes = []
    for index, strike in enumerate(strikes):
        call_iv = _skewedIv(base_iv, spot, strike, years)
        put_iv = _skewedIv(base_iv * 1.02, spot, strike, years)
        call_mid, call_delta, call_gamma, call_theta, call_vega = _blackScholes(
            spot, strike, years, RATE, call_iv, call=True
        )
        put_mid, put_delta, put_gamma, put_theta, put_vega = _blackScholes(
            spot, strike, years, RATE, put_iv, call=False
        )
        spread = max(0.05, call_mid * 0.03)
        put_spread = max(0.05, put_mid * 0.03)
        distance = abs(index - 8)
        quotes.append(
            OptionQuote(
                strike=strike,
                call_bid=max(0.01, call_mid - spread / 2),
                call_ask=call_mid + spread / 2,
                call_mid=call_mid,
                call_iv=call_iv,
                call_delta=call_delta,
                call_gamma=call_gamma,
                call_theta=call_theta,
                call_vega=call_vega,
                put_bid=max(0.01, put_mid - put_spread / 2),
                put_ask=put_mid + put_spread / 2,
                put_mid=put_mid,
                put_iv=put_iv,
                put_delta=put_delta,
                put_gamma=put_gamma,
                put_theta=put_theta,
                put_vega=put_vega,
                call_oi=18_000 - distance * 1_100,
                put_oi=16_500 - distance * 950,
                call_volume=4_200 - distance * 220,
                put_volume=3_800 - distance * 200,
            )
        )
    return spot, quotes


def buildIvSmile(symbol: str, expiry: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    spot, quotes = buildChain(symbol, expiry)
    strikes = np.array([quote.strike for quote in quotes], dtype=float)
    call_ivs = np.array([quote.call_iv * 100 for quote in quotes], dtype=float)
    put_ivs = np.array([quote.put_iv * 100 for quote in quotes], dtype=float)
    return strikes, call_ivs, put_ivs


SURFACE_METRICS = (
    ("iv", "Implied volatility"),
    ("mid", "Mid price"),
    ("delta", "Delta"),
    ("gamma", "Gamma"),
    ("theta", "Theta"),
    ("vega", "Vega"),
)


def _metricFromQuote(quote: OptionQuote, metric: str, side: str) -> float:
    prefix = "call_" if side == "call" else "put_"
    if metric == "iv":
        return getattr(quote, f"{prefix}iv") * 100.0
    if metric == "mid":
        return getattr(quote, f"{prefix}mid")
    return getattr(quote, f"{prefix}{metric}")


def buildMetricSurface(
    symbol: str, metric: str = "iv", side: str = "call"
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Dense expiry × strike grid for the 3D surfaces view."""
    meta = UNDERLYINGS[symbol]
    spot = meta["spot"]
    base_iv = meta["iv"]
    # Finer + wider strike ladder than the chain table.
    step = 2.5 if spot >= 200 else (1.0 if spot >= 80 else 0.5)
    center = round(spot / step) * step
    strikes = np.array(
        [center + step * offset for offset in range(-24, 25)], dtype=float
    )
    # More tenors so the surface reads as a full term structure.
    day_ladder = list(range(5, 186, 5))  # 5D … 185D → 37 expiries
    expiries = [f"{days}D" for days in day_ladder]
    grid = np.zeros((len(day_ladder), len(strikes)), dtype=float)
    call = side == "call"
    for row, days in enumerate(day_ladder):
        years = days / 365.0
        for col, strike in enumerate(strikes):
            iv = _skewedIv(
                base_iv if call else base_iv * 1.02, spot, float(strike), years
            )
            mid, delta, gamma, theta, vega = _blackScholes(
                spot, float(strike), years, RATE, iv, call=call
            )
            if metric == "iv":
                grid[row, col] = iv * 100.0
            elif metric == "mid":
                grid[row, col] = mid
            elif metric == "delta":
                grid[row, col] = delta
            elif metric == "gamma":
                grid[row, col] = gamma
            elif metric == "theta":
                grid[row, col] = theta
            else:
                grid[row, col] = vega
    return expiries, strikes, grid


def buildIvSurface(symbol: str) -> tuple[list[str], np.ndarray, np.ndarray]:
    return buildMetricSurface(symbol, metric="iv", side="call")


STRATEGIES = (
    {
        "name": "Long Call",
        "bias": "Bullish",
        "legs": "Buy 1 ATM call",
        "max_loss": "Premium paid",
        "max_gain": "Unlimited",
        "summary": "Directional upside with defined risk equal to the debit paid.",
    },
    {
        "name": "Long Put",
        "bias": "Bearish",
        "legs": "Buy 1 ATM put",
        "max_loss": "Premium paid",
        "max_gain": "Strike − premium",
        "summary": "Directional downside hedge or speculation with capped risk.",
    },
    {
        "name": "Bull Call Spread",
        "bias": "Moderately bullish",
        "legs": "Buy ATM call · Sell OTM call",
        "max_loss": "Net debit",
        "max_gain": "Width − debit",
        "summary": "Defined-risk upside. Lower cost than a naked long call.",
    },
    {
        "name": "Bear Put Spread",
        "bias": "Moderately bearish",
        "legs": "Buy ATM put · Sell OTM put",
        "max_loss": "Net debit",
        "max_gain": "Width − debit",
        "summary": "Defined-risk downside with a lower debit than a long put.",
    },
    {
        "name": "Iron Condor",
        "bias": "Neutral",
        "legs": "Sell OTM put spread · Sell OTM call spread",
        "max_loss": "Wing width − credit",
        "max_gain": "Net credit",
        "summary": "Range-bound income strategy that profits if price stays inside the short strikes.",
    },
    {
        "name": "Long Straddle",
        "bias": "Volatile",
        "legs": "Buy ATM call · Buy ATM put",
        "max_loss": "Total premium",
        "max_gain": "Unlimited",
        "summary": "Long volatility. Needs a large move in either direction to pay off.",
    },
)


class OptionsPlaceholder(QtWidgets.QWidget):
    def __init__(self, title: str, blurb: str, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        heading = QtWidgets.QLabel(title)
        heading.setObjectName("placeholderTitle")
        layout.addWidget(heading)
        status = QtWidgets.QLabel(blurb)
        status.setObjectName("placeholderStatus")
        status.setWordWrap(True)
        status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        status.setMaximumWidth(520)
        layout.addWidget(status)


class ChainTab(QtWidgets.QWidget):
    """Simulated options chain with calls / puts around spot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = "AAPL"
        self.expiry = "30D"
        self._buildUi()
        self._reload()

    def _buildUi(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("optionsToolbar")
        row = QtWidgets.QHBoxLayout(toolbar)
        row.setContentsMargins(14, 9, 14, 9)
        row.setSpacing(8)

        row.addWidget(QtWidgets.QLabel("Underlying"))
        self.symbolCombo = QtWidgets.QComboBox()
        for symbol, meta in UNDERLYINGS.items():
            self.symbolCombo.addItem(f"{symbol}  ·  {meta['name']}", symbol)
        self.symbolCombo.currentIndexChanged.connect(self._symbolChanged)
        row.addWidget(self.symbolCombo)

        row.addWidget(QtWidgets.QLabel("Expiry"))
        self.expiryCombo = QtWidgets.QComboBox()
        for expiry in EXPIRIES:
            self.expiryCombo.addItem(expiry, expiry)
        self.expiryCombo.setCurrentIndex(2)
        self.expiryCombo.currentIndexChanged.connect(self._expiryChanged)
        row.addWidget(self.expiryCombo)

        self.spotLabel = QtWidgets.QLabel()
        self.spotLabel.setObjectName("spotLabel")
        row.addWidget(self.spotLabel)
        row.addStretch()
        badge = QtWidgets.QLabel("SIMULATED")
        badge.setObjectName("demoBadge")
        row.addWidget(badge)
        root.addWidget(toolbar)

        self.table = QtWidgets.QTableWidget(0, 15)
        self.table.setObjectName("chainTable")
        self.table.setHorizontalHeaderLabels(
            [
                "Call bid",
                "Call ask",
                "Call IV",
                "Δ",
                "Γ",
                "Θ",
                "Vega",
                "Strike",
                "Put bid",
                "Put ask",
                "Put IV",
                "Δ",
                "Γ",
                "Θ",
                "Vega",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.table, 1)

    def _symbolChanged(self, index):
        self.symbol = self.symbolCombo.itemData(index)
        self._reload()

    def _expiryChanged(self, index):
        self.expiry = self.expiryCombo.itemData(index)
        self._reload()

    def _reload(self):
        spot, quotes = buildChain(self.symbol, self.expiry)
        self.spotLabel.setText(f"Spot  {spot:,.2f}")
        self.table.setRowCount(len(quotes))
        atm = min(quotes, key=lambda quote: abs(quote.strike - spot)).strike
        for row, quote in enumerate(quotes):
            values = (
                f"{quote.call_bid:.2f}",
                f"{quote.call_ask:.2f}",
                f"{quote.call_iv * 100:.1f}%",
                f"{quote.call_delta:.2f}",
                f"{quote.call_gamma:.4f}",
                f"{quote.call_theta:.3f}",
                f"{quote.call_vega:.3f}",
                f"{quote.strike:.1f}",
                f"{quote.put_bid:.2f}",
                f"{quote.put_ask:.2f}",
                f"{quote.put_iv * 100:.1f}%",
                f"{quote.put_delta:.2f}",
                f"{quote.put_gamma:.4f}",
                f"{quote.put_theta:.3f}",
                f"{quote.put_vega:.3f}",
            )
            for column, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
                if column == 7:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    if quote.strike == atm:
                        item.setForeground(QtGui.QColor("#9db4ff"))
                elif column < 7:
                    item.setForeground(QtGui.QColor(UP))
                else:
                    item.setForeground(QtGui.QColor(DOWN))
                self.table.setItem(row, column, item)
            if quote.strike == atm:
                for column in range(15):
                    self.table.item(row, column).setBackground(
                        QtGui.QColor("#151c2c")
                    )


class VolatilityTab(QtWidgets.QWidget):
    """IV smile for the selected underlying and expiry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = "AAPL"
        self.expiry = "30D"
        self._buildUi()
        self._reload()

    def _buildUi(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("optionsToolbar")
        row = QtWidgets.QHBoxLayout(toolbar)
        row.setContentsMargins(14, 9, 14, 9)
        row.setSpacing(8)
        row.addWidget(QtWidgets.QLabel("Underlying"))
        self.symbolCombo = QtWidgets.QComboBox()
        for symbol in UNDERLYINGS:
            self.symbolCombo.addItem(symbol, symbol)
        self.symbolCombo.currentIndexChanged.connect(self._symbolChanged)
        row.addWidget(self.symbolCombo)
        row.addWidget(QtWidgets.QLabel("Expiry"))
        self.expiryCombo = QtWidgets.QComboBox()
        for expiry in EXPIRIES:
            self.expiryCombo.addItem(expiry, expiry)
        self.expiryCombo.setCurrentIndex(2)
        self.expiryCombo.currentIndexChanged.connect(self._expiryChanged)
        row.addWidget(self.expiryCombo)
        row.addStretch()
        hint = QtWidgets.QLabel("Implied volatility smile · call vs put")
        hint.setObjectName("legendText")
        row.addWidget(hint)
        root.addWidget(toolbar)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#090c12")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("left", "IV %")
        self.plot.setLabel("bottom", "Strike")
        self.plot.addLegend(offset=(10, 10))
        self.callCurve = self.plot.plot(
            pen=pg.mkPen(UP, width=2), name="Call IV", symbol="o", symbolSize=6
        )
        self.putCurve = self.plot.plot(
            pen=pg.mkPen(DOWN, width=2), name="Put IV", symbol="t", symbolSize=6
        )
        self.spotLine = pg.InfiniteLine(
            angle=90, pen=pg.mkPen("#6f8cff", width=1, style=QtCore.Qt.PenStyle.DashLine)
        )
        self.plot.addItem(self.spotLine)
        root.addWidget(self.plot, 1)

    def _symbolChanged(self, index):
        self.symbol = self.symbolCombo.itemData(index)
        self._reload()

    def _expiryChanged(self, index):
        self.expiry = self.expiryCombo.itemData(index)
        self._reload()

    def _reload(self):
        strikes, call_ivs, put_ivs = buildIvSmile(self.symbol, self.expiry)
        spot = UNDERLYINGS[self.symbol]["spot"]
        self.callCurve.setData(strikes, call_ivs)
        self.putCurve.setData(strikes, put_ivs)
        self.spotLine.setPos(spot)


class _ColorLegend(QtWidgets.QWidget):
    """Vertical color scale next to the surface canvas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.low = 0.0
        self.high = 1.0
        self.label = ""
        self.setFixedWidth(54)
        self._stops = [
            QtGui.QColor("#2fae4a"),
            QtGui.QColor("#a8e63a"),
            QtGui.QColor("#f7e017"),
            QtGui.QColor("#f28c1c"),
            QtGui.QColor("#e6221f"),
        ]

    def setRange(self, low, high, label=""):
        self.low = float(low)
        self.high = float(high)
        self.label = label
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(self.rect(), QtGui.QColor(_TAB_BG))
            bar = QtCore.QRectF(8, 28, 14, max(1, self.height() - 56))
            gradient = QtGui.QLinearGradient(bar.topLeft(), bar.bottomLeft())
            for index, color in enumerate(self._stops):
                gradient.setColorAt(index / (len(self._stops) - 1), color)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRect(bar)
            painter.setPen(QtGui.QPen(QtGui.QColor("#c9d1d9")))
            font = painter.font()
            font.setPointSize(7)
            painter.setFont(font)
            painter.drawText(4, 16, self.label[:10])
            painter.drawText(26, int(bar.top()) + 8, f"{self.high:.1f}")
            painter.drawText(26, int(bar.bottom()), f"{self.low:.1f}")
        finally:
            painter.end()


class _SurfaceCanvas(QtWidgets.QWidget):
    """Projected 3D surface with far-side panes, scales, and hover projections."""

    _CMAP = [
        (0.00, (47, 174, 74)),
        (0.25, (168, 230, 58)),
        (0.50, (247, 224, 23)),
        (0.75, (242, 140, 28)),
        (1.00, (230, 34, 31)),
    ]
    # World extents for surface / panes.
    # Surface object (must stay inside pane insets with clear margin).
    _SX0, _SX1 = -8.0, 8.0
    _SY0, _SY1 = -6.0, 6.0
    _SZ0, _SZ1 = 0.0, 7.0
    # Outer plane positions + inset drawable sheets (always larger than object).
    _X_LO, _X_HI = -18.5, 18.5
    _Y_LO, _Y_HI = -15.0, 15.0
    _Z_LO, _Z_HI = -5.5, 14.0
    _GAP = 2.8
    _IX0, _IX1 = -15.5, 15.5
    _IY0, _IY1 = -12.5, 12.5
    _IZ0, _IZ1 = -3.0, 12.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setMouseTracking(True)
        self.grid = np.zeros((0, 0))
        self.strikes = np.zeros(0)
        self.expiries: list[str] = []
        self.azimuth = -55.0
        self.elevation = 24.0
        self.distance = 38.0
        self._drag = None
        self._z_low = 0.0
        self._z_high = 1.0
        self.x_label = "Strike"
        self.y_label = "Expiry"
        self.z_label = "Value"
        self._hover = None  # world point on surface or None
        self._tri_cache = []  # (world tri pts, screen poly bbox helpers)

    def setGrid(self, grid, strikes=None, expiries=None, z_label="Value"):
        self.grid = np.asarray(grid, dtype=float)
        self.z_label = z_label
        if strikes is not None:
            self.strikes = np.asarray(strikes, dtype=float)
        if expiries is not None:
            self.expiries = list(expiries)
        if self.grid.size:
            self._z_low = float(self.grid.min())
            self._z_high = float(self.grid.max())
        self._hover = None
        self.update()

    def resetView(self):
        self.azimuth = -55.0
        self.elevation = 24.0
        self.distance = 38.0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag = event.position()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            delta = event.position() - self._drag
            self._drag = event.position()
            self.azimuth = (self.azimuth + float(delta.x()) * 0.55) % 360.0
            self.elevation = (self.elevation - float(delta.y()) * 0.45) % 360.0
            self._hover = None
            self.update()
            event.accept()
            return
        self._hover = self._pickSurface(event.position())
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._hover = None
        self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120.0
        self.distance = float(np.clip(self.distance * (0.90 ** steps), 12.0, 100.0))
        self.update()
        event.accept()

    def _color(self, amount):
        amount = float(np.clip(amount, 0.0, 1.0))
        for index in range(len(self._CMAP) - 1):
            a0, c0 = self._CMAP[index]
            a1, c1 = self._CMAP[index + 1]
            if amount <= a1:
                t = 0.0 if a1 == a0 else (amount - a0) / (a1 - a0)
                rgb = tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
                return QtGui.QColor(*rgb)
        return QtGui.QColor(*self._CMAP[-1][1])

    def _project(self, points):
        pts = np.asarray(points, dtype=float)
        if pts.ndim == 1:
            pts = pts.reshape(1, 3)
        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)
        ca, sa = math.cos(az), math.sin(az)
        ce, se = math.cos(el), math.sin(el)
        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
        x1 = x * ca - y * sa
        y1 = x * sa + y * ca
        y2 = y1 * ce - z * se
        z2 = y1 * se + z * ce
        depth = np.maximum(self.distance - y2, 0.5)
        focal = min(self.width(), self.height()) * 0.92
        cx = self.width() * 0.50
        cy = self.height() * 0.54
        sx = cx + x1 * focal / depth
        sy = cy - z2 * focal / depth
        return np.column_stack([sx, sy, depth])

    def _mean_depth(self, corners):
        return float(self._project(corners)[:, 2].mean())

    def _far_coord(self, lo, hi, build_lo, build_hi):
        """Pick the face that sits farther from the camera (always behind the object)."""
        d_lo = self._mean_depth(build_lo(lo))
        d_hi = self._mean_depth(build_hi(hi))
        return lo if d_lo >= d_hi else hi

    def _pane_geometry(self):
        gap = self._GAP
        x0, x1 = self._IX0, self._IX1
        y0, y1 = self._IY0, self._IY1
        z0, z1 = self._IZ0, self._IZ1

        def x_face(xv):
            return np.array(
                [
                    [xv, y0 + gap, z0 + gap],
                    [xv, y1 - gap, z0 + gap],
                    [xv, y1 - gap, z1 - gap],
                    [xv, y0 + gap, z1 - gap],
                ],
                dtype=float,
            )

        def y_face(yv):
            return np.array(
                [
                    [x0 + gap, yv, z0 + gap],
                    [x1 - gap, yv, z0 + gap],
                    [x1 - gap, yv, z1 - gap],
                    [x0 + gap, yv, z1 - gap],
                ],
                dtype=float,
            )

        def z_face(zv):
            return np.array(
                [
                    [x0 + gap, y0 + gap, zv],
                    [x1 - gap, y0 + gap, zv],
                    [x1 - gap, y1 - gap, zv],
                    [x0 + gap, y1 - gap, zv],
                ],
                dtype=float,
            )

        x_plane = self._far_coord(self._X_LO, self._X_HI, x_face, x_face)
        y_plane = self._far_coord(self._Y_LO, self._Y_HI, y_face, y_face)
        z_plane = self._far_coord(self._Z_LO, self._Z_HI, z_face, z_face)

        return [
            {
                "axis": "x",
                "const": float(x_plane),
                "label": self.x_label,
                "corners": x_face(x_plane),
                "u": ("y", y0 + gap, y1 - gap),
                "v": ("z", z0 + gap, z1 - gap),
            },
            {
                "axis": "y",
                "const": float(y_plane),
                "label": self.y_label,
                "corners": y_face(y_plane),
                "u": ("x", x0 + gap, x1 - gap),
                "v": ("z", z0 + gap, z1 - gap),
            },
            {
                "axis": "z",
                "const": float(z_plane),
                "label": self.z_label,
                "corners": z_face(z_plane),
                "u": ("x", x0 + gap, x1 - gap),
                "v": ("y", y0 + gap, y1 - gap),
            },
        ]

    def _world_point(self, x=None, y=None, z=None, axis=None, const=None):
        pt = [0.0, 0.0, 0.0]
        if axis == "x":
            pt[0] = const
            pt[1] = y if y is not None else 0.0
            pt[2] = z if z is not None else 0.0
        elif axis == "y":
            pt[1] = const
            pt[0] = x if x is not None else 0.0
            pt[2] = z if z is not None else 0.0
        else:
            pt[2] = const
            pt[0] = x if x is not None else 0.0
            pt[1] = y if y is not None else 0.0
        return np.array(pt, dtype=float)

    def _data_to_world(self, strike_i, expiry_i, value):
        cols = max(self.grid.shape[1] - 1, 1)
        rows = max(self.grid.shape[0] - 1, 1)
        x = self._SX0 + (self._SX1 - self._SX0) * (strike_i / cols)
        y = self._SY0 + (self._SY1 - self._SY0) * (expiry_i / rows)
        span = max(self._z_high - self._z_low, 1e-9)
        z = self._SZ0 + (self._SZ1 - self._SZ0) * ((value - self._z_low) / span)
        return np.array([x, y, z], dtype=float)

    def _surface_mesh(self):
        """Triangles as (world3, amount, screen_proj)."""
        if self.grid.size == 0:
            return []
        rows, cols = self.grid.shape
        xs = np.linspace(self._SX0, self._SX1, cols)
        ys = np.linspace(self._SY0, self._SY1, rows)
        span = max(self._z_high - self._z_low, 1e-9)
        zz = self._SZ0 + (self.grid - self._z_low) / span * (self._SZ1 - self._SZ0)
        tris = []
        for r in range(rows - 1):
            for c in range(cols - 1):
                p00 = np.array([xs[c], ys[r], zz[r, c]])
                p10 = np.array([xs[c + 1], ys[r], zz[r, c + 1]])
                p01 = np.array([xs[c], ys[r + 1], zz[r + 1, c]])
                p11 = np.array([xs[c + 1], ys[r + 1], zz[r + 1, c + 1]])
                for tri in ((p00, p10, p11), (p00, p11, p01)):
                    world = np.asarray(tri, dtype=float)
                    proj = self._project(world)
                    amount = float(np.mean(world[:, 2] - self._SZ0) / (self._SZ1 - self._SZ0))
                    tris.append((world, amount, proj))
        return tris

    def _pickSurface(self, pos):
        """Nearest surface triangle under the cursor → world point."""
        if self.grid.size == 0:
            return None
        mx, my = float(pos.x()), float(pos.y())
        best = None
        best_d = 14.0  # px pick radius
        for world, _amount, proj in self._surface_mesh():
            # barycentric in screen space
            ax, ay = proj[0, 0], proj[0, 1]
            bx, by = proj[1, 0], proj[1, 1]
            cx, cy = proj[2, 0], proj[2, 1]
            denom = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(denom) < 1e-9:
                continue
            w1 = ((by - cy) * (mx - cx) + (cx - bx) * (my - cy)) / denom
            w2 = ((cy - ay) * (mx - cx) + (ax - cx) * (my - cy)) / denom
            w3 = 1.0 - w1 - w2
            if w1 < -0.02 or w2 < -0.02 or w3 < -0.02:
                # outside — use distance to centroid as fallback soft pick
                cx0 = (ax + bx + cx) / 3.0
                cy0 = (ay + by + cy) / 3.0
                dist = math.hypot(mx - cx0, my - cy0)
                if dist < best_d:
                    best_d = dist
                    best = world.mean(axis=0)
                continue
            point = w1 * world[0] + w2 * world[1] + w3 * world[2]
            # exact hit preferred
            return point
        return best

    def _format_tick(self, axis, t01):
        """Map 0..1 pane parameter to a display string."""
        t01 = float(np.clip(t01, 0.0, 1.0))
        if axis == "x":
            if self.strikes.size:
                value = float(self.strikes[0] + (self.strikes[-1] - self.strikes[0]) * t01)
                return f"{value:.0f}"
            return f"{t01:.1f}"
        if axis == "y":
            if self.expiries:
                index = int(round(t01 * (len(self.expiries) - 1)))
                return self.expiries[index]
            return f"{t01:.1f}"
        # z metric
        value = self._z_low + (self._z_high - self._z_low) * t01
        if abs(value) >= 100:
            return f"{value:.0f}"
        if abs(value) >= 10:
            return f"{value:.1f}"
        return f"{value:.2f}"

    def _draw_pane(self, painter, pane, n_grid=6):
        corners = pane["corners"]
        proj = self._project(corners)
        poly = QtGui.QPolygonF([QtCore.QPointF(p[0], p[1]) for p in proj])
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 255))
        painter.drawPolygon(poly)

        grid_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 110))
        grid_pen.setWidthF(1.0)
        painter.setPen(grid_pen)
        for t in np.linspace(0.0, 1.0, n_grid):
            a = corners[0] * (1 - t) + corners[1] * t
            b = corners[3] * (1 - t) + corners[2] * t
            pa, pb = self._project(np.vstack([a, b]))
            painter.drawLine(QtCore.QPointF(pa[0], pa[1]), QtCore.QPointF(pb[0], pb[1]))
            a = corners[0] * (1 - t) + corners[3] * t
            b = corners[1] * (1 - t) + corners[2] * t
            pa, pb = self._project(np.vstack([a, b]))
            painter.drawLine(QtCore.QPointF(pa[0], pa[1]), QtCore.QPointF(pb[0], pb[1]))

        border = QtGui.QPen(QtGui.QColor(255, 255, 255, 245))
        border.setWidthF(2.0)
        painter.setPen(border)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawPolygon(poly)

        self._draw_scales(painter, pane)
        self._draw_axis_name(painter, pane)

    def _draw_scales(self, painter, pane):
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QtGui.QPen(QtGui.QColor(200, 205, 215)))
        metrics = QtGui.QFontMetrics(font)
        u_axis, u0, u1 = pane["u"]
        v_axis, v0, v1 = pane["v"]
        const = pane["const"]
        axis = pane["axis"]
        obj = self._project([[0.0, 0.0, 3.5]])[0, :2]

        def place_label(screen_pt, text):
            outward = screen_pt[:2] - obj
            norm = float(np.linalg.norm(outward)) or 1.0
            outward = outward / norm * 14.0
            tw = metrics.horizontalAdvance(text)
            painter.drawText(
                QtCore.QPointF(
                    screen_pt[0] + outward[0] - tw * 0.5,
                    screen_pt[1] + outward[1] + 4,
                ),
                text,
            )

        # U-edge ticks (corners 0 → 1)
        for t in np.linspace(0.0, 1.0, 5):
            u = u0 + (u1 - u0) * t
            if axis == "x":
                p0 = np.array([const, u, v0])
                p1 = np.array([const, u, v0 + (v1 - v0) * 0.035])
            elif axis == "y":
                p0 = np.array([u, const, v0])
                p1 = np.array([u, const, v0 + (v1 - v0) * 0.035])
            else:
                p0 = np.array([u, v0, const])
                p1 = np.array([u, v0 + (v1 - v0) * 0.035, const])
            s0, s1 = self._project(np.vstack([p0, p1]))
            painter.drawLine(QtCore.QPointF(s0[0], s0[1]), QtCore.QPointF(s1[0], s1[1]))
            place_label(s0, self._format_tick(u_axis, t))

        # V-edge ticks (corners 0 → 3)
        for t in np.linspace(0.0, 1.0, 5):
            v = v0 + (v1 - v0) * t
            if axis == "x":
                p0 = np.array([const, u0, v])
                p1 = np.array([const, u0 + (u1 - u0) * 0.035, v])
            elif axis == "y":
                p0 = np.array([u0, const, v])
                p1 = np.array([u0 + (u1 - u0) * 0.035, const, v])
            else:
                p0 = np.array([u0, v, const])
                p1 = np.array([u0 + (u1 - u0) * 0.035, v, const])
            s0, s1 = self._project(np.vstack([p0, p1]))
            painter.drawLine(QtCore.QPointF(s0[0], s0[1]), QtCore.QPointF(s1[0], s1[1]))
            place_label(s0, self._format_tick(v_axis, t))

    def _draw_axis_name(self, painter, pane):
        """Axis name sits outside the plane, on the side away from the object."""
        corners = pane["corners"]
        mid = corners.mean(axis=0)
        pane_s = self._project([mid])[0, :2]
        obj_s = self._project([[0.0, 0.0, 3.5]])[0, :2]
        outward = pane_s - obj_s
        norm = float(np.linalg.norm(outward)) or 1.0
        outward = outward / norm

        edge_pts = self._project(corners)[:, :2]
        extents = [float((p - pane_s) @ outward) for p in edge_pts]
        pos = pane_s + outward * (max(extents) + 24.0)

        e0 = self._project(np.vstack([corners[0], corners[1]]))
        e1 = self._project(np.vstack([corners[0], corners[3]]))
        d0 = e0[1, :2] - e0[0, :2]
        d1 = e1[1, :2] - e1[0, :2]
        axis_vec = d0 if np.linalg.norm(d0) >= np.linalg.norm(d1) else d1
        angle = math.degrees(math.atan2(float(axis_vec[1]), float(axis_vec[0])))
        if angle > 90:
            angle -= 180
        elif angle < -90:
            angle += 180

        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        label = pane["label"]
        width = metrics.horizontalAdvance(label)
        painter.save()
        painter.translate(pos[0], pos[1])
        painter.rotate(angle)
        painter.setPen(QtGui.QPen(QtGui.QColor(235, 240, 250)))
        painter.drawText(QtCore.QPointF(-width * 0.5, metrics.ascent() * 0.35), label)
        painter.restore()

    def _draw_hover_projections(self, painter, panes, hover):
        """Full-span crosshair on every pane through the projected hover point."""
        hx, hy, hz = float(hover[0]), float(hover[1]), float(hover[2])
        pen = QtGui.QPen(QtGui.QColor(120, 190, 255, 230))
        pen.setWidthF(1.6)
        painter.setPen(pen)

        for pane in panes:
            axis = pane["axis"]
            const = pane["const"]
            u_axis, u0, u1 = pane["u"]
            v_axis, v0, v1 = pane["v"]
            coords = {"x": hx, "y": hy, "z": hz}
            cu = float(np.clip(coords[u_axis], u0, u1))
            cv = float(np.clip(coords[v_axis], v0, v1))

            def pt(u, v):
                if axis == "x":
                    return np.array([const, u, v], dtype=float)
                if axis == "y":
                    return np.array([u, const, v], dtype=float)
                return np.array([u, v, const], dtype=float)

            a, b = pt(u0, cv), pt(u1, cv)
            c, d = pt(cu, v0), pt(cu, v1)
            sa, sb = self._project(np.vstack([a, b]))
            sc, sd = self._project(np.vstack([c, d]))
            painter.drawLine(QtCore.QPointF(sa[0], sa[1]), QtCore.QPointF(sb[0], sb[1]))
            painter.drawLine(QtCore.QPointF(sc[0], sc[1]), QtCore.QPointF(sd[0], sd[1]))

        drop = QtGui.QPen(QtGui.QColor(120, 190, 255, 120))
        drop.setWidthF(1.0)
        drop.setStyle(QtCore.Qt.PenStyle.DashLine)
        painter.setPen(drop)
        for pane in panes:
            axis = pane["axis"]
            const = pane["const"]
            if axis == "x":
                target = np.array([const, hy, hz])
            elif axis == "y":
                target = np.array([hx, const, hz])
            else:
                target = np.array([hx, hy, const])
            s0, s1 = self._project(np.vstack([hover, target]))
            painter.drawLine(QtCore.QPointF(s0[0], s0[1]), QtCore.QPointF(s1[0], s1[1]))

        sp = self._project([hover])[0]
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(255, 255, 255, 230))
        painter.drawEllipse(QtCore.QPointF(sp[0], sp[1]), 4.0, 4.0)

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            painter.fillRect(self.rect(), QtGui.QColor(_TAB_BG))
            if self.grid.size == 0:
                return

            panes = self._pane_geometry()
            draw_list = []
            for pane in panes:
                depth = self._mean_depth(pane["corners"])
                draw_list.append((depth, "pane", pane, None))

            for world, amount, proj in self._surface_mesh():
                depth = float(proj[:, 2].mean())
                draw_list.append((depth, "tri", proj, amount))

            draw_list.sort(key=lambda item: -item[0])

            edge = QtGui.QPen(QtGui.QColor(15, 15, 15, 210))
            edge.setWidthF(0.7)
            for _, kind, payload, amount in draw_list:
                if kind == "pane":
                    self._draw_pane(painter, payload)
                else:
                    poly = QtGui.QPolygonF(
                        [QtCore.QPointF(p[0], p[1]) for p in payload]
                    )
                    painter.setPen(edge)
                    painter.setBrush(self._color(amount))
                    painter.drawPolygon(poly)

            if self._hover is not None:
                self._draw_hover_projections(painter, panes, self._hover)
        finally:
            painter.end()


class MetricSurface3D(QtWidgets.QWidget):
    """Bloomberg-style metric surface with floating axis panes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("metricSurfaceHost")
        self.setStyleSheet(f"QWidget#metricSurfaceHost {{ background: {_TAB_BG}; }}")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.canvas = _SurfaceCanvas()
        layout.addWidget(self.canvas, 1)

        self.legend = _ColorLegend()
        layout.addWidget(self.legend)

        self.expiries: list[str] = []
        self.strikes = np.zeros(0)
        self.grid = np.zeros((0, 0))
        self.metric_label = "Implied volatility"
        self.smile_row = 0
        self.term_col = 0

    def setSurface(self, expiries, strikes, grid, metric_label):
        self.expiries = list(expiries)
        self.strikes = np.asarray(strikes, dtype=float)
        self.grid = np.asarray(grid, dtype=float)
        self.metric_label = metric_label
        rows, cols = self.grid.shape if self.grid.size else (0, 0)
        if rows:
            self.smile_row = max(0, min(rows - 1, self.smile_row))
        if cols:
            self.term_col = max(0, min(cols - 1, self.term_col))
        z_name = self.metric_label.split("·")[0].strip() or "Value"
        self.canvas.setGrid(
            self.grid,
            strikes=self.strikes,
            expiries=self.expiries,
            z_label=z_name,
        )
        if self.grid.size:
            self.legend.setRange(float(self.grid.min()), float(self.grid.max()), z_name)
        else:
            self.legend.setRange(0, 1, "")

    def setSlices(self, smile_row: int, term_col: int):
        rows, cols = self.grid.shape if self.grid.size else (0, 0)
        if rows:
            self.smile_row = max(0, min(rows - 1, smile_row))
        if cols:
            self.term_col = max(0, min(cols - 1, term_col))

    def resetView(self):
        self.canvas.resetView()

    def _redraw(self):
        self.canvas.update()


class SurfacesTab(QtWidgets.QWidget):
    """Full-bleed Bloomberg-style 3D metric surfaces."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = "AAPL"
        self.metric = "iv"
        self.side = "call"
        self._buildUi()
        self._reload()

    def _buildUi(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("optionsToolbar")
        row = QtWidgets.QHBoxLayout(toolbar)
        row.setContentsMargins(14, 9, 14, 9)
        row.setSpacing(8)

        row.addWidget(QtWidgets.QLabel("Underlying"))
        self.symbolCombo = QtWidgets.QComboBox()
        for symbol in UNDERLYINGS:
            self.symbolCombo.addItem(symbol, symbol)
        self.symbolCombo.currentIndexChanged.connect(self._symbolChanged)
        row.addWidget(self.symbolCombo)

        row.addWidget(QtWidgets.QLabel("Metric"))
        self.metricCombo = QtWidgets.QComboBox()
        for key, label in SURFACE_METRICS:
            self.metricCombo.addItem(label, key)
        self.metricCombo.currentIndexChanged.connect(self._metricChanged)
        row.addWidget(self.metricCombo)

        row.addWidget(QtWidgets.QLabel("Side"))
        self.sideCombo = QtWidgets.QComboBox()
        self.sideCombo.addItem("Calls", "call")
        self.sideCombo.addItem("Puts", "put")
        self.sideCombo.currentIndexChanged.connect(self._sideChanged)
        row.addWidget(self.sideCombo)

        row.addStretch()
        hint = QtWidgets.QLabel("Drag rotate · Scroll zoom")
        hint.setObjectName("legendText")
        row.addWidget(hint)
        reset = QtWidgets.QPushButton("Reset view")
        row.addWidget(reset)
        root.addWidget(toolbar)

        self.surface = MetricSurface3D()
        self.surface.setMinimumSize(0, 0)
        root.addWidget(self.surface, 1)
        reset.clicked.connect(self.surface.resetView)

    def _symbolChanged(self, index):
        self.symbol = self.symbolCombo.itemData(index)
        self._reload()

    def _metricChanged(self, index):
        self.metric = self.metricCombo.itemData(index)
        self._reload()

    def _sideChanged(self, index):
        self.side = self.sideCombo.itemData(index)
        self._reload()

    def _reload(self):
        expiries, strikes, grid = buildMetricSurface(
            self.symbol, metric=self.metric, side=self.side
        )
        label = dict(SURFACE_METRICS).get(self.metric, self.metric)
        side_label = "Calls" if self.side == "call" else "Puts"
        self.surface.setSurface(
            expiries, strikes, grid, f"{label} · {side_label}"
        )


class StrategiesTab(QtWidgets.QWidget):
    """Common multi-leg option strategies with payoff sketches."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buildUi()
        self._showStrategy(0)

    def _buildUi(self):
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("strategyList")
        self.list.setFixedWidth(220)
        for strategy in STRATEGIES:
            self.list.addItem(strategy["name"])
        self.list.currentRowChanged.connect(self._showStrategy)
        root.addWidget(self.list)

        detail = QtWidgets.QWidget()
        detail.setObjectName("strategyDetail")
        layout = QtWidgets.QVBoxLayout(detail)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)
        self.title = QtWidgets.QLabel()
        self.title.setObjectName("strategyTitle")
        layout.addWidget(self.title)
        self.bias = QtWidgets.QLabel()
        self.bias.setObjectName("legendText")
        layout.addWidget(self.bias)
        self.summary = QtWidgets.QLabel()
        self.summary.setObjectName("strategySummary")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        facts = QtWidgets.QFormLayout()
        facts.setSpacing(8)
        self.legs = QtWidgets.QLabel()
        self.maxLoss = QtWidgets.QLabel()
        self.maxGain = QtWidgets.QLabel()
        for label in (self.legs, self.maxLoss, self.maxGain):
            label.setObjectName("factValue")
        facts.addRow("Legs", self.legs)
        facts.addRow("Max loss", self.maxLoss)
        facts.addRow("Max gain", self.maxGain)
        layout.addLayout(facts)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#090c12")
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.plot.setLabel("left", "P/L")
        self.plot.setLabel("bottom", "Underlying")
        self.payoffCurve = self.plot.plot(pen=pg.mkPen(DRAW, width=2))
        self.zeroLine = pg.InfiniteLine(
            angle=0, pen=pg.mkPen("#3a4250", width=1)
        )
        self.plot.addItem(self.zeroLine)
        layout.addWidget(self.plot, 1)
        root.addWidget(detail, 1)
        self.list.setCurrentRow(0)

    def _showStrategy(self, index):
        if index < 0 or index >= len(STRATEGIES):
            return
        strategy = STRATEGIES[index]
        self.title.setText(strategy["name"])
        self.bias.setText(strategy["bias"].upper())
        self.summary.setText(strategy["summary"])
        self.legs.setText(strategy["legs"])
        self.maxLoss.setText(strategy["max_loss"])
        self.maxGain.setText(strategy["max_gain"])
        prices, payoff = self._payoff(strategy["name"])
        self.payoffCurve.setData(prices, payoff)

    @staticmethod
    def _payoff(name: str) -> tuple[np.ndarray, np.ndarray]:
        spot = 100.0
        prices = np.linspace(70, 130, 200)
        if name == "Long Call":
            premium = 4.0
            payoff = np.maximum(prices - spot, 0) - premium
        elif name == "Long Put":
            premium = 4.0
            payoff = np.maximum(spot - prices, 0) - premium
        elif name == "Bull Call Spread":
            long_k, short_k, debit = 100.0, 110.0, 3.2
            payoff = (
                np.maximum(prices - long_k, 0)
                - np.maximum(prices - short_k, 0)
                - debit
            )
        elif name == "Bear Put Spread":
            long_k, short_k, debit = 100.0, 90.0, 3.2
            payoff = (
                np.maximum(long_k - prices, 0)
                - np.maximum(short_k - prices, 0)
                - debit
            )
        elif name == "Iron Condor":
            put_short, put_long = 90.0, 85.0
            call_short, call_long = 110.0, 115.0
            credit = 1.8
            put_spread = np.maximum(put_short - prices, 0) - np.maximum(
                put_long - prices, 0
            )
            call_spread = np.maximum(prices - call_short, 0) - np.maximum(
                prices - call_long, 0
            )
            payoff = credit - put_spread - call_spread
        else:  # Long Straddle
            premium = 8.0
            payoff = (
                np.maximum(prices - spot, 0) + np.maximum(spot - prices, 0) - premium
            )
        return prices, payoff


def _surfaceColorLut():
    """Green → yellow → red LUT for heatmap cells."""
    stops = np.array(
        [
            [47, 174, 74],
            [168, 230, 58],
            [247, 224, 23],
            [242, 140, 28],
            [230, 34, 31],
        ],
        dtype=float,
    )
    lut = np.zeros((256, 3), dtype=np.ubyte)
    for index in range(256):
        amount = index / 255.0
        pos = amount * (len(stops) - 1)
        lo = int(pos)
        hi = min(lo + 1, len(stops) - 1)
        t = pos - lo
        lut[index] = (stops[lo] * (1 - t) + stops[hi] * t).astype(np.ubyte)
    return lut


class HeatmapTab(QtWidgets.QWidget):
    """2D strike × expiry metric heatmap."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = "AAPL"
        self.metric = "iv"
        self.side = "call"
        self._lut = _surfaceColorLut()
        self._buildUi()
        self._reload()

    def _buildUi(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("optionsToolbar")
        row = QtWidgets.QHBoxLayout(toolbar)
        row.setContentsMargins(14, 9, 14, 9)
        row.setSpacing(8)

        row.addWidget(QtWidgets.QLabel("Underlying"))
        self.symbolCombo = QtWidgets.QComboBox()
        for symbol in UNDERLYINGS:
            self.symbolCombo.addItem(symbol, symbol)
        self.symbolCombo.currentIndexChanged.connect(self._symbolChanged)
        row.addWidget(self.symbolCombo)

        row.addWidget(QtWidgets.QLabel("Metric"))
        self.metricCombo = QtWidgets.QComboBox()
        for key, label in SURFACE_METRICS:
            self.metricCombo.addItem(label, key)
        self.metricCombo.currentIndexChanged.connect(self._metricChanged)
        row.addWidget(self.metricCombo)

        row.addWidget(QtWidgets.QLabel("Side"))
        self.sideCombo = QtWidgets.QComboBox()
        self.sideCombo.addItem("Calls", "call")
        self.sideCombo.addItem("Puts", "put")
        self.sideCombo.currentIndexChanged.connect(self._sideChanged)
        row.addWidget(self.sideCombo)
        row.addStretch()
        hint = QtWidgets.QLabel("Strike →  ·  Expiry ↑")
        hint.setObjectName("legendText")
        row.addWidget(hint)
        root.addWidget(toolbar)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#090c12")
        self.plot.setLabel("bottom", "Strike")
        self.plot.setLabel("left", "Expiry")
        self.image = pg.ImageItem()
        self.image.setLookupTable(self._lut)
        self.plot.addItem(self.image)
        root.addWidget(self.plot, 1)

    def _symbolChanged(self, index):
        self.symbol = self.symbolCombo.itemData(index)
        self._reload()

    def _metricChanged(self, index):
        self.metric = self.metricCombo.itemData(index)
        self._reload()

    def _sideChanged(self, index):
        self.side = self.sideCombo.itemData(index)
        self._reload()

    def _reload(self):
        expiries, strikes, grid = buildMetricSurface(
            self.symbol, metric=self.metric, side=self.side
        )
        data = np.asarray(grid.T, dtype=float)
        low, high = float(data.min()), float(data.max())
        self.image.setImage(data, levels=(low, high))
        self.image.setRect(
            QtCore.QRectF(
                float(strikes[0]),
                0.0,
                float(strikes[-1] - strikes[0]),
                float(len(expiries)),
            )
        )
        step = max(1, len(expiries) // 8)
        ticks = [
            (index + 0.5, label)
            for index, label in enumerate(expiries)
            if index % step == 0 or index == len(expiries) - 1
        ]
        self.plot.getAxis("left").setTicks([ticks])
        self.plot.setXRange(float(strikes[0]), float(strikes[-1]), padding=0.02)
        self.plot.setYRange(0.0, float(len(expiries)), padding=0.02)


def buildOptionClusters(symbol: str, expiry: str) -> list[dict]:
    """Bucket chain quotes by log-moneyness into liquidity clusters."""
    spot, quotes = buildChain(symbol, expiry)

    def moneyness(quote: OptionQuote) -> float:
        return math.log(quote.strike / spot)

    rules = (
        ("Deep OTM puts", lambda m: m < -0.08),
        ("OTM puts", lambda m: -0.08 <= m < -0.02),
        ("ATM", lambda m: -0.02 <= m < 0.02),
        ("OTM calls", lambda m: 0.02 <= m < 0.08),
        ("Deep OTM calls", lambda m: m >= 0.08),
    )
    clusters = []
    for name, predicate in rules:
        members = [quote for quote in quotes if predicate(moneyness(quote))]
        call_oi = sum(quote.call_oi for quote in members)
        put_oi = sum(quote.put_oi for quote in members)
        call_vol = sum(quote.call_volume for quote in members)
        put_vol = sum(quote.put_volume for quote in members)
        avg_iv = (
            float(np.mean([quote.call_iv for quote in members])) * 100.0
            if members
            else 0.0
        )
        clusters.append(
            {
                "name": name,
                "count": len(members),
                "call_oi": call_oi,
                "put_oi": put_oi,
                "call_volume": call_vol,
                "put_volume": put_vol,
                "avg_iv": avg_iv,
            }
        )
    return clusters


class ClustersTab(QtWidgets.QWidget):
    """Moneyness liquidity clusters for the selected chain."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = "AAPL"
        self.expiry = "30D"
        self._buildUi()
        self._reload()

    def _buildUi(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("optionsToolbar")
        row = QtWidgets.QHBoxLayout(toolbar)
        row.setContentsMargins(14, 9, 14, 9)
        row.setSpacing(8)

        row.addWidget(QtWidgets.QLabel("Underlying"))
        self.symbolCombo = QtWidgets.QComboBox()
        for symbol in UNDERLYINGS:
            self.symbolCombo.addItem(symbol, symbol)
        self.symbolCombo.currentIndexChanged.connect(self._symbolChanged)
        row.addWidget(self.symbolCombo)

        row.addWidget(QtWidgets.QLabel("Expiry"))
        self.expiryCombo = QtWidgets.QComboBox()
        for expiry in EXPIRIES:
            self.expiryCombo.addItem(expiry, expiry)
        self.expiryCombo.setCurrentIndex(2)
        self.expiryCombo.currentIndexChanged.connect(self._expiryChanged)
        row.addWidget(self.expiryCombo)
        row.addStretch()
        hint = QtWidgets.QLabel("OI / volume by moneyness cluster")
        hint.setObjectName("legendText")
        row.addWidget(hint)
        root.addWidget(toolbar)

        split = QtWidgets.QSplitter()
        split.setOrientation(QtCore.Qt.Orientation.Horizontal)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setObjectName("chainTable")
        self.table.setHorizontalHeaderLabels(
            ["Cluster", "Strikes", "Call OI", "Put OI", "Volume", "Avg IV"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        split.addWidget(self.table)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#090c12")
        self.plot.showGrid(x=True, y=False, alpha=0.12)
        self.plot.setLabel("bottom", "Open interest")
        self.plot.setLabel("left", "Cluster")
        self.callBars = pg.BarGraphItem(
            x0=[], y=[], height=0.35, width=[], brush=pg.mkBrush(UP)
        )
        self.putBars = pg.BarGraphItem(
            x0=[], y=[], height=0.35, width=[], brush=pg.mkBrush(DOWN)
        )
        self.plot.addItem(self.callBars)
        self.plot.addItem(self.putBars)
        split.addWidget(self.plot)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 4)
        root.addWidget(split, 1)

    def _symbolChanged(self, index):
        self.symbol = self.symbolCombo.itemData(index)
        self._reload()

    def _expiryChanged(self, index):
        self.expiry = self.expiryCombo.itemData(index)
        self._reload()

    def _reload(self):
        clusters = buildOptionClusters(self.symbol, self.expiry)
        self.table.setRowCount(len(clusters))
        names = []
        call_oi = []
        put_oi = []
        for row, cluster in enumerate(clusters):
            names.append(cluster["name"])
            call_oi.append(cluster["call_oi"])
            put_oi.append(cluster["put_oi"])
            values = (
                cluster["name"],
                str(cluster["count"]),
                f"{cluster['call_oi']:,}",
                f"{cluster['put_oi']:,}",
                f"{cluster['call_volume'] + cluster['put_volume']:,}",
                f"{cluster['avg_iv']:.1f}%",
            )
            for column, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if column == 0:
                    item.setTextAlignment(
                        int(QtCore.Qt.AlignmentFlag.AlignLeft)
                        | int(QtCore.Qt.AlignmentFlag.AlignVCenter)
                    )
                else:
                    item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

        ys = np.arange(len(clusters))
        call_w = np.asarray(call_oi, dtype=float)
        put_w = np.asarray(put_oi, dtype=float)
        self.callBars.setOpts(
            x0=np.zeros(len(clusters)),
            y=ys + 0.18,
            height=0.32,
            width=call_w,
        )
        self.putBars.setOpts(
            x0=np.zeros(len(clusters)),
            y=ys - 0.18,
            height=0.32,
            width=put_w,
        )
        ticks = [(float(index), name) for index, name in enumerate(names)]
        self.plot.getAxis("left").setTicks([ticks])
        max_oi = float(max(call_w.max(initial=0), put_w.max(initial=0), 1.0))
        self.plot.setXRange(0.0, max_oi * 1.08, padding=0.0)
        self.plot.setYRange(-0.6, len(clusters) - 0.4, padding=0.0)


class OptionsView(QtWidgets.QWidget):
    """Container for options analysis subtabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("optionsView")
        self.setStyleSheet(f"""
            QWidget#optionsView, QWidget#optionsView QWidget {{
                color: {FG};
                background: #090c12;
            }}
            QWidget#optionsView *:focus {{
                outline: none;
            }}
            QTabWidget#optionsTabs {{
                border: 0px;
                background: #090c12;
                outline: none;
            }}
            QTabWidget#optionsTabs::pane {{
                border: 0px;
                margin: 0px;
                padding: 0px;
                background: #090c12;
            }}
            QTabWidget#optionsTabs > QTabBar {{
                border: 0px;
                outline: none;
                background: #090c12;
            }}
            QTabWidget#optionsTabs > QTabBar::tab {{
                color: {MUTED};
                background: #090c12;
                border: 0px;
                outline: none;
                margin: 0px;
                padding: 9px 18px;
            }}
            QTabWidget#optionsTabs > QTabBar::tab:selected {{
                color: #ffffff;
                background: #090c12;
                border: 0px;
            }}
            QTabWidget#optionsTabs > QTabBar::tab:hover {{
                color: #ffffff;
            }}
            QWidget#optionsToolbar {{
                background: #090c12;
                border: 0px;
            }}
            QLabel#demoBadge {{
                color: #b99cff;
                background: #24183c;
                border: 1px solid #49336f;
                border-radius: 4px;
                padding: 3px 7px;
                font-size: 8pt;
                font-weight: 700;
            }}
            QLabel#spotLabel {{
                color: #9db4ff;
                font-weight: 700;
                padding-left: 10px;
            }}
            QLabel#legendText {{
                color: {MUTED};
                font-size: 8.5pt;
            }}
            QPushButton {{
                color: {FG};
                background: #171c25;
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: {DRAW};
            }}
            QComboBox {{
                color: {FG};
                background: #171c25;
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 6px 9px;
                min-width: 90px;
            }}
            QComboBox QAbstractItemView {{
                color: {FG};
                background: #171c25;
                selection-background-color: {DRAW};
            }}
            QTableWidget#chainTable {{
                background: #090c12;
                alternate-background-color: #0d121a;
                color: {FG};
                border: none;
                gridline-color: transparent;
            }}
            QHeaderView::section {{
                background: #0d121a;
                color: {MUTED};
                border: none;
                border-bottom: 1px solid {BORDER};
                padding: 8px 4px;
                font-size: 8.5pt;
            }}
            QListWidget#strategyList {{
                background: #0b0f16;
                border: none;
                border-right: 1px solid {BORDER};
                outline: none;
            }}
            QListWidget#strategyList::item {{
                padding: 12px 14px;
                color: {MUTED};
            }}
            QListWidget#strategyList::item:selected {{
                background: #171e2a;
                color: #ffffff;
            }}
            QWidget#strategyDetail {{
                background: #090c12;
            }}
            QLabel#strategyTitle {{
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
            }}
            QLabel#strategySummary {{
                color: {FG};
                font-size: 10.5pt;
            }}
            QLabel#factValue {{
                color: #e7ebf2;
                font-weight: 600;
            }}
            QLabel#placeholderTitle {{
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
            }}
            QLabel#placeholderStatus {{
                color: {MUTED};
                padding-top: 8px;
            }}
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("optionsTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        bar = self.tabs.tabBar()
        bar.setDrawBase(False)
        bar.setExpanding(False)
        bar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        bar.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.tabs.addTab(ChainTab(), "Chain")
        self.tabs.addTab(VolatilityTab(), "Volatility")
        self.tabs.addTab(SurfacesTab(), "Surfaces")
        self.tabs.addTab(HeatmapTab(), "Heatmap")
        self.tabs.addTab(ClustersTab(), "Clusters")
        self.tabs.addTab(StrategiesTab(), "Strategies")
        layout.addWidget(self.tabs)


__all__ = [
    "ChainTab",
    "ClustersTab",
    "HeatmapTab",
    "MetricSurface3D",
    "OptionsView",
    "StrategiesTab",
    "SurfacesTab",
    "VolatilityTab",
    "buildChain",
    "buildIvSmile",
    "buildIvSurface",
    "buildMetricSurface",
    "buildOptionClusters",
]
