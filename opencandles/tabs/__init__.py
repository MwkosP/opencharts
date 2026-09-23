"""Generic tab workspace and page registration."""

from .page_registry import PageRegistry, create_default_registry
from .workspace_tabs import WorkspaceTabs

__all__ = ["PageRegistry", "WorkspaceTabs", "create_default_registry"]
