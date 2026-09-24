"""TradingView-style financial news workspace."""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from PyQt6 import QtNetwork
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from chartist.theme import BG, BORDER, DRAW, FG, MUTED, UP


FEEDS = (
    (
        "CNBC",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "Markets",
    ),
    (
        "MarketWatch",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "Markets",
    ),
    (
        "CoinDesk",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "Crypto",
    ),
)

CATEGORIES = ("Top stories", "Markets", "Stocks", "Crypto", "Economy", "Earnings")
TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class NewsArticle:
    article_id: str
    title: str
    source: str
    category: str
    published: datetime
    summary: str
    url: str = ""
    symbols: tuple[str, ...] = ()


def _plainText(value: str | None) -> str:
    text = html.unescape(TAG_RE.sub(" ", value or ""))
    return " ".join(text.split())


def _parseDate(value: str | None) -> datetime:
    if value:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                pass
    return datetime.now(timezone.utc)


def _categoryFor(title: str, fallback: str) -> str:
    lowered = title.lower()
    if any(word in lowered for word in ("bitcoin", "crypto", "ether", "token")):
        return "Crypto"
    if any(word in lowered for word in ("earnings", "revenue", "quarter", "profit")):
        return "Earnings"
    if any(word in lowered for word in ("fed", "inflation", "gdp", "jobs", "economy")):
        return "Economy"
    if any(word in lowered for word in ("stock", "shares", "nasdaq", "s&p", "dow")):
        return "Stocks"
    return fallback


def parseFeed(payload: bytes, source: str, fallback_category: str) -> list[NewsArticle]:
    """Parse RSS or Atom bytes into normalized financial-news articles."""
    root = ET.fromstring(payload)
    articles = []
    entries = [
        node
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] in {"item", "entry"}
    ]
    for entry in entries[:30]:
        fields = {}
        link = ""
        for child in entry:
            name = child.tag.rsplit("}", 1)[-1]
            if name == "link" and child.attrib.get("href"):
                link = child.attrib["href"]
            elif child.text:
                fields.setdefault(name, child.text)
        title = _plainText(fields.get("title"))
        if not title:
            continue
        link = link or _plainText(fields.get("link"))
        summary = _plainText(
            fields.get("description")
            or fields.get("summary")
            or fields.get("content")
        )
        published = _parseDate(
            fields.get("pubDate")
            or fields.get("published")
            or fields.get("updated")
        )
        article_id = hashlib.sha1(
            f"{source}|{link}|{title}".encode("utf-8")
        ).hexdigest()
        articles.append(
            NewsArticle(
                article_id=article_id,
                title=title,
                source=source,
                category=_categoryFor(title, fallback_category),
                published=published,
                summary=summary or "Open the original article to read the full story.",
                url=link,
            )
        )
    return articles


