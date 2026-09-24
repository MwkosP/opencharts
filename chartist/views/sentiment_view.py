"""Sentiment workspace: Gauge, Indicators, Socials, Mentions, Backtest."""

from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from chartist.chart.items import CandleItem
from chartist.config import (
    CHART_TYPES,
    DEFAULT_TF,
    TIMEFRAMES,
    VISIBLE_CANDLES,
)
from chartist.core.indicators import heikinAshi
from chartist.core.market import Market
from chartist.core.sentiment import (
    LIVE_MS,
    PLATFORMS,
    TICKERS,
    SocialPost,
    buildGauge,
    buildIndicators,
    buildPostsSentiment,
    buildSocial,
    postsInRange,
    rangeSentimentSummary,
)
from chartist.core.series import Series
from chartist.theme import BAR_CSS, BORDER, DRAW, FG, MENU_CSS, MUTED, UP, DOWN


_TAB_BG = "#090c12"
_BACKTEST_TYPES = tuple(name for name in CHART_TYPES if name != "Footprint")


def _sentimentStyles() -> str:
    return f"""
        QWidget#sentimentView, QWidget#sentimentView QWidget {{
            color: {FG};
            background: {_TAB_BG};
        }}
        QWidget#sentimentView *:focus {{ outline: none; }}
        QTabWidget#sentimentTabs {{
            border: 0px; background: {_TAB_BG}; outline: none;
        }}
        QTabWidget#sentimentTabs::pane {{
            border: 0px; margin: 0px; padding: 0px; background: {_TAB_BG};
        }}
        QTabWidget#sentimentTabs > QTabBar {{
            border: 0px; outline: none; background: {_TAB_BG};
        }}
        QTabWidget#sentimentTabs > QTabBar::tab {{
            color: {MUTED}; background: {_TAB_BG}; border: 0px;
            outline: none; margin: 0px; padding: 9px 18px;
        }}
        QTabWidget#sentimentTabs > QTabBar::tab:selected {{
            color: #ffffff; background: {_TAB_BG}; border: 0px;
        }}
        QTabWidget#sentimentTabs > QTabBar::tab:hover {{ color: #ffffff; }}
        QWidget#sentToolbar {{ background: {_TAB_BG}; border: 0px; }}
        QLabel#legendText {{ color: {MUTED}; font-size: 8.5pt; }}
        QLabel#demoBadge {{
            color: #b99cff; background: #24183c; border: 1px solid #49336f;
            border-radius: 4px; padding: 3px 7px; font-size: 8pt; font-weight: 700;
        }}
        QLabel#statValue {{ color: #e7ebf2; font-weight: 600; font-size: 13pt; }}
        QLabel#statCaption {{ color: {MUTED}; font-size: 8.5pt; }}
        QComboBox {{
            color: {FG}; background: #171c25; border: 1px solid {BORDER};
            border-radius: 5px; padding: 6px 9px; min-width: 90px;
        }}
        QComboBox QAbstractItemView {{
            color: {FG}; background: #171c25; selection-background-color: {DRAW};
        }}
        QTableWidget#socialTable, QTableWidget#postsTable {{
            background: {_TAB_BG}; alternate-background-color: #0d121a;
            color: {FG}; border: none; gridline-color: transparent;
        }}
        QHeaderView::section {{
            background: #0d121a; color: {MUTED}; border: none;
            border-bottom: 1px solid {BORDER}; padding: 8px 4px; font-size: 8.5pt;
        }}
        QTextEdit#postDetail {{
            background: #0d121a; color: {FG}; border: 1px solid {BORDER};
            border-radius: 4px; padding: 8px;
        }}
    """


def _scoreColor(score: float) -> QtGui.QColor:
    t = float(np.clip(score / 100.0, 0.0, 1.0))
    if t < 0.5:
        u = t * 2.0
        r, g, b = (
            int(239 + (255 - 239) * u),
            int(83 + (193 - 83) * u),
            int(80 + (7 - 80) * u),
        )
    else:
        u = (t - 0.5) * 2.0
        r, g, b = (
            int(255 + (38 - 255) * u),
            int(193 + (166 - 193) * u),
            int(7 + (154 - 7) * u),
        )
    return QtGui.QColor(r, g, b)


