"""Price and indicator pane widgets."""

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from chartist.chart.axes import OffsetDateAxis, PriceAxis, ValueAxis
from chartist.chart.items import BarsItem, curve
from chartist.chart.viewbox import ChartViewBox
from chartist.core.formatting import finite, fmtValue, spanHtml
from chartist.core.indicators import atr, macd, obv, rsi, sma, stochastic
from chartist.theme import CANDLE_DOWN, CANDLE_UP, CROSS, MUTED, PANE_CSS

Qt = QtCore.Qt

def _stylePlot(plot):
    plot.showGrid(x=True, y=True, alpha=0.12)
    plot.showAxis("right")
    plot.hideAxis("left")
    plot.hideButtons()
    plot.setMenuEnabled(False)
    plot.disableAutoRange()
    bottom = plot.getAxis("bottom")
    bottom.setStyle(showValues=False)
    bottom.setHeight(0)


def _closeButton(tip, slot):
    b = QtWidgets.QToolButton()
    b.setObjectName("close")
    b.setText("✕")
    b.setToolTip(tip)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    b.clicked.connect(lambda *_: slot())
    return b


class LeaveFilter(QtCore.QObject):
    def __init__(self, chart):
        super().__init__()
        self.chart = chart

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.Type.Leave:
            self.chart.hideCrosshair()
        return False


class Pane(QtWidgets.QWidget):
    """A header row + a plot. Base for the price pane and the indicator panes."""

    def __init__(self, chart, viewbox, right_axis):
        super().__init__()
        self.chart = chart
        self.setStyleSheet(PANE_CSS)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.head = QtWidgets.QWidget()
        self.head.setObjectName("paneHead")
        self.head_layout = QtWidgets.QHBoxLayout(self.head)
        self.head_layout.setContentsMargins(8, 3, 4, 0)
        self.head_layout.setSpacing(12)
        lay.addWidget(self.head)

        self.widget = pg.PlotWidget(viewBox=viewbox, axisItems={
            "right": right_axis, "bottom": OffsetDateAxis(chart.t0, orientation="bottom")})
        self.widget.setMinimumHeight(50)
        lay.addWidget(self.widget, 1)
        self.plot = self.widget.getPlotItem()
        _stylePlot(self.plot)
        self.axis = right_axis

        cross_pen = pg.mkPen("#6e7681", style=Qt.PenStyle.DashLine)
        self.vline = pg.InfiniteLine(angle=90, movable=False, pen=cross_pen)
        self.hline = pg.InfiniteLine(angle=0, movable=False, pen=cross_pen)
        for line in (self.vline, self.hline):
            line.setVisible(False)
            line.setZValue(100)
            self.plot.addItem(line, ignoreBounds=True)

        scene = self.widget.scene()
        self.proxy = pg.SignalProxy(scene.sigMouseMoved, rateLimit=60,
                                    slot=lambda evt: chart.onMouse(self, evt))
        scene.sigMouseClicked.connect(lambda ev: chart.onSceneClick(self, ev))
        self.widget.installEventFilter(chart.leave_filter)

    @property
    def vb(self):
        return self.plot.getViewBox()

    def setCross(self, x, y=None):
        self.vline.setVisible(x is not None)
        self.hline.setVisible(y is not None)
        if x is not None:
            self.vline.setValue(x)
        if y is not None:
            self.hline.setValue(y)
        self.axis.update()


class PricePane(Pane):
    def __init__(self, chart):
        super().__init__(chart, ChartViewBox(chart, pans_y=True), PriceAxis(chart))
        self.info = QtWidgets.QLabel()
        self.info.setTextFormat(Qt.TextFormat.RichText)
        self.head_layout.addWidget(self.info)
        self.head_layout.addStretch()

        self.legend = QtWidgets.QWidget()
        self.legend.setObjectName("indicatorLegend")
        self.legend_layout = QtWidgets.QHBoxLayout(self.legend)
        self.legend_layout.setContentsMargins(8, 1, 4, 3)
        self.legend_layout.setSpacing(10)
        self.legend_layout.addStretch()
        self.layout().insertWidget(1, self.legend)
        self.legend.setVisible(False)
        self.chips = {}

    def addChip(self, key, slot):
        chip = QtWidgets.QWidget()
        chip.setObjectName("indicatorChip")
        cl = QtWidgets.QHBoxLayout(chip)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(2)
        label = QtWidgets.QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        cl.addWidget(label)
        cl.addWidget(_closeButton("Remove indicator", slot))
        self.legend_layout.insertWidget(self.legend_layout.count() - 1, chip)
        self.chips[key] = (chip, label)
        self.legend.setVisible(True)

    def removeChip(self, key):
        chip, _ = self.chips.pop(key)
        chip.setParent(None)
        chip.deleteLater()
        self.legend.setVisible(bool(self.chips))


