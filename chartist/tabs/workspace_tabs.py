"""Generic top-level tab workspace."""

from pyqtgraph.Qt import QtCore, QtWidgets

from chartist.theme import BG, BORDER, DRAW, FG, MUTED

from .new_workspace_view import NewWorkspaceView
from .page_registry import PageRegistry, createDefaultRegistry


class WorkspaceTabBar(QtWidgets.QTabBar):
    """Dark tab strip with an add button kept beside the final tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.setExpanding(False)
        self.setUsesScrollButtons(True)

        self.addButton = QtWidgets.QToolButton(self)
        self.addButton.setObjectName("addTab")
        self.addButton.setText("+")
        self.addButton.setToolTip("New workspace")
        self.addButton.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.tabMoved.connect(lambda *_: self._placeAddButton())

    def tabInserted(self, index):
        super().tabInserted(index)
        QtCore.QTimer.singleShot(0, self._placeAddButton)

    def tabRemoved(self, index):
        super().tabRemoved(index)
        QtCore.QTimer.singleShot(0, self._placeAddButton)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._placeAddButton()

    def _placeAddButton(self):
        size = 28
        if self.count():
            x = self.tabRect(self.count() - 1).right() + 7
        else:
            x = 6
        x = min(x, max(0, self.width() - size - 4))
        self.addButton.setGeometry(x, max(0, (self.height() - size) // 2), size, size)
        self.addButton.raise_()


class WorkspaceTabs(QtWidgets.QTabWidget):
    """Hosts registered QWidget views without knowing their implementation."""

    def __init__(self, parent=None, registry: PageRegistry | None = None):
        super().__init__(parent)
        self.registry = registry or createDefaultRegistry()
        self._title_counts: dict[str, int] = {}

        self.setObjectName("workspaceTabs")
        self.tabBarWidget = WorkspaceTabBar(self)
        self.setTabBar(self.tabBarWidget)
        self.setDocumentMode(True)
        self.setMovable(True)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.closePage)
        self.tabBarDoubleClicked.connect(self._promptRename)
        self.tabBarWidget.addButton.clicked.connect(self.openWorkspaceSelector)
        self.setStyleSheet(f"""
            QTabWidget#workspaceTabs {{
                background: {BG};
                border: none;
            }}
            QTabWidget#workspaceTabs::pane {{
                background: {BG};
                border: none;
                border-top: 1px solid {BORDER};
            }}
            QTabWidget#workspaceTabs QTabBar {{
                background: {BG};
            }}
            QTabWidget#workspaceTabs QTabBar::tab {{
                min-width: 118px;
                max-width: 210px;
                height: 31px;
                padding: 0 28px 0 12px;
                margin: 3px 1px 0 0;
                color: {MUTED};
                background: {BG};
                border: none;
                border-right: 1px solid {BORDER};
            }}
            QTabWidget#workspaceTabs QTabBar::tab:hover {{
                color: {FG};
                background: #171b22;
            }}
            QTabWidget#workspaceTabs QTabBar::tab:selected {{
                color: {FG};
                background: #1c2128;
                border-top: 2px solid {DRAW};
            }}
            QTabWidget#workspaceTabs QToolButton#addTab {{
                color: {FG};
                background: transparent;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: 400;
            }}
            QTabWidget#workspaceTabs QToolButton#addTab:hover {{
                background: #252b35;
            }}
        """)

        self.addPage("chart")

    def openWorkspaceSelector(self):
        chooser = NewWorkspaceView(self.registry)
        chooser.pageSelected.connect(
            lambda page_type, view=chooser: self._replaceSelector(view, page_type)
        )
        return self.addView(chooser, "New Tab")

    def _replaceSelector(self, chooser, page_type):
        index = self.indexOf(chooser)
        if index < 0:
            return None
        widget = self.registry.create(page_type)
        widget.setProperty("pageType", page_type)
        title = self._nextTitle(page_type)
        self.removeTab(index)
        chooser.deleteLater()
        self.insertTab(index, widget, title)
        self.selectPage(index)
        return widget

    def _nextTitle(self, page_type):
        base_title = self.registry.titleFor(page_type)
        sequence = self._title_counts.get(page_type, 0) + 1
        self._title_counts[page_type] = sequence
        return f"{base_title} {sequence}"

    def addPage(self, page_type: str = "chart", title: str | None = None):
        widget = self.registry.create(page_type)
        widget.setProperty("pageType", page_type)
        if title is None:
            title = self._nextTitle(page_type)
        return self.addView(widget, title)

    def addView(self, widget: QtWidgets.QWidget, title: str):
        """Add any QWidget subclass, making it the active workspace page."""
        if not isinstance(widget, QtWidgets.QWidget):
            raise TypeError("Workspace pages must be QWidget instances")
        index = self.addTab(widget, title)
        self.selectPage(index)
        return widget

    def detachPages(self):
        """Remove and return real pages without deleting or cleaning them up."""
        pages = []
        indexes = []
        for index in range(self.count()):
            widget = self.widget(index)
            page_type = widget.property("pageType")
            if page_type:
                pages.append((page_type, self.tabText(index), widget))
                indexes.append(index)
        for index in reversed(indexes):
            self.removeTab(index)
        return pages

    def adoptPage(self, page_type: str, title: str, widget):
        """Attach an existing page widget while preserving all of its state."""
        widget.setProperty("pageType", page_type)
        return self.addView(widget, title)

    def selectPage(self, index: int):
        if not 0 <= index < self.count():
            raise IndexError(f"Tab index out of range: {index}")
        self.setCurrentIndex(index)
        current = self.currentWidget()
        if current is not None:
            current.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def renamePage(self, index: int, title: str):
        if not 0 <= index < self.count():
            raise IndexError(f"Tab index out of range: {index}")
        title = title.strip()
        if not title:
            raise ValueError("Tab title cannot be empty")
        self.setTabText(index, title)

    def closePage(self, index: int) -> bool:
        if not 0 <= index < self.count():
            return False
        if self.count() == 1:
            return False

        widget = self.widget(index)
        cleanup = getattr(widget, "cleanup", None)
        if callable(cleanup):
            cleanup()
        self.removeTab(index)
        widget.deleteLater()
        return True

    def _promptRename(self, index: int):
        if index < 0:
            return
        title, accepted = QtWidgets.QInputDialog.getText(
            self,
            "Rename tab",
            "Tab name:",
            text=self.tabText(index),
        )
        if accepted and title.strip():
            self.renamePage(index, title)

    def closeEvent(self, event):
        for index in range(self.count()):
            cleanup = getattr(self.widget(index), "cleanup", None)
            if callable(cleanup):
                cleanup()
        super().closeEvent(event)


__all__ = ["WorkspaceTabBar", "WorkspaceTabs"]
