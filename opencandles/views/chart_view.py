"""Chart view composition and interaction controller."""

import time

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from opencandles.chart.axes import TimeAxis
from opencandles.chart.items import CandleItem, FootprintItem, curve
from opencandles.chart.panes import BB_COLORS, OVERLAYS, PANES, LeaveFilter, PricePane
from opencandles.config import (
    CHART_TYPES,
    DEFAULT_OVERLAYS,
    DEFAULT_PANES,
    DEFAULT_TF,
    MIN_VISIBLE,
    RENDER_MS,
    SYMBOL,
    TICK_MS,
    TIMEFRAMES,
    VISIBLE_CANDLES,
)
from opencandles.core.formatting import finite, fmt_price, fmt_val, span_html
from opencandles.core.indicators import bollinger, ema, heikin_ashi, sma
from opencandles.core.market import Market
from opencandles.core.series import Series
from opencandles.drawings.tools import (
    FibDrawing,
    HLineDrawing,
    MeasureDrawing,
    RectDrawing,
    TextDrawing,
    TrendDrawing,
    VLineDrawing,
)
from opencandles.theme import (
    BAR_CSS,
    BG,
    BOTTOM_CSS,
    CROSS,
    DOWN,
    DRAW,
    FG,
    MENU_CSS,
    MUTED,
    SIDEBAR_CSS,
    SPLITTER_CSS,
    UP,
)
from opencandles.ui.icons import (
    icon_arrow,
    icon_cross,
    icon_eye,
    icon_fib,
    icon_hline,
    icon_lock,
    icon_measure,
    icon_rect,
    icon_text,
    icon_trash,
    icon_trend,
    icon_vline,
    icon_zoom_in,
    icon_zoom_out,
    make_icon,
)

Qt = QtCore.Qt
try:
    Shortcut = QtGui.QShortcut
except AttributeError:
    Shortcut = QtWidgets.QShortcut