def demoArticles() -> list[NewsArticle]:
    now = datetime.now(timezone.utc)
    rows = (
        (
            "Global markets steady as investors weigh the next rate decision",
            "Chartist Newswire",
            "Markets",
            4,
            "Stocks traded in a narrow range while Treasury yields eased. "
            "Investors are balancing resilient growth data against expectations "
            "that policy rates will remain restrictive for longer.",
            ("SPX", "NDX", "DXY"),
        ),
        (
            "Technology shares lead pre-market gains after strong guidance",
            "Market Desk",
            "Stocks",
            13,
            "Large-cap technology names moved higher before the opening bell "
            "after several companies issued stronger-than-expected guidance. "
            "Semiconductors and cloud software led the advance.",
            ("NVDA", "MSFT", "QQQ"),
        ),
        (
            "Bitcoin volatility rises as traders test a key resistance zone",
            "Digital Assets",
            "Crypto",
            24,
            "Bitcoin pushed into a closely watched resistance area as derivatives "
            "open interest increased. Traders are monitoring funding rates and "
            "spot-market demand for confirmation of the move.",
            ("BTCUSD", "ETHUSD"),
        ),
        (
            "Dollar slips after inflation expectations moderate",
            "Macro Wire",
            "Economy",
            39,
            "The dollar index moved lower after survey data showed a moderation "
            "in long-run inflation expectations. Currency markets remain focused "
            "on upcoming labor-market and consumer-price reports.",
            ("DXY", "EURUSD", "USDJPY"),
        ),
        (
            "Energy sector outperforms as crude inventories decline",
            "Commodities Desk",
            "Markets",
            58,
            "Energy shares outperformed the broader market after weekly inventory "
            "figures pointed to tighter near-term supply. Crude futures extended "
            "gains while refined-product margins improved.",
            ("CL1!", "XLE"),
        ),
        (
            "Retailer beats quarterly earnings estimates and lifts outlook",
            "Earnings Pulse",
            "Earnings",
            81,
            "The company reported stronger comparable sales and improved margins, "
            "then raised its full-year forecast. Management cited stable demand "
            "and easing freight expenses.",
            ("XRT",),
        ),
        (
            "European equities open higher as banks and industrials advance",
            "Europe Markets",
            "Stocks",
            112,
            "European benchmarks opened in positive territory with banks and "
            "industrial companies leading. Regional bond yields were little "
            "changed ahead of fresh economic data.",
            ("DAX", "SX5E", "UKX"),
        ),
        (
            "Gold holds near session high while real yields retreat",
            "Metals Brief",
            "Markets",
            146,
            "Gold remained supported as real yields edged down and the dollar "
            "softened. Traders continue to watch central-bank demand and the "
            "path of monetary policy.",
            ("XAUUSD", "GC1!"),
        ),
    )
    articles = []
    for title, source, category, minutes, summary, symbols in rows:
        article_id = hashlib.sha1(title.encode("utf-8")).hexdigest()
        articles.append(
            NewsArticle(
                article_id=article_id,
                title=title,
                source=source,
                category=category,
                published=now - timedelta(minutes=minutes),
                summary=summary,
                symbols=symbols,
            )
        )
    return articles


def _ageText(published: datetime) -> str:
    seconds = max(
        0, int((datetime.now(timezone.utc) - published).total_seconds())
    )
    if seconds < 60:
        return "now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


