"""Compact launcher bar and standalone workspace windows."""

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from opencandles.tabs.page_registry import PageRegistry, create_default_registry
from opencandles.theme import BORDER, DRAW, FG, MUTED


class StandalonePageWindow(QtWidgets.QMainWindow):
    """Top-level window containing one workspace view and no tab UI."""

    def __init__(
        self,
        page_type: str,
        registry: PageRegistry,
        parent=None,
        page=None,
        title=None,
    ):
        super().__init__(parent)
        self.page_type = page_type
        self.page = page or registry.create(page_type)
        self.page.setProperty("pageType", page_type)
        self.page_title = title or registry.title_for(page_type)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.WindowMinimizeButtonHint
            | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            | QtCore.Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumSize(640, 420)
        self.setCentralWidget(self.page)
        self.setWindowTitle(f"OpenCandles — {self.page_title}")
        self.resize(1360, 880)

    def take_page(self):
        page = self.takeCentralWidget()
        self.page = None
        return page

    def closeEvent(self, event):
        cleanup = getattr(self.page, "cleanup", None) if self.page is not None else None
        if callable(cleanup):
            cleanup()
        super().closeEvent(event)


class LauncherWindow(QtWidgets.QWidget):
    """Small draggable bar used to launch independent OpenCandles tools."""

    modeSwitchRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None, registry: PageRegistry | None = None):
        super().__init__(parent)
        self.registry = registry or create_default_registry()
        self.open_windows = []
        self._drag_offset = None
        self._native_drag = False
        self._initial_positioned = False
        self._user_positioned = False
        self._bar_size = QtCore.QSize(1200, 58)

        self.setObjectName("launcher")
        self.setWindowTitle("OpenCandles")
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self.setFixedSize(self._bar_size)
        self.setStyleSheet(f"""
            QWidget#launcher {{
                background: #08090b;
                border: 1px solid {BORDER};
                border-radius: 7px;
            }}
            QLabel#brand {{
                color: #ffffff;
                font-size: 14px;
                font-weight: 700;
                padding: 0 12px;
            }}
            QLabel#dragHandle {{
                color: {MUTED};
                font-size: 18px;
                padding-left: 5px;
            }}
            QPushButton#launch {{
                color: {FG};
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 10px 10px;
                font-size: 9.5pt;
            }}
            QPushButton#launch:hover {{
                color: #ffffff;
                background: #1a1d23;
            }}
            QPushButton#modeToggle {{
                color: #ffffff;
                background: #172036;
                border: 1px solid {DRAW};
                border-radius: 12px;
                padding: 7px 12px;
                font-size: 9pt;
            }}
            QPushButton#modeToggle:hover {{ background: #20305a; }}
            QLabel#status {{
                color: {MUTED};
                padding: 0 8px;
                font-size: 9pt;
            }}
            QToolButton#windowControl {{
                color: {MUTED};
                background: transparent;
                border: none;
                border-radius: 4px;
                font-size: 15px;
            }}
            QToolButton#windowControl:hover {{
                color: #ffffff;
                background: #242830;
            }}
            QToolButton#closeControl:hover {{
                color: #ffffff;
                background: #c42b1c;
            }}
        """)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        drag_handle = QtWidgets.QLabel("⠿")
        drag_handle.setObjectName("dragHandle")
        drag_handle.setFixedWidth(22)
        self._make_drag_target(drag_handle)
        layout.addWidget(drag_handle)

        brand = QtWidgets.QLabel("OPENCANDLES")
        brand.setObjectName("brand")
        self._make_drag_target(brand)
        layout.addWidget(brand)
        self.launch_buttons = {}
        labels = (
            ("chart", "Technical Analysis"),
            ("options", "Options"),
            ("orderflow", "Order Flow"),
            ("fundamentals", "Fundamentals"),
            ("macro", "Macro"),
            ("sentiment", "Sentiment"),
            ("news", "News"),
        )
        for page_type, label in labels:
            button = QtWidgets.QPushButton(label)
            button.setObjectName("launch")
            button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            button.clicked.connect(
                lambda _, key=page_type: self.open_page(key)
            )
            layout.addWidget(button)
            self.launch_buttons[page_type] = button

        self.mode_toggle = QtWidgets.QPushButton("● Bar  |  Tabs")
        self.mode_toggle.setObjectName("modeToggle")
        self.mode_toggle.setToolTip("Switch to tabbed workspace mode")
        self.mode_toggle.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.mode_toggle.clicked.connect(self.modeSwitchRequested)
        layout.addWidget(self.mode_toggle)

        layout.addStretch()
        status = QtWidgets.QLabel("DUMMY/USD  •  LIVE")
        status.setObjectName("status")
        self._make_drag_target(status)
        layout.addWidget(status)

        minimize = self._window_button("−", "Minimize", self.showMinimized)
        layout.addWidget(minimize)
        close = self._window_button("×", "Close OpenCandles", self.close, close=True)
        layout.addWidget(close)

    def _window_button(self, text, tooltip, slot, close=False):
        button = QtWidgets.QToolButton()
        button.setObjectName("closeControl" if close else "windowControl")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(38, 38)
        button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        button.clicked.connect(slot)
        return button

    def _make_drag_target(self, widget):
        widget.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        widget.installEventFilter(self)

    def _begin_drag(self, global_position):
        self._user_positioned = True
        self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        self._drag_offset = global_position - self.frameGeometry().topLeft()
        handle = self.windowHandle()
        self._native_drag = bool(handle and handle.startSystemMove())

    def _continue_drag(self, global_position):
        if self._drag_offset is not None and not self._native_drag:
            self.move(global_position - self._drag_offset)

    def _end_drag(self):
        self._drag_offset = None
        self._native_drag = False
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)

    def eventFilter(self, watched, event):
        event_type = event.type()
        if (
            event_type == QtCore.QEvent.Type.MouseButtonPress
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            watched.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            self._begin_drag(event.globalPosition().toPoint())
            return True
        if (
            event_type == QtCore.QEvent.Type.MouseMove
            and event.buttons() & QtCore.Qt.MouseButton.LeftButton
        ):
            self._continue_drag(event.globalPosition().toPoint())
            return True
        if event_type == QtCore.QEvent.Type.MouseButtonRelease:
            watched.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
            self._end_drag()
            return True
        return super().eventFilter(watched, event)

    def open_page(self, page_type: str):
        window = StandalonePageWindow(page_type, self.registry)
        return self._show_page_window(window)

    def adopt_page(self, page_type: str, page, title=None):
        window = StandalonePageWindow(
            page_type, self.registry, page=page, title=title
        )
        return self._show_page_window(window)

    def _show_page_window(self, window):
        window.destroyed.connect(
            lambda *_: self._forget_window(window)
        )
        self.open_windows.append(window)
        window.show()
        window.raise_()
        window.activateWindow()
        return window

    def _forget_window(self, window):
        if window in self.open_windows:
            self.open_windows.remove(window)

    def _position_top_center(self):
        if self._user_positioned:
            return
        screen = (
            QtGui.QGuiApplication.screenAt(QtGui.QCursor.pos())
            or QtWidgets.QApplication.primaryScreen()
            or self.screen()
        )
        if screen is None:
            return
        area = screen.availableGeometry()
        x = area.left() + (area.width() - self.width()) // 2
        position = QtCore.QPoint(max(area.left(), x), area.top())
        self.move(position)
        handle = self.windowHandle()
        if handle is not None:
            handle.setPosition(position)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_positioned:
            self._initial_positioned = True
            self._position_top_center()
            for delay in (0, 60, 180):
                QtCore.QTimer.singleShot(delay, self._position_top_center)

    def showMaximized(self):
        self.showNormal()

    def showFullScreen(self):
        self.showNormal()

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.Type.WindowStateChange:
            blocked = (
                QtCore.Qt.WindowState.WindowMaximized
                | QtCore.Qt.WindowState.WindowFullScreen
            )
            if self.windowState() & blocked:
                QtCore.QTimer.singleShot(0, self._restore_compact_state)
        super().changeEvent(event)

    def _restore_compact_state(self):
        self.setWindowState(QtCore.Qt.WindowState.WindowNoState)
        self.setFixedSize(self._bar_size)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._begin_drag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_offset is not None
            and event.buttons() & QtCore.Qt.MouseButton.LeftButton
        ):
            self._continue_drag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._end_drag()
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        for window in list(self.open_windows):
            window.close()
        super().closeEvent(event)
