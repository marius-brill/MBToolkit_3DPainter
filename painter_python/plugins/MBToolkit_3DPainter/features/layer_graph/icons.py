"""Small dependency-free, scalable node-type glyphs (no private Painter resources)."""
from PySide6 import QtCore, QtGui


KINDS = {"PaintLayer": "brush", "PaintEffect": "brush", "FillLayer": "fill", "FillEffect": "fill",
         "GroupLayer": "folder", "InstanceLayer": "link", "AnchorPointEffect": "anchor",
         "LevelsEffect": "levels", "FilterEffect": "filter", "GeneratorEffect": "generator",
         "ColorSelectionEffect": "color", "CompareMaskEffect": "compare", "Mask": "mask"}


def draw(painter, kind, x, y, color):
    painter.save()
    painter.translate(x, y)
    painter.setPen(QtGui.QPen(color, 1.8))
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    symbol = KINDS.get(kind, "node")
    def line(a, b, c, d):
        painter.drawLine(QtCore.QPointF(a, b), QtCore.QPointF(c, d))
    if symbol == "mask":
        painter.drawRoundedRect(QtCore.QRectF(2, 1, 20, 22), 2, 2)
        painter.drawEllipse(QtCore.QRectF(7, 7, 10, 10))
        painter.setBrush(color)
        painter.drawPie(QtCore.QRectF(7, 7, 10, 10), 90 * 16, 180 * 16)
    elif symbol == "brush":
        line(8, 13, 19, 2)
        line(11, 16, 22, 5)
        painter.drawEllipse(QtCore.QRectF(2, 13, 9, 8))
    elif symbol == "fill":
        painter.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(3, 10), QtCore.QPointF(11, 2),
                                            QtCore.QPointF(20, 11), QtCore.QPointF(12, 19)]))
        line(5, 12, 18, 12)
        painter.drawEllipse(QtCore.QRectF(18, 17, 4, 5))
    elif symbol == "folder":
        painter.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(1, 5), QtCore.QPointF(9, 5),
                                            QtCore.QPointF(12, 8), QtCore.QPointF(23, 8),
                                            QtCore.QPointF(23, 21), QtCore.QPointF(1, 21)]))
    elif symbol == "anchor":
        painter.drawEllipse(QtCore.QRectF(9, 1, 6, 6))
        line(12, 7, 12, 22)
        line(6, 10, 18, 10)
        path = QtGui.QPainterPath(QtCore.QPointF(2, 14))
        path.cubicTo(2, 25, 22, 25, 22, 14)
        painter.drawPath(path)
        line(2, 14, 6, 17)
        line(22, 14, 18, 17)
    elif symbol == "link":
        painter.drawRoundedRect(QtCore.QRectF(1, 9, 14, 10), 4, 4)
        painter.drawRoundedRect(QtCore.QRectF(9, 3, 14, 10), 4, 4)
    elif symbol == "levels":
        for i, height in enumerate((7, 15, 20, 11)):
            painter.drawRect(QtCore.QRectF(2 + i * 6, 23 - height, 3, height))
    elif symbol == "filter":
        painter.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(1, 3), QtCore.QPointF(23, 3),
                                            QtCore.QPointF(14, 13), QtCore.QPointF(14, 22),
                                            QtCore.QPointF(10, 22), QtCore.QPointF(10, 13)]))
    elif symbol == "generator":
        painter.drawEllipse(QtCore.QRectF(6, 6, 12, 12))
        for a, b, c, d in ((12, 0, 12, 5), (12, 19, 12, 24), (0, 12, 5, 12), (19, 12, 24, 12),
                            (3, 3, 6, 6), (18, 18, 21, 21), (3, 21, 6, 18), (18, 6, 21, 3)):
            line(a, b, c, d)
    elif symbol == "color":
        for a, b in ((2, 2), (13, 2), (2, 13), (13, 13)):
            painter.drawRect(QtCore.QRectF(a, b, 8, 8))
    elif symbol == "compare":
        painter.drawEllipse(QtCore.QRectF(0, 5, 15, 15))
        painter.drawEllipse(QtCore.QRectF(9, 5, 15, 15))
    else:
        painter.drawRoundedRect(QtCore.QRectF(2, 3, 20, 18), 3, 3)
    painter.restore()