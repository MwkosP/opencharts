"""Order Book / Flow workspace with Orderbook, Orderflow, Depth, and Tape tabs."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from chartist.core.orderflow import (
    EXCHANGES,
    buildOrderBook,
    buildTape,
    nextTapePrints,
)
from chartist.theme import BORDER, DRAW, FG, MUTED, UP, DOWN


SYMBOLS = {
    "AAPL": {"name": "Apple Inc.", "mid": 198.40},
    "MSFT": {"name": "Microsoft Corp.", "mid": 428.10},
    "NVDA": {"name": "NVIDIA Corp.", "mid": 118.55},
    "SPY": {"name": "SPDR S&P 500 ETF", "mid": 562.80},
    "TSLA": {"name": "Tesla Inc.", "mid": 248.90},
}

_TAB_BG = "#090c12"


def _flowStyles() -> str:
    return f"""
        QWidget#orderFlowView, QWidget#orderFlowView QWidget {{
            color: {FG};
            background: {_TAB_BG};
        }}
        QWidget#orderFlowView *:focus {{
            outline: none;
        }}
        QTabWidget#orderFlowTabs {{
            border: 0px;
            background: {_TAB_BG};
            outline: none;
        }}
        QTabWidget#orderFlowTabs::pane {{
            border: 0px;
            margin: 0px;
            padding: 0px;
            background: {_TAB_BG};
        }}
        QTabWidget#orderFlowTabs > QTabBar {{
            border: 0px;
            outline: none;
            background: {_TAB_BG};
        }}
        QTabWidget#orderFlowTabs > QTabBar::tab {{
            color: {MUTED};
            background: {_TAB_BG};
            border: 0px;
            outline: none;
            margin: 0px;
            padding: 9px 18px;
        }}
        QTabWidget#orderFlowTabs > QTabBar::tab:selected {{
            color: #ffffff;
            background: {_TAB_BG};
            border: 0px;
        }}
        QTabWidget#orderFlowTabs > QTabBar::tab:hover {{
            color: #ffffff;
        }}
        QWidget#flowToolbar {{
            background: {_TAB_BG};
            border: 0px;
        }}
        QLabel#legendText {{
            color: {MUTED};
            font-size: 8.5pt;
        }}
        QLabel#midLabel {{
            color: #9db4ff;
            font-weight: 700;
            padding-left: 10px;
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
        QTableWidget#bookTable, QTableWidget#tapeTable {{
            background: {_TAB_BG};
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
        QLabel#statValue {{
            color: #e7ebf2;
            font-weight: 600;
            font-size: 13pt;
        }}
        QLabel#statCaption {{
            color: {MUTED};
            font-size: 8.5pt;
        }}
    """


class _BinanceBookLadder(QtWidgets.QWidget):
    """Single-column Binance ladder: asks above, bids below; depth bars on the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.book = None
        self._prev_sizes: dict[tuple[str, float], float] = {}
        self._flashes: dict[tuple[str, float], float] = {}  # key -> alpha 0..1
        self._row_h = 22

    def setBook(self, book):
        if book is not None and book.bids and book.asks:
            next_sizes: dict[tuple[str, float], float] = {}
            for level in book.asks:
                key = ("ask", float(level.price))
                next_sizes[key] = float(level.size)
                prev = self._prev_sizes.get(key)
                if prev is not None and abs(prev - level.size) / max(prev, 1.0) > 0.04:
                    self._flashes[key] = 1.0
            for level in book.bids:
                key = ("bid", float(level.price))
                next_sizes[key] = float(level.size)
                prev = self._prev_sizes.get(key)
                if prev is not None and abs(prev - level.size) / max(prev, 1.0) > 0.04:
                    self._flashes[key] = 1.0
            self._prev_sizes = next_sizes
            # Decay flashes each paint cycle driven by the live timer.
            for key in list(self._flashes):
                self._flashes[key] *= 0.72
                if self._flashes[key] < 0.05:
                    del self._flashes[key]
        self.book = book
        levels = 0 if book is None else len(book.asks) + len(book.bids)
        self.setMinimumHeight(max(200, (levels + 2) * self._row_h))
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(self.rect(), QtGui.QColor(_TAB_BG))
            if self.book is None or not self.book.bids or not self.book.asks:
                return

            asks = list(reversed(self.book.asks))  # far ask at top
            bids = list(self.book.bids)  # best bid first
            max_size = max(
                max(level.size for level in self.book.asks),
                max(level.size for level in self.book.bids),
                1.0,
            )
            ask_cum = list(reversed(np.cumsum([level.size for level in self.book.asks])))
            bid_cum = list(np.cumsum([level.size for level in self.book.bids]))

            width = self.width()
            # Columns: Price | Amount | Total — depth heat always from the right.
            col_price = int(width * 0.30)
            col_amount = int(width * 0.28)
            y = 0

            header_font = painter.font()
            header_font.setPointSize(8)
            painter.setFont(header_font)
            painter.setPen(QtGui.QPen(QtGui.QColor(MUTED)))
            painter.drawText(12, y + 16, "Price")
            painter.drawText(col_price + 8, y + 16, "Amount")
            painter.drawText(col_price + col_amount + 8, y + 16, "Total")
            y += self._row_h

            body = painter.font()
            body.setPointSize(9)
            painter.setFont(body)

            def draw_row(level, total, side, yy):
                heat = float(level.size / max_size)
                bar_w = max(2, int((width - 24) * heat))
                flash = self._flashes.get((side, float(level.price)), 0.0)
                if side == "ask":
                    bar_color = QtGui.QColor(239, 83, 80, int(40 + 100 * heat))
                    text_color = QtGui.QColor(DOWN)
                    flash_fill = QtGui.QColor(239, 83, 80, int(55 * flash))
                else:
                    bar_color = QtGui.QColor(38, 166, 154, int(40 + 100 * heat))
                    text_color = QtGui.QColor(UP)
                    flash_fill = QtGui.QColor(38, 166, 154, int(55 * flash))

                # Both buy and sell depth grow from the right edge.
                painter.fillRect(
                    width - 12 - bar_w, yy + 1, bar_w, self._row_h - 2, bar_color
                )
                if flash > 0.05:
                    painter.fillRect(0, yy, width, self._row_h, flash_fill)

                painter.setPen(QtGui.QPen(text_color))
                painter.drawText(
                    12,
                    yy,
                    col_price - 16,
                    self._row_h,
                    int(QtCore.Qt.AlignmentFlag.AlignVCenter)
                    | int(QtCore.Qt.AlignmentFlag.AlignLeft),
                    f"{level.price:.2f}",
                )
                painter.setPen(QtGui.QPen(QtGui.QColor(FG)))
                painter.drawText(
                    col_price + 8,
                    yy,
                    col_amount - 12,
                    self._row_h,
                    int(QtCore.Qt.AlignmentFlag.AlignVCenter)
                    | int(QtCore.Qt.AlignmentFlag.AlignLeft),
                    f"{level.size:,.3f}",
                )
                painter.drawText(
                    col_price + col_amount + 8,
                    yy,
                    width - col_price - col_amount - 20,
                    self._row_h,
                    int(QtCore.Qt.AlignmentFlag.AlignVCenter)
                    | int(QtCore.Qt.AlignmentFlag.AlignLeft),
                    f"{total:,.3f}",
                )

            for level, total in zip(asks, ask_cum):
                draw_row(level, float(total), "ask", y)
                y += self._row_h

            # Mid / last banner
            painter.fillRect(0, y, width, self._row_h + 6, QtGui.QColor(20, 26, 36))
            mid_font = painter.font()
            mid_font.setPointSize(12)
            mid_font.setBold(True)
            painter.setFont(mid_font)
            spread = self.book.spread
            imb = self.book.imbalance
            mid_color = QtGui.QColor(UP if imb >= 0 else DOWN)
            painter.setPen(QtGui.QPen(mid_color))
            painter.drawText(
                12,
                y,
                width - 24,
                self._row_h + 6,
                int(QtCore.Qt.AlignmentFlag.AlignVCenter)
                | int(QtCore.Qt.AlignmentFlag.AlignLeft),
                f"{self.book.mid:.2f}",
            )
            painter.setFont(body)
            painter.setPen(QtGui.QPen(QtGui.QColor(MUTED)))
            painter.drawText(
                12,
                y,
                width - 24,
                self._row_h + 6,
                int(QtCore.Qt.AlignmentFlag.AlignVCenter)
                | int(QtCore.Qt.AlignmentFlag.AlignRight),
                f"Spread {spread:.4f}   Imb {imb:+.0%}",
            )
            y += self._row_h + 6

            for level, total in zip(bids, bid_cum):
                draw_row(level, float(total), "bid", y)
                y += self._row_h
        finally:
            painter.end()


