"""TradingView-like chart mouse navigation."""

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

Qt = QtCore.Qt

class ChartViewBox(pg.ViewBox):
    def __init__(self, chart, pans_y):
        super().__init__(enableMenu=False)
        self.chart = chart
        self.pans_y = pans_y

    def wheelEvent(self, ev, axis=None):
        ev.accept()
        delta = ev.delta()
        horizontal = (hasattr(ev, "orientation")
                      and ev.orientation() == Qt.Orientation.Horizontal)
        shift = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if horizontal or shift:
            xmin, xmax = self.viewRange()[0]
            self.chart.pan_x(-delta / 1200 * (xmax - xmin))
        else:
            self.chart.zoom_x(0.9985 ** delta, center=self.mapToView(ev.pos()).x())

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() != Qt.MouseButton.LeftButton:
            return ev.ignore()
        ev.accept()
        if self.pans_y and self.chart.tool == "zoom_in":
            start = self.mapToView(ev.buttonDownPos())
            current = self.mapToView(ev.pos())
            if ev.isStart():
                self.chart.begin_zoom_box((start.x(), start.y()))
            self.chart.update_zoom_box((current.x(), current.y()))
            if ev.isFinish():
                self.chart.finish_zoom_box((current.x(), current.y()))
            return
        a, b = self.mapToView(ev.lastPos()), self.mapToView(ev.pos())
        dx, dy = a.x() - b.x(), a.y() - b.y()
        if dx:
            self.chart.pan_x(dx)
        if dy and self.pans_y and not self.chart.auto_y:
            self.translateBy(y=dy)