class ArticleCard(QtWidgets.QWidget):
    def __init__(self, article: NewsArticle, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("articleCard")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(6)

        meta = QtWidgets.QHBoxLayout()
        source = QtWidgets.QLabel(article.source.upper())
        source.setObjectName("cardSource")
        meta.addWidget(source)
        meta.addStretch()
        age = QtWidgets.QLabel(_ageText(article.published))
        age.setObjectName("cardMeta")
        meta.addWidget(age)
        layout.addLayout(meta)

        title = QtWidgets.QLabel(article.title)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        title.setMaximumHeight(48)
        layout.addWidget(title)

        if article.symbols:
            symbols = QtWidgets.QLabel("  ".join(article.symbols))
            symbols.setObjectName("cardSymbols")
            layout.addWidget(symbols)


class NewsView(QtWidgets.QWidget):
    """Searchable financial-news feed with an integrated reading pane."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("newsView")
        self.articles = {item.article_id: item for item in demoArticles()}
        self.saved = set()
        self.currentCategory = "Top stories"
        self.currentArticle = None
        self.activeReplies = set()
        self.completedFeeds = 0
        self.successfulFeeds = 0
        self.network = QtNetwork.QNetworkAccessManager(self)
        self._buildUi()
        self.applyFilters()
        QtCore.QTimer.singleShot(350, self.refreshFeeds)

    def _buildUi(self):
        self.setStyleSheet(f"""
            QWidget#newsView {{
                background: #090b10;
                color: {FG};
            }}
            QWidget#newsToolbar {{
                background: #0d1016;
                border-bottom: 1px solid {BORDER};
            }}
            QLabel#newsTitle {{
                color: #ffffff;
                font-size: 17px;
                font-weight: 700;
            }}
            QLabel#liveDot {{
                color: {UP};
                font-size: 13px;
            }}
            QLineEdit {{
                color: {FG};
                background: #151922;
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 7px 10px;
                selection-background-color: {DRAW};
            }}
            QLineEdit:focus {{ border-color: {DRAW}; }}
            QPushButton {{
                color: {FG};
                background: transparent;
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 7px 11px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                background: #1a1f29;
            }}
            QPushButton:checked {{
                color: #ffffff;
                background: #1b315f;
                border-color: {DRAW};
            }}
            QWidget#feedNav {{
                background: #0d1016;
                border-right: 1px solid {BORDER};
            }}
            QLabel#navHeading {{
                color: {MUTED};
                font-size: 8.5pt;
                font-weight: 700;
                padding: 8px 10px 3px 10px;
            }}
            QPushButton#feedButton {{
                border: none;
                border-radius: 4px;
                padding: 8px 11px;
                text-align: left;
            }}
            QPushButton#feedButton:checked {{
                color: #ffffff;
                background: #172445;
            }}
            QListWidget {{
                color: {FG};
                background: #0b0e13;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                border-bottom: 1px solid {BORDER};
            }}
            QListWidget::item:selected {{
                background: #151d2d;
                border-left: 2px solid {DRAW};
            }}
            QWidget#articleCard {{ background: transparent; }}
            QLabel#cardSource {{
                color: #7796ff;
                font-size: 8pt;
                font-weight: 700;
            }}
            QLabel#cardMeta {{
                color: {MUTED};
                font-size: 8.5pt;
            }}
            QLabel#cardTitle {{
                color: #edf1f7;
                font-size: 10.5pt;
                font-weight: 600;
            }}
            QLabel#cardSymbols {{
                color: {UP};
                font-size: 8.5pt;
            }}
            QScrollArea#reader {{
                background: {BG};
                border: none;
                border-left: 1px solid {BORDER};
            }}
            QWidget#readerBody {{ background: {BG}; }}
            QLabel#readerSource {{
                color: #7796ff;
                font-size: 9pt;
                font-weight: 700;
            }}
            QLabel#readerTitle {{
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
            }}
            QLabel#readerMeta {{
                color: {MUTED};
                font-size: 9pt;
            }}
            QLabel#readerSummary {{
                color: #c7cfdb;
                font-size: 11pt;
                line-height: 1.5;
            }}
            QLabel#emptyReader {{
                color: {MUTED};
                font-size: 11pt;
            }}
            QLabel#status {{
                color: {MUTED};
                background: #0d1016;
                border-top: 1px solid {BORDER};
                padding: 5px 10px;
                font-size: 8.5pt;
            }}
            QSplitter::handle {{ background: {BORDER}; width: 1px; }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background: #303744;
                border-radius: 4px;
                min-height: 28px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("newsToolbar")
        top = QtWidgets.QHBoxLayout(toolbar)
        top.setContentsMargins(14, 8, 14, 8)
        top.setSpacing(10)
        title = QtWidgets.QLabel("NEWS")
        title.setObjectName("newsTitle")
        top.addWidget(title)
        live = QtWidgets.QLabel("●  LIVE FEEDS")
        live.setObjectName("liveDot")
        top.addWidget(live)
        top.addStretch()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search news, sources, or symbols")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(280)
        self.search.textChanged.connect(self.applyFilters)
        top.addWidget(self.search)
        self.refreshButton = QtWidgets.QPushButton("↻  Refresh")
        self.refreshButton.clicked.connect(self.refreshFeeds)
        top.addWidget(self.refreshButton)
        root.addWidget(toolbar)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._buildFeedNavigation())
        splitter.addWidget(self._buildHeadlinePane())
        splitter.addWidget(self._buildReader())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([180, 430, 620])
        root.addWidget(splitter, 1)

        self.status = QtWidgets.QLabel(
            "Showing built-in market feed · Connecting to live sources…"
        )
        self.status.setObjectName("status")
        root.addWidget(self.status)

    def _buildFeedNavigation(self):
        panel = QtWidgets.QWidget()
        panel.setObjectName("feedNav")
        panel.setMinimumWidth(155)
        panel.setMaximumWidth(220)
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(7, 10, 7, 10)
        layout.setSpacing(2)

        heading = QtWidgets.QLabel("FEEDS")
        heading.setObjectName("navHeading")
        layout.addWidget(heading)
        self.feedGroup = QtWidgets.QButtonGroup(self)
        self.feedGroup.setExclusive(True)
        self.feedButtons = {}
        for category in CATEGORIES:
            button = self._feedButton(category)
            layout.addWidget(button)
        layout.addSpacing(12)
        library = QtWidgets.QLabel("LIBRARY")
        library.setObjectName("navHeading")
        layout.addWidget(library)
        saved = self._feedButton("Saved")
        saved.setText("☆  Saved")
        layout.addWidget(saved)
        layout.addStretch()
        self.feedButtons["Top stories"].setChecked(True)
        return panel

    def _feedButton(self, category):
        button = QtWidgets.QPushButton(category)
        button.setObjectName("feedButton")
        button.setCheckable(True)
        button.clicked.connect(
            lambda _, selected=category: self.selectCategory(selected)
        )
        self.feedGroup.addButton(button)
        self.feedButtons[category] = button
        return button

    def _buildHeadlinePane(self):
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.headlines = QtWidgets.QListWidget()
        self.headlines.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.headlines.currentItemChanged.connect(self._headlineSelected)
        layout.addWidget(self.headlines)
        return panel

    def _buildReader(self):
        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("reader")
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(360)
        self.readerBody = QtWidgets.QWidget()
        self.readerBody.setObjectName("readerBody")
        self.readerLayout = QtWidgets.QVBoxLayout(self.readerBody)
        self.readerLayout.setContentsMargins(30, 28, 30, 30)
        self.readerLayout.setSpacing(13)

        self.readerSource = QtWidgets.QLabel()
        self.readerSource.setObjectName("readerSource")
        self.readerLayout.addWidget(self.readerSource)
        self.readerTitle = QtWidgets.QLabel("Select a story to start reading")
        self.readerTitle.setObjectName("readerTitle")
        self.readerTitle.setWordWrap(True)
        self.readerLayout.addWidget(self.readerTitle)
        self.readerMeta = QtWidgets.QLabel(
            "Live and curated financial headlines appear here."
        )
        self.readerMeta.setObjectName("readerMeta")
        self.readerMeta.setWordWrap(True)
        self.readerLayout.addWidget(self.readerMeta)

        symbol_row = QtWidgets.QHBoxLayout()
        self.readerSymbols = QtWidgets.QLabel()
        self.readerSymbols.setObjectName("cardSymbols")
        symbol_row.addWidget(self.readerSymbols)
        symbol_row.addStretch()
        self.readerLayout.addLayout(symbol_row)

        self.readerSummary = QtWidgets.QLabel()
        self.readerSummary.setObjectName("readerSummary")
        self.readerSummary.setWordWrap(True)
        self.readerSummary.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.readerLayout.addWidget(self.readerSummary)
        self.readerLayout.addStretch()

        actions = QtWidgets.QHBoxLayout()
        self.saveButton = QtWidgets.QPushButton("☆  Save story")
        self.saveButton.clicked.connect(self.toggleSaved)
        self.saveButton.setEnabled(False)
        actions.addWidget(self.saveButton)
        self.openButton = QtWidgets.QPushButton("Open original  ↗")
        self.openButton.clicked.connect(self.openOriginal)
        self.openButton.setEnabled(False)
        actions.addWidget(self.openButton)
        actions.addStretch()
        self.readerLayout.addLayout(actions)
        scroll.setWidget(self.readerBody)
        return scroll

    def selectCategory(self, category):
        self.currentCategory = category
        self.applyFilters()

    def applyFilters(self):
        query = self.search.text().strip().lower()
        articles = sorted(
            self.articles.values(), key=lambda item: item.published, reverse=True
        )
        if self.currentCategory == "Saved":
            articles = [
                item for item in articles if item.article_id in self.saved
            ]
        elif self.currentCategory != "Top stories":
            articles = [
                item for item in articles if item.category == self.currentCategory
            ]
        if query:
            articles = [
                item
                for item in articles
                if query
                in " ".join(
                    (
                        item.title,
                        item.summary,
                        item.source,
                        item.category,
                        *item.symbols,
                    )
                ).lower()
            ]

        selected_id = (
            self.currentArticle.article_id if self.currentArticle else None
        )
        self.headlines.clear()
        selected_item = None
        for article in articles:
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.ItemDataRole.UserRole, article.article_id)
            card = ArticleCard(article)
            item.setSizeHint(
                QtCore.QSize(
                    max(320, self.headlines.viewport().width()), card.sizeHint().height()
                )
            )
            self.headlines.addItem(item)
            self.headlines.setItemWidget(item, card)
            if article.article_id == selected_id:
                selected_item = item
        if selected_item is not None:
            self.headlines.setCurrentItem(selected_item)
        elif self.headlines.count():
            self.headlines.setCurrentRow(0)
        else:
            self._clearReader("No stories match this feed.")
        self._updateSavedCount()

    def _headlineSelected(self, current, _previous):
        if current is None:
            return
        article_id = current.data(QtCore.Qt.ItemDataRole.UserRole)
        article = self.articles.get(article_id)
        if article is not None:
            self.showArticle(article)

    def showArticle(self, article):
        self.currentArticle = article
        self.readerSource.setText(
            f"{article.source.upper()}  ·  {article.category.upper()}"
        )
        self.readerTitle.setText(article.title)
        local_time = article.published.astimezone().strftime(
            "%A, %B %d · %H:%M"
        )
        self.readerMeta.setText(f"{local_time}  ·  {_ageText(article.published)} ago")
        self.readerSymbols.setText("   ".join(article.symbols))
        self.readerSummary.setText(
            article.summary
            + (
                "\n\nThis feed provides a summary. Open the original source "
                "for the complete article."
                if article.url
                else "\n\nThis is a built-in demonstration story available offline."
            )
        )
        self.saveButton.setEnabled(True)
        self.openButton.setEnabled(bool(article.url))
        self.saveButton.setText(
            "★  Saved"
            if article.article_id in self.saved
            else "☆  Save story"
        )

    def _clearReader(self, message):
        self.currentArticle = None
        self.readerSource.clear()
        self.readerTitle.setText(message)
        self.readerMeta.clear()
        self.readerSymbols.clear()
        self.readerSummary.clear()
        self.saveButton.setEnabled(False)
        self.openButton.setEnabled(False)

    def toggleSaved(self):
        if self.currentArticle is None:
            return
        article_id = self.currentArticle.article_id
        if article_id in self.saved:
            self.saved.remove(article_id)
        else:
            self.saved.add(article_id)
        self.showArticle(self.currentArticle)
        self._updateSavedCount()
        if self.currentCategory == "Saved":
            self.applyFilters()

    def _updateSavedCount(self):
        label = "☆  Saved"
        if self.saved:
            label += f"  {len(self.saved)}"
        self.feedButtons["Saved"].setText(label)

    def openOriginal(self):
        if self.currentArticle and self.currentArticle.url:
            QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(self.currentArticle.url)
            )

    def refreshFeeds(self):
        if self.activeReplies:
            return
        self.completedFeeds = 0
        self.successfulFeeds = 0
        self.refreshButton.setEnabled(False)
        self.refreshButton.setText("Refreshing…")
        self.status.setText("Updating live financial-news feeds…")
        for source, url, category in FEEDS:
            request = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
            request.setRawHeader(
                b"User-Agent", b"Chartist/0.1 Financial News Reader"
            )
            request.setTransferTimeout(9000)
            reply = self.network.get(request)
            reply.setProperty("source", source)
            reply.setProperty("category", category)
            reply.finished.connect(
                lambda current=reply: self._feedFinished(current)
            )
            self.activeReplies.add(reply)

    def _feedFinished(self, reply):
        self.activeReplies.discard(reply)
        self.completedFeeds += 1
        if reply.error() == QtNetwork.QNetworkReply.NetworkError.NoError:
            try:
                articles = parseFeed(
                    bytes(reply.readAll()),
                    str(reply.property("source")),
                    str(reply.property("category")),
                )
            except (ET.ParseError, ValueError):
                articles = []
            if articles:
                self.successfulFeeds += 1
                for article in articles:
                    self.articles[article.article_id] = article
        reply.deleteLater()
        if self.completedFeeds == len(FEEDS):
            self.refreshButton.setEnabled(True)
            self.refreshButton.setText("↻  Refresh")
            if self.successfulFeeds:
                self.status.setText(
                    f"Live · {self.successfulFeeds}/{len(FEEDS)} feeds updated · "
                    f"{len(self.articles)} stories"
                )
            else:
                self.status.setText(
                    "Offline mode · Showing built-in market feed"
                )
            self.applyFilters()

    def cleanup(self):
        for reply in tuple(self.activeReplies):
            reply.abort()
            reply.deleteLater()
        self.activeReplies.clear()


__all__ = ["NewsArticle", "NewsView", "demoArticles", "parseFeed"]