def _liveToolbar(parent, hint_text: str):
    toolbar = QtWidgets.QWidget()
    toolbar.setObjectName("sentToolbar")
    row = QtWidgets.QHBoxLayout(toolbar)
    row.setContentsMargins(14, 9, 14, 9)
    row.setSpacing(8)
    live = QtWidgets.QLabel("● LIVE")
    live.setStyleSheet(f"color: {UP}; font-weight: 700; font-size: 9pt;")
    row.addWidget(live)
    row.addStretch()
    badge = QtWidgets.QLabel("DEMO")
    badge.setObjectName("demoBadge")
    row.addWidget(badge)
    hint = QtWidgets.QLabel(hint_text)
    hint.setObjectName("legendText")
    row.addWidget(hint)
    parent._liveDot = live
    return toolbar, row


def _wireSlowLive(widget, tick_slot, interval_ms=LIVE_MS):
    widget._pulse = 0
    widget._live_on = True
    widget._timer = QtCore.QTimer(widget)
    widget._timer.setInterval(interval_ms)
    widget._timer.timeout.connect(tick_slot)
    widget._timer.start()
    widget._blink = QtCore.QTimer(widget)
    widget._blink.setInterval(1400)
    widget._blink.timeout.connect(lambda: _toggleLive(widget))
    widget._blink.start()


def _toggleLive(widget):
    widget._live_on = not widget._live_on
    color = UP if widget._live_on else MUTED
    if hasattr(widget, "_liveDot"):
        widget._liveDot.setStyleSheet(
            f"color: {color}; font-weight: 700; font-size: 9pt;"
        )


def _showHideTimers(widget, event, showing: bool):
    if showing:
        if not widget._timer.isActive():
            widget._timer.start()
        if not widget._blink.isActive():
            widget._blink.start()
    else:
        widget._timer.stop()
        widget._blink.stop()


class _FearGreedDial(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.score = 50.0
        self.label = "Neutral"
        self.setMinimumSize(260, 170)

    def setScore(self, score: float, label: str):
        self.score = float(score)
        self.label = label
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        try:
            painter.fillRect(self.rect(), QtGui.QColor(_TAB_BG))
            w, h = self.width(), self.height()
            cx, cy = w * 0.5, h * 0.78
            radius = min(w * 0.42, h * 0.72)
            rect = QtCore.QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
            pen = QtGui.QPen()
            pen.setWidthF(18)
            pen.setCapStyle(QtCore.Qt.PenCapStyle.FlatCap)
            segments = (
                (0, 20, QtGui.QColor(239, 83, 80)),
                (20, 40, QtGui.QColor(255, 138, 101)),
                (40, 60, QtGui.QColor(255, 193, 7)),
                (60, 80, QtGui.QColor(129, 199, 132)),
                (80, 100, QtGui.QColor(38, 166, 154)),
            )
            for lo, hi, color in segments:
                pen.setColor(color)
                painter.setPen(pen)
                span = -((hi - lo) / 100.0) * 180 * 16
                painter.drawArc(
                    rect, int(180 * 16 - (lo / 100.0) * 180 * 16), int(span)
                )
            angle = math.radians(180.0 - (self.score / 100.0) * 180.0)
            needle_len = radius - 28
            nx = cx + math.cos(angle) * needle_len
            ny = cy - math.sin(angle) * needle_len
            color = _scoreColor(self.score)
            painter.setPen(QtGui.QPen(color, 3))
            painter.drawLine(QtCore.QPointF(cx, cy), QtCore.QPointF(nx, ny))
            painter.setBrush(color)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawEllipse(QtCore.QPointF(cx, cy), 7, 7)
            painter.setPen(QtGui.QPen(color))
            font = painter.font()
            font.setPointSize(22)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                QtCore.QRectF(0, cy - radius * 0.55, w, 40),
                int(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter),
                f"{self.score:.0f}",
            )
            font.setPointSize(10)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QtGui.QPen(QtGui.QColor(MUTED)))
            painter.drawText(
                QtCore.QRectF(0, cy - radius * 0.28, w, 28),
                int(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter),
                self.label,
            )
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(
                QtCore.QRectF(cx - radius - 8, cy + 4, 70, 18),
                int(QtCore.Qt.AlignmentFlag.AlignLeft),
                "Fear",
            )
            painter.drawText(
                QtCore.QRectF(cx + radius - 62, cy + 4, 70, 18),
                int(QtCore.Qt.AlignmentFlag.AlignRight),
                "Greed",
            )
        finally:
            painter.end()


