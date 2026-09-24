"""OnChain workspace: network analytics, indicators, flows, wallet graphs."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from chartist.core.onchain import (
    LIVE_MS,
    NETWORKS,
    buildIndicators,
    buildKpis,
    buildTransfers,
    buildWalletGraph,
)
from chartist.theme import BORDER, DRAW, FG, MUTED, UP, DOWN


_TAB_BG = "#090c12"
_CLUSTER_COLORS = {
    "Exchanges": "#2962ff",
    "Whales": "#26a69a",
    "Miners/Validators": "#f0b429",
    "DeFi": "#9db4ff",
    "OTC": "#b99cff",
    "Retail hubs": "#8b949e",
}


def _styles() -> str:
    return f"""
        QWidget#onChainView, QWidget#onChainView QWidget {{
            color: {FG}; background: {_TAB_BG};
        }}
        QWidget#onChainView *:focus {{ outline: none; }}
        QTabWidget#onChainTabs {{
            border: 0px; background: {_TAB_BG}; outline: none;
        }}
        QTabWidget#onChainTabs::pane {{
            border: 0px; margin: 0px; padding: 0px; background: {_TAB_BG};
        }}
        QTabWidget#onChainTabs > QTabBar {{
            border: 0px; outline: none; background: {_TAB_BG};
        }}
        QTabWidget#onChainTabs > QTabBar::tab {{
            color: {MUTED}; background: {_TAB_BG}; border: 0px;
            outline: none; margin: 0px; padding: 9px 18px;
        }}
        QTabWidget#onChainTabs > QTabBar::tab:selected {{
            color: #ffffff; background: {_TAB_BG}; border: 0px;
        }}
        QTabWidget#onChainTabs > QTabBar::tab:hover {{ color: #ffffff; }}
        QWidget#ocToolbar {{ background: {_TAB_BG}; border: 0px; }}
        QLabel#legendText {{ color: {MUTED}; font-size: 8.5pt; }}
        QLabel#demoBadge {{
            color: #b99cff; background: #24183c; border: 1px solid #49336f;
            border-radius: 4px; padding: 3px 7px; font-size: 8pt; font-weight: 700;
        }}
        QLabel#statValue {{ color: #e7ebf2; font-weight: 600; font-size: 14pt; }}
        QLabel#statCaption {{ color: {MUTED}; font-size: 8.5pt; }}
        QComboBox {{
            color: {FG}; background: #171c25; border: 1px solid {BORDER};
            border-radius: 5px; padding: 6px 9px; min-width: 100px;
        }}
        QComboBox QAbstractItemView {{
            color: {FG}; background: #171c25; selection-background-color: {DRAW};
        }}
        QTableWidget#ocTable {{
            background: {_TAB_BG}; alternate-background-color: #0d121a;
            color: {FG}; border: none; gridline-color: transparent;
        }}
        QHeaderView::section {{
            background: #0d121a; color: {MUTED}; border: none;
            border-bottom: 1px solid {BORDER}; padding: 8px 4px; font-size: 8.5pt;
        }}
    """


def _networkCombo(current="BTC"):
    combo = QtWidgets.QComboBox()
    for code, name in NETWORKS:
        combo.addItem(f"{code}  ·  {name}", code)
    idx = next((i for i, (c, _) in enumerate(NETWORKS) if c == current), 0)
    combo.setCurrentIndex(idx)
    return combo


def _liveToolbar(hint: str):
    toolbar = QtWidgets.QWidget()
    toolbar.setObjectName("ocToolbar")
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
    tip = QtWidgets.QLabel(hint)
    tip.setObjectName("legendText")
    row.addWidget(tip)
    return toolbar, row, live


def _wireSlow(widget, tick, interval=LIVE_MS):
    widget._pulse = 0
    widget._live_on = True
    widget._timer = QtCore.QTimer(widget)
    widget._timer.setInterval(interval)
    widget._timer.timeout.connect(tick)
    widget._timer.start()
    widget._blink = QtCore.QTimer(widget)
    widget._blink.setInterval(1400)
    widget._blink.timeout.connect(lambda: _blink(widget))
    widget._blink.start()


def _blink(widget):
    widget._live_on = not widget._live_on
    color = UP if widget._live_on else MUTED
    if hasattr(widget, "_liveDot"):
        widget._liveDot.setStyleSheet(
            f"color: {color}; font-weight: 700; font-size: 9pt;"
        )


def _timers(widget, showing: bool):
    if showing:
        if not widget._timer.isActive():
            widget._timer.start()
        if not widget._blink.isActive():
            widget._blink.start()
    else:
        widget._timer.stop()
        widget._blink.stop()


class OverviewTab(QtWidgets.QWidget):
    """Network KPIs + headline on-chain charts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = "BTC"
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        toolbar, row, self._liveDot = _liveToolbar("Network overview · KPIs + flows")
        row.insertWidget(1, QtWidgets.QLabel("Network"))
        self.netCombo = _networkCombo()
        self.netCombo.currentIndexChanged.connect(self._netChanged)
        row.insertWidget(2, self.netCombo)
        root.addWidget(toolbar)

        self.kpiRow = QtWidgets.QHBoxLayout()
        self.kpiRow.setContentsMargins(16, 8, 16, 8)
        self.kpiLabels = []
        for _ in range(6):
            box = QtWidgets.QVBoxLayout()
            value = QtWidgets.QLabel("—")
            value.setObjectName("statValue")
            caption = QtWidgets.QLabel("")
            caption.setObjectName("statCaption")
            box.addWidget(value)
            box.addWidget(caption)
            self.kpiRow.addLayout(box)
            self.kpiLabels.append((value, caption))
        root.addLayout(self.kpiRow)

        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(8, 0, 8, 8)
        grid.setSpacing(8)
        self.activePlot = self._plot("Active addresses")
        self.activeCurve = self.activePlot.plot(pen=pg.mkPen(DRAW, width=2))
        grid.addWidget(self.activePlot, 0, 0)
        self.flowPlot = self._plot("Exchange netflow")
        self.inCurve = self.flowPlot.plot(pen=pg.mkPen(DOWN, width=2), name="In")
        self.outCurve = self.flowPlot.plot(pen=pg.mkPen(UP, width=2), name="Out")
        self.flowPlot.addLegend(offset=(8, 8))
        grid.addWidget(self.flowPlot, 0, 1)
        self.mvrvPlot = self._plot("MVRV / SOPR")
        self.mvrvCurve = self.mvrvPlot.plot(pen=pg.mkPen("#f0b429", width=2), name="MVRV")
        self.soprCurve = self.mvrvPlot.plot(pen=pg.mkPen("#9db4ff", width=2), name="SOPR")
        self.mvrvPlot.addLegend(offset=(8, 8))
        grid.addWidget(self.mvrvPlot, 1, 0, 1, 2)
        root.addLayout(grid, 1)

        _wireSlow(self, self._tick)
        self._reload()

    def showEvent(self, e):
        super().showEvent(e)
        _timers(self, True)

    def hideEvent(self, e):
        _timers(self, False)
        super().hideEvent(e)

    def _plot(self, title):
        plot = pg.PlotWidget()
        plot.setBackground(_TAB_BG)
        plot.showGrid(x=True, y=True, alpha=0.12)
        plot.setTitle(title, color=MUTED, size="9pt")
        return plot

    def _netChanged(self, _=None):
        self.network = self.netCombo.currentData()
        self._reload()

    def _tick(self):
        self._pulse += 1
        self._reload()

    def _reload(self):
        k = buildKpis(self.network, self._pulse)
        unit_label = "Hashrate EH/s" if self.network == "BTC" else "Stake / security metric"
        stats = (
            (f"{k.active_addresses:,.0f}", "Active addresses"),
            (f"{k.tx_count:,.0f}", "Transactions"),
            (f"{k.fees_native:.4g}", "Fees (native)"),
            (f"{k.exchange_netflow:+,.0f}", "Exch. netflow"),
            (f"{k.whale_ratio:.0%}", "Whale ratio"),
            (f"{k.hash_or_stake:,.1f}", unit_label),
        )
        for (value, caption), (text, label) in zip(self.kpiLabels, stats):
            value.setText(text)
            if "netflow" in label.lower():
                value.setStyleSheet(
                    f"color: {UP if k.exchange_netflow < 0 else DOWN}; "
                    f"font-weight: 600; font-size: 14pt;"
                )
            else:
                value.setStyleSheet("color: #e7ebf2; font-weight: 600; font-size: 14pt;")
            caption.setText(label)

        series = {s.key: s for s in buildIndicators(self.network, self._pulse)}
        self.activeCurve.setData(series["active"].dates, series["active"].values)
        self.inCurve.setData(series["flows"].dates, series["flows"].values)
        self.outCurve.setData(series["flows"].dates, series["flows"].secondary)
        self.mvrvCurve.setData(series["mvrv"].dates, series["mvrv"].values)
        self.soprCurve.setData(series["sopr"].dates, series["sopr"].values)


class IndicatorsTab(QtWidgets.QWidget):
    """Full on-chain indicator grid for the selected network."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = "BTC"
        self._plots = {}
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        toolbar, row, self._liveDot = _liveToolbar("On-chain indicators")
        row.insertWidget(1, QtWidgets.QLabel("Network"))
        self.netCombo = _networkCombo()
        self.netCombo.currentIndexChanged.connect(self._netChanged)
        row.insertWidget(2, self.netCombo)
        root.addWidget(toolbar)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        host = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(host)
        self.grid.setContentsMargins(8, 4, 8, 8)
        self.grid.setSpacing(8)
        scroll.setWidget(host)
        root.addWidget(scroll, 1)
        _wireSlow(self, self._tick)
        self._reload()

    def showEvent(self, e):
        super().showEvent(e)
        _timers(self, True)

    def hideEvent(self, e):
        _timers(self, False)
        super().hideEvent(e)

    def _netChanged(self, _=None):
        self.network = self.netCombo.currentData()
        # Clear plots when network family changes (BTC vs L2 set).
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._plots.clear()
        self._reload()

    def _tick(self):
        self._pulse += 1
        self._reload()

    def _reload(self):
        series_list = buildIndicators(self.network, self._pulse)
        for index, series in enumerate(series_list):
            if series.key not in self._plots:
                plot = pg.PlotWidget()
                plot.setBackground(_TAB_BG)
                plot.showGrid(x=True, y=True, alpha=0.12)
                plot.setTitle(series.title, color=MUTED, size="9pt")
                plot.setMinimumHeight(150)
                primary = plot.plot(pen=pg.mkPen(DRAW, width=2))
                secondary = None
                if series.secondary is not None:
                    secondary = plot.plot(pen=pg.mkPen(UP, width=2))
                    plot.addLegend(offset=(8, 8))
                self.grid.addWidget(plot, index // 2, index % 2)
                self._plots[series.key] = {
                    "plot": plot,
                    "primary": primary,
                    "secondary": secondary,
                }
            entry = self._plots[series.key]
            entry["plot"].setTitle(series.title, color=MUTED, size="9pt")
            entry["primary"].setData(series.dates, series.values)
            if entry["secondary"] is not None and series.secondary is not None:
                entry["secondary"].setData(series.dates, series.secondary)


class FlowsTab(QtWidgets.QWidget):
    """Exchange / whale transfer tape + flow charts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = "BTC"
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        toolbar, row, self._liveDot = _liveToolbar("Large transfers · exchange flows")
        row.insertWidget(1, QtWidgets.QLabel("Network"))
        self.netCombo = _networkCombo()
        self.netCombo.currentIndexChanged.connect(self._netChanged)
        row.insertWidget(2, self.netCombo)
        root.addWidget(toolbar)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.flowPlot = pg.PlotWidget()
        self.flowPlot.setBackground(_TAB_BG)
        self.flowPlot.showGrid(x=True, y=True, alpha=0.12)
        self.flowPlot.setTitle("Exchange inflow vs outflow", color=MUTED, size="9pt")
        self.inCurve = self.flowPlot.plot(
            pen=pg.mkPen(DOWN, width=2),
            fillLevel=0,
            brush=pg.mkBrush(239, 83, 80, 40),
            name="Inflow",
        )
        self.outCurve = self.flowPlot.plot(
            pen=pg.mkPen(UP, width=2),
            fillLevel=0,
            brush=pg.mkBrush(38, 166, 154, 40),
            name="Outflow",
        )
        self.flowPlot.addLegend(offset=(8, 8))
        split.addWidget(self.flowPlot)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setObjectName("ocTable")
        self.table.setHorizontalHeaderLabels(
            ["Time", "From", "To", "Amount", "USD", "Kind"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        split.addWidget(self.table)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        root.addWidget(split, 1)
        _wireSlow(self, self._tick)
        self._reload()

    def showEvent(self, e):
        super().showEvent(e)
        _timers(self, True)

    def hideEvent(self, e):
        _timers(self, False)
        super().hideEvent(e)

    def _netChanged(self, _=None):
        self.network = self.netCombo.currentData()
        self._reload()

    def _tick(self):
        self._pulse += 1
        self._reload()

    def _reload(self):
        series = {s.key: s for s in buildIndicators(self.network, self._pulse)}
        flows = series["flows"]
        self.inCurve.setData(flows.dates, flows.values)
        self.outCurve.setData(flows.dates, flows.secondary)
        transfers = buildTransfers(self.network, self._pulse)
        self.table.setRowCount(len(transfers))
        kind_color = {
            "exchange_in": DOWN,
            "exchange_out": UP,
            "whale": "#f0b429",
            "bridge": "#9db4ff",
            "dex": DRAW,
        }
        for row, t in enumerate(transfers):
            values = (
                t.time_label,
                t.from_label,
                t.to_label,
                f"{t.amount:,.4g}",
                f"${t.usd:,.0f}",
                t.kind,
            )
            color = QtGui.QColor(kind_color.get(t.kind, FG))
            for col, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
                if col == 5:
                    item.setForeground(color)
                self.table.setItem(row, col, item)


class WalletGraphCanvas(QtWidgets.QWidget):
    selectionChanged = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.graph = None
        self.selected = None
        self.setMinimumSize(420, 360)
        self.setMouseTracking(True)

    def setGraph(self, graph):
        self.graph = graph
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        try:
            painter.fillRect(self.rect(), QtGui.QColor(_TAB_BG))
            if self.graph is None:
                return
            w, h = self.width(), self.height()
            cx, cy = w * 0.5, h * 0.5
            scale = min(w, h) * 0.38
            by_id = {n.wallet_id: n for n in self.graph.nodes}

            def pos(node):
                return QtCore.QPointF(cx + node.x * scale, cy + node.y * scale)

            for edge in self.graph.edges:
                a, b = by_id.get(edge.source), by_id.get(edge.target)
                if a is None or b is None:
                    continue
                alpha = int(40 + 140 * edge.weight)
                painter.setPen(
                    QtGui.QPen(QtGui.QColor(120, 140, 180, alpha), 1.0 + edge.weight)
                )
                painter.drawLine(pos(a), pos(b))

            for node in self.graph.nodes:
                color = QtGui.QColor(_CLUSTER_COLORS.get(node.cluster, FG))
                r = 5 + 10 * node.size
                p = pos(node)
                if self.selected == node.wallet_id:
                    painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 2))
                else:
                    painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(p, r, r)

            y = 12
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            for cluster, color in _CLUSTER_COLORS.items():
                painter.setBrush(QtGui.QColor(color))
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.drawEllipse(QtCore.QPointF(16, y + 6), 5, 5)
                painter.setPen(QtGui.QPen(QtGui.QColor(MUTED)))
                painter.drawText(
                    28, y, 140, 16, int(QtCore.Qt.AlignmentFlag.AlignVCenter), cluster
                )
                y += 18
        finally:
            painter.end()

    def mousePressEvent(self, event):
        if self.graph is None:
            return
        w, h = self.width(), self.height()
        cx, cy = w * 0.5, h * 0.5
        scale = min(w, h) * 0.38
        click = event.position()
        hit = None
        for node in self.graph.nodes:
            px = cx + node.x * scale
            py = cy + node.y * scale
            r = 5 + 10 * node.size
            if (click.x() - px) ** 2 + (click.y() - py) ** 2 <= (r + 4) ** 2:
                hit = node.wallet_id
                break
        self.selected = hit
        self.update()
        self.selectionChanged.emit(hit)


