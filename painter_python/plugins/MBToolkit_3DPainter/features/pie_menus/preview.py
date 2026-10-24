"""Embedded radial editor sharing the runtime wheel's rendering and hit testing."""
from PySide6 import QtCore, QtWidgets
from .wheel import Wheel


class Preview(QtWidgets.QWidget):
    SIZE = Wheel.SIZE
    INNER = Wheel.INNER
    OUTER = Wheel.OUTER
    _label_box = Wheel._label_box
    _fit_labels = Wheel._fit_labels
    _draw_label = Wheel._draw_label
    _hit = Wheel._hit
    paintEvent = Wheel.paintEvent

    def __init__(self, select, reorder, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.title = ""
        self.actions = []
        self.hovered = None
        self._pressed = None
        self.select = select
        self.reorder = reorder
        self.setToolTip("Click a slice to edit it. Drag onto another slice to swap only those two positions.")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._pressed = self._hit(event.position())
            if self._pressed is not None:
                self.select(self._pressed)

    def mouseReleaseEvent(self, event):
        target = self._hit(event.position())
        if self._pressed is not None and target is not None and target != self._pressed:
            self.reorder(self._pressed, target)
        self._pressed = None