class SubPane(Pane):
    """Indicator pane below the chart. Subclasses implement setup() and compute()."""

    title = ""
    fixed = None                    # fixed y range, e.g. (0, 100) for RSI

    def __init__(self, chart, key):
        super().__init__(chart, ChartViewBox(chart, pans_y=False), ValueAxis(chart, None))
        self.axis.pane = self
        self.key = key
        self.label = QtWidgets.QLabel()
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.head_layout.addWidget(self.label)
        self.head_layout.addWidget(_closeButton("Remove indicator", lambda: chart.removeIndicator(key)))
        self.head_layout.addStretch()
        self.plot.setXLink(chart.price_plot)
        self.lines = {}             # name -> (curve, color)
        self.values = {}            # name -> array
        self.setup()

    # building blocks
    def addLine(self, name, color, width=1):
        item = curve(color, width)
        self.plot.addItem(item)
        self.lines[name] = (item, color)

    def addGuides(self, levels, band=None):
        pen = pg.mkPen("#6e7681", style=Qt.PenStyle.DashLine)
        for lv in levels:
            self.plot.addItem(pg.InfiniteLine(pos=lv, angle=0, pen=pen), ignoreBounds=True)
        if band:
            region = pg.LinearRegionItem(values=band, orientation="horizontal", movable=False,
                                         brush=pg.mkBrush("#7e57c21a"), pen=pg.mkPen(None))
            self.plot.addItem(region, ignoreBounds=True)

    def setLine(self, name, x, y):
        self.values[name] = y
        self.lines[name][0].setData(*finite(x, y))

    # to override
    def setup(self):
        pass

    def compute(self, d, width):
        pass

    def fitArrays(self):
        return list(self.values.values())

    # shared behaviour
    def fitY(self, mask):
        if self.fixed:
            self.plot.setYRange(*self.fixed, padding=0)
            return
        vals = [a[mask] for a in self.fitArrays() if len(a) == len(mask)]
        vals = np.concatenate(vals) if vals else np.array([])
        vals = vals[np.isfinite(vals)]
        if not len(vals):
            return
        lo, hi = float(vals.min()), float(vals.max())
        pad = max((hi - lo) * 0.1, abs(hi) * 1e-6, 1e-9)
        self.plot.setYRange(lo - pad, hi + pad, padding=0)

    def header(self, i):
        parts = [spanHtml(self.title, MUTED)]
        for name, (_, color) in self.lines.items():
            arr = self.values.get(name)
            if arr is not None and len(arr) > i:
                parts.append(spanHtml(fmtValue(arr[i]), color))
        self.label.setText("&nbsp;&nbsp;".join(parts))

    def valueTags(self):
        tags = []
        for name, (_, color) in self.lines.items():
            arr = self.values.get(name)
            if arr is not None and len(arr) and np.isfinite(arr[-1]):
                tags.append((arr[-1], fmtValue(arr[-1]), color))
        if self.chart.cross_pane is self and self.chart.cross_y is not None:
            tags.append((self.chart.cross_y, fmtValue(self.chart.cross_y), CROSS))
        return tags


class VolumePane(SubPane):
    title = "Volume"

    def setup(self):
        self.bars = BarsItem()
        self.plot.addItem(self.bars)
        self.addLine("MA 20", "#f0b429")

    def compute(self, d, width):
        self.up = d["c"] >= d["o"]
        colors = np.where(self.up, CANDLE_UP + "90", CANDLE_DOWN + "90")
        self.bars.setData(d["x"], d["v"], colors, width)
        self.vol = d["v"]
        self.setLine("MA 20", d["x"], sma(d["v"], 20))

    def fitY(self, mask):
        if mask.any():
            self.plot.setYRange(0, float(self.vol[mask].max()) * 1.15, padding=0)

    def header(self, i):
        if i < len(self.vol):
            color = CANDLE_UP if self.up[i] else CANDLE_DOWN
            ma = self.values["MA 20"][i]
            self.label.setText(f'{spanHtml("Vol", MUTED)}&nbsp;&nbsp;{spanHtml(fmtValue(self.vol[i]), color)}'
                               f'&nbsp;&nbsp;{spanHtml(fmtValue(ma), "#f0b429")}')

    def valueTags(self):
        tags = []
        if len(self.vol):
            color = CANDLE_UP if self.up[-1] else CANDLE_DOWN
            tags.append((self.vol[-1], fmtValue(self.vol[-1]), color))
        if self.chart.cross_pane is self and self.chart.cross_y is not None:
            tags.append((self.chart.cross_y, fmtValue(self.chart.cross_y), CROSS))
        return tags


class RsiPane(SubPane):
    title = "RSI 14"
    fixed = (0, 100)

    def setup(self):
        self.addGuides([30, 50, 70], band=(30, 70))
        self.addLine("RSI", "#7e57c2")

    def compute(self, d, width):
        self.setLine("RSI", d["x"], rsi(d["c"]))