class OrderbookTab(QtWidgets.QWidget):
    """Live Binance-style L2 book with Aggregated / per-exchange feeds."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = "AAPL"
        self.exchange = "AGG"
        self._mid = SYMBOLS[self.symbol]["mid"]
        self._pulse = 0
        self._rng = np.random.default_rng(7)
        self._buildUi()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self._tickLive)
        self._timer.start()
        self._blink = QtCore.QTimer(self)
        self._blink.setInterval(700)
        self._blink.timeout.connect(self._toggleLiveDot)
        self._blink.start()
        self._live_on = True
        self._reload()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()
        if not self._blink.isActive():
            self._blink.start()

    def hideEvent(self, event):
        self._timer.stop()
        self._blink.stop()
        super().hideEvent(event)

    def _toggleLiveDot(self):
        self._live_on = not self._live_on
        color = UP if self._live_on else MUTED
        self.liveDot.setStyleSheet(
            f"color: {color}; font-weight: 700; font-size: 9pt;"
        )

    def _buildUi(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("flowToolbar")
        row = QtWidgets.QHBoxLayout(toolbar)
        row.setContentsMargins(14, 9, 14, 9)
        row.setSpacing(8)

        row.addWidget(QtWidgets.QLabel("Symbol"))
        self.symbolCombo = QtWidgets.QComboBox()
        for symbol, meta in SYMBOLS.items():
            self.symbolCombo.addItem(f"{symbol}  ·  {meta['name']}", symbol)
        self.symbolCombo.currentIndexChanged.connect(self._symbolChanged)
        row.addWidget(self.symbolCombo)

        row.addWidget(QtWidgets.QLabel("Exchange"))
        self.exchangeCombo = QtWidgets.QComboBox()
        for code, label in EXCHANGES:
            self.exchangeCombo.addItem(label, code)
        self.exchangeCombo.setCurrentIndex(0)
        self.exchangeCombo.currentIndexChanged.connect(self._exchangeChanged)
        row.addWidget(self.exchangeCombo)

        self.liveDot = QtWidgets.QLabel("● LIVE")
        self.liveDot.setStyleSheet(f"color: {UP}; font-weight: 700; font-size: 9pt;")
        row.addWidget(self.liveDot)
        row.addStretch()
        badge = QtWidgets.QLabel("DEMO")
        badge.setObjectName("demoBadge")
        row.addWidget(badge)
        hint = QtWidgets.QLabel("Depth bars right · asks + bids")
        hint.setObjectName("legendText")
        row.addWidget(hint)
        root.addWidget(toolbar)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {_TAB_BG}; border: none; }}")
        self.ladder = _BinanceBookLadder()
        scroll.setWidget(self.ladder)
        root.addWidget(scroll, 1)

    def _symbolChanged(self, index):
        self.symbol = self.symbolCombo.itemData(index)
        self._mid = SYMBOLS[self.symbol]["mid"]
        self._pulse = 0
        self.ladder._prev_sizes.clear()
        self.ladder._flashes.clear()
        self._reload()

    def _exchangeChanged(self, index):
        self.exchange = self.exchangeCombo.itemData(index)
        self._pulse = 0
        self.ladder._prev_sizes.clear()
        self.ladder._flashes.clear()
        self._reload()

    def _tickLive(self):
        # Micro random-walk mid + size pulse — keeps the book “alive”.
        tick = max(self._mid * 1e-4, 0.01)
        self._mid = float(
            np.clip(
                self._mid + self._rng.normal(0.0, tick * 0.55),
                SYMBOLS[self.symbol]["mid"] * 0.985,
                SYMBOLS[self.symbol]["mid"] * 1.015,
            )
        )
        self._pulse += 1
        self._reload()

    def _reload(self):
        book = buildOrderBook(
            self.symbol,
            self._mid,
            exchange=self.exchange,
            levels=20,
            pulse=self._pulse,
        )
        self.ladder.setBook(book)


class OrderflowTab(QtWidgets.QWidget):
    """Technicals-style footprint / heatmap chart with orderflow indicator panes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        from chartist.views.orderflow_chart import OrderflowChartView

        self.chart = OrderflowChartView()
        layout.addWidget(self.chart, 1)

    def hideEvent(self, event):
        super().hideEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "chart"):
            self.chart.cleanup()
        super().closeEvent(event)