class ChartView(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._cleaned_up = False
        self.setWindowTitle(f"{SYMBOL} live (dummy data)")
        self.resize(1360, 880)

        self.market = Market()
        self.t0 = self.market.t0
        self.tf = DEFAULT_TF
        self.series = Series(self.market, self.tf)
        self.raw = self.disp = self.series.data()
        self.chart_type = "Candles"
        self.dirty = True

        # view state
        self.paused = False
        self.follow = True
        self.auto_y = True
        self.log_mode = False
        self.span = VISIBLE_CANDLES * self.tf
        self.hover_idx = None
        self.cross_x = self.cross_y = self.cross_pane = None

        # drawings
        self.cursor_mode = "cross"
        self.tool = None
        self.pending = None
        self.preview = None
        self.zoom_box = None
        self.zoom_start = None
        self.measure = None
        self.drawings = []
        self.magnet = False
        self.locked = False
        self.hidden = False

        # indicators
        self.panes = {}             # key -> SubPane
        self.overlays = {}          # key -> list of plot items

        self.leave_filter = LeaveFilter(self)
        self._build_ui()
        for key in DEFAULT_OVERLAYS:
            self.add_overlay(key)
        for key in DEFAULT_PANES:
            self.add_pane(key)
        self.render(force=True)
        self._apply_follow()
        self.fit_y()
        self.sync_buttons()

        self.tick_timer = QtCore.QTimer(self)
        self.tick_timer.timeout.connect(self.on_tick)
        self.tick_timer.start(TICK_MS)
        self.render_timer = QtCore.QTimer(self)
        self.render_timer.timeout.connect(self.render)
        self.render_timer.start(RENDER_MS)

    # ----- price transform (linear / log) ----------------------------------

    def fy(self, p):
        return np.log10(p) if self.log_mode else p

    def inv(self, y):
        return 10 ** y if self.log_mode else y

    # ----- UI -------------------------------------------------------------

    def _build_ui(self):
        pg.setConfigOptions(antialias=True, background=BG, foreground=FG)
        self.setStyleSheet(f"background:{BG}; color:{FG};")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_topbar())

        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._build_sidebar())

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

        # shared time scale under all panes
        self.time_axis = TimeAxis(self, self.t0)
        blank = pg.AxisItem("right")
        blank.setStyle(showValues=False)
        blank.setWidth(90)
        blank.setPen(pg.mkPen(None))
        self.time_widget = pg.PlotWidget(axisItems={"bottom": self.time_axis, "right": blank})
        tp = self.time_widget.getPlotItem()
        tp.showAxis("right")
        tp.hideAxis("left")
        tp.hideButtons()
        tp.setMenuEnabled(False)
        tp.setMouseEnabled(False, False)
        tp.setXLink(self.price_plot)
        self.time_widget.setFixedHeight(34)
        column.addWidget(self.time_widget)

        row.addLayout(column, 1)
        layout.addLayout(row, 1)

        # price items
        self.candles = CandleItem()
        self.price_plot.addItem(self.candles)
        self.footprint = FootprintItem()
        self.footprint.setVisible(False)
        self.price_plot.addItem(self.footprint)
        self.line_item = curve(DRAW, 2)
        self.line_item.setVisible(False)
        self.price_plot.addItem(self.line_item)
        self.last_line = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen("#8b949e", style=Qt.PenStyle.DashLine))
        self.price_plot.addItem(self.last_line, ignoreBounds=True)

        self.price_plot.sigXRangeChanged.connect(lambda *_: self.fit_y())
        layout.addWidget(self._build_bottombar())

        keys = {
            "Space": self.toggle_pause, "F": self.toggle_follow, "R": self.reset_view,
            "L": lambda: self.set_log(not self.log_mode), "A": lambda: self.set_auto(not self.auto_y),
            "T": lambda: self.set_tool("trend"), "H": lambda: self.set_tool("hline"),
            "V": lambda: self.set_tool("vline"), "B": lambda: self.set_tool("rect"),
            "G": lambda: self.set_tool("fib"), "M": lambda: self.set_tool("measure"),
            "N": lambda: self.set_tool("text"),
            "Delete": self.clear_drawings, "Escape": self.cancel,
        }
        self.shortcuts = [Shortcut(QtGui.QKeySequence(k), self, activated=f) for k, f in keys.items()]
        for shortcut in self.shortcuts:
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def _build_topbar(self):
        bar = QtWidgets.QWidget()
        bar.setObjectName("topbar")
        bar.setStyleSheet(BAR_CSS)
        bl = QtWidgets.QHBoxLayout(bar)
        bl.setContentsMargins(6, 3, 12, 3)
        bl.setSpacing(2)

        def vsep():
            f = QtWidgets.QFrame()
            f.setObjectName("vsep")
            f.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            bl.addWidget(f)

        symbol = QtWidgets.QLabel(SYMBOL)
        symbol.setObjectName("symbol")
        bl.addWidget(symbol)
        vsep()

        self.tf_buttons = {}
        group = QtWidgets.QButtonGroup(bar)
        for label, tf in TIMEFRAMES:
            b = QtWidgets.QPushButton(label)
            b.setCheckable(True)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setToolTip(f"{label} candles")
            b.clicked.connect(lambda _, t=tf: self.set_timeframe(t))
            group.addButton(b)
            bl.addWidget(b)
            self.tf_buttons[tf] = b
        vsep()

        self.type_button = QtWidgets.QToolButton()
        self.type_button.setObjectName("menu")
        self.type_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.type_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        menu = QtWidgets.QMenu(self.type_button)
        menu.setStyleSheet(MENU_CSS)
        self.type_actions = {}
        for name in CHART_TYPES:
            act = menu.addAction(name)
            act.setCheckable(True)
            act.triggered.connect(lambda _, n=name: self.set_chart_type(n))
            self.type_actions[name] = act
        self.type_button.setMenu(menu)
        bl.addWidget(self.type_button)
        vsep()

        ind = QtWidgets.QToolButton()
        ind.setObjectName("menu")
        ind.setText("ƒx  Indicators")
        ind.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        ind.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        menu = QtWidgets.QMenu(ind)
        menu.setStyleSheet(MENU_CSS)
        self.ind_actions = {}
        menu.addSection("On the chart")
        for key, name in OVERLAYS.items():
            act = menu.addAction(name)
            act.setCheckable(True)
            act.triggered.connect(lambda on, k=key: self.add_overlay(k) if on else self.remove_overlay(k))
            self.ind_actions[key] = act
        menu.addSection("Below the chart")
        for key, (name, _) in PANES.items():
            act = menu.addAction(name)
            act.setCheckable(True)
            act.triggered.connect(lambda on, k=key: self.add_pane(k) if on else self.remove_pane(k))
            self.ind_actions[key] = act
        ind.setMenu(menu)
        bl.addWidget(ind)

        bl.addStretch()
        self.status = QtWidgets.QLabel()
        self.status.setTextFormat(Qt.TextFormat.RichText)
        self.status.setStyleSheet("font-size:10pt;")
        bl.addWidget(self.status)
        return bar

    def _build_sidebar(self):
        side = QtWidgets.QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(58)
        side.setStyleSheet(SIDEBAR_CSS)
        vl = QtWidgets.QVBoxLayout(side)
        vl.setContentsMargins(4, 8, 4, 8)
        vl.setSpacing(3)
        self.side_buttons = {}
        self.sidebar_categories = {}
        self.sidebar_choices = {}
        self.sidebar_category_state = {}

        def category(key, icon, tip, choices):
            row = QtWidgets.QWidget()
            row.setObjectName("toolGroup")
            rl = QtWidgets.QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(0)

            b = QtWidgets.QToolButton()
            b.setIcon(make_icon(icon))
            b.setIconSize(QtCore.QSize(22, 22))
            b.setFixedSize(39, 38)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            rl.addWidget(b)

            more = QtWidgets.QToolButton()
            more.setObjectName("toolGroupArrow")
            more.setText("›")
            more.setFixedSize(11, 38)
            more.setToolTip(tip)
            more.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            more.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            menu = QtWidgets.QMenu(more)
            menu.setStyleSheet(MENU_CSS)
            more.setMenu(menu)
            rl.addWidget(more)

            first_enabled = None
            for choice_key, label, choice_icon, slot in choices:
                action = menu.addAction(make_icon(choice_icon), label)
                action.setEnabled(slot is not None)
                if slot is not None:
                    self.sidebar_choices[choice_key] = (key, choice_icon, label, slot)
                    action.triggered.connect(
                        lambda _, ck=choice_key: self._activate_sidebar_choice(ck)
                    )
                    if first_enabled is None:
                        first_enabled = choice_key

            self.sidebar_categories[key] = b
            self.sidebar_category_state[key] = first_enabled
            b.setCheckable(first_enabled is not None)
            b.clicked.connect(lambda _, ck=key: self._activate_sidebar_category(ck))
            vl.addWidget(row)

        def sep():
            f = QtWidgets.QFrame()
            f.setObjectName("sep")
            f.setFrameShape(QtWidgets.QFrame.Shape.HLine)
            vl.addWidget(f)

        category("cursors", icon_cross, "Cursors", [
            ("cross", "Cross", icon_cross, lambda: self.set_cursor("cross")),
            ("arrow", "Arrow", icon_arrow, lambda: self.set_cursor("arrow")),
        ])
        category("trend", icon_trend, "Trend line tools", [
            ("trend", "Trend Line", icon_trend, lambda: self.set_tool("trend")),
            ("hline", "Horizontal Line", icon_hline, lambda: self.set_tool("hline")),
            ("vline", "Vertical Line", icon_vline, lambda: self.set_tool("vline")),
        ])
        category("gann_fib", icon_fib, "Gann and Fibonacci tools", [
            ("fib", "Fib Retracement", icon_fib, lambda: self.set_tool("fib")),
            ("gann_box", "Gann Box — coming soon", icon_rect, None),
            ("gann_fan", "Gann Fan — coming soon", icon_trend, None),
        ])
        category("patterns", icon_trend, "Patterns", [
            ("xabcd", "XABCD Pattern — coming soon", icon_trend, None),
            ("head_shoulders", "Head and Shoulders — coming soon", icon_trend, None),
        ])
        category("forecasting", icon_measure, "Forecasting and measurement tools", [
            ("long_position", "Long Position — coming soon", icon_measure, None),
            ("short_position", "Short Position — coming soon", icon_measure, None),
        ])
        category("shapes", icon_rect, "Geometric shapes", [
            ("rect", "Rectangle", icon_rect, lambda: self.set_tool("rect")),
            ("path", "Path — coming soon", icon_trend, None),
        ])
        category("annotations", icon_text, "Annotation tools", [
            ("text", "Text Note", icon_text, lambda: self.set_tool("text")),
            ("anchored_text", "Anchored Text — coming soon", icon_text, None),
        ])
        sep()

        def utility(key, icon, tip, slot, checkable=True):
            b = QtWidgets.QToolButton()
            b.setIcon(make_icon(icon))
            b.setIconSize(QtCore.QSize(22, 22))
            b.setFixedSize(50, 36)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda *_: slot())
            vl.addWidget(b)
            self.side_buttons[key] = b

        utility("measure", icon_measure, "Measure (M)", lambda: self.set_tool("measure"))
        utility("zoom_in", icon_zoom_in, "Zoom in: drag a rectangle over the chart",
                lambda: self.set_tool("zoom_in"))
        utility("zoom_out", icon_zoom_out, "Zoom out", self.zoom_out, checkable=False)
        sep()
        utility("hide", icon_eye, "Hide all drawings", self.toggle_hide)
        utility("lock", icon_lock, "Lock all drawings", self.toggle_lock)
        sep()
        utility("trash", icon_trash, "Remove all drawings (Del)", self.clear_drawings, checkable=False)
        vl.addStretch()
        return side

    def _activate_sidebar_choice(self, choice_key):
        category, _, _, slot = self.sidebar_choices[choice_key]
        self.sidebar_category_state[category] = choice_key
        slot()

    def _activate_sidebar_category(self, category):
        choice_key = self.sidebar_category_state.get(category)
        if choice_key is not None:
            self.sidebar_choices[choice_key][3]()

    def _build_bottombar(self):
        bar = QtWidgets.QWidget()
        bar.setObjectName("bottombar")
        bar.setStyleSheet(BOTTOM_CSS)
        bl = QtWidgets.QHBoxLayout(bar)
        bl.setContentsMargins(10, 5, 10, 6)
        bl.setSpacing(6)

        def button(text, tip, slot, checkable=False):
            b = QtWidgets.QPushButton(text)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda *_: slot())
            bl.addWidget(b)
            return b

        hint = QtWidgets.QLabel("drag pane dividers to resize · ✕ removes an indicator · "
                                "right-click a drawing to delete · shift+wheel to scroll")
        hint.setStyleSheet("color:#6e7681; font-size:9pt; border:none;")
        bl.addWidget(hint)
        bl.addStretch()
        self.btn_pause = button("❚❚  Pause", "Pause / resume feed (Space)", self.toggle_pause, True)
        self.btn_follow = button("⇥  Follow", "Follow latest candle (F)", self.toggle_follow, True)
        button("⟲  Reset", "Reset view (R)", self.reset_view)
        self.btn_log = button("log", "Logarithmic price scale (L)", lambda: self.set_log(not self.log_mode), True)
        self.btn_auto = button("auto", "Auto-fit price scale (A)", lambda: self.set_auto(not self.auto_y), True)
        return bar

    def all_panes(self):
        return [self.price_pane] + list(self.panes.values())

    def sync_buttons(self):
        sb = self.side_buttons
        active_choice = self.cursor_mode if self.tool is None else self.tool
        active_category = None
        if active_choice in self.sidebar_choices:
            category, icon, label, _ = self.sidebar_choices[active_choice]
            active_category = category
            self.sidebar_category_state[category] = active_choice
            button = self.sidebar_categories[category]
            button.setIcon(make_icon(icon))
            button.setToolTip(label)
        for category, button in self.sidebar_categories.items():
            button.setChecked(category == active_category)
        sb["measure"].setChecked(self.tool == "measure")
        sb["zoom_in"].setChecked(self.tool == "zoom_in")
        sb["lock"].setChecked(self.locked)
        sb["hide"].setChecked(self.hidden)
        for tf, b in self.tf_buttons.items():
            b.setChecked(tf == self.tf)
        self.type_button.setText(f"{self.chart_type}  ▾")
        for name, act in self.type_actions.items():
            act.setChecked(name == self.chart_type)
        for key, act in self.ind_actions.items():
            act.setChecked(key in self.overlays or key in self.panes)
        self.btn_pause.setChecked(self.paused)
        self.btn_follow.setChecked(self.follow)
        self.btn_log.setChecked(self.log_mode)
        self.btn_auto.setChecked(self.auto_y)
        cursor = Qt.CursorShape.CrossCursor if self.tool else Qt.CursorShape.ArrowCursor
        for pane in self.all_panes():
            pane.widget.setCursor(cursor)
        self.update_info()

    # ----- indicators -----------------------------------------------------

    def add_overlay(self, key):
        if key in self.overlays:
            return
        P = self.price_plot
        if key == "sma":
            items = [curve("#f0b429")]
        elif key == "ema":
            items = [curve("#58a6ff")]
        else:
            mid = curve(BB_COLORS[0])
            upper = curve(BB_COLORS[1])
            lower = curve(BB_COLORS[1])
            fill = pg.FillBetweenItem(upper, lower, brush=pg.mkBrush(BB_COLORS[1] + "1a"))
            items = [mid, upper, lower, fill]
        for it in items:
            P.addItem(it)
        self.overlays[key] = {"items": items, "values": []}
        self.price_pane.add_chip(key, lambda: self.remove_overlay(key))
        self.render(force=True)
        self.sync_buttons()

    def remove_overlay(self, key):
        ov = self.overlays.pop(key, None)
        if ov is None:
            return
        for it in ov["items"]:
            self.price_plot.removeItem(it)
        self.price_pane.remove_chip(key)
        self.sync_buttons()

    def update_overlays(self):
        x, c = self.raw["x"], self.raw["c"]
        for key, ov in self.overlays.items():
            if key == "sma":
                vals = [sma(c, 20)]
            elif key == "ema":
                vals = [ema(c, 50)]
            else:
                vals = list(bollinger(c))
            ov["values"] = vals
            for item, v in zip(ov["items"], vals):
                item.setData(*finite(x, self.fy(v)))

    def add_pane(self, key):
        if key in self.panes:
            return
        pane = PANES[key][1](self, key)
        self.panes[key] = pane
        self.splitter.addWidget(pane)
        self.layout_panes()
        for d in self.drawings:
            if isinstance(d, VLineDrawing):
                d.attach(pane)
        self.render(force=True)
        self.fit_y()
        self.sync_buttons()

    def remove_pane(self, key):
        pane = self.panes.pop(key, None)
        if pane is None:
            return
        for d in self.drawings:
            if isinstance(d, VLineDrawing):
                d.detach(pane)
        if self.cross_pane is pane:
            self.hide_crosshair()
        pane.setParent(None)
        pane.deleteLater()
        self.layout_panes()
        self.sync_buttons()

    def layout_panes(self):
        """Price pane gets most of the height, indicator panes share the rest."""
        H = self.splitter.height()
        if H < 200:
            H = max(400, self.height() - 130)
        n = len(self.panes)
        share = min(0.2, 0.55 / n) if n else 0
        self.splitter.setSizes([int(H * (1 - share * n))] + [int(H * share)] * n)

    def remove_indicator(self, key):
        if key in self.panes:
            self.remove_pane(key)
        else:
            self.remove_overlay(key)

    # ----- data / rendering -----------------------------------------------

    def on_tick(self):
        if self.paused:
            return
        sec, price, size = self.market.tick()
        self.series.update(sec, price, size)
        self.dirty = True

    def render(self, force=False):
        if not (self.dirty or force):
            return
        self.dirty = False
        self.raw = self.series.data()
        self.disp = heikin_ashi(self.raw) if self.chart_type == "Heikin Ashi" else self.raw
        d, f = self.disp, self.fy

        if self.chart_type in ("Line", "Area"):
            self.candles.setVisible(False)
            self.footprint.setVisible(False)
            self.line_item.setVisible(True)
            self.line_item.setData(d["x"], f(d["c"]))
            if self.chart_type == "Area":
                fill = QtGui.QColor(DRAW)
                fill.setAlpha(45)
                self.line_item.setFillLevel(0)
                self.line_item.setBrush(fill)
            else:
                self.line_item.setFillLevel(None)
                self.line_item.setBrush(None)
        elif self.chart_type == "Footprint":
            self.line_item.setVisible(False)
            self.candles.setVisible(False)
            self.footprint.setVisible(True)
            self.footprint.set_data(
                d["x"], f(d["o"]), f(d["h"]), f(d["l"]), f(d["c"]),
                d["v"], self.tf,
            )
        else:
            self.line_item.setVisible(False)
            self.footprint.setVisible(False)
            self.candles.setVisible(True)
            style = {"Hollow candles": "hollow", "Bars": "bars"}.get(self.chart_type, "candles")
            self.candles.set_data(d["x"], f(d["o"]), f(d["h"]), f(d["l"]), f(d["c"]), self.tf, style)

        self.update_overlays()
        for pane in self.panes.values():
            pane.compute(self.raw, self.tf)
        self.last_line.setValue(f(self.raw["c"][-1]))

        if self.follow:
            self._apply_follow()
        self.fit_y()
        self.update_info()
        for pane in self.all_panes():
            pane.axis.update()

    def set_timeframe(self, tf):
        self.tf = tf
        self.series = Series(self.market, tf)
        self.cancel_pending()
        self.clear_measure()
        self.hover_idx = None
        self.span = VISIBLE_CANDLES * tf
        self.follow = True
        self.render(force=True)
        self._apply_follow()
        self.sync_buttons()

    def set_chart_type(self, name):
        self.chart_type = name
        if name == "Footprint":
            # Footprint cells need enough horizontal space for bid/ask values.
            self.span = min(self.span, 10 * self.tf)
        self.render(force=True)
        if name == "Footprint" and self.follow:
            self._apply_follow()
        self.sync_buttons()

    # ----- view: time axis ------------------------------------------------

    def _clamp_span(self, w):
        return float(np.clip(w, MIN_VISIBLE * self.tf, (len(self.raw["x"]) + 50) * self.tf))

    def _apply_follow(self):
        right = self.raw["x"][-1] + self.tf * 4
        self.price_plot.setXRange(right - self.span, right, padding=0)

    def zoom_x(self, factor, center=None):
        """factor < 1 zooms in. While following, zoom stays anchored to the latest candle."""
        vb = self.price_plot.getViewBox()
        xmin, xmax = vb.viewRange()[0]
        if self.follow:
            self.span = self._clamp_span(self.span * factor)
            self._apply_follow()
            return
        if center is None:
            center = xmax
        f = self._clamp_span((xmax - xmin) * factor) / (xmax - xmin)
        vb.setXRange(center - (center - xmin) * f, center + (xmax - center) * f, padding=0)

    def pan_x(self, dx):
        self.set_follow(False)
        self.price_plot.getViewBox().translateBy(x=dx)

    # ----- view: price axis -----------------------------------------------

    def visible_mask(self):
        xmin, xmax = self.price_plot.getViewBox().viewRange()[0]
        x = self.disp["x"]
        return (x >= xmin) & (x <= xmax)

    def fit_y(self):
        mask = self.visible_mask()
        if not mask.any():
            return
        for pane in self.panes.values():
            pane.fit_y(mask)
        if self.auto_y:
            d = self.disp
            if self.chart_type in ("Line", "Area"):
                lo, hi = d["c"][mask].min(), d["c"][mask].max()
            else:
                lo, hi = d["l"][mask].min(), d["h"][mask].max()
            lo, hi = self.fy(lo), self.fy(hi)
            pad = max((hi - lo) * 0.08, abs(hi) * 1e-6)
            self.price_plot.setYRange(lo - pad, hi + pad, padding=0)

    def scale_y(self, factor):
        """factor > 1 squeezes the chart (shows a bigger price range)."""
        self.set_auto(False)
        a, b = self.price_plot.getViewBox().viewRange()[1]
        mid, half = (a + b) / 2, (b - a) / 2 * factor
        self.price_plot.setYRange(mid - half, mid + half, padding=0)

    def begin_zoom_box(self, point):
        self.cancel_pending()
        self.zoom_start = point
        self.zoom_box = pg.PlotCurveItem(
            pen=pg.mkPen(DRAW, width=1.2, style=Qt.PenStyle.DashLine)
        )
        self.price_plot.addItem(self.zoom_box, ignoreBounds=True)
        self.update_zoom_box(point)

    def update_zoom_box(self, point):
        if self.zoom_box is None or self.zoom_start is None:
            return
        x1, y1 = self.zoom_start
        x2, y2 = point
        self.zoom_box.setData(
            [x1, x2, x2, x1, x1],
            [y1, y1, y2, y2, y1],
        )

    def finish_zoom_box(self, point):
        if self.zoom_start is None:
            return
        x1, y1 = self.zoom_start
        x2, y2 = point
        self.cancel_pending()
        if abs(x2 - x1) > 1e-9 and abs(y2 - y1) > 1e-9:
            self.follow = False
            self.auto_y = False
            self.span = self._clamp_span(abs(x2 - x1))
            self.price_plot.setXRange(min(x1, x2), max(x1, x2), padding=0)
            self.price_plot.setYRange(min(y1, y2), max(y1, y2), padding=0)
        self.tool = None
        self.sync_buttons()

    def zoom_out(self):
        self.cancel_pending()
        self.tool = None
        self.follow = False
        self.auto_y = False
        (xmin, xmax), (ymin, ymax) = self.price_plot.getViewBox().viewRange()
        xmid, ymid = (xmin + xmax) / 2, (ymin + ymax) / 2
        xhalf = self._clamp_span((xmax - xmin) * 1.5) / 2
        yhalf = (ymax - ymin) * 0.75
        self.span = xhalf * 2
        self.price_plot.setXRange(xmid - xhalf, xmid + xhalf, padding=0)
        self.price_plot.setYRange(ymid - yhalf, ymid + yhalf, padding=0)
        self.sync_buttons()

    def set_auto(self, on):
        self.auto_y = on
        self.fit_y()
        self.sync_buttons()

    def set_log(self, on):
        if on == self.log_mode:
            return
        a, b = self.price_plot.getViewBox().viewRange()[1]
        pa, pb = self.inv(a), self.inv(b)
        self.log_mode = on
        self.render(force=True)
        for d in self.drawings:
            d.refresh()
        if self.measure:
            self.measure.refresh()
        self.cancel_pending()
        if not self.auto_y:
            self.price_plot.setYRange(self.fy(max(pa, 1e-9)), self.fy(pb), padding=0)
        self.fit_y()
        self.price_axis.picture = None                    # rebuild tick labels
        self.price_axis.update()
        self.sync_buttons()

    # ----- modes ----------------------------------------------------------

    def set_follow(self, on):
        if on == self.follow:
            return
        if on:
            xmin, xmax = self.price_plot.getViewBox().viewRange()[0]
            self.span = self._clamp_span(xmax - xmin)
            self.follow = True
            self._apply_follow()
        else:
            self.follow = False
        self.sync_buttons()

    def toggle_follow(self):
        self.set_follow(not self.follow)

    def reset_view(self):
        self.span = VISIBLE_CANDLES * self.tf
        self.follow = True
        self.auto_y = True
        self._apply_follow()
        self.fit_y()
        self.sync_buttons()

    def toggle_pause(self):
        self.paused = not self.paused
        self.sync_buttons()

    # ----- drawing tools --------------------------------------------------

    def set_cursor(self, mode):
        self.cursor_mode = mode
        self.set_tool(None)

    def set_tool(self, tool):
        self.cancel_pending()
        self.tool = None if tool == self.tool else tool
        self.sync_buttons()

    def cancel(self):
        self.cancel_pending()
        self.clear_measure()
        self.tool = None
        self.sync_buttons()

    def cancel_pending(self):
        self.pending = None
        if self.preview is not None:
            self.price_plot.removeItem(self.preview)
            self.preview = None
        self.zoom_start = None
        if self.zoom_box is not None:
            self.price_plot.removeItem(self.zoom_box)
            self.zoom_box = None

    def clear_measure(self):
        if self.measure is not None:
            self.measure.remove()
            self.measure = None

    def toggle_magnet(self):
        self.magnet = not self.magnet
        self.sync_buttons()

    def toggle_lock(self):
        self.locked = not self.locked
        for d in self.drawings:
            d.set_locked(self.locked)
        self.sync_buttons()

    def toggle_hide(self):
        self.set_hidden(not self.hidden)

    def set_hidden(self, hidden):
        self.hidden = hidden
        for d in self.drawings:
            d.set_visible(not hidden)
        self.price_axis.update()
        self.time_axis.update()
        self.sync_buttons()

    def nearest_index(self, xv):
        x = self.disp["x"]
        i = int(np.clip(np.searchsorted(x, xv), 0, len(x) - 1))
        if i > 0 and abs(x[i - 1] - xv) < abs(x[i] - xv):
            i -= 1
        return i

    def nearest_x(self, xv):
        return self.disp["x"][self.nearest_index(xv)]

    def snap(self, xv, yv):
        """Magnet: snap to the nearest candle's open / high / low / close."""
        if not self.magnet:
            return xv, yv
        d = self.disp
        i = self.nearest_index(xv)
        levels = self.fy(np.array([d["o"][i], d["h"][i], d["l"][i], d["c"][i]]))
        return d["x"][i], float(levels[np.argmin(np.abs(levels - yv))])

    def on_scene_click(self, pane, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool is None:
            self.clear_measure()                          # like TradingView: click clears it
            return
        vb = pane.vb
        pos = ev.scenePos()
        if not vb.sceneBoundingRect().contains(pos):
            return
        in_price = pane is self.price_pane
        if not in_price and self.tool != "vline":
            return
        if self.tool == "zoom_in":
            return
        mp = vb.mapSceneToView(pos)
        xv, yv = self.snap(mp.x(), mp.y()) if in_price else (mp.x(), 0)
        point = (xv, self.inv(yv))

        tool = self.tool
        if tool == "hline":
            self.add_drawing(HLineDrawing(self, point[1]))
        elif tool == "vline":
            self.add_drawing(VLineDrawing(self, self.nearest_x(xv)))
        elif tool == "text":
            text, ok = QtWidgets.QInputDialog.getText(self, "Text note", "Text:")
            if ok and text:
                self.add_drawing(TextDrawing(self, point, text))
        elif self.pending is None:                        # first click of a two-click tool
            if tool == "measure":
                self.clear_measure()
                point = (self.nearest_x(xv), point[1])
                self.measure = MeasureDrawing(self, point)
            else:
                self.preview = pg.PlotCurveItem(pen=pg.mkPen(DRAW, width=1.2, style=Qt.PenStyle.DashLine))
                self.price_plot.addItem(self.preview, ignoreBounds=True)
            self.pending = point
            self.update_preview(point)
            return
        else:                                             # second click: finish
            p1 = self.pending
            self.cancel_pending()
            if tool == "trend":
                self.add_drawing(TrendDrawing(self, p1, point))
            elif tool == "rect":
                self.add_drawing(RectDrawing(self, p1, point))
            elif tool == "fib":
                self.add_drawing(FibDrawing(self, p1, point))
            elif tool == "measure" and self.measure:
                self.measure.update_end((self.nearest_x(xv), point[1]))

        self.tool = None                                  # one-shot, like TradingView
        self.sync_buttons()

    def update_preview(self, point):
        if self.pending is None:
            return
        if self.tool == "measure" and self.measure:
            self.measure.update_end((self.nearest_x(point[0]), point[1]))
            return
        if self.preview is None:
            return
        (x1, pr1), (x2, pr2) = self.pending, point
        y1, y2 = self.fy(pr1), self.fy(pr2)
        if self.tool == "rect":
            self.preview.setData([x1, x2, x2, x1, x1], [y1, y1, y2, y2, y1])
        else:
            self.preview.setData([x1, x2], [y1, y2])

    def add_drawing(self, d):
        self.drawings.append(d)
        d.set_locked(self.locked)
        if self.hidden:
            self.set_hidden(False)
        self.price_axis.update()
        self.time_axis.update()

    def remove_drawing(self, d):
        if d in self.drawings:
            self.drawings.remove(d)
            d.remove()
        self.price_axis.update()
        self.time_axis.update()

    def clear_drawings(self):
        for d in list(self.drawings):
            self.remove_drawing(d)
        self.clear_measure()
        self.cancel_pending()

    # ----- axis tags ------------------------------------------------------

    def price_tags(self):
        """(view y, text, color) drawn on the price scale; last one is on top."""
        tags = [] if self.hidden else [t for d in self.drawings for t in d.price_tags()]
        c = self.raw["c"]
        up = c[-1] >= (c[-2] if len(c) > 1 else c[-1])
        tags.append((self.fy(c[-1]), fmt_price(c[-1]), UP if up else DOWN))
        if self.cross_pane is self.price_pane and self.cross_y is not None:
            tags.append((self.cross_y, fmt_price(self.inv(self.cross_y)), CROSS))
        return tags

    def time_text(self, xv):
        fmt = "%d %b  %H:%M:%S" if self.tf < 60 else "%a %d %b  %H:%M"
        return time.strftime(fmt, time.localtime(xv + self.t0))

    def time_tags(self):
        tags = [] if self.hidden else [t for d in self.drawings for t in d.time_tags()]
        if self.cross_x is not None:
            tags.append((self.cross_x, self.time_text(self.cross_x), CROSS))
        return tags

    # ----- crosshair + info -----------------------------------------------

    def hide_crosshair(self):
        self.cross_x = self.cross_y = self.cross_pane = None
        self.hover_idx = None
        for pane in self.all_panes():
            pane.set_cross(None)
        self.time_axis.update()
        self.update_info()

    def on_mouse(self, pane, evt):
        pos = evt[0]
        if not pane.vb.sceneBoundingRect().contains(pos):
            self.hide_crosshair()
            return
        mp = pane.vb.mapSceneToView(pos)
        self.hover_idx = self.nearest_index(mp.x())
        snapped_x = self.disp["x"][self.hover_idx]

        if pane is self.price_pane and self.pending is not None:
            xv, yv = self.snap(mp.x(), mp.y())
            self.update_preview((xv, self.inv(yv)))

        if self.cursor_mode == "arrow" and self.tool is None:
            self.cross_x = self.cross_y = self.cross_pane = None
            for p in self.all_panes():
                p.set_cross(None)
        else:
            self.cross_x, self.cross_y, self.cross_pane = snapped_x, mp.y(), pane
            for p in self.all_panes():
                p.set_cross(snapped_x, mp.y() if p is pane else None)
        self.time_axis.update()
        self.update_info()

    def update_info(self):
        d = self.disp
        n = len(d["x"])
        i = self.hover_idx if self.hover_idx is not None and self.hover_idx < n else n - 1

        # top bar: live status + last price
        last = self.raw["c"][-1]
        sess = (last / self.market.first_open - 1) * 100
        status = (span_html("❚❚ PAUSED", "#f0b429") if self.paused else span_html("● LIVE", UP))
        self.status.setText(f'{status} &nbsp;&nbsp; <b>{span_html(fmt_price(last), UP if sess >= 0 else DOWN)}</b>'
                            f' &nbsp;{span_html(f"{sess:+.2f}%", UP if sess >= 0 else DOWN)}')

        # price pane header: OHLC of hovered candle + overlay values
        col = UP if d["c"][i] >= d["o"][i] else DOWN
        chg = (d["c"][i] / d["o"][i] - 1) * 100
        tf_label = next(lbl for lbl, t in TIMEFRAMES if t == self.tf)
        self.price_pane.info.setText(
            f'{span_html(f"{SYMBOL} · {tf_label} · {self.chart_type}", MUTED)} &nbsp; '
            f'O {span_html(fmt_price(d["o"][i]), col)} &nbsp;H {span_html(fmt_price(d["h"][i]), col)} '
            f'&nbsp;L {span_html(fmt_price(d["l"][i]), col)} &nbsp;C {span_html(fmt_price(d["c"][i]), col)} '
            f'&nbsp;{span_html(f"({chg:+.2f}%)", col)}')

        colors = {"sma": ["#f0b429"], "ema": ["#58a6ff"], "bb": [BB_COLORS[0], BB_COLORS[1], BB_COLORS[1]]}
        for key, (chip, label) in self.price_pane.chips.items():
            vals = self.overlays.get(key, {}).get("values", [])
            parts = [span_html(OVERLAYS[key], MUTED)]
            for v, cc in zip(vals, colors[key]):
                if len(v) > i:
                    parts.append(span_html(fmt_val(v[i]), cc))
            label.setText("&nbsp;".join(parts))

        for pane in self.panes.values():
            pane.header(i)

    def cleanup(self):
        """Stop background activity before this view is removed from a workspace."""
        if self._cleaned_up:
            return
        self._cleaned_up = True
        self.tick_timer.stop()
        self.render_timer.stop()

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)
