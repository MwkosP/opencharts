"""Cached graphics items used by charts and indicator panes."""

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from chartist.core.orderflow import syntheticFootprint
from chartist.theme import CANDLE_DOWN, CANDLE_UP, FG

Qt = QtCore.Qt

def curve(color, width=1):
    """Create a clipped, automatically downsampled plot curve."""
    item = pg.PlotDataItem(pen=pg.mkPen(color, width=width))
    item.setClipToView(True)
    item.setDownsampling(auto=True, method="peak")
    return item


class CachedItem(pg.GraphicsObject):
    """Draws all closed bars once into a QPicture; only the live (last) bar is
    redrawn on every update. Keeps painting fast with thousands of bars."""

    def __init__(self):
        super().__init__()
        self.picture = QtGui.QPicture()
        self.key = None
        self.rows = []
        self.rect = QtCore.QRectF()

    def _set(self, rows, key, rect):
        self.prepareGeometryChange()
        if key != self.key:
            self.picture = QtGui.QPicture()
            p = QtGui.QPainter(self.picture)
            for row in rows[:-1]:
                self._drawOne(p, *row)
            p.end()
            self.key = key
        self.rows = rows
        self.rect = rect
        self.update()

    def boundingRect(self):
        return self.rect

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)
        if self.rows:
            self._drawOne(p, *self.rows[-1])

    def _drawOne(self, p, *row):
        raise NotImplementedError


def _fingerprint(*arrays):
    return tuple(float(np.nansum(a[:-1])) for a in arrays)


class CandleItem(CachedItem):
    """Candles, hollow candles or OHLC bars."""

    def __init__(self):
        super().__init__()
        self.w = 1.0
        self.style = "candles"
        self.pens = {
            True: pg.mkPen(CANDLE_UP),
            False: pg.mkPen(CANDLE_DOWN),
        }
        self.bar_pens = {
            True: pg.mkPen(CANDLE_UP, width=1.5),
            False: pg.mkPen(CANDLE_DOWN, width=1.5),
        }
        self.brushes = {
            True: pg.mkBrush(CANDLE_UP),
            False: pg.mkBrush(CANDLE_DOWN),
        }

    def setData(self, x, o, h, l, c, width, style):
        self.w, self.style = width * 0.7, style
        if style == "hollow":                       # color by close vs previous close
            prev = np.r_[o[0], c[:-1]]
            up, filled = c >= prev, c < o
        else:
            up = c >= o
            filled = np.ones(len(c), bool)
        rows = list(zip(x.tolist(), o.tolist(), h.tolist(), l.tolist(), c.tolist(),
                        up.tolist(), filled.tolist()))
        n = len(x)
        key = (n, x[0], x[-2] if n > 1 else None, width, style) + _fingerprint(o, h, l, c)
        rect = QtCore.QRectF(x[0] - self.w, float(np.min(l)),
                             x[-1] - x[0] + 2 * self.w, float(np.max(h) - np.min(l)))
        self._set(rows, key, rect)

    def _drawOne(self, p, x, o, h, l, c, up, filled):
        w = self.w
        P = QtCore.QPointF
        if self.style == "bars":
            p.setPen(self.bar_pens[up])
            p.drawLine(P(x, l), P(x, h))
            p.drawLine(P(x - w / 2, o), P(x, o))
            p.drawLine(P(x, c), P(x + w / 2, c))
            return
        p.setPen(self.pens[up])
        p.setBrush(self.brushes[up] if filled else Qt.BrushStyle.NoBrush)
        top, bot = max(o, c), min(o, c)
        if filled:
            p.drawLine(P(x, l), P(x, h))
        else:                                       # hollow body: wick outside the box only
            p.drawLine(P(x, l), P(x, bot))
            p.drawLine(P(x, top), P(x, h))
        if top > bot:
            p.drawRect(QtCore.QRectF(x - w / 2, bot, w, top - bot))
        else:
            p.drawLine(P(x - w / 2, o), P(x + w / 2, o))