class _CorrHeatmap(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.matrix = None
        self.labels = ()
        self.setMinimumSize(260, 260)

    def setMatrix(self, matrix, labels):
        self.matrix = np.asarray(matrix, dtype=float)
        self.labels = tuple(labels)
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(self.rect(), QtGui.QColor(_TAB_BG))
            if self.matrix is None or not self.labels:
                return
            n = len(self.labels)
            left, top = 88, 28
            size = min(self.width() - left - 16, self.height() - top - 16)
            cell = size / n
            font = painter.font()
            font.setPointSize(7)
            painter.setFont(font)
            for i, label in enumerate(self.labels):
                painter.setPen(QtGui.QPen(QtGui.QColor(MUTED)))
                painter.drawText(
                    4,
                    int(top + i * cell),
                    left - 8,
                    int(cell),
                    int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight),
                    label[:10],
                )
                painter.drawText(
                    int(left + i * cell),
                    4,
                    int(cell),
                    20,
                    int(QtCore.Qt.AlignmentFlag.AlignCenter),
                    label[:3],
                )
            for i in range(n):
                for j in range(n):
                    v = float(self.matrix[i, j])
                    # -1 red … 0 dark … +1 teal
                    if v >= 0:
                        color = QtGui.QColor(38, 166, 154, int(40 + 180 * v))
                    else:
                        color = QtGui.QColor(239, 83, 80, int(40 + 180 * abs(v)))
                    painter.fillRect(
                        QtCore.QRectF(left + j * cell, top + i * cell, cell - 1, cell - 1),
                        color,
                    )
        finally:
            painter.end()


