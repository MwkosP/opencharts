"""Technicals-style Orderflow chart: Footprint, Heatmap, and flow indicator panes."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from chartist.chart.axes import TimeAxis
from chartist.chart.items import CandleItem, FootprintItem, VolumeHeatmapItem
from chartist.chart.panes import FLOW_PANES, LeaveFilter, PricePane
from chartist.config import (
    DEFAULT_TF,
    HISTORY_SEC,
    MAX_BARS,
    MIN_VISIBLE,
    RENDER_MS,
    START_PRICE,
    SYMBOL,
    TICK_MS,
    TIMEFRAMES,
    VISIBLE_CANDLES,
)
from chartist.core.formatting import fmtPrice, spanHtml
from chartist.core.market import Market
from chartist.core.series import Series
from chartist.theme import (
    BAR_CSS,
    BG,
    BOTTOM_CSS,
    DOWN,
    DRAW,
    FG,
    MENU_CSS,
    MUTED,
    SPLITTER_CSS,
    UP,
)
from chartist.ui.ticker_search import TickerSearchOverlay, TickerTypingFilter

Qt = QtCore.Qt
Shortcut = QtGui.QShortcut

FLOW_CHART_TYPES = ("Footprint", "Heatmap", "Candles")


class OrderflowChartView(QtWidgets.QWidget):
    """Same chrome as Technicals, focused on footprint / heatmap / flow panes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cleaned_up = False
        self.symbol = SYMBOL
        self.market = Market()
        self.t0 = self.market.t0
        self.tf = DEFAULT_TF
        self.series = Series(self.market, self.tf)
        self.raw = self.disp = self.series.data()
        self.chart_type = "Footprint"
        self.dirty = True

        self.paused = False
        self.follow = True
        self.auto_y = True
        self.log_mode = False
        self.span = min(VISIBLE_CANDLES, 40) * self.tf
        self.hover_idx = None
        self.cross_x = self.cross_y = self.cross_pane = None
        self.tool = None  # ChartViewBox expects this
        self.cursor_mode = "cross"
        self.panes = {}

        self.leave_filter = LeaveFilter(self)
        self._buildUi()
        self.symbolSearch = TickerSearchOverlay(self)
        self.symbolSearch.setGeometry(self.rect())
        self.symbolSearch.symbolSelected.connect(self.setSymbol)
        self.symbolSearch.searchClosed.connect(
            lambda: self._setShortcutsEnabled(True)
        )
        self._tickerTypingFilter = TickerTypingFilter(self)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.installEventFilter(self._tickerTypingFilter)

        for key in ("delta", "cvd"):
            self.addPane(key)
        self.render(force=True)
        self._applyFollow()
        self.fitY()
        self.syncButtons()

        self.tick_timer = QtCore.QTimer(self)
        self.tick_timer.timeout.connect(self.onTick)
        self.tick_timer.start(TICK_MS)
        self.render_timer = QtCore.QTimer(self)
        self.render_timer.timeout.connect(self.render)
        self.render_timer.start(RENDER_MS)

    def fy(self, p):
        return np.log10(p) if self.log_mode else p

    def inv(self, y):
        return 10 ** y if self.log_mode else y

    def openSymbolSearch(self, initialText=""):
        self._setShortcutsEnabled(False)
        self.symbolSearch.openSearch(initialText)

    def setSymbol(self, symbol):
        self.symbol = symbol.strip().upper()
        self.symbolButton.setText(self.symbol)
        self.updateInfo()

    def _setShortcutsEnabled(self, enabled):
        for shortcut in self.shortcuts:
            shortcut.setEnabled(enabled)

    def _buildUi(self):
        pg.setConfigOptions(antialias=True, background=BG, foreground=FG)
        self.setStyleSheet(f"background:{BG}; color:{FG};")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._buildTopbar())

        column = QtWidgets.QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self.splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(4)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStyleSheet(SPLITTER_CSS)
        self.price_pane = PricePane(self)
        self.price_plot = self.price_pane.plot
        self.price_axis = self.price_pane.axis
        self.splitter.addWidget(self.price_pane)
        column.addWidget(self.splitter, 1)

        self.time_axis = TimeAxis(self, self.t0)
        blank = pg.AxisItem("right")
        blank.setStyle(showValues=False)
        blank.setWidth(90)
        blank.setPen(pg.mkPen(None))
        self.time_widget = pg.PlotWidget(
            axisItems={"bottom": self.time_axis, "right": blank}
        )
        tp = self.time_widget.getPlotItem()
        tp.showAxis("right")
        tp.hideAxis("left")
        tp.hideButtons()
        tp.setMenuEnabled(False)
        tp.setMouseEnabled(False, False)
        tp.setXLink(self.price_plot)
        self.time_widget.setFixedHeight(34)
        column.addWidget(self.time_widget)
        layout.addLayout(column, 1)

        self.candles = CandleItem()
        self.candles.setVisible(False)
        self.price_plot.addItem(self.candles)
        self.footprint = FootprintItem(levels=8)
        self.price_plot.addItem(self.footprint)
        self.heatmap = VolumeHeatmapItem(levels=12)
        self.heatmap.setVisible(False)
        self.price_plot.addItem(self.heatmap)
        self.last_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen("#8b949e", style=Qt.PenStyle.DashLine),
        )
        self.price_plot.addItem(self.last_line, ignoreBounds=True)
        self.price_plot.sigXRangeChanged.connect(lambda *_: self.fitY())

        layout.addWidget(self._buildBottombar())

        keys = {
            "Space": self.togglePause,
            "F": self.toggleFollow,
            "R": self.resetView,
            "A": lambda: self.setAuto(not self.auto_y),
        }
        self.shortcuts = [
            Shortcut(QtGui.QKeySequence(k), self, activated=fn) for k, fn in keys.items()
        ]
        for shortcut in self.shortcuts:
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def _buildTopbar(self):
        bar = QtWidgets.QWidget()
        bar.setObjectName("topbar")
        bar.setStyleSheet(BAR_CSS + MENU_CSS)
        bl = QtWidgets.QHBoxLayout(bar)
        bl.setContentsMargins(6, 3, 12, 3)
        bl.setSpacing(2)

        def vsep():
            frame = QtWidgets.QFrame()
            frame.setObjectName("vsep")
            frame.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            bl.addWidget(frame)

        self.symbolButton = QtWidgets.QPushButton(self.symbol)
        self.symbolButton.setObjectName("symbol")
        self.symbolButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.symbolButton.clicked.connect(lambda: self.openSymbolSearch())
        bl.addWidget(self.symbolButton)
        vsep()

        self.tf_buttons = {}
        group = QtWidgets.QButtonGroup(self)
        group.setExclusive(True)
        for label, tf in TIMEFRAMES:
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda *_ , value=tf: self.setTimeframe(value))
            group.addButton(button)
            bl.addWidget(button)
            self.tf_buttons[tf] = button
        vsep()

        self.type_button = QtWidgets.QPushButton()
        self.type_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        menu = QtWidgets.QMenu(self.type_button)
        menu.setStyleSheet(MENU_CSS)
        self.type_actions = {}
        for name in FLOW_CHART_TYPES:
            action = menu.addAction(name)
            action.setCheckable(True)
            action.triggered.connect(lambda *_ , n=name: self.setChartType(n))
            self.type_actions[name] = action
        self.type_button.setMenu(menu)
        bl.addWidget(self.type_button)
        vsep()

        self.ind_button = QtWidgets.QPushButton("ƒx  Indicators  ▾")
        self.ind_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ind_menu = QtWidgets.QMenu(self.ind_button)
        ind_menu.setStyleSheet(MENU_CSS)
        self.ind_actions = {}
        for key, (label, _) in FLOW_PANES.items():
            action = ind_menu.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(lambda *_ , k=key: self.togglePane(k))
            self.ind_actions[key] = action
        self.ind_button.setMenu(ind_menu)
        bl.addWidget(self.ind_button)

        bl.addStretch()
        self.status = QtWidgets.QLabel()
        self.status.setTextFormat(Qt.TextFormat.RichText)
        bl.addWidget(self.status)
        return bar

    def _buildBottombar(self):
        bar = QtWidgets.QWidget()
        bar.setObjectName("bottombar")
        bar.setStyleSheet(BOTTOM_CSS)
        row = QtWidgets.QHBoxLayout(bar)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(6)
        hint = QtWidgets.QLabel("Footprint · Heatmap · Delta / CVD")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        row.addWidget(hint)
        row.addStretch()

        def button(text, tip, slot, checkable=False):
            btn = QtWidgets.QPushButton(text)
            btn.setCheckable(checkable)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            row.addWidget(btn)
            return btn

        self.btn_pause = button("❚❚  Pause", "Pause live feed (Space)", self.togglePause, True)
        self.btn_follow = button("⇥  Follow", "Follow latest bar (F)", self.toggleFollow, True)
        button("⟲  Reset", "Reset view (R)", self.resetView)
        self.btn_auto = button(
            "auto", "Auto-fit price scale (A)", lambda: self.setAuto(not self.auto_y), True
        )
        return bar

    def allPanes(self):
        return [self.price_pane] + list(self.panes.values())

    def syncButtons(self):
        for tf, button in self.tf_buttons.items():
            button.setChecked(tf == self.tf)
        self.type_button.setText(f"{self.chart_type}  ▾")
        for name, action in self.type_actions.items():
            action.setChecked(name == self.chart_type)
        for key, action in self.ind_actions.items():
            action.setChecked(key in self.panes)
        self.btn_pause.setChecked(self.paused)
        self.btn_follow.setChecked(self.follow)
        self.btn_auto.setChecked(self.auto_y)
        self.updateInfo()

    def togglePane(self, key):
        if key in self.panes:
            self.removePane(key)
        else:
            self.addPane(key)

    def addPane(self, key):
        if key in self.panes:
            return
        label, factory = FLOW_PANES[key]
        pane = factory(self, key)
        self.panes[key] = pane
        self.splitter.addWidget(pane)
        self.layoutPanes()
        self.render(force=True)
        self.fitY()
        self.syncButtons()

    def removePane(self, key):
        pane = self.panes.pop(key, None)
        if pane is None:
            return
        if self.cross_pane is pane:
            self.hideCrosshair()
        pane.setParent(None)
        pane.deleteLater()
        self.layoutPanes()
        self.syncButtons()

    def removeIndicator(self, key):
        self.removePane(key)

    def layoutPanes(self):
        height = self.splitter.height()
        if height < 200:
            height = max(400, self.height() - 100)
        count = len(self.panes)
        share = min(0.22, 0.55 / count) if count else 0
        self.splitter.setSizes(
            [int(height * (1 - share * count))] + [int(height * share)] * count
        )

    def onTick(self):
        if self.paused:
            return
        sec, price, size = self.market.tick()
        self.series.update(sec, price, size)
        self.dirty = True

    def render(self, force=False):
        if not (self.dirty or force):
            return
        self.dirty = False
        self.raw = self.disp = self.series.data()
        data, fy = self.disp, self.fy

        if self.chart_type == "Footprint":
            self.candles.setVisible(False)
            self.heatmap.setVisible(False)
            self.footprint.setVisible(True)
            self.footprint.setData(
                data["x"],
                fy(data["o"]),
                fy(data["h"]),
                fy(data["l"]),
                fy(data["c"]),
                data["v"],
                self.tf,
            )
        elif self.chart_type == "Heatmap":
            self.candles.setVisible(False)
            self.footprint.setVisible(False)
            self.heatmap.setVisible(True)
            self.heatmap.setData(
                data["x"],
                fy(data["h"]),
                fy(data["l"]),
                fy(data["o"]),
                fy(data["c"]),
                data["v"],
                self.tf,
            )
        else:
            self.footprint.setVisible(False)
            self.heatmap.setVisible(False)
            self.candles.setVisible(True)
            self.candles.setData(
                data["x"],
                fy(data["o"]),
                fy(data["h"]),
                fy(data["l"]),
                fy(data["c"]),
                self.tf,
                "candles",
            )

        for pane in self.panes.values():
            pane.compute(self.raw, self.tf)
        self.last_line.setValue(fy(self.raw["c"][-1]))
        if self.follow:
            self._applyFollow()
        self.fitY()
        self.updateInfo()
        for pane in self.allPanes():
            pane.axis.update()

    def setTimeframe(self, tf):
        self.tf = tf
        self.series = Series(self.market, tf)
        self.hover_idx = None
        self.span = min(VISIBLE_CANDLES, 40) * tf
        if self.chart_type in ("Footprint", "Heatmap"):
            self.span = min(self.span, 14 * tf)
        self.follow = True
        self.render(force=True)
        self._applyFollow()
        self.syncButtons()

    def setChartType(self, name):
        self.chart_type = name
        if name in ("Footprint", "Heatmap"):
            self.span = min(self.span, 14 * self.tf)
        self.render(force=True)
        if self.follow:
            self._applyFollow()
        self.syncButtons()

    def _clampSpan(self, width):
        return float(
            np.clip(width, MIN_VISIBLE * self.tf, (len(self.raw["x"]) + 50) * self.tf)
        )

    def _applyFollow(self):
        right = self.raw["x"][-1] + self.tf * 4
        self.price_plot.setXRange(right - self.span, right, padding=0)

    def zoomX(self, factor, center=None):
        vb = self.price_plot.getViewBox()
        xmin, xmax = vb.viewRange()[0]
        if self.follow:
            self.span = self._clampSpan(self.span * factor)
            self._applyFollow()
            return
        if center is None:
            center = xmax
        scale = self._clampSpan((xmax - xmin) * factor) / (xmax - xmin)
        vb.setXRange(
            center - (center - xmin) * scale,
            center + (xmax - center) * scale,
            padding=0,
        )

    def panX(self, dx):
        self.setFollow(False)
        self.price_plot.getViewBox().translateBy(x=dx)

    def visibleMask(self):
        xmin, xmax = self.price_plot.getViewBox().viewRange()[0]
        x = self.disp["x"]
        return (x >= xmin) & (x <= xmax)

    def fitY(self):
        mask = self.visibleMask()
        if not mask.any():
            return
        for pane in self.panes.values():
            pane.fitY(mask)
        if self.auto_y:
            data = self.disp
            lo, hi = data["l"][mask].min(), data["h"][mask].max()
            lo, hi = self.fy(lo), self.fy(hi)
            pad = max((hi - lo) * 0.08, abs(hi) * 1e-6)
            self.price_plot.setYRange(lo - pad, hi + pad, padding=0)

    def scaleY(self, factor):
        self.setAuto(False)
        a, b = self.price_plot.getViewBox().viewRange()[1]
        mid, half = (a + b) / 2, (b - a) / 2 * factor
        self.price_plot.setYRange(mid - half, mid + half, padding=0)

    def setAuto(self, on):
        self.auto_y = on
        self.fitY()
        self.syncButtons()

    def setFollow(self, on):
        self.follow = on
        if on:
            self._applyFollow()
        self.syncButtons()

    def toggleFollow(self):
        self.setFollow(not self.follow)

    def togglePause(self):
        self.paused = not self.paused
        self.syncButtons()

    def resetView(self):
        self.follow = True
        self.auto_y = True
        self.span = min(VISIBLE_CANDLES, 40) * self.tf
        if self.chart_type in ("Footprint", "Heatmap"):
            self.span = min(self.span, 14 * self.tf)
        self._applyFollow()
        self.fitY()
        self.syncButtons()

    def nearestIndex(self, xv):
        return int(np.clip(np.searchsorted(self.disp["x"], xv) - 1, 0, len(self.disp["x"]) - 1))

    def timeText(self, xv):
        import time

        fmt = "%d %b  %H:%M:%S" if self.tf < 60 else "%a %d %b  %H:%M"
        return time.strftime(fmt, time.localtime(xv + self.t0))

    def timeTags(self):
        tags = []
        if self.cross_x is not None:
            from chartist.theme import CROSS

            tags.append((self.cross_x, self.timeText(self.cross_x), CROSS))
        return tags

    def priceTags(self):
        from chartist.theme import CROSS

        tags = []
        if len(self.raw["c"]):
            last = self.fy(self.raw["c"][-1])
            tags.append((last, fmtPrice(self.raw["c"][-1]), UP))
        if self.cross_pane is self.price_pane and self.cross_y is not None:
            tags.append((self.cross_y, fmtPrice(self.inv(self.cross_y)), CROSS))
        return tags

    def hideCrosshair(self):
        self.cross_x = self.cross_y = self.cross_pane = None
        self.hover_idx = None
        for pane in self.allPanes():
            pane.setCross(None)
        self.time_axis.update()
        self.updateInfo()

    def onMouse(self, pane, evt):
        pos = evt[0]
        if not pane.vb.sceneBoundingRect().contains(pos):
            self.hideCrosshair()
            return
        mp = pane.vb.mapSceneToView(pos)
        self.hover_idx = self.nearestIndex(mp.x())
        snapped_x = self.disp["x"][self.hover_idx]
        self.cross_x, self.cross_y, self.cross_pane = snapped_x, mp.y(), pane
        for item in self.allPanes():
            item.setCross(snapped_x, mp.y() if item is pane else None)
        self.time_axis.update()
        self.updateInfo()

    def onSceneClick(self, pane, ev):
        return

    def updateInfo(self):
        data = self.disp
        n = len(data["x"])
        if n == 0:
            return
        index = (
            self.hover_idx
            if self.hover_idx is not None and self.hover_idx < n
            else n - 1
        )
        last = self.raw["c"][-1]
        sess = (last / self.market.first_open - 1) * 100
        status = (
            spanHtml("❚❚ PAUSED", "#f0b429") if self.paused else spanHtml("● LIVE", UP)
        )
        self.status.setText(
            f'{status} &nbsp;&nbsp; <b>{spanHtml(fmtPrice(last), UP if sess >= 0 else DOWN)}</b>'
            f' &nbsp;{spanHtml(f"{sess:+.2f}%", UP if sess >= 0 else DOWN)}'
        )
        col = UP if data["c"][index] >= data["o"][index] else DOWN
        chg = (data["c"][index] / data["o"][index] - 1) * 100
        tf_label = next(label for label, value in TIMEFRAMES if value == self.tf)
        self.price_pane.info.setText(
            f'{spanHtml(f"{self.symbol} · {tf_label} · {self.chart_type}", MUTED)} &nbsp; '
            f'O {spanHtml(fmtPrice(data["o"][index]), col)} &nbsp;'
            f'H {spanHtml(fmtPrice(data["h"][index]), col)} &nbsp;'
            f'L {spanHtml(fmtPrice(data["l"][index]), col)} &nbsp;'
            f'C {spanHtml(fmtPrice(data["c"][index]), col)} &nbsp;'
            f'{spanHtml(f"({chg:+.2f}%)", col)}'
        )
        for pane in self.panes.values():
            pane.header(index)

    def cleanup(self):
        if self._cleaned_up:
            return
        self._cleaned_up = True
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self._tickerTypingFilter)
        self.tick_timer.stop()
        self.render_timer.stop()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "symbolSearch"):
            self.symbolSearch.setGeometry(self.rect())

    def hideEvent(self, event):
        # Keep timers running while tab is hidden so switching back is warm;
        # pause only on cleanup.
        super().hideEvent(event)

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)


__all__ = ["FLOW_CHART_TYPES", "OrderflowChartView"]