class FootprintItem(pg.GraphicsObject):
    """A normal candle followed by a bid/ask footprint grid."""

    def __init__(self, levels=6):
        super().__init__()
        self.levels = levels
        self.w = 1.0
        self.x = np.array([])
        self.o = self.h = self.l = self.c = self.v = np.array([])
        self.prices = self.bid = self.ask = np.empty((0, levels))
        self.step = np.array([])
        self.rect = QtCore.QRectF()
        self.up_pen = pg.mkPen(CANDLE_UP, width=1.8)
        self.down_pen = pg.mkPen(CANDLE_DOWN, width=1.8)
        self.up_doji_pen = pg.mkPen(CANDLE_UP, width=3)
        self.down_doji_pen = pg.mkPen(CANDLE_DOWN, width=3)
        self.split_pen = pg.mkPen("#6e7681", width=1)
        self.cell_pen = pg.mkPen("#30363d", width=0.8)
        self.text_pen = pg.mkPen(FG)
        self.up_brush = pg.mkBrush(CANDLE_UP)
        self.down_brush = pg.mkBrush(CANDLE_DOWN)
        self.setFlag(
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption,
            True,
        )

    def setData(self, x, o, h, l, c, volume, width):
        self.prepareGeometryChange()
        self.w = width * 0.86
        self.x, self.o, self.h, self.l, self.c, self.v = (
            np.asarray(values, dtype=float) for values in (x, o, h, l, c, volume)
        )
        self.prices, self.bid, self.ask, self.step = syntheticFootprint(
            self.o, self.h, self.l, self.c, self.v, self.levels
        )
        if len(self.x):
            self.rect = QtCore.QRectF(
                self.x[0] - self.w,
                float(np.min(self.l)),
                self.x[-1] - self.x[0] + 2 * self.w,
                float(np.max(self.h) - np.min(self.l)),
            )
        else:
            self.rect = QtCore.QRectF()
        self.update()

    def boundingRect(self):
        return self.rect

    @staticmethod
    def _volumeText(value):
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}m"
        if value >= 1_000:
            return f"{value / 1_000:.1f}k"
        if value >= 10:
            return f"{value:.0f}"
        return f"{value:.1f}"

    def paint(self, p, opt, widget):
        if not len(self.x):
            return
        exposed = opt.exposedRect
        first = max(0, int(np.searchsorted(self.x, exposed.left() - self.w)) - 1)
        last = min(len(self.x), int(np.searchsorted(self.x, exposed.right() + self.w)) + 1)
        transform = p.transform()
        bar_pixels = abs(self.w * transform.m11())
        show_cells = bar_pixels >= 52
        font = p.font()
        font.setPixelSize(9)
        p.setFont(font)

        for i in range(first, last):
            x, o, h, l, c = self.x[i], self.o[i], self.h[i], self.l[i], self.c[i]
            up = c >= o
            pen = self.up_pen if up else self.down_pen
            left = x - self.w / 2
            right = x + self.w / 2

            if show_cells:
                peak = max(float(np.max(self.bid[i])), float(np.max(self.ask[i])), 1e-12)
                candle_x = left + self.w * 0.12
                candle_width = self.w * 0.16
                footprint_left = left + self.w * 0.27
                footprint_mid = footprint_left + (right - footprint_left) / 2
                for price, bid, ask in zip(self.prices[i], self.bid[i], self.ask[i]):
                    bottom = price - self.step[i] / 2
                    height = self.step[i]
                    bid_rect = QtCore.QRectF(
                        footprint_left, bottom, footprint_mid - footprint_left, height
                    )
                    ask_rect = QtCore.QRectF(
                        footprint_mid, bottom, right - footprint_mid, height
                    )
                    bid_color = QtGui.QColor(CANDLE_DOWN)
                    ask_color = QtGui.QColor(CANDLE_UP)
                    bid_color.setAlpha(35 + int(150 * bid / peak))
                    ask_color.setAlpha(35 + int(150 * ask / peak))
                    p.fillRect(bid_rect, bid_color)
                    p.fillRect(ask_rect, ask_color)
                    p.setPen(self.cell_pen)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRect(bid_rect)
                    p.drawRect(ask_rect)
                    p.setPen(self.text_pen)
                    p.drawText(
                        bid_rect, Qt.AlignmentFlag.AlignCenter, self._volumeText(bid)
                    )
                    p.drawText(
                        ask_rect, Qt.AlignmentFlag.AlignCenter, self._volumeText(ask)
                    )
                # Explicit divider: bid numbers are left, ask numbers are right.
                p.setPen(self.split_pen)
                p.drawLine(
                    QtCore.QPointF(footprint_mid, l),
                    QtCore.QPointF(footprint_mid, h),
                )
            else:
                candle_x = x
                candle_width = self.w * 0.7

            # A standalone normal candle/doji is placed left of the grid.
            p.setPen(pen)
            p.setBrush(self.up_brush if up else self.down_brush)
            p.drawLine(QtCore.QPointF(candle_x, l), QtCore.QPointF(candle_x, h))
            top, bottom = max(o, c), min(o, c)
            is_doji = abs(top - bottom) <= max(abs(h - l) * 0.05, 1e-12)
            if is_doji:
                p.setPen(self.up_doji_pen if up else self.down_doji_pen)
                p.drawLine(
                    QtCore.QPointF(candle_x - candle_width / 2, o),
                    QtCore.QPointF(candle_x + candle_width / 2, o),
                )
            else:
                p.drawRect(QtCore.QRectF(
                    candle_x - candle_width / 2,
                    bottom,
                    candle_width,
                    top - bottom,
                ))


