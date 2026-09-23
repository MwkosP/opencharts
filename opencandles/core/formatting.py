"""Formatting helpers shared by chart components."""

import numpy as np

def finite(x, y):
    """Return paired values where y is finite."""
    mask = np.isfinite(y)
    return x[mask], y[mask]


def fmt_price(price):
    return f"{price:,.2f}"


def fmt_val(value):
    if not np.isfinite(value):
        return "–"
    return f"{value:,.0f}" if abs(value) >= 10_000 else f"{value:,.2f}"


def span_html(text, color):
    return f'<span style="color:{color}">{text}</span>'