class GraphTab(QtWidgets.QWidget):
    """Wallet graph analytics + cluster correlation heatmap."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = "BTC"
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        toolbar, row, self._liveDot = _liveToolbar(
            "Wallet relationships · cluster correlations"
        )
        row.insertWidget(1, QtWidgets.QLabel("Network"))
        self.netCombo = _networkCombo()
        self.netCombo.currentIndexChanged.connect(self._netChanged)
        row.insertWidget(2, self.netCombo)
        root.addWidget(toolbar)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(8, 0, 8, 8)
        body.setSpacing(10)
        self.canvas = WalletGraphCanvas()
        self.canvas.selectionChanged.connect(self._onSelect)
        body.addWidget(self.canvas, 3)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(self._caption("Cluster correlation"))
        self.corr = _CorrHeatmap()
        right.addWidget(self.corr, 2)
        right.addWidget(self._caption("Selection"))
        self.detail = QtWidgets.QLabel("Click a wallet node")
        self.detail.setObjectName("legendText")
        self.detail.setWordWrap(True)
        right.addWidget(self.detail)
        right.addStretch()
        body.addLayout(right, 2)
        root.addLayout(body, 1)
        _wireSlow(self, self._tick)
        self._reload()

    def _caption(self, text):
        label = QtWidgets.QLabel(text)
        label.setObjectName("legendText")
        return label

    def showEvent(self, e):
        super().showEvent(e)
        _timers(self, True)

    def hideEvent(self, e):
        _timers(self, False)
        super().hideEvent(e)

    def _netChanged(self, _=None):
        self.network = self.netCombo.currentData()
        self._reload()

    def _tick(self):
        self._pulse += 1
        self._reload()

    def _reload(self):
        graph = buildWalletGraph(self.network, self._pulse)
        self._graph = graph
        self.canvas.setGraph(graph)
        self.corr.setMatrix(graph.correlation, graph.clusters)

    def _onSelect(self, wallet_id):
        if not wallet_id or not hasattr(self, "_graph"):
            self.detail.setText("Click a wallet node")
            return
        node = next(n for n in self._graph.nodes if n.wallet_id == wallet_id)
        links = [
            e
            for e in self._graph.edges
            if e.source == wallet_id or e.target == wallet_id
        ]
        self.detail.setText(
            f"{node.label} · {node.cluster}\n"
            f"Size {node.size:.2f} · {len(links)} edges\n"
            f"Top link weight {max((e.weight for e in links), default=0):.2f}"
        )


class TradesTab(QtWidgets.QWidget):
    """Trade / transfer graph view — who traded with whom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = "BTC"
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        toolbar, row, self._liveDot = _liveToolbar(
            "Trade graph · counterparties from large prints"
        )
        row.insertWidget(1, QtWidgets.QLabel("Network"))
        self.netCombo = _networkCombo()
        self.netCombo.currentIndexChanged.connect(self._netChanged)
        row.insertWidget(2, self.netCombo)
        root.addWidget(toolbar)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.canvas = WalletGraphCanvas()
        split.addWidget(self.canvas)

        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 4, 4)
        self.usdPlot = pg.PlotWidget()
        self.usdPlot.setBackground(_TAB_BG)
        self.usdPlot.showGrid(x=True, y=True, alpha=0.12)
        self.usdPlot.setTitle("Large transfer USD (recent)", color=MUTED, size="9pt")
        self.usdBars = pg.BarGraphItem(x=[], height=[], width=0.7, brush=DRAW)
        self.usdPlot.addItem(self.usdBars)
        rl.addWidget(self.usdPlot, 1)
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setObjectName("ocTable")
        self.table.setHorizontalHeaderLabels(
            ["Time", "From", "To", "USD", "Kind"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        rl.addWidget(self.table, 2)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 1)
        _wireSlow(self, self._tick)
        self._reload()

    def showEvent(self, e):
        super().showEvent(e)
        _timers(self, True)

    def hideEvent(self, e):
        _timers(self, False)
        super().hideEvent(e)

    def _netChanged(self, _=None):
        self.network = self.netCombo.currentData()
        self._reload()

    def _tick(self):
        self._pulse += 1
        self._reload()

    def _reload(self):
        self.canvas.setGraph(buildWalletGraph(self.network, self._pulse))
        transfers = buildTransfers(self.network, self._pulse, count=40)
        xs = np.arange(len(transfers), dtype=float)
        heights = np.array([t.usd for t in transfers], dtype=float)
        colors = [
            DOWN if t.kind == "exchange_in" else UP if t.kind == "exchange_out" else DRAW
            for t in transfers
        ]
        self.usdPlot.removeItem(self.usdBars)
        self.usdBars = pg.BarGraphItem(
            x=xs, height=heights, width=0.7, brushes=colors
        )
        self.usdPlot.addItem(self.usdBars)
        self.table.setRowCount(len(transfers))
        for row, t in enumerate(transfers):
            for col, text in enumerate(
                (t.time_label, t.from_label, t.to_label, f"${t.usd:,.0f}", t.kind)
            ):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
                self.table.setItem(row, col, item)


class OnChainView(QtWidgets.QWidget):
    """Top-level OnChain analytics workspace."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("onChainView")
        self.setStyleSheet(_styles())
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("onChainTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        bar = self.tabs.tabBar()
        bar.setDrawBase(False)
        bar.setExpanding(False)
        bar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        bar.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.tabs.addTab(OverviewTab(), "Overview")
        self.tabs.addTab(IndicatorsTab(), "Indicators")
        self.tabs.addTab(FlowsTab(), "Flows")
        self.tabs.addTab(GraphTab(), "Graph")
        self.tabs.addTab(TradesTab(), "Trades")
        layout.addWidget(self.tabs)


__all__ = [
    "FlowsTab",
    "GraphTab",
    "IndicatorsTab",
    "OnChainView",
    "OverviewTab",
    "TradesTab",
]
