"""Compact launcher bar and standalone workspace windows."""

from pathlib import Path

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from chartist.settings import SettingsWindow
from chartist.tabs.page_registry import PageRegistry, createDefaultRegistry
from chartist.theme import BORDER, DRAW, FG, MUTED
from chartist.ui.icons import iconPin, iconSettings, makeIcon


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
        self.pageType = page_type
        self.page = page or registry.create(page_type)
        self.page.setProperty("pageType", page_type)
        self.pageTitle = title or registry.titleFor(page_type)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.WindowMinimizeButtonHint
            | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            | QtCore.Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumSize(640, 420)
        self.setCentralWidget(self.page)
        self.setWindowTitle(f"Chartist — {self.pageTitle}")
        self.resize(1360, 880)

    def takePage(self):
        page = self.takeCentralWidget()
        self.page = None
        return page

    def closeEvent(self, event):
        cleanup = getattr(self.page, "cleanup", None) if self.page is not None else None
        if callable(cleanup):
            cleanup()
        super().closeEvent(event)


class LauncherWindow(QtWidgets.QWidget):
    """Small draggable bar used to launch independent Chartist tools."""

    modeSwitchRequested = QtCore.pyqtSignal()

    def __init__(
        self,
        parent=None,
        registry: PageRegistry | None = None,
        settings_window: SettingsWindow | None = None,
    ):
        super().__init__(parent)
        self.registry = registry or createDefaultRegistry()
        self.settingsWindow = settings_window or SettingsWindow()
        self.openWindows = []
        self._drag_offset = None
        self._native_drag = False
        self._drag_targets = []
        self._initial_positioned = False
        self._user_positioned = False
        self._bar_size = QtCore.QSize(1000, 58)

        self.setObjectName("launcher")
        self.setWindowTitle("Chartist")
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
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
            QToolButton#profileAvatar {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            QToolButton#profileAvatar:hover,
            QToolButton#profileAvatar:pressed {{
                background: transparent;
            }}
            QToolButton#profileAvatar::menu-indicator {{
                image: none;
                width: 0px;
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
            QToolButton#optionsControl {{
                color: {MUTED};
                background: transparent;
                border: none;
                padding: 0;
            }}
            QToolButton#optionsControl:hover,
            QToolButton#optionsControl:pressed {{
                color: #ffffff;
                background: transparent;
            }}
            QToolButton#optionsControl::menu-indicator {{
                image: none;
                width: 0px;
            }}
            QToolButton#pinControl {{
                color: {MUTED};
                background: transparent;
                border: none;
                padding: 0;
            }}
            QToolButton#pinControl:hover {{
                color: #ffffff;
                background: transparent;
            }}
            QToolButton#pinControl:checked {{
                color: #ffffff;
                background: transparent;
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
            QMenu {{
                color: {FG};
                background: #111318;
                border: 1px solid {BORDER};
                padding: 5px;
            }}
            QMenu::item {{
                border-radius: 4px;
                padding: 7px 28px 7px 10px;
            }}
            QMenu::item:selected {{
                color: #ffffff;
                background: #242830;
            }}
            QMenu::separator {{
                height: 1px;
                background: {BORDER};
                margin: 5px 8px;
            }}
        """)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        self.profileAvatar = QtWidgets.QToolButton()
        self.profileAvatar.setObjectName("profileAvatar")
        self.profileAvatar.setIcon(
            QtGui.QIcon(self._defaultProfilePixmap(42))
        )
        self.profileAvatar.setIconSize(QtCore.QSize(42, 42))
        self.profileAvatar.setFixedSize(46, 46)
        self.profileAvatar.setToolTip("Profile")
        self.profileAvatar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.profileAvatar.clicked.connect(self.showProfileMenu)
        self.profileMenu = self._buildProfileMenu()
        layout.addWidget(self.profileAvatar)

        brand = QtWidgets.QLabel("CHARTIST")
        brand.setObjectName("brand")
        self._makeDragTarget(brand)
        layout.addWidget(brand)
        self.launchButtons = {}
        labels = (
            ("chart", "Technicals"),
            ("options", "Options"),
            ("orderflow", "OrderFlow"),
            ("fundamentals", "Fundamentals"),
            ("macro", "Macro"),
            ("sentiment", "Sentiment"),
            ("onchain", "OnChain"),
            ("news", "News"),
        )
        for page_type, label in labels:
            button = QtWidgets.QPushButton(label)
            button.setObjectName("launch")
            button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            button.clicked.connect(
                lambda _, key=page_type: self.openPage(key)
            )
            layout.addWidget(button)
            self.launchButtons[page_type] = button

        layout.addStretch()
        self.pinButton = QtWidgets.QToolButton()
        self.pinButton.setObjectName("pinControl")
        self.pinButton.setIcon(makeIcon(iconPin))
        self.pinButton.setIconSize(QtCore.QSize(16, 16))
        self.pinButton.setFixedSize(26, 30)
        self.pinButton.setCheckable(True)
        self.pinButton.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.pinButton.setToolTip("Allow other windows above launcher")
        self.pinButton.toggled.connect(self._updatePinIcon)
        self.pinButton.clicked.connect(self.setPinned)
        self.pinButton.setChecked(True)
        self._updateDragCursor(True)
        layout.addWidget(self.pinButton)

        self.optionsButton = QtWidgets.QToolButton()
        self.optionsButton.setObjectName("optionsControl")
        self.optionsButton.setIcon(makeIcon(iconSettings))
        self.optionsButton.setIconSize(QtCore.QSize(17, 17))
        self.optionsButton.setFixedSize(27, 30)
        self.optionsButton.setCheckable(True)
        self.optionsButton.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.optionsButton.setToolTip("Settings")
        self.optionsButton.clicked.connect(self._toggleSettingsMenu)
        self.settingsWindow.visibilityChanged.connect(
            self._setSettingsButtonActive
        )
        layout.addWidget(self.optionsButton)

        minimize = self._windowButton("−", "Minimize", self.showMinimized)
        layout.addWidget(minimize)
        close = self._windowButton("×", "Close Chartist", self.close, close=True)
        layout.addWidget(close)

    def _windowButton(self, text, tooltip, slot, close=False):
        button = QtWidgets.QToolButton()
        button.setObjectName("closeControl" if close else "windowControl")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(38, 38)
        button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        button.clicked.connect(slot)
        return button

    def _buildProfileMenu(self):
        menu = QtWidgets.QMenu(self)
        menu.setMinimumWidth(300)

        card = QtWidgets.QWidget()
        card.setStyleSheet("background: transparent;")
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)

        avatar = QtWidgets.QLabel()
        avatar.setPixmap(self._defaultProfilePixmap(54))
        avatar.setFixedSize(58, 58)
        avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(avatar)

        details = QtWidgets.QVBoxLayout()
        details.setSpacing(3)
        name = QtWidgets.QLabel("Guest User")
        name.setStyleSheet(
            "color: #ffffff; font-size: 11pt; font-weight: 700;"
        )
        details.addWidget(name)
        profile_type = QtWidgets.QLabel("Default local profile")
        profile_type.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        details.addWidget(profile_type)
        status = QtWidgets.QLabel("Not signed in")
        status.setStyleSheet("color: #6f8cff; font-size: 9pt;")
        details.addWidget(status)
        card_layout.addLayout(details, 1)

        card_action = QtWidgets.QWidgetAction(menu)
        card_action.setDefaultWidget(card)
        menu.addAction(card_action)
        menu.addSeparator()
        version = menu.addAction("Chartist  ·  Version 0.1.0")
        version.setEnabled(False)
        return menu

    def showProfileMenu(self):
        position = self.profileAvatar.mapToGlobal(
            QtCore.QPoint(0, self.profileAvatar.height() + 4)
        )
        self.profileMenu.popup(position)

    @staticmethod
    def _defaultProfilePixmap(size):
        source = QtGui.QPixmap(
            str(Path(__file__).with_name("assets") / "default_profile.jpg")
        )
        avatar = QtGui.QPixmap(size, size)
        avatar.fill(QtCore.Qt.GlobalColor.transparent)

        painter = QtGui.QPainter(avatar)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        circle = QtGui.QPainterPath()
        circle.addEllipse(QtCore.QRectF(1, 1, size - 2, size - 2))
        painter.setClipPath(circle)
        painter.fillRect(avatar.rect(), QtGui.QColor("#ffffff"))
        if not source.isNull():
            scaled = source.scaled(
                size,
                size,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            image = scaled.toImage().convertToFormat(
                QtGui.QImage.Format.Format_RGBA8888
            )
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    if color.red() < 12 and color.green() < 12 and color.blue() < 12:
                        color.setAlpha(0)
                        image.setPixelColor(x, y, color)
            scaled = QtGui.QPixmap.fromImage(image)
            painter.drawPixmap(
                (size - scaled.width()) // 2,
                (size - scaled.height()) // 2,
                scaled,
            )
        painter.setClipping(False)
        painter.setPen(QtGui.QPen(QtGui.QColor("#6f35a5"), 1.5))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QtCore.QRectF(1, 1, size - 2, size - 2))
        painter.end()
        return avatar

    def _updatePinIcon(self, pinned):
        self.pinButton.setIcon(
            makeIcon(iconPin, DRAW if pinned else FG)
        )

    def _updateSettingsIcon(self, active):
        self.optionsButton.setIcon(
            makeIcon(iconSettings, DRAW if active else FG)
        )

    def _setSettingsButtonActive(self, active):
        with QtCore.QSignalBlocker(self.optionsButton):
            self.optionsButton.setChecked(active)
        self._updateSettingsIcon(active)

    def _toggleSettingsMenu(self, active):
        if active:
            self.showSettingsMenu()
        else:
            self.settingsWindow.close()

    def setPinned(self, pinned):
        self._endDrag()
        position = self.pos()
        self.setWindowFlag(
            QtCore.Qt.WindowType.WindowStaysOnTopHint, bool(pinned)
        )
        self.pinButton.setChecked(bool(pinned))
        self.pinButton.setToolTip(
            "Allow other windows above launcher"
            if pinned
            else "Keep launcher above other windows"
        )
        self._updateDragCursor(pinned)
        self.show()
        self.move(position)
        if pinned:
            self.raise_()

    def resetPosition(self):
        self._user_positioned = False
        self._positionTopCenter()

    def showSettingsMenu(self):
        self._setSettingsButtonActive(True)
        screen = (
            QtGui.QGuiApplication.screenAt(
                self.mapToGlobal(self.rect().center())
            )
            or self.screen()
            or QtWidgets.QApplication.primaryScreen()
        )
        if screen is None:
            return
        self.settingsWindow.setContext(
            "compact",
            always_on_top=self.pinButton.isChecked(),
        )
        self.settingsWindow.showOnScreen(screen)

    def _makeDragTarget(self, widget):
        widget.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        widget.installEventFilter(self)
        self._drag_targets.append(widget)

    def _updateDragCursor(self, pinned):
        cursor = (
            QtCore.Qt.CursorShape.ArrowCursor
            if pinned
            else QtCore.Qt.CursorShape.OpenHandCursor
        )
        self.setCursor(cursor)
        for target in self._drag_targets:
            target.setCursor(cursor)

    def _beginDrag(self, global_position):
        if self.pinButton.isChecked():
            return False
        self._user_positioned = True
        self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        self._drag_offset = global_position - self.frameGeometry().topLeft()
        handle = self.windowHandle()
        self._native_drag = bool(handle and handle.startSystemMove())
        return True

    def _continueDrag(self, global_position):
        if self._drag_offset is not None and not self._native_drag:
            self.move(global_position - self._drag_offset)

    def _endDrag(self):
        self._drag_offset = None
        self._native_drag = False
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)

    def eventFilter(self, watched, event):
        event_type = event.type()
        if (
            event_type == QtCore.QEvent.Type.MouseButtonPress
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            if not self._beginDrag(event.globalPosition().toPoint()):
                return False
            watched.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            return True
        if (
            event_type == QtCore.QEvent.Type.MouseMove
            and event.buttons() & QtCore.Qt.MouseButton.LeftButton
        ):
            self._continueDrag(event.globalPosition().toPoint())
            return True
        if event_type == QtCore.QEvent.Type.MouseButtonRelease:
            watched.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
            self._endDrag()
            return True
        return super().eventFilter(watched, event)

    def openPage(self, page_type: str):
        window = StandalonePageWindow(page_type, self.registry)
        return self._showPageWindow(window)

    def adoptPage(self, page_type: str, page, title=None):
        window = StandalonePageWindow(
            page_type, self.registry, page=page, title=title
        )
        return self._showPageWindow(window)

    def _showPageWindow(self, window):
        window.destroyed.connect(
            lambda *_: self._forgetWindow(window)
        )
        self.openWindows.append(window)
        window.show()
        window.raise_()
        window.activateWindow()
        return window

    def _forgetWindow(self, window):
        if window in self.openWindows:
            self.openWindows.remove(window)

    def _positionTopCenter(self):
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
            self._positionTopCenter()
            for delay in (0, 60, 180):
                QtCore.QTimer.singleShot(delay, self._positionTopCenter)

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
                QtCore.QTimer.singleShot(0, self._restoreCompactState)
        super().changeEvent(event)

    def _restoreCompactState(self):
        self.setWindowState(QtCore.Qt.WindowState.WindowNoState)
        self.setFixedSize(self._bar_size)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self._beginDrag(event.globalPosition().toPoint()):
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_offset is not None
            and event.buttons() & QtCore.Qt.MouseButton.LeftButton
        ):
            self._continueDrag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._endDrag()
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        self.settingsWindow.close()
        for window in list(self.openWindows):
            window.close()
        super().closeEvent(event)


__all__ = ["LauncherWindow", "StandalonePageWindow"]
