"""Centered symbol search overlay and keyboard activation filter."""

from pyqtgraph.Qt import QtCore, QtWidgets

from chartist.theme import BG, BORDER, DRAW, FG, MUTED


TICKERS = (
    ("BTC/USD", "Bitcoin / US Dollar"),
    ("ETH/USD", "Ethereum / US Dollar"),
    ("SOL/USD", "Solana / US Dollar"),
    ("AAPL", "Apple Inc."),
    ("MSFT", "Microsoft Corporation"),
    ("NVDA", "NVIDIA Corporation"),
    ("TSLA", "Tesla Inc."),
    ("SPY", "S&P 500 ETF"),
    ("QQQ", "Nasdaq 100 ETF"),
    ("EUR/USD", "Euro / US Dollar"),
    ("GBP/USD", "British Pound / US Dollar"),
    ("USD/JPY", "US Dollar / Japanese Yen"),
    ("XAU/USD", "Gold / US Dollar"),
    ("WTI", "West Texas Intermediate Crude"),
)


class TickerSearchOverlay(QtWidgets.QWidget):
    """Full-view dimmer containing a centered ticker search panel."""

    symbolSelected = QtCore.pyqtSignal(str)
    searchClosed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tickerSearchOverlay")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#tickerSearchOverlay {{
                background: rgba(0, 0, 0, 185);
            }}
            QFrame#tickerSearchPanel {{
                background: {BG};
                border: 1px solid #30363d;
                border-radius: 8px;
            }}
            QLabel#tickerSearchTitle {{
                color: {FG};
                font-size: 16px;
                font-weight: 600;
            }}
            QLineEdit {{
                min-height: 38px;
                padding: 0 12px;
                color: {FG};
                background: #090c12;
                border: 1px solid {DRAW};
                border-radius: 5px;
                font-size: 12pt;
                selection-background-color: {DRAW};
            }}
            QListWidget {{
                color: {FG};
                background: #090c12;
                border: 1px solid {BORDER};
                border-radius: 5px;
                outline: none;
                font-size: 10pt;
            }}
            QListWidget::item {{
                min-height: 36px;
                padding: 4px 10px;
                border-bottom: 1px solid {BORDER};
            }}
            QListWidget::item:hover {{ background: #171d27; }}
            QListWidget::item:selected {{
                color: #ffffff;
                background: #1d315e;
            }}
            QLabel#tickerSearchHint {{
                color: {MUTED};
                font-size: 9pt;
            }}
        """)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch()

        centered = QtWidgets.QHBoxLayout()
        centered.addStretch()
        panel = QtWidgets.QFrame()
        panel.setObjectName("tickerSearchPanel")
        panel.setFixedSize(560, 430)
        panelLayout = QtWidgets.QVBoxLayout(panel)
        panelLayout.setContentsMargins(20, 18, 20, 16)
        panelLayout.setSpacing(10)

        title = QtWidgets.QLabel("Symbol Search")
        title.setObjectName("tickerSearchTitle")
        panelLayout.addWidget(title)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search ticker, company, forex, crypto…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refreshResults)
        self.search.returnPressed.connect(self._chooseCurrent)
        panelLayout.addWidget(self.search)

        self.results = QtWidgets.QListWidget()
        self.results.itemClicked.connect(lambda *_: self._chooseCurrent())
        self.results.itemActivated.connect(lambda *_: self._chooseCurrent())
        panelLayout.addWidget(self.results, 1)

        hint = QtWidgets.QLabel("Enter to select  ·  Esc to close")
        hint.setObjectName("tickerSearchHint")
        panelLayout.addWidget(hint)

        centered.addWidget(panel)
        centered.addStretch()
        outer.addLayout(centered)
        outer.addStretch()

        self.hide()

    def openSearch(self, initialText=""):
        self.search.setText(initialText.upper())
        self._refreshResults(self.search.text())
        self.show()
        self.raise_()
        self.search.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
        self.search.setCursorPosition(len(self.search.text()))

    def closeSearch(self):
        if not self.isVisible():
            return
        self.hide()
        self.searchClosed.emit()
        if self.parentWidget() is not None:
            self.parentWidget().setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def _refreshResults(self, query):
        query = query.strip().upper()
        self.results.clear()
        for symbol, description in TICKERS:
            if query and query not in symbol and query not in description.upper():
                continue
            item = QtWidgets.QListWidgetItem(f"{symbol:<12}  {description}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, symbol)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def _chooseCurrent(self):
        item = self.results.currentItem()
        symbol = (
            item.data(QtCore.Qt.ItemDataRole.UserRole)
            if item is not None
            else self.search.text().strip().upper()
        )
        if symbol:
            self.symbolSelected.emit(symbol)
            self.closeSearch()


class TickerTypingFilter(QtCore.QObject):
    """Opens search when printable ticker text is typed over an active chart."""

    def __init__(self, chart):
        super().__init__(chart)
        self.chart = chart
        self._suppressedKey = None

    def eventFilter(self, watched, event):
        eventType = event.type()
        if eventType not in (
            QtCore.QEvent.Type.ShortcutOverride,
            QtCore.QEvent.Type.KeyPress,
        ):
            return False
        if not self.chart.isVisible():
            return False
        if self.chart.symbolSearch.isVisible():
            if event.key() == QtCore.Qt.Key.Key_Escape:
                self.chart.symbolSearch.closeSearch()
                self._suppressedKey = event.key()
                event.accept()
                return True
            if eventType == QtCore.QEvent.Type.KeyPress and event.key() == self._suppressedKey:
                self._suppressedKey = None
                return True
            return False
        if eventType == QtCore.QEvent.Type.KeyPress and event.key() == self._suppressedKey:
            self._suppressedKey = None
            return True
        modifiers = event.modifiers()
        allowed = (
            QtCore.Qt.KeyboardModifier.NoModifier
            | QtCore.Qt.KeyboardModifier.ShiftModifier
        )
        if modifiers & ~allowed:
            return False
        text = event.text()
        if len(text) != 1 or not text.isalnum():
            return False
        focus = QtWidgets.QApplication.focusWidget()
        if focus is not None and focus is not self.chart and not self.chart.isAncestorOf(focus):
            return False
        self.chart.openSymbolSearch(text)
        if eventType == QtCore.QEvent.Type.ShortcutOverride:
            self._suppressedKey = event.key()
            event.accept()
        return True


__all__ = ["TICKERS", "TickerSearchOverlay", "TickerTypingFilter"]
