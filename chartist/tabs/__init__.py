"""Generic tab workspace and page registration."""

from .page_registry import PageRegistry, createDefaultRegistry
from .workspace_tabs import WorkspaceTabs

__all__ = ["PageRegistry", "WorkspaceTabs", "createDefaultRegistry"]