class MacdPane(SubPane):
    title = "MACD 12 26 9"

    def setup(self):
        self.hist = BarsItem()
        self.plot.addItem(self.hist)
        self.addGuides([0])
        self.addLine("MACD", "#2962ff")
        self.addLine("Signal", "#ff6d00")

    def compute(self, d, width):
        m, s, h = macd(d["c"])
        prev = np.r_[h[0], h[:-1]]
        colors = np.where(h >= 0, np.where(h >= prev, "#26a69a", "#b2dfdb"),
                          np.where(h <= prev, "#ef5350", "#ffcdd2"))
        self.hist.setData(d["x"], h, colors, width)
        self.h = h
        self.setLine("MACD", d["x"], m)
        self.setLine("Signal", d["x"], s)

    def fitArrays(self):
        return super().fitArrays() + [self.h]


class StochPane(SubPane):
    title = "Stoch 14 3 3"
    fixed = (0, 100)

    def setup(self):
        self.addGuides([20, 80], band=(20, 80))
        self.addLine("%K", "#2962ff")
        self.addLine("%D", "#ff6d00")

    def compute(self, d, width):
        k, dd = stochastic(d["h"], d["l"], d["c"])
        self.setLine("%K", d["x"], k)
        self.setLine("%D", d["x"], dd)


class AtrPane(SubPane):
    title = "ATR 14"

    def setup(self):
        self.addLine("ATR", "#f23645")

    def compute(self, d, width):
        self.setLine("ATR", d["x"], atr(d["h"], d["l"], d["c"]))


class ObvPane(SubPane):
    title = "OBV"

    def setup(self):
        self.addLine("OBV", "#2962ff")

    def compute(self, d, width):
        self.setLine("OBV", d["x"], obv(d["c"], d["v"]))


class DeltaPane(SubPane):
    """Ask − bid aggressor delta from synthetic footprint."""

    title = "Delta"

    def setup(self):
        self.bars = BarsItem()
        self.plot.addItem(self.bars)
        self.addGuides([0])

    def compute(self, d, width):
        from chartist.core.orderflow import syntheticFootprint

        _, bid, ask, _ = syntheticFootprint(d["o"], d["h"], d["l"], d["c"], d["v"], levels=8)
        delta = ask.sum(axis=1) - bid.sum(axis=1)
        prev = np.r_[delta[0], delta[:-1]]
        colors = np.where(
            delta >= 0,
            np.where(delta >= prev, "#26a69a", "#b2dfdb"),
            np.where(delta <= prev, "#ef5350", "#ffcdd2"),
        )
        self.bars.setData(d["x"], delta, colors, width)
        self.delta = delta

    def fitArrays(self):
        return [self.delta]

    def fitY(self, mask):
        if mask.any() and len(self.delta):
            lo = float(self.delta[mask].min())
            hi = float(self.delta[mask].max())
            pad = max((hi - lo) * 0.12, abs(hi) * 1e-6, 1.0)
            self.plot.setYRange(lo - pad, hi + pad, padding=0)

    def header(self, i):
        if i < len(self.delta):
            value = self.delta[i]
            color = CANDLE_UP if value >= 0 else CANDLE_DOWN
            self.label.setText(
                f'{spanHtml("Delta", MUTED)}&nbsp;&nbsp;{spanHtml(fmtValue(value), color)}'
            )


class CvdPane(SubPane):
    """Cumulative volume delta."""

    title = "CVD"

    def setup(self):
        self.addGuides([0])
        self.addLine("CVD", "#2962ff", width=2)

    def compute(self, d, width):
        from chartist.core.orderflow import syntheticFootprint

        _, bid, ask, _ = syntheticFootprint(d["o"], d["h"], d["l"], d["c"], d["v"], levels=8)
        delta = ask.sum(axis=1) - bid.sum(axis=1)
        self.cvd = np.cumsum(delta)
        self.setLine("CVD", d["x"], self.cvd)

    def fitArrays(self):
        return [self.cvd]


PANES = {
    "vol": ("Volume", VolumePane),
    "rsi": ("RSI", RsiPane),
    "macd": ("MACD", MacdPane),
    "stoch": ("Stochastic", StochPane),
    "atr": ("ATR", AtrPane),
    "obv": ("OBV", ObvPane),
    "delta": ("Delta", DeltaPane),
    "cvd": ("CVD", CvdPane),
}

OVERLAYS = {"sma": "SMA 20", "ema": "EMA 50", "bb": "Bollinger Bands 20 2"}
FLOW_PANES = {"delta": ("Delta", DeltaPane), "cvd": ("CVD", CvdPane), "vol": ("Volume", VolumePane)}
BB_COLORS = ("#ff6d00", "#7e57c2")

__all__ = [
    "AtrPane",
    "BB_COLORS",
    "CvdPane",
    "DeltaPane",
    "FLOW_PANES",
    "LeaveFilter",
    "MacdPane",
    "ObvPane",
    "OVERLAYS",
    "PANES",
    "Pane",
    "PricePane",
    "RsiPane",
    "StochPane",
    "SubPane",
    "VolumePane",
]
