"""Interactive chart drawing tools."""

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from chartist.core.formatting import fmtPrice
from chartist.theme import DOWN, DRAW

Qt = QtCore.Qt

def _drawPens(color=DRAW):
    return pg.mkPen(color, width=1.5), pg.mkPen(color, width=3)


class Drawing:
    """Base class: owns graphics items, can lock / hide / remove / refresh itself."""

    def __init__(self, chart):
        self.chart = chart
        self.items = []                 # (plot, item)
        self.locked = False
        self._busy = False              # ignore change signals while refreshing

    def _add(self, plot, item):
        plot.addItem(item, ignoreBounds=True)
        self.items.append((plot, item))
        return item

    def _clicked(self, item, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            ev.accept()
            self.chart.removeDrawing(self)

    def setVisible(self, on):
        for _, item in self.items:
            item.setVisible(on)

    def setLocked(self, locked):
        self.locked = locked

    def remove(self):
        for plot, item in self.items:
            plot.removeItem(item)

    def refresh(self):
        pass

    def priceTags(self):
        return []

    def timeTags(self):
        return []


class HlineDrawing(Drawing):
    def __init__(self, chart, price):
        super().__init__(chart)
        self.price = price
        pen, hover = _drawPens()
        self.line = self._add(chart.price_plot, pg.InfiniteLine(
            pos=chart.fy(price), angle=0, movable=True, pen=pen, hoverPen=hover))
        self.line.sigPositionChanged.connect(self._moved)
        self.line.sigClicked.connect(self._clicked)

    def _moved(self, line):
        if not self._busy:
            self.price = self.chart.inv(line.value())
        self.chart.price_axis.update()

    def refresh(self):
        self._busy = True
        self.line.setValue(self.chart.fy(self.price))
        self._busy = False

    def setLocked(self, locked):
        super().setLocked(locked)
        self.line.setMovable(not locked)

    def priceTags(self):
        return [(self.line.value(), fmtPrice(self.price), DRAW)]


class VlineDrawing(Drawing):
    """Vertical line through the price pane and every indicator pane."""

    def __init__(self, chart, x):
        super().__init__(chart)
        self.pen, hover = _drawPens()
        self.line = self._add(chart.price_plot, pg.InfiniteLine(
            pos=x, angle=90, movable=True, pen=self.pen, hoverPen=hover))
        self.partners = {}
        for pane in chart.panes.values():
            self.attach(pane)
        self.line.sigPositionChanged.connect(self._moved)
        self.line.sigClicked.connect(self._clicked)

    def attach(self, pane):
        partner = pg.InfiniteLine(pos=self.line.value(), angle=90, pen=self.pen)
        partner.setVisible(self.line.isVisible())
        pane.plot.addItem(partner, ignoreBounds=True)
        self.partners[pane] = partner

    def detach(self, pane):
        partner = self.partners.pop(pane, None)
        if partner is not None:
            pane.plot.removeItem(partner)

    def _moved(self, line):
        for partner in self.partners.values():
            partner.setValue(line.value())
        self.chart.time_axis.update()

    def setVisible(self, on):
        super().setVisible(on)
        for partner in self.partners.values():
            partner.setVisible(on)

    def setLocked(self, locked):
        super().setLocked(locked)
        self.line.setMovable(not locked)

    def remove(self):
        super().remove()
        for pane, partner in self.partners.items():
            pane.plot.removeItem(partner)
        self.partners.clear()

    def timeTags(self):
        return [(self.line.value(), self.chart.timeText(self.line.value()), DRAW)]


class SegmentDrawing(Drawing):
    """Two-point drawing controlled by a draggable segment with end handles."""

    def __init__(self, chart, p1, p2, pen, hover):
        super().__init__(chart)
        self.p1, self.p2 = p1, p2
        self.roi = self._add(chart.price_plot, pg.LineSegmentROI(
            positions=[self._view(p1), self._view(p2)], pen=pen, hoverPen=hover,
            handlePen=pg.mkPen(DRAW), handleHoverPen=pg.mkPen("#ffffff")))
        self.roi.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.roi.sigClicked.connect(self._clicked)
        self.roi.sigRegionChanged.connect(self._sync)

    def _view(self, pt):
        return (pt[0], self.chart.fy(pt[1]))

    def _sync(self, *_):
        if self._busy:
            return
        a, b = (self.roi.mapToParent(h["item"].pos()) for h in self.roi.handles)
        self.p1 = (a.x(), self.chart.inv(a.y()))
        self.p2 = (b.x(), self.chart.inv(b.y()))
        self._changed()

    def _changed(self):
        pass

    def refresh(self):
        self._busy = True
        for h, pt in zip(self.roi.handles, (self.p1, self.p2)):
            self.roi.movePoint(h["item"], QtCore.QPointF(*self._view(pt)), finish=False)
        self._busy = False
        self._changed()

    def setLocked(self, locked):
        super().setLocked(locked)
        self.roi.translatable = not locked
        for h in self.roi.getHandles():
            h.setVisible(not locked)


class TrendDrawing(SegmentDrawing):
    def __init__(self, chart, p1, p2):
        super().__init__(chart, p1, p2, *_drawPens())


FIB_LEVELS = [(0, "#787b86"), (0.236, "#f23645"), (0.382, "#ff9800"), (0.5, "#4caf50"),
              (0.618, "#089981"), (0.786, "#00bcd4"), (1, "#787b86")]


class FibDrawing(SegmentDrawing):
    """Fib retracement: level 1 at the first click, level 0 at the second."""

    def __init__(self, chart, p1, p2):
        dashed = pg.mkPen("#8b949e", width=1, style=Qt.PenStyle.DashLine)
        super().__init__(chart, p1, p2, dashed, pg.mkPen("#ffffff", width=1.5))
        self.lines, self.labels = [], []
        for lvl, color in FIB_LEVELS:
            self.lines.append(self._add(chart.price_plot, pg.PlotCurveItem(pen=pg.mkPen(color, width=1.2))))
            self.labels.append(self._add(chart.price_plot, pg.TextItem(color=color, anchor=(0, 1))))
        self._changed()

    def _changed(self):
        if not hasattr(self, "lines"):
            return
        (x1, pr1), (x2, pr2) = self.p1, self.p2
        xa, xb = min(x1, x2), max(x1, x2)
        for (lvl, _), line, label in zip(FIB_LEVELS, self.lines, self.labels):
            price = pr2 + (pr1 - pr2) * lvl
            y = self.chart.fy(price)
            line.setData([xa, xb], [y, y])
            label.setText(f"{lvl:g} ({fmtPrice(price)})")
            label.setPos(xa, y)


class FilledRectRoi(pg.RectROI):
    def __init__(self, pos, size, brush, **kwargs):
        super().__init__(pos, size, **kwargs)
        self.brush = brush
        for pos_, center in (([0, 0], [1, 1]), ([1, 0], [0, 1]), ([0, 1], [1, 0])):
            self.addScaleHandle(pos_, center)

    def paint(self, p, opt, widget):
        w, h = self.state["size"]
        p.fillRect(QtCore.QRectF(0, 0, w, h).normalized(), self.brush)
        super().paint(p, opt, widget)


class RectDrawing(Drawing):
    def __init__(self, chart, p1, p2):
        super().__init__(chart)
        self.p1, self.p2 = p1, p2
        pen, hover = _drawPens()
        fill = QtGui.QColor(DRAW)
        fill.setAlpha(40)
        (x, y), (w, h) = self._geom()
        self.roi = self._add(chart.price_plot, FilledRectRoi(
            (x, y), (w, h), pg.mkBrush(fill), pen=pen, hoverPen=hover,
            handlePen=pg.mkPen(DRAW), handleHoverPen=pg.mkPen("#ffffff")))
        self.roi.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.roi.sigClicked.connect(self._clicked)
        self.roi.sigRegionChanged.connect(self._sync)

    def _geom(self):
        (x1, pr1), (x2, pr2) = self.p1, self.p2
        y1, y2 = self.chart.fy(pr1), self.chart.fy(pr2)
        return (min(x1, x2), min(y1, y2)), (abs(x2 - x1) or 1e-9, abs(y2 - y1) or 1e-9)

    def _sync(self, *_):
        if self._busy:
            return
        (x, y), (w, h) = self.roi.pos(), self.roi.size()
        self.p1 = (x, self.chart.inv(y))
        self.p2 = (x + w, self.chart.inv(y + h))

    def refresh(self):
        self._busy = True
        (x, y), (w, h) = self._geom()
        self.roi.setPos(QtCore.QPointF(x, y), update=False, finish=False)
        self.roi.setSize(QtCore.QPointF(w, h), finish=False)
        self._busy = False

    def setLocked(self, locked):
        super().setLocked(locked)
        self.roi.translatable = not locked
        for h in self.roi.getHandles():
            h.setVisible(not locked)


class NoteText(pg.TextItem):
    """Text note: drag to move, double-click to edit, right-click to delete."""

    def __init__(self, drawing, text):
        super().__init__(text, color="#ffffff", fill=pg.mkBrush(DRAW + "d0"), anchor=(0, 1))
        self.drawing = drawing
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)

    def mouseDragEvent(self, ev):
        if self.drawing.locked or ev.button() != Qt.MouseButton.LeftButton:
            return ev.ignore()
        ev.accept()
        vb = self.getViewBox()
        if ev.isStart():
            self._offset = self.pos() - vb.mapSceneToView(ev.buttonDownScenePos())
        self.setPos(vb.mapSceneToView(ev.scenePos()) + self._offset)
        self.drawing._syncPosition()

    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            ev.accept()
            self.drawing.chart.removeDrawing(self.drawing)
        elif ev.double() and not self.drawing.locked:
            ev.accept()
            self.drawing._edit()


