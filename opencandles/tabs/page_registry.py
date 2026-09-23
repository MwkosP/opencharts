"""Factories for the view types that can be opened in a workspace."""

from collections.abc import Callable
from dataclasses import dataclass

from pyqtgraph.Qt import QtWidgets


PageFactory = Callable[[], QtWidgets.QWidget]


@dataclass(frozen=True)
class PageDefinition:
    title: str
    factory: PageFactory
    menu_label: str


class PageRegistry:
    """Maps stable page type names to QWidget factories."""

    def __init__(self):
        self._pages: dict[str, PageDefinition] = {}

    def register(
        self,
        page_type: str,
        title: str,
        factory: PageFactory,
        menu_label: str | None = None,
    ):
        if not page_type:
            raise ValueError("page_type cannot be empty")
        self._pages[page_type] = PageDefinition(
            title=title,
            factory=factory,
            menu_label=menu_label or title,
        )

    def create(self, page_type: str) -> QtWidgets.QWidget:
        try:
            definition = self._pages[page_type]
        except KeyError as exc:
            raise KeyError(f"Unknown page type: {page_type!r}") from exc
        widget = definition.factory()
        if not isinstance(widget, QtWidgets.QWidget):
            raise TypeError(f"Factory for {page_type!r} did not return a QWidget")
        return widget

    def title_for(self, page_type: str) -> str:
        try:
            return self._pages[page_type].title
        except KeyError as exc:
            raise KeyError(f"Unknown page type: {page_type!r}") from exc

    def menu_entries(self):
        """Return registered page types in their display order."""
        return tuple(
            (page_type, definition.menu_label)
            for page_type, definition in self._pages.items()
        )


def create_default_registry() -> PageRegistry:
    """Build the application registry without coupling tab code to chart internals."""
    from functools import partial

    from opencandles.views.chart_view import ChartView
    from opencandles.views.placeholder_view import PlaceholderView

    registry = PageRegistry()
    registry.register(
        "chart", "Chart", ChartView, menu_label="Chart — Technical Analysis"
    )
    registry.register(
        "options", "Options", partial(PlaceholderView, "Options")
    )
    registry.register(
        "orderflow",
        "Order Flow",
        partial(PlaceholderView, "Order Book / Flow"),
        menu_label="Order Book / Flow",
    )
    registry.register(
        "fundamentals", "Fundamentals", partial(PlaceholderView, "Fundamentals")
    )
    registry.register("macro", "Macro", partial(PlaceholderView, "Macro"))
    registry.register(
        "sentiment", "Sentiment", partial(PlaceholderView, "Sentiment")
    )
    registry.register("news", "News", partial(PlaceholderView, "News"))
    return registry
