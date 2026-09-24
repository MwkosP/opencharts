"""Interactive time and value axes."""

import math

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui

Qt = QtCore.Qt

def _drawTag(painter, rect, text, background):
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(pg.mkBrush(background))
    painter.drawRoundedRect(rect, 2, 2)
    painter.setPen(pg.mkPen("#ffffff"))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


def _tagFont():
    font = QtGui.QFont()
    font.setPointSize(9)
    return font


class OffsetDateAxis(pg.DateAxisItem):
    """x values are seconds since t0 (keeps floats small and precise)."""

    def __init__(self, t0, **kwargs):
        super().__init__(**kwargs)
        self.t0 = t0

    def tickValues(self, minVal, maxVal, size):
        levels = super().tickValues(minVal + self.t0, maxVal + self.t0, size)
        return [(spacing, [v - self.t0 for v in values]) for spacing, values in levels]

    def tickStrings(self, values, scale, spacing):
        return super().tickStrings([v + self.t0 for v in values], scale, spacing)


class TimeAxis(OffsetDateAxis):
    """Bottom time scale: draws tags, drag / wheel to zoom time."""

    def __init__(self, chart, t0):
        super().__init__(t0, orientation="bottom")
        self.chart = chart

    def paint(self, p, opt, widget):
        super().paint(p, opt, widget)
        vb = self.linkedView()
        if vb is None:
            return
        p.setFont(_tagFont())
        for xv, text, bg in self.chart.timeTags():
            x = self.mapFromScene(vb.mapViewToScene(QtCore.QPointF(xv, 0))).x()
            if 0 <= x <= self.width():
                _drawTag(p, QtCore.QRectF(x - 62, 3, 124, 18), text, bg)

    def mouseDragEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return ev.ignore()
        ev.accept()
        dx = ev.pos().x() - ev.lastPos().x()
        self.chart.zoomX(math.exp(-dx * 0.006))        # drag right = zoom in

    def wheelEvent(self, ev):
        ev.accept()
        self.chart.zoomX(0.9985 ** ev.delta())

    def mouseClickEvent(self, ev):
        ev.accept()
        if ev.double():
            self.chart.resetView()


class ValueAxis(pg.AxisItem):
    """Right scale of an indicator pane, with value tags."""

    def __init__(self, chart, pane):
        super().__init__("right")
        self.chart, self.pane = chart, pane
        self.enableAutoSIPrefix(False)
        self.setWidth(90)

    def tickStrings(self, values, scale, spacing):
        dec = min(4, max(0, -int(math.floor(math.log10(spacing))))) if spacing > 0 else 2
        return [f"{v:,.{dec}f}" for v in values]

    def paint(self, p, opt, widget):
        super().paint(p, opt, widget)
        vb = self.linkedView()
        if vb is None:
            return
        p.setFont(_tagFont())
        for yv, text, bg in self.pane.valueTags():
            y = self.mapFromScene(vb.mapViewToScene(QtCore.QPointF(0, yv))).y()
            if 0 <= y <= self.height():
                _drawTag(p, QtCore.QRectF(1, y - 9, self.width() - 2, 18), text, bg)

    def mouseDragEvent(self, ev):
        ev.ignore()

    def wheelEvent(self, ev):
        ev.accept()

    def mouseClickEvent(self, ev):
        ev.accept()


class PriceAxis(ValueAxis):
    """Price scale: log-aware ticks, tags, drag / wheel to scale price."""

    def __init__(self, chart):
        super().__init__(chart, None)

    def tickValues(self, minVal, maxVal, size):
        if not self.chart.log_mode:
            return super().tickValues(minVal, maxVal, size)
        levels = super().tickValues(10 ** minVal, 10 ** maxVal, size)   # nice ticks in price
        return [(sp, [math.log10(v) for v in vals if v > 0]) for sp, vals in levels]

    def tickStrings(self, values, scale, spacing):
        prices = [10 ** v for v in values] if self.chart.log_mode else values
        dec = max(0, -int(math.floor(math.log10(spacing)))) if spacing > 0 else 2
        return [f"{p:,.{dec}f}" for p in prices]

    def paint(self, p, opt, widget):
        pg.AxisItem.paint(self, p, opt, widget)
        vb = self.linkedView()
        if vb is None:
            return
        p.setFont(_tagFont())
        for yv, text, bg in self.chart.priceTags():
            y = self.mapFromScene(vb.mapViewToScene(QtCore.QPointF(0, yv))).y()
            if 0 <= y <= self.height():
                _drawTag(p, QtCore.QRectF(1, y - 9, self.width() - 2, 18), text, bg)

    def mouseDragEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return ev.ignore()
        ev.accept()
        dy = ev.pos().y() - ev.lastPos().y()
        self.chart.scaleY(math.exp(dy * 0.006))         # drag down = squeeze

    def wheelEvent(self, ev):
        ev.accept()
        self.chart.scaleY(0.9985 ** ev.delta())

    def mouseClickEvent(self, ev):
        ev.accept()
        if ev.double():
            self.chart.setAuto(True)


__all__ = ["OffsetDateAxis", "PriceAxis", "TimeAxis", "ValueAxis"]