class VolumeHeatmapItem(pg.GraphicsObject):
    """Time × price volume heatmap from synthetic footprint rows."""

    def __init__(self, levels=10):
        super().__init__()
        self.levels = levels
        self.w = 1.0
        self.x = np.array([])
        self.h = self.l = np.array([])
        self.prices = self.vol = np.empty((0, levels))
        self.step = np.array([])
        self.rect = QtCore.QRectF()
        self.setFlag(
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption,
            True,
        )

    def setData(self, x, h, l, o, c, volume, width):
        self.prepareGeometryChange()
        self.w = width * 0.92
        self.x = np.asarray(x, dtype=float)
        self.h = np.asarray(h, dtype=float)
        self.l = np.asarray(l, dtype=float)
        o = np.asarray(o, dtype=float)
        c = np.asarray(c, dtype=float)
        volume = np.asarray(volume, dtype=float)
        prices, bid, ask, step = syntheticFootprint(
            o, self.h, self.l, c, volume, self.levels
        )
        self.prices = prices
        self.vol = bid + ask
        self.step = step
        if len(self.x):
            self.rect = QtCore.QRectF(
                self.x[0] - self.w,
                float(np.min(self.l)),
                self.x[-1] - self.x[0] + 2 * self.w,
                float(np.max(self.h) - np.min(self.l)),
            )
        else:
            self.rect = QtCore.QRectF()
        self.update()

    def boundingRect(self):
        return self.rect

    def paint(self, p, opt, widget):
        if not len(self.x):
            return
        exposed = opt.exposedRect
        first = max(0, int(np.searchsorted(self.x, exposed.left() - self.w)) - 1)
        last = min(
            len(self.x), int(np.searchsorted(self.x, exposed.right() + self.w)) + 1
        )
        peak = float(np.max(self.vol[first:last])) if last > first else 1.0
        peak = max(peak, 1e-12)
        for i in range(first, last):
            left = self.x[i] - self.w / 2
            for price, vol in zip(self.prices[i], self.vol[i]):
                bottom = price - self.step[i] / 2
                # Green→yellow→red by relative volume.
                amount = float(vol / peak)
                if amount < 0.5:
                    t = amount / 0.5
                    r, g, b = int(47 + (247 - 47) * t), int(174 + (224 - 174) * t), int(74 + (23 - 74) * t)
                else:
                    t = (amount - 0.5) / 0.5
                    r, g, b = int(247 + (230 - 247) * t), int(224 + (34 - 224) * t), int(23 + (31 - 23) * t)
                color = QtGui.QColor(r, g, b, int(50 + 180 * amount))
                p.fillRect(
                    QtCore.QRectF(left, bottom, self.w, self.step[i]),
                    color,
                )


class BarsItem(CachedItem):
    """Histogram bars (volume, MACD histogram) with a color per bar."""

    def __init__(self):
        super().__init__()
        self.w = 1.0
        self.brushes = {}
        self.no_pen = pg.mkPen(None)

    def setData(self, x, heights, colors, width):
        self.w = width * 0.7
        rows = list(zip(x.tolist(), heights.tolist(), list(colors)))
        n = len(x)
        key = (n, x[0], x[-2] if n > 1 else None, width,
               hash(np.asarray(colors[:-1]).tobytes())) + _fingerprint(heights)
        lo = min(0.0, float(np.nanmin(heights)))
        hi = max(0.0, float(np.nanmax(heights)))
        self._set(rows, key, QtCore.QRectF(x[0] - self.w, lo, x[-1] - x[0] + 2 * self.w, hi - lo))

    def _drawOne(self, p, x, v, color):
        if not np.isfinite(v):
            return
        if color not in self.brushes:
            self.brushes[color] = pg.mkBrush(color)
        p.setPen(self.no_pen)
        p.setBrush(self.brushes[color])
        p.drawRect(QtCore.QRectF(x - self.w / 2, 0, self.w, v))


__all__ = ["BarsItem", "CachedItem", "CandleItem", "FootprintItem", "VolumeHeatmapItem", "curve"]