class _ComponentBars(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.components: tuple[tuple[str, float], ...] = ()
        self.setMinimumHeight(220)

    def setComponents(self, components):
        self.components = tuple(components)
        self.setMinimumHeight(max(180, 28 + len(self.components) * 34))
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(self.rect(), QtGui.QColor(_TAB_BG))
            y = 8
            for name, value in self.components:
                painter.setPen(QtGui.QPen(QtGui.QColor(MUTED)))
                painter.drawText(8, y, 100, 24, int(QtCore.Qt.AlignmentFlag.AlignVCenter), name)
                track_x = 116
                track_w = self.width() - track_x - 52
                painter.fillRect(track_x, y + 7, track_w, 10, QtGui.QColor(28, 34, 44))
                painter.fillRect(
                    track_x, y + 7, int(track_w * (value / 100.0)), 10, _scoreColor(value)
                )
                painter.setPen(QtGui.QPen(QtGui.QColor(FG)))
                painter.drawText(
                    track_x + track_w + 8,
                    y,
                    40,
                    24,
                    int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight),
                    f"{value:.0f}",
                )
                y += 34
        finally:
            painter.end()


class GaugeTab(QtWidgets.QWidget):
    """Fear & Greed composite — time crawls very slowly."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        toolbar, _ = _liveToolbar(self, "Fear & Greed · very slow pulse")
        root.addWidget(toolbar)

        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(12, 4, 12, 4)
        self.dial = _FearGreedDial()
        top.addWidget(self.dial, 2)
        self.components = _ComponentBars()
        top.addWidget(self.components, 3)
        root.addLayout(top, 2)

        self.history = pg.PlotWidget()
        self.history.setBackground(_TAB_BG)
        self.history.showGrid(x=True, y=True, alpha=0.12)
        self.history.setLabel("left", "Score")
        self.history.setLabel("bottom", "Days")
        self.history.setYRange(0, 100)
        self.histCurve = self.history.plot(pen=pg.mkPen(DRAW, width=2))
        self.histFill = self.history.plot(
            pen=None, fillLevel=50, brush=pg.mkBrush(41, 98, 255, 40)
        )
        root.addWidget(self.history, 2)
        _wireSlowLive(self, self._tickLive)
        self._reload()

    def showEvent(self, event):
        super().showEvent(event)
        _showHideTimers(self, event, True)

    def hideEvent(self, event):
        _showHideTimers(self, event, False)
        super().hideEvent(event)

    def _tickLive(self):
        self._pulse += 1
        self._reload()

    def _reload(self):
        snap = buildGauge(pulse=self._pulse)
        self.dial.setScore(snap.score, snap.label)
        self.components.setComponents(snap.components)
        x = np.arange(len(snap.history), dtype=float)
        self.histCurve.setData(x, snap.history)
        self.histFill.setData(x, snap.history)


class IndicatorsTab(QtWidgets.QWidget):
    """Many sentiment / market-internals indicators."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        toolbar, _ = _liveToolbar(self, "Market internals & sentiment indicators")
        root.addWidget(toolbar)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {_TAB_BG}; border: none; }}")
        host = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(host)
        self.grid.setContentsMargins(8, 4, 8, 8)
        self.grid.setSpacing(8)
        scroll.setWidget(host)
        root.addWidget(scroll, 1)

        self._plots: dict[str, dict] = {}
        _wireSlowLive(self, self._tickLive)
        self._reload()

    def showEvent(self, event):
        super().showEvent(event)
        _showHideTimers(self, event, True)

    def hideEvent(self, event):
        _showHideTimers(self, event, False)
        super().hideEvent(event)

    def _tickLive(self):
        self._pulse += 1
        self._reload()

    def _ensurePlot(self, series, row, col):
        if series.key in self._plots:
            return self._plots[series.key]
        plot = pg.PlotWidget()
        plot.setBackground(_TAB_BG)
        plot.showGrid(x=True, y=True, alpha=0.12)
        plot.setTitle(series.title, color=MUTED, size="9pt")
        plot.setMinimumHeight(160)
        primary = plot.plot(pen=pg.mkPen(DRAW, width=2), name=series.title)
        secondary = None
        if series.secondary is not None:
            secondary = plot.plot(
                pen=pg.mkPen(UP if "bull" in (series.secondary_title or "").lower() or "50" in series.title else DOWN, width=2),
                name=series.secondary_title or "B",
            )
            plot.addLegend(offset=(8, 8))
        if series.y_min is not None and series.y_max is not None:
            plot.setYRange(series.y_min, series.y_max)
        self.grid.addWidget(plot, row, col)
        entry = {"plot": plot, "primary": primary, "secondary": secondary}
        self._plots[series.key] = entry
        return entry

    def _reload(self):
        series_list = buildIndicators(pulse=self._pulse)
        for index, series in enumerate(series_list):
            entry = self._ensurePlot(series, index // 2, index % 2)
            entry["primary"].setData(series.dates, series.values)
            if entry["secondary"] is not None and series.secondary is not None:
                entry["secondary"].setData(series.dates, series.secondary)
            if series.key == "ma":
                entry["primary"].opts["name"] = "50-day"
            if series.key == "nhl":
                entry["primary"].opts["name"] = "New highs"
            if series.key == "aaii":
                entry["primary"].opts["name"] = "Bull %"


class SocialsTab(QtWidgets.QWidget):
    """Posts sentiment overall — platform + asset, F&G-like series."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = "SPY"
        self.platform = "ALL"
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar, row = _liveToolbar(self, "Posts sentiment · fear/greed from socials")
        # Insert filters before stretch (row already has live + stretch + badge + hint)
        row.insertWidget(1, QtWidgets.QLabel("Asset"))
        self.symbolCombo = QtWidgets.QComboBox()
        for symbol, name in TICKERS:
            self.symbolCombo.addItem(f"{symbol}  ·  {name}", symbol)
        self.symbolCombo.currentIndexChanged.connect(self._filtersChanged)
        row.insertWidget(2, self.symbolCombo)
        row.insertWidget(3, QtWidgets.QLabel("Platform"))
        self.platformCombo = QtWidgets.QComboBox()
        for code, label in PLATFORMS:
            self.platformCombo.addItem(label, code)
        self.platformCombo.currentIndexChanged.connect(self._filtersChanged)
        row.insertWidget(4, self.platformCombo)
        root.addWidget(toolbar)

        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(12, 4, 12, 4)
        self.dial = _FearGreedDial()
        top.addWidget(self.dial, 1)

        right = QtWidgets.QVBoxLayout()
        self.scoreCaption = QtWidgets.QLabel("Overall posts sentiment")
        self.scoreCaption.setObjectName("statCaption")
        right.addWidget(self.scoreCaption)
        self.volPlot = pg.PlotWidget()
        self.volPlot.setBackground(_TAB_BG)
        self.volPlot.showGrid(x=True, y=True, alpha=0.1)
        self.volPlot.setTitle("Post volume", color=MUTED, size="9pt")
        self.volPlot.setMaximumHeight(120)
        self.volBars = pg.BarGraphItem(x=[], height=[], width=0.7, brush=DRAW)
        self.volPlot.addItem(self.volBars)
        right.addWidget(self.volPlot)
        top.addLayout(right, 2)
        root.addLayout(top, 2)

        self.seriesPlot = pg.PlotWidget()
        self.seriesPlot.setBackground(_TAB_BG)
        self.seriesPlot.showGrid(x=True, y=True, alpha=0.12)
        self.seriesPlot.setLabel("left", "Posts F&G")
        self.seriesPlot.setLabel("bottom", "Days")
        self.seriesPlot.setYRange(0, 100)
        self.seriesPlot.setTitle(
            "Fear & Greed–style series from social posts", color=MUTED, size="9pt"
        )
        self.fgCurve = self.seriesPlot.plot(pen=pg.mkPen(DRAW, width=2))
        self.fgFill = self.seriesPlot.plot(
            pen=None, fillLevel=50, brush=pg.mkBrush(41, 98, 255, 35)
        )
        root.addWidget(self.seriesPlot, 2)

        self.postsTable = QtWidgets.QTableWidget(0, 5)
        self.postsTable.setObjectName("postsTable")
        self.postsTable.setHorizontalHeaderLabels(
            ["Time", "Platform", "Sentiment", "Likes", "Post"]
        )
        self.postsTable.verticalHeader().setVisible(False)
        self.postsTable.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.postsTable.setAlternatingRowColors(True)
        self.postsTable.horizontalHeader().setSectionResizeMode(
            4, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        root.addWidget(self.postsTable, 2)

        _wireSlowLive(self, self._tickLive)
        self._reload()

    def showEvent(self, event):
        super().showEvent(event)
        _showHideTimers(self, event, True)

    def hideEvent(self, event):
        _showHideTimers(self, event, False)
        super().hideEvent(event)

    def _filtersChanged(self, _index=None):
        self.symbol = self.symbolCombo.currentData()
        self.platform = self.platformCombo.currentData()
        self._reload()

    def _tickLive(self):
        self._pulse += 1
        self._reload()

    def _reload(self):
        snap = buildPostsSentiment(
            symbol=self.symbol, platform=self.platform, pulse=self._pulse
        )
        self.dial.setScore(snap.score, snap.label)
        self.fgCurve.setData(snap.dates, snap.history)
        self.fgFill.setData(snap.dates, snap.history)
        self.volPlot.removeItem(self.volBars)
        self.volBars = pg.BarGraphItem(
            x=snap.dates, height=snap.volume, width=0.7, brush=pg.mkBrush(41, 98, 255, 160)
        )
        self.volPlot.addItem(self.volBars)

        show = snap.posts[:60]
        self.postsTable.setRowCount(len(show))
        for row, post in enumerate(show):
            values = (
                post.time_label,
                post.platform,
                f"{post.sentiment:.0f}  {_labelShort(post.sentiment)}",
                f"{post.likes:,}",
                post.text,
            )
            color = _scoreColor(post.sentiment)
            for col, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter) if col < 4 else int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft))
                if col == 2:
                    item.setForeground(color)
                self.postsTable.setItem(row, col, item)


def _labelShort(score: float) -> str:
    if score < 20:
        return "EF"
    if score < 40:
        return "F"
    if score < 60:
        return "N"
    if score < 80:
        return "G"
    return "EG"


class _BuzzBars(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.setMinimumWidth(220)

    def setRows(self, rows):
        self.rows = list(rows)[:8]
        self.setMinimumHeight(max(160, 20 + len(self.rows) * 28))
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(self.rect(), QtGui.QColor(_TAB_BG))
            y = 6
            for row in self.rows:
                painter.setPen(QtGui.QPen(QtGui.QColor(FG)))
                painter.drawText(8, y, 48, 22, int(QtCore.Qt.AlignmentFlag.AlignVCenter), row.symbol)
                track_x, track_w = 60, self.width() - 72
                painter.fillRect(track_x, y + 6, track_w, 10, QtGui.QColor(28, 34, 44))
                color = QtGui.QColor(UP) if row.bullish >= 0.5 else QtGui.QColor(DOWN)
                painter.fillRect(track_x, y + 6, int(track_w * row.buzz), 10, color)
                y += 28
        finally:
            painter.end()


class MentionsTab(QtWidgets.QWidget):
    """Ticker mentions / buzz board (former Social tab)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        toolbar, _ = _liveToolbar(self, "Mentions · buzz · bullish share")
        root.addWidget(toolbar)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(8, 0, 8, 8)
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setObjectName("socialTable")
        self.table.setHorizontalHeaderLabels(
            ["Symbol", "Bullish %", "Mentions", "1h Δ", "Name"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        body.addWidget(self.table, 3)
        right = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel("Buzz leaders")
        label.setObjectName("legendText")
        right.addWidget(label)
        self.buzz = _BuzzBars()
        right.addWidget(self.buzz, 1)
        body.addLayout(right, 1)
        root.addLayout(body, 1)
        _wireSlowLive(self, self._tickLive)
        self._reload()

    def showEvent(self, event):
        super().showEvent(event)
        _showHideTimers(self, event, True)

    def hideEvent(self, event):
        _showHideTimers(self, event, False)
        super().hideEvent(event)

    def _tickLive(self):
        self._pulse += 1
        self._reload()

    def _reload(self):
        rows = buildSocial(pulse=self._pulse)
        self.buzz.setRows(rows)
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = (
                row.symbol,
                f"{row.bullish * 100:.0f}%",
                f"{row.mentions:,}",
                f"{row.change_1h:+.1f}pp",
                row.name,
            )
            color = QtGui.QColor(UP if row.bullish >= 0.5 else DOWN)
            for column, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
                if column in (1, 3):
                    item.setForeground(color)
                self.table.setItem(index, column, item)


class BacktestTab(QtWidgets.QWidget):
    """Price chart (top bar only) + drag a region to inspect posts / sentiment."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = "SPY"
        self.tf = DEFAULT_TF
        self.chart_type = "Candles"
        self.market = Market()
        self.series = Series(self.market, self.tf)
        self.raw = self.series.data()
        self._posts = ()
        self._pulse = 0

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._buildTopbar())

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        split.setHandleWidth(4)
        split.setStyleSheet(
            f"QSplitter::handle {{ background: {BORDER}; }}"
        )

        self.plot = pg.PlotWidget()
        self.plot.setBackground(_TAB_BG)
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.plot.setLabel("left", "Price")
        self.candles = CandleItem()
        self.plot.addItem(self.candles)
        self.line = self.plot.plot(pen=pg.mkPen(DRAW, width=2))
        self.line.hide()
        self.area = self.plot.plot(
            pen=pg.mkPen(DRAW, width=1),
            fillLevel=0,
            brush=pg.mkBrush(41, 98, 255, 40),
        )
        self.area.hide()
        x = self.raw["x"]
        if len(x):
            mid = float(x[len(x) // 2])
            span = max(float(self.tf) * 40, (x[-1] - x[0]) * 0.12)
            self.region = pg.LinearRegionItem(
                values=[mid - span / 2, mid + span / 2],
                brush=pg.mkBrush(41, 98, 255, 35),
                pen=pg.mkPen(DRAW, width=1),
            )
        else:
            self.region = pg.LinearRegionItem()
        self.region.setZValue(10)
        self.region.sigRegionChanged.connect(self._regionChanged)
        self.plot.addItem(self.region)
        split.addWidget(self.plot)

        bottom = QtWidgets.QWidget()
        bl = QtWidgets.QVBoxLayout(bottom)
        bl.setContentsMargins(8, 4, 8, 8)
        bl.setSpacing(6)
        stats = QtWidgets.QHBoxLayout()
        self.statLabels = []
        for _ in range(4):
            box = QtWidgets.QVBoxLayout()
            value = QtWidgets.QLabel("—")
            value.setObjectName("statValue")
            caption = QtWidgets.QLabel("")
            caption.setObjectName("statCaption")
            box.addWidget(value)
            box.addWidget(caption)
            stats.addLayout(box)
            self.statLabels.append((value, caption))
        bl.addLayout(stats)
        self.rangeTable = QtWidgets.QTableWidget(0, 5)
        self.rangeTable.setObjectName("postsTable")
        self.rangeTable.setHorizontalHeaderLabels(
            ["Time", "Platform", "Sentiment", "Likes", "Post"]
        )
        self.rangeTable.verticalHeader().setVisible(False)
        self.rangeTable.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.rangeTable.setAlternatingRowColors(True)
        self.rangeTable.horizontalHeader().setSectionResizeMode(
            4, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        bl.addWidget(self.rangeTable, 1)
        tip = QtWidgets.QLabel(
            "Drag the blue region on the chart to inspect posts & sentiment in that window."
        )
        tip.setObjectName("legendText")
        bl.addWidget(tip)
        split.addWidget(bottom)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 1)

        _wireSlowLive(self, self._tickLive, interval_ms=LIVE_MS)
        self._reloadPrice()
        self._reloadPosts()
        self._regionChanged()

    def showEvent(self, event):
        super().showEvent(event)
        _showHideTimers(self, event, True)

    def hideEvent(self, event):
        _showHideTimers(self, event, False)
        super().hideEvent(event)

    def _buildTopbar(self):
        bar = QtWidgets.QWidget()
        bar.setObjectName("topbar")
        bar.setStyleSheet(BAR_CSS)
        bl = QtWidgets.QHBoxLayout(bar)
        bl.setContentsMargins(6, 3, 12, 3)
        bl.setSpacing(2)

        def vsep():
            frame = QtWidgets.QFrame()
            frame.setObjectName("vsep")
            frame.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            bl.addWidget(frame)

        self.symbolCombo = QtWidgets.QComboBox()
        for symbol, name in TICKERS:
            self.symbolCombo.addItem(f"{symbol}", symbol)
        self.symbolCombo.setCurrentIndex(0)
        self.symbolCombo.currentIndexChanged.connect(self._symbolChanged)
        bl.addWidget(self.symbolCombo)
        vsep()

        self.tf_buttons = {}
        group = QtWidgets.QButtonGroup(bar)
        for label, tf in TIMEFRAMES:
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            button.setChecked(tf == self.tf)
            button.clicked.connect(lambda _, t=tf: self._setTimeframe(t))
            group.addButton(button)
            bl.addWidget(button)
            self.tf_buttons[tf] = button
        vsep()

        self.type_button = QtWidgets.QToolButton()
        self.type_button.setObjectName("menu")
        self.type_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.type_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        menu = QtWidgets.QMenu(self.type_button)
        menu.setStyleSheet(MENU_CSS)
        self.type_actions = {}
        for name in _BACKTEST_TYPES:
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(name == self.chart_type)
            act.triggered.connect(lambda _, n=name: self._setChartType(n))
            self.type_actions[name] = act
        self.type_button.setMenu(menu)
        self.type_button.setText(f"{self.chart_type}  ▾")
        bl.addWidget(self.type_button)
        bl.addStretch()
        self._liveDot = QtWidgets.QLabel("● LIVE")
        self._liveDot.setStyleSheet(f"color: {UP}; font-weight: 700; font-size: 9pt;")
        bl.addWidget(self._liveDot)
        badge = QtWidgets.QLabel("DEMO")
        badge.setObjectName("demoBadge")
        bl.addWidget(badge)
        return bar

    def _symbolChanged(self, _index):
        self.symbol = self.symbolCombo.currentData()
        self._reloadPosts()
        self._regionChanged()

    def _setTimeframe(self, tf):
        self.tf = tf
        self.series = Series(self.market, self.tf)
        self.raw = self.series.data()
        for value, button in self.tf_buttons.items():
            button.setChecked(value == tf)
        self._reloadPrice()
        self._reloadPosts()
        self._regionChanged()

    def _setChartType(self, name):
        self.chart_type = name
        self.type_button.setText(f"{name}  ▾")
        for key, act in self.type_actions.items():
            act.setChecked(key == name)
        self._reloadPrice()

    def _tickLive(self):
        self._pulse += 1
        # Crawl price slowly — a few synthetic ticks then rebundle.
        for _ in range(3):
            sec, price, size = self.market.tick()
            self.series.update(sec, price, size)
        self.raw = self.series.data()
        self._reloadPrice()
        self._reloadPosts()
        self._regionChanged()

    def _reloadPrice(self):
        disp = heikinAshi(self.raw) if self.chart_type == "Heikin Ashi" else self.raw
        x, o, h, l, c = disp["x"], disp["o"], disp["h"], disp["l"], disp["c"]
        if self.chart_type in ("Line", "Area"):
            self.candles.hide()
            self.line.show()
            self.line.setData(x, c)
            if self.chart_type == "Area":
                self.area.show()
                self.area.setData(x, c)
            else:
                self.area.hide()
        else:
            self.line.hide()
            self.area.hide()
            self.candles.show()
            style = {"Hollow candles": "hollow", "Bars": "bars"}.get(
                self.chart_type, "candles"
            )
            self.candles.setData(x, o, h, l, c, self.tf, style)
        if len(x):
            n = min(VISIBLE_CANDLES, len(x))
            span = n * float(self.tf)
            self.plot.setXRange(x[-1] - span, x[-1] + self.tf * 2, padding=0)
            lo, hi = float(np.nanmin(l[-n:])), float(np.nanmax(h[-n:]))
            pad = max((hi - lo) * 0.08, 1e-6)
            self.plot.setYRange(lo - pad, hi + pad, padding=0)

    def _reloadPosts(self):
        # Map posts onto bar index space so the region matches price x.
        x = self.raw["x"]
        if not len(x):
            self._posts = ()
            return
        days = min(90, len(x))
        snap = buildPostsSentiment(
            symbol=self.symbol, platform="ALL", pulse=self._pulse, days=days
        )
        # Remap day indices → chart x values.
        mapped = []
        start = max(0, len(x) - days)
        for post in snap.posts:
            day = int(np.clip(post.time_index, 0, days - 1))
            xi = float(x[start + day])
            mapped.append(
                SocialPost(
                    post_id=post.post_id,
                    platform=post.platform,
                    symbol=post.symbol,
                    time_index=xi,
                    time_label=post.time_label,
                    author=post.author,
                    text=post.text,
                    sentiment=post.sentiment,
                    likes=post.likes,
                )
            )
        self._posts = tuple(mapped)

    def _regionChanged(self):
        x0, x1 = self.region.getRegion()
        selected = postsInRange(self._posts, x0, x1)
        summary = rangeSentimentSummary(selected)
        labels = (
            (f"{summary['score']:.0f}", summary["label"]),
            (f"{summary['count']}", "Posts in range"),
            (f"{summary['bullish_pct']:.0f}%", "Bullish share"),
            (f"{summary['avg_likes']:.0f}", "Avg likes"),
        )
        for (value, caption), (text, label) in zip(self.statLabels, labels):
            value.setText(text)
            if label == summary["label"]:
                value.setStyleSheet(
                    f"color: {_scoreColor(summary['score']).name()}; "
                    f"font-weight: 600; font-size: 13pt;"
                )
            else:
                value.setStyleSheet(
                    "color: #e7ebf2; font-weight: 600; font-size: 13pt;"
                )
            caption.setText(label)

        show = selected[:80]
        self.rangeTable.setRowCount(len(show))
        for row, post in enumerate(show):
            values = (
                post.time_label,
                post.platform,
                f"{post.sentiment:.0f}",
                f"{post.likes:,}",
                f"@{post.author}: {post.text}",
            )
            color = _scoreColor(post.sentiment)
            for col, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                align = (
                    int(QtCore.Qt.AlignmentFlag.AlignCenter)
                    if col < 4
                    else int(
                        QtCore.Qt.AlignmentFlag.AlignVCenter
                        | QtCore.Qt.AlignmentFlag.AlignLeft
                    )
                )
                item.setTextAlignment(align)
                if col == 2:
                    item.setForeground(color)
                self.rangeTable.setItem(row, col, item)


class SentimentView(QtWidgets.QWidget):
    """Container for sentiment analysis subtabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sentimentView")
        self.setStyleSheet(_sentimentStyles())
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("sentimentTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        bar = self.tabs.tabBar()
        bar.setDrawBase(False)
        bar.setExpanding(False)
        bar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        bar.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.tabs.addTab(GaugeTab(), "Gauge")
        self.tabs.addTab(IndicatorsTab(), "Indicators")
        self.tabs.addTab(SocialsTab(), "Socials")
        self.tabs.addTab(MentionsTab(), "Mentions")
        self.tabs.addTab(BacktestTab(), "Backtest")
        layout.addWidget(self.tabs)


__all__ = [
    "BacktestTab",
    "GaugeTab",
    "IndicatorsTab",
    "MentionsTab",
    "SentimentView",
    "SocialsTab",
]
