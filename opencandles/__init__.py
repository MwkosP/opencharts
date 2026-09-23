"""OpenCandles desktop application bootstrap settings."""

import os
import sys


def _configure_linux_window_backend():
    """Use XWayland when Wayland would reject compact-window positioning."""
    if (
        sys.platform.startswith("linux")
        and os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        and os.environ.get("DISPLAY")
        and "QT_QPA_PLATFORM" not in os.environ
    ):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


_configure_linux_window_backend()

__all__ = []