class DepthTab(QtWidgets.QWidget):
    """Live cumulative depth chart for the selected venue book."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = "AAPL"
        self.exchange = "AGG"
        self._mid = SYMBOLS[self.symbol]["mid"]
        self._pulse = 0
        self._rng = np.random.default_rng(11)
        self._buildUi()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._tickLive)
        self._timer.start()
        self._blink = QtCore.QTimer(self)
        self._blink.setInterval(700)
        self._blink.timeout.connect(self._toggleLiveDot)
        self._blink.start()
        self._live_on = True
        self._reload()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()
        if not self._blink.isActive():
            self._blink.start()

    def hideEvent(self, event):
        self._timer.stop()
        self._blink.stop()
        super().hideEvent(event)

    def _toggleLiveDot(self):
        self._live_on = not self._live_on
        color = UP if self._live_on else MUTED
        self.liveDot.setStyleSheet(
            f"color: {color}; font-weight: 700; font-size: 9pt;"
        )

    def _buildUi(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("flowToolbar")
        row = QtWidgets.QHBoxLayout(toolbar)
        row.setContentsMargins(14, 9, 14, 9)
        row.setSpacing(8)
        row.addWidget(QtWidgets.QLabel("Symbol"))
        self.symbolCombo = QtWidgets.QComboBox()
        for symbol in SYMBOLS:
            self.symbolCombo.addItem(symbol, symbol)
        self.symbolCombo.currentIndexChanged.connect(self._symbolChanged)
        row.addWidget(self.symbolCombo)
        row.addWidget(QtWidgets.QLabel("Exchange"))
        self.exchangeCombo = QtWidgets.QComboBox()
        for code, label in EXCHANGES:
            self.exchangeCombo.addItem(label, code)
        self.exchangeCombo.currentIndexChanged.connect(self._exchangeChanged)
        row.addWidget(self.exchangeCombo)
        self.liveDot = QtWidgets.QLabel("● LIVE")
        self.liveDot.setStyleSheet(f"color: {UP}; font-weight: 700; font-size: 9pt;")
        row.addWidget(self.liveDot)
        row.addStretch()
        hint = QtWidgets.QLabel("Cumulative size by price")
        hint.setObjectName("legendText")
        row.addWidget(hint)
        root.addWidget(toolbar)

        self.plot = pg.PlotWidget()
        self.plot.setBackground(_TAB_BG)
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.plot.setLabel("bottom", "Price")
        self.plot.setLabel("left", "Cumulative size")
        self.plot.addLegend(offset=(10, 10))
        self.bidCurve = self.plot.plot(
            pen=pg.mkPen(UP, width=2),
            fillLevel=0,
            brush=pg.mkBrush(38, 166, 154, 60),
            name="Bids",
        )
        self.askCurve = self.plot.plot(
            pen=pg.mkPen(DOWN, width=2),
            fillLevel=0,
            brush=pg.mkBrush(239, 83, 80, 60),
            name="Asks",
        )
        self.midLine = pg.InfiniteLine(
            angle=90, pen=pg.mkPen("#6f8cff", width=1, style=QtCore.Qt.PenStyle.DashLine)
        )
        self.plot.addItem(self.midLine)
        root.addWidget(self.plot, 1)

    def _symbolChanged(self, index):
        self.symbol = self.symbolCombo.itemData(index)
        self._mid = SYMBOLS[self.symbol]["mid"]
        self._pulse = 0
        self._reload()

    def _exchangeChanged(self, index):
        self.exchange = self.exchangeCombo.itemData(index)
        self._pulse = 0
        self._reload()

    def _tickLive(self):
        tick = max(self._mid * 1e-4, 0.01)
        self._mid = float(
            np.clip(
                self._mid + self._rng.normal(0.0, tick * 0.45),
                SYMBOLS[self.symbol]["mid"] * 0.985,
                SYMBOLS[self.symbol]["mid"] * 1.015,
            )
        )
        self._pulse += 1
        self._reload()

    def _reload(self):
        book = buildOrderBook(
            self.symbol,
            self._mid,
            exchange=self.exchange,
            levels=24,
            pulse=self._pulse,
        )
        bid_prices = np.array([level.price for level in book.bids], dtype=float)
        bid_cum = np.cumsum([level.size for level in book.bids])
        ask_prices = np.array([level.price for level in book.asks], dtype=float)
        ask_cum = np.cumsum([level.size for level in book.asks])
        self.bidCurve.setData(bid_prices, bid_cum)
        self.askCurve.setData(ask_prices, ask_cum)
        self.midLine.setPos(self._mid)


class TapeTab(QtWidgets.QWidget):
    """Live time & sales tape, filterable by exchange."""

    _MAX_ROWS = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol = "AAPL"
        self.exchange = "AGG"
        self._mid = SYMBOLS[self.symbol]["mid"]
        self._pulse = 0
        self._rng = np.random.default_rng(19)
        self._prints = []
        self._buildUi()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(220)
        self._timer.timeout.connect(self._tickLive)
        self._timer.start()
        self._blink = QtCore.QTimer(self)
        self._blink.setInterval(700)
        self._blink.timeout.connect(self._toggleLiveDot)
        self._blink.start()
        self._live_on = True
        self._reload()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()
        if not self._blink.isActive():
            self._blink.start()

    def hideEvent(self, event):
        self._timer.stop()
        self._blink.stop()
        super().hideEvent(event)

    def _toggleLiveDot(self):
        self._live_on = not self._live_on
        color = UP if self._live_on else MUTED
        self.liveDot.setStyleSheet(
            f"color: {color}; font-weight: 700; font-size: 9pt;"
        )

    def _buildUi(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("flowToolbar")
        row = QtWidgets.QHBoxLayout(toolbar)
        row.setContentsMargins(14, 9, 14, 9)
        row.setSpacing(8)
        row.addWidget(QtWidgets.QLabel("Symbol"))
        self.symbolCombo = QtWidgets.QComboBox()
        for symbol in SYMBOLS:
            self.symbolCombo.addItem(symbol, symbol)
        self.symbolCombo.currentIndexChanged.connect(self._symbolChanged)
        row.addWidget(self.symbolCombo)
        row.addWidget(QtWidgets.QLabel("Exchange"))
        self.exchangeCombo = QtWidgets.QComboBox()
        for code, label in EXCHANGES:
            self.exchangeCombo.addItem(label, code)
        self.exchangeCombo.currentIndexChanged.connect(self._exchangeChanged)
        row.addWidget(self.exchangeCombo)
        self.liveDot = QtWidgets.QLabel("● LIVE")
        self.liveDot.setStyleSheet(f"color: {UP}; font-weight: 700; font-size: 9pt;")
        row.addWidget(self.liveDot)
        row.addStretch()
        hint = QtWidgets.QLabel("Time & sales · streaming prints")
        hint.setObjectName("legendText")
        row.addWidget(hint)
        root.addWidget(toolbar)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setObjectName("tapeTable")
        self.table.setHorizontalHeaderLabels(
            ["Time", "Price", "Size", "Side", "Exchange"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        root.addWidget(self.table, 1)

    def _symbolChanged(self, index):
        self.symbol = self.symbolCombo.itemData(index)
        self._mid = SYMBOLS[self.symbol]["mid"]
        self._pulse = 0
        self._reload()

    def _exchangeChanged(self, index):
        self.exchange = self.exchangeCombo.itemData(index)
        self._pulse = 0
        self._reload()

    def _tickLive(self):
        tick = max(self._mid * 1e-4, 0.01)
        self._mid = float(
            np.clip(
                self._mid + self._rng.normal(0.0, tick * 0.4),
                SYMBOLS[self.symbol]["mid"] * 0.985,
                SYMBOLS[self.symbol]["mid"] * 1.015,
            )
        )
        self._pulse += 1
        fresh = nextTapePrints(
            self.symbol,
            self._mid,
            exchange=self.exchange,
            pulse=self._pulse,
            count=int(self._rng.integers(1, 4)),
        )
        self._prints = (fresh + self._prints)[: self._MAX_ROWS]
        self._paintTable(highlight=len(fresh))

    def _reload(self):
        self._prints = buildTape(
            self.symbol,
            self._mid,
            exchange=self.exchange,
            count=80,
            pulse=self._pulse,
        )
        self._paintTable(highlight=0)

    def _paintTable(self, highlight: int = 0):
        self.table.setRowCount(len(self._prints))
        for row, print_ in enumerate(self._prints):
            values = (
                print_.time_label,
                f"{print_.price:.2f}",
                f"{print_.size:,.0f}",
                print_.side.upper(),
                print_.exchange,
            )
            color = QtGui.QColor(UP if print_.side == "buy" else DOWN)
            bg = None
            if row < highlight:
                bg = QtGui.QColor(38, 166, 154, 40) if print_.side == "buy" else QtGui.QColor(
                    239, 83, 80, 40
                )
            for column, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
                item.setForeground(color)
                if bg is not None:
                    item.setBackground(bg)
                self.table.setItem(row, column, item)
        if highlight and self.table.rowCount():
            self.table.scrollToTop()


class OrderFlowView(QtWidgets.QWidget):
    """Container for Order Book / Flow analysis subtabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("orderFlowView")
        self.setStyleSheet(_flowStyles())
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("orderFlowTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        bar = self.tabs.tabBar()
        bar.setDrawBase(False)
        bar.setExpanding(False)
        bar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        bar.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.tabs.addTab(OrderbookTab(), "Orderbook")
        self.tabs.addTab(OrderflowTab(), "Orderflow")
        self.tabs.addTab(DepthTab(), "Depth")
        self.tabs.addTab(TapeTab(), "Tape")
        layout.addWidget(self.tabs)


__all__ = [
    "DepthTab",
    "OrderFlowView",
    "OrderbookTab",
    "OrderflowTab",
    "TapeTab",
]