class TextDrawing(Drawing):
    def __init__(self, chart, point, text):
        super().__init__(chart)
        self.point, self.text = point, text
        self.item = self._add(chart.price_plot, NoteText(self, text))
        self.refresh()

    def _syncPosition(self):
        pos = self.item.pos()
        self.point = (pos.x(), self.chart.inv(pos.y()))

    def refresh(self):
        self.item.setPos(self.point[0], self.chart.fy(self.point[1]))

    def _edit(self):
        text, ok = QtWidgets.QInputDialog.getText(self.chart, "Edit note", "Text:", text=self.text)
        if ok and text:
            self.text = text
            self.item.setText(text)


class MeasureDrawing(Drawing):
    """Price / time range box. Temporary: disappears on the next click."""

    def __init__(self, chart, p1):
        super().__init__(chart)
        self.p1 = self.p2 = p1
        self.box = self._add(chart.price_plot, QtWidgets.QGraphicsRectItem())
        self.label = self._add(chart.price_plot, pg.TextItem(color="#ffffff", anchor=(0.5, 1)))
        self.updateEnd(p1)

    def updateEnd(self, p2):
        self.p2 = p2
        (x1, pr1), (x2, pr2) = self.p1, p2
        y1, y2 = self.chart.fy(pr1), self.chart.fy(pr2)
        color = QtGui.QColor(DRAW if pr2 >= pr1 else DOWN)
        self.box.setRect(QtCore.QRectF(QtCore.QPointF(min(x1, x2), min(y1, y2)),
                                       QtCore.QPointF(max(x1, x2), max(y1, y2))))
        self.box.setPen(pg.mkPen(color))
        fill = QtGui.QColor(color)
        fill.setAlpha(45)
        self.box.setBrush(fill)

        diff = pr2 - pr1
        pct = diff / pr1 * 100
        secs = abs(x2 - x1)
        bars = round(secs / self.chart.tf)
        dur = f"{int(secs // 60)}m {int(secs % 60)}s" if secs >= 60 else f"{int(secs)}s"
        self.label.setText(f"{diff:+,.2f} ({pct:+.2f}%)\n{bars} bars · {dur}")
        self.label.fill = pg.mkBrush(color)
        self.label.update()
        self.label.setPos((x1 + x2) / 2, max(y1, y2))

    def refresh(self):
        self.updateEnd(self.p2)


__all__ = [
    "Drawing",
    "FibDrawing",
    "FilledRectRoi",
    "HlineDrawing",
    "MeasureDrawing",
    "NoteText",
    "RectDrawing",
    "SegmentDrawing",
    "TextDrawing",
    "TrendDrawing",
    "VlineDrawing",
]
