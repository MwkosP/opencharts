"""In-tab workspace-type chooser."""

from pyqtgraph.Qt import QtCore, QtWidgets

from chartist.theme import BORDER, DRAW, FG, MUTED
from chartist.ui.workspace_icons import workspaceIcon

from .page_registry import PageRegistry


class NewWorkspaceView(QtWidgets.QWidget):
    """Card selector displayed as the content of a newly created tab."""

    pageSelected = QtCore.pyqtSignal(str)

    def __init__(self, registry: PageRegistry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.setObjectName("newWorkspaceView")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#newWorkspaceView,
            QWidget#newWorkspaceView QWidget {{
                background: #000000;
                color: {FG};
            }}
            QLabel#title {{
                color: {FG};
                font-size: 24px;
                font-weight: 600;
            }}
            QLabel#subtitle {{
                color: {MUTED};
                font-size: 10pt;
            }}
            QPushButton#workspaceCard {{
                min-height: 76px;
                padding: 10px 16px;
                color: {FG};
                background: #000000;
                border: 1px solid {BORDER};
                border-radius: 6px;
                text-align: left;
                font-size: 11pt;
            }}
            QPushButton#workspaceCard:hover {{
                background: #0d1117;
                border-color: {DRAW};
            }}
        """)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(36, 34, 36, 34)
        outer.addStretch()

        content = QtWidgets.QWidget()
        content.setMaximumWidth(760)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QtWidgets.QLabel("Open a new workspace")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Choose what this tab will contain")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        layout.addSpacing(18)

        cards = QtWidgets.QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        self.pageButtons = {}
        for index, (page_type, label) in enumerate(registry.menuEntries()):
            button = QtWidgets.QPushButton(label)
            button.setObjectName("workspaceCard")
            button.setIcon(workspaceIcon(page_type))
            button.setIconSize(QtCore.QSize(36, 36))
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _, key=page_type: self.pageSelected.emit(key)
            )
            cards.addWidget(button, index // 2, index % 2)
            self.pageButtons[page_type] = button
        layout.addLayout(cards)

        centered = QtWidgets.QHBoxLayout()
        centered.addStretch()
        centered.addWidget(content, 1)
        centered.addStretch()
        outer.addLayout(centered)
        outer.addStretch()
