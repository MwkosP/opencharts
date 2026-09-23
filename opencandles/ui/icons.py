"""Programmatically painted sidebar icons."""

from pyqtgraph.Qt import QtCore, QtGui

from opencandles.theme import FG

Qt = QtCore.Qt

def make_icon(draw):
    pm = QtGui.QPixmap(48, 48)
    pm.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.scale(2, 2)                                           # draw on a 24x24 grid
    pen = QtGui.QPen(QtGui.QColor(FG), 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    draw(p)
    p.end()
    return QtGui.QIcon(pm)


def _dot(p, x, y, r=2.0):
    p.save()
    p.setBrush(QtGui.QColor(FG))
    p.drawEllipse(QtCore.QPointF(x, y), r, r)
    p.restore()


def _L(p, x1, y1, x2, y2):
    p.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))


def icon_cross(p):
    _L(p, 12, 3, 12, 21); _L(p, 3, 12, 21, 12)


def icon_arrow(p):
    pts = [(7, 3), (7, 19), (11, 15), (14, 21), (16, 20), (13, 14), (18.5, 14)]
    p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(*pt) for pt in pts]))


def icon_trend(p):
    _L(p, 5, 19, 19, 5); _dot(p, 5, 19); _dot(p, 19, 5)


def icon_hline(p):
    _L(p, 2, 12, 22, 12); _dot(p, 12, 12)


def icon_vline(p):
    _L(p, 12, 2, 12, 22); _dot(p, 12, 12)


def icon_rect(p):
    p.drawRect(QtCore.QRectF(4, 6, 16, 12))
    for x, y in ((4, 6), (20, 6), (4, 18), (20, 18)):
        _dot(p, x, y, 1.6)


def icon_fib(p):
    for y in (5, 9.5, 14.5, 19):
        _L(p, 3, y, 21, y)
    _dot(p, 3, 19, 1.6); _dot(p, 21, 5, 1.6)


def icon_measure(p):
    p.save()
    p.translate(12, 12); p.rotate(-45)
    p.drawRect(QtCore.QRectF(-10, -3.5, 20, 7))
    for x in (-6, -2, 2, 6):
        _L(p, x, -3.5, x, -0.5)
    p.restore()


def icon_zoom_in(p):
    p.setPen(QtGui.QPen(QtGui.QColor(FG), 1.4, Qt.PenStyle.DashLine))
    p.drawRect(QtCore.QRectF(4, 4, 13, 13))
    p.setPen(QtGui.QPen(QtGui.QColor(FG), 1.6))
    _L(p, 17, 17, 22, 22)
    _L(p, 7, 10.5, 14, 10.5)
    _L(p, 10.5, 7, 10.5, 14)


def icon_zoom_out(p):
    p.drawEllipse(QtCore.QRectF(3, 3, 14, 14))
    _L(p, 16.5, 16.5, 22, 22)
    _L(p, 6.5, 10, 13.5, 10)


def icon_text(p):
    _L(p, 5, 5, 19, 5); _L(p, 12, 5, 12, 20); _L(p, 9, 20, 15, 20)


def icon_magnet(p):
    path = QtGui.QPainterPath()
    path.moveTo(6, 4)
    path.lineTo(6, 12)
    path.arcTo(QtCore.QRectF(6, 6, 12, 12), 180, 180)
    path.lineTo(18, 4)
    p.drawPath(path)
    _L(p, 4, 7, 8, 7); _L(p, 16, 7, 20, 7)


def icon_lock(p):
    p.drawRoundedRect(QtCore.QRectF(5, 11, 14, 10), 2, 2)
    path = QtGui.QPainterPath()
    path.moveTo(8, 11)
    path.lineTo(8, 8)
    path.arcTo(QtCore.QRectF(8, 3, 8, 10), 180, -180)
    path.lineTo(16, 11)
    p.drawPath(path)
    _dot(p, 12, 16, 1.4)


def icon_eye(p):
    path = QtGui.QPainterPath()
    path.moveTo(2, 12)
    path.quadTo(12, 2, 22, 12)
    path.quadTo(12, 22, 2, 12)
    p.drawPath(path)
    p.drawEllipse(QtCore.QPointF(12, 12), 3, 3)


def icon_trash(p):
    _L(p, 4, 7, 20, 7); _L(p, 10, 4, 14, 4)
    p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(*pt)
                                   for pt in ((6.5, 7), (7.5, 20), (16.5, 20), (17.5, 7))]))
    _L(p, 10, 10, 10, 17); _L(p, 14, 10, 14, 17)
