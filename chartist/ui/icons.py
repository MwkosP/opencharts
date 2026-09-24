"""Programmatically painted sidebar icons."""

from pyqtgraph.Qt import QtCore, QtGui

from chartist.theme import FG

Qt = QtCore.Qt

def makeIcon(draw, color=FG):
    pm = QtGui.QPixmap(48, 48)
    pm.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.scale(2, 2)                                           # draw on a 24x24 grid
    pen = QtGui.QPen(QtGui.QColor(color), 1.6)
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


def _line(p, x1, y1, x2, y2):
    p.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))


def iconCross(p):
    _line(p, 12, 3, 12, 21); _line(p, 3, 12, 21, 12)


def iconSidebar(p):
    p.drawRoundedRect(QtCore.QRectF(3, 4, 18, 16), 2, 2)
    _line(p, 8, 4, 8, 20)
    _line(p, 5.5, 8, 5.5, 16)


def iconPin(p):
    p.drawPolygon(QtGui.QPolygonF([
        QtCore.QPointF(8, 4),
        QtCore.QPointF(17, 4),
        QtCore.QPointF(15, 10),
        QtCore.QPointF(19, 14),
        QtCore.QPointF(6, 14),
        QtCore.QPointF(10, 10),
    ]))
    _line(p, 12.5, 14, 12.5, 22)


def iconSettings(p):
    color = p.pen().color()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QtCore.QPointF(12, 12), 7.6, 7.6)
    for angle in range(0, 360, 45):
        p.save()
        p.translate(12, 12)
        p.rotate(angle)
        p.drawRoundedRect(QtCore.QRectF(-2.1, -10.8, 4.2, 5.2), 0.8, 0.8)
        p.restore()
    p.save()
    p.setCompositionMode(
        QtGui.QPainter.CompositionMode.CompositionMode_Clear
    )
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(Qt.GlobalColor.white)
    p.drawEllipse(QtCore.QPointF(12, 12), 3.4, 3.4)
    p.restore()


def iconArrow(p):
    pts = [(7, 3), (7, 19), (11, 15), (14, 21), (16, 20), (13, 14), (18.5, 14)]
    p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(*pt) for pt in pts]))


def iconTrend(p):
    _line(p, 5, 19, 19, 5); _dot(p, 5, 19); _dot(p, 19, 5)


def iconHline(p):
    _line(p, 2, 12, 22, 12); _dot(p, 12, 12)


def iconVline(p):
    _line(p, 12, 2, 12, 22); _dot(p, 12, 12)


def iconRect(p):
    p.drawRect(QtCore.QRectF(4, 6, 16, 12))
    for x, y in ((4, 6), (20, 6), (4, 18), (20, 18)):
        _dot(p, x, y, 1.6)


def iconFib(p):
    for y in (5, 9.5, 14.5, 19):
        _line(p, 3, y, 21, y)
    _dot(p, 3, 19, 1.6); _dot(p, 21, 5, 1.6)


def iconMeasure(p):
    p.save()
    p.translate(12, 12); p.rotate(-45)
    p.drawRect(QtCore.QRectF(-10, -3.5, 20, 7))
    for x in (-6, -2, 2, 6):
        _line(p, x, -3.5, x, -0.5)
    p.restore()


def iconZoomIn(p):
    p.setPen(QtGui.QPen(QtGui.QColor(FG), 1.4, Qt.PenStyle.DashLine))
    p.drawRect(QtCore.QRectF(4, 4, 13, 13))
    p.setPen(QtGui.QPen(QtGui.QColor(FG), 1.6))
    _line(p, 17, 17, 22, 22)
    _line(p, 7, 10.5, 14, 10.5)
    _line(p, 10.5, 7, 10.5, 14)


def iconZoomOut(p):
    p.drawEllipse(QtCore.QRectF(3, 3, 14, 14))
    _line(p, 16.5, 16.5, 22, 22)
    _line(p, 6.5, 10, 13.5, 10)


def iconText(p):
    _line(p, 5, 5, 19, 5); _line(p, 12, 5, 12, 20); _line(p, 9, 20, 15, 20)


def iconMagnet(p):
    path = QtGui.QPainterPath()
    path.moveTo(6, 4)
    path.lineTo(6, 12)
    path.arcTo(QtCore.QRectF(6, 6, 12, 12), 180, 180)
    path.lineTo(18, 4)
    p.drawPath(path)
    _line(p, 4, 7, 8, 7); _line(p, 16, 7, 20, 7)


def iconLock(p):
    p.drawRoundedRect(QtCore.QRectF(5, 11, 14, 10), 2, 2)
    path = QtGui.QPainterPath()
    path.moveTo(8, 11)
    path.lineTo(8, 8)
    path.arcTo(QtCore.QRectF(8, 3, 8, 10), 180, -180)
    path.lineTo(16, 11)
    p.drawPath(path)
    _dot(p, 12, 16, 1.4)


def iconEye(p):
    path = QtGui.QPainterPath()
    path.moveTo(2, 12)
    path.quadTo(12, 2, 22, 12)
    path.quadTo(12, 22, 2, 12)
    p.drawPath(path)
    p.drawEllipse(QtCore.QPointF(12, 12), 3, 3)


def iconTrash(p):
    _line(p, 4, 7, 20, 7); _line(p, 10, 4, 14, 4)
    p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(*pt)
                                   for pt in ((6.5, 7), (7.5, 20), (16.5, 20), (17.5, 7))]))
    _line(p, 10, 10, 10, 17); _line(p, 14, 10, 14, 17)


__all__ = [
    "iconArrow",
    "iconCross",
    "iconEye",
    "iconFib",
    "iconHline",
    "iconLock",
    "iconMagnet",
    "iconMeasure",
    "iconPin",
    "iconRect",
    "iconSettings",
    "iconText",
    "iconTrash",
    "iconTrend",
    "iconVline",
    "iconZoomIn",
    "iconZoomOut",
    "makeIcon",
]
