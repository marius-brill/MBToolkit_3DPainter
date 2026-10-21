"""Qt-native mouse-driven radial menu. Slices scale with item count."""
import math
from PySide6 import QtCore, QtGui, QtWidgets
from ...core.models import normalized_angle_index
from ...ui.common import error


class Wheel(QtWidgets.QWidget):
    SIZE = 494
    OUTER = 228
    INNER = 119

    def _label_box(self, angle, count):
        """Return a padded label rectangle fully inside its annular slice."""
        radius = (self.OUTER + self.INNER)/2
        x, y = math.cos(angle)*radius, math.sin(angle)*radius
        clearance = (self.OUTER-self.INNER)/2 - 8
        half_width = min(82, clearance/max(abs(math.cos(angle)), .3))
        half_height = min(42, clearance/max(abs(math.sin(angle)), .3))
        while True:
            corners = [(x+dx*half_width, y+dy*half_height)
                       for dx in (-1, 1) for dy in (-1, 1)]
            nearest = math.hypot(max(abs(x)-half_width, 0), max(abs(y)-half_height, 0))
            inside = nearest >= self.INNER+8
            for cx, cy in corners:
                delta = math.atan2(math.sin(math.atan2(cy, cx)-angle),
                                   math.cos(math.atan2(cy, cx)-angle))
                inside = inside and math.hypot(cx, cy) <= self.OUTER-8
                if count > 1:
                    inside = inside and abs(delta) <= math.pi/count - .035
            if inside:
                return x-half_width, y-half_height, half_width*2, half_height*2
            half_width *= .96
            half_height *= .96

    def _fit_labels(self, labels):
        """Choose one font and scale that fits every feature and the title."""
        font = QtGui.QFont("Segoe UI")
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        font.setStyleName("Semibold")
        flags = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.TextFlag.TextWordWrap
        for size in range(16, 0, -1):
            font.setPixelSize(size)
            metrics = QtGui.QFontMetricsF(font)
            scale = 1
            for rect, text in labels:
                measured = metrics.boundingRect(
                    QtCore.QRectF(0, 0, rect.width(), 1000000), flags, text)
                scale = min(scale, rect.width()/max(measured.width(), 1),
                            rect.height()/max(measured.height(), 1))
            if scale >= 1:
                break
        return font, scale

    def _draw_label(self, painter, rect, text, font, scale):
        flags = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.TextFlag.TextWordWrap
        painter.save()
        painter.setFont(font)
        painter.translate(rect.center())
        painter.scale(scale, scale)
        painter.drawText(QtCore.QRectF(-rect.width()/(2*scale), -rect.height()/(2*scale),
                                      rect.width()/scale, rect.height()/scale), flags, text)
        painter.restore()

    def __init__(self, title, actions, execute, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.Popup | QtCore.Qt.WindowType.FramelessWindowHint |
                         QtCore.Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.title = title
        self.actions = actions
        self.execute = execute
        self.hovered = None
        self._activated = False
        self._release_keys = set()

    def set_hold_shortcut(self, shortcut):
        sequence = QtGui.QKeySequence(shortcut)
        self._release_keys.clear()
        if sequence.isEmpty():
            return
        combination = sequence[sequence.count()-1]
        self._release_keys.add(combination.key())
        modifiers = combination.keyboardModifiers()
        for modifier, key in ((QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_Control),
                              (QtCore.Qt.KeyboardModifier.ShiftModifier, QtCore.Qt.Key.Key_Shift),
                              (QtCore.Qt.KeyboardModifier.AltModifier, QtCore.Qt.Key.Key_Alt),
                              (QtCore.Qt.KeyboardModifier.MetaModifier, QtCore.Qt.Key.Key_Meta)):
            if modifiers & modifier:
                self._release_keys.add(key)

    def open_at_cursor(self):
        pos = QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(pos) or QtGui.QGuiApplication.primaryScreen()
        bounds = screen.availableGeometry()
        x = max(bounds.left(), min(pos.x() - self.width() // 2, bounds.right() - self.width() + 1))
        y = max(bounds.top(), min(pos.y() - self.height() // 2, bounds.bottom() - self.height() + 1))
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def _hit(self, point):
        x = point.x() - self.width()/2
        y = point.y() - self.height()/2
        r = math.hypot(x, y)
        if r < self.INNER or r > self.OUTER or not self.actions:
            return None
        return normalized_angle_index(x, y, len(self.actions))

    def mouseMoveEvent(self, event):
        self.hovered = self._hit(event.position())
        self.update()

    def leaveEvent(self, event):
        self.hovered = None
        self.update()

    def _activate(self, index):
        if self._activated or not self.isVisible():
            return
        self._activated = True
        self.close()
        command = self.actions[index][0]
        # Dispatch after the popup releases focus, and catch deferred errors too.
        def dispatch():
            try:
                self.execute(command)
            except Exception as exc:
                error(None, "Pie menu action", exc)
        QtCore.QTimer.singleShot(0, dispatch)

    def mouseReleaseEvent(self, event):
        if self._release_keys:
            event.accept()
            return
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            index = self._hit(event.position())
            if index is not None:
                self._activate(index)
            else:
                self.close()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
        elif self._release_keys:
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not self._release_keys:
            super().keyReleaseEvent(event)
            return
        event.accept()
        if event.isAutoRepeat() or event.key() not in self._release_keys or not self.isVisible():
            return
        # Recheck the actual cursor so leaving the ring never commits a stale hover.
        self.hovered = self._hit(self.mapFromGlobal(QtGui.QCursor.pos()))
        if self.hovered is None:
            self.close()
        else:
            self._activate(self.hovered)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        center = QtCore.QPointF(self.width()/2, self.height()/2)
        rect = QtCore.QRectF(center.x()-self.OUTER, center.y()-self.OUTER,
                             self.OUTER*2, self.OUTER*2)
        n = len(self.actions)
        if not n:
            painter.end()
            return
        size = 360/n
        labels = []
        for i, (_id, label) in enumerate(self.actions):
            angle = math.radians(-90 + (i+.5)*size)
            x, y, width, height = self._label_box(angle, n)
            labels.append((QtCore.QRectF(center.x()+x, center.y()+y, width, height), label))
        title_rect = QtCore.QRectF(center.x()-self.INNER+16, center.y()-48,
                                  (self.INNER-16)*2, 96)
        font, scale = self._fit_labels(labels + [(title_rect, self.title)])
        for i, (_id, label) in enumerate(self.actions):
            path = QtGui.QPainterPath()
            path.moveTo(center)
            path.arcTo(rect, 90 - i*size, -size)  # QPainter angles run counter-clockwise
            path.closeSubpath()
            selected = i == self.hovered
            painter.setBrush(QtGui.QColor("#1677d2" if selected else "#273746"))
            painter.setPen(QtGui.QPen(QtGui.QColor("#a4b3c1"), 1.2))
            painter.drawPath(path)
            painter.setPen(QtGui.QColor("#ffffff"))
            self._draw_label(painter, labels[i][0], label, font, scale)
        painter.setBrush(QtGui.QColor("#16222e"))
        painter.setPen(QtGui.QPen(QtGui.QColor("#a4b3c1"), 1.5))
        painter.drawEllipse(center, self.INNER, self.INNER)
        painter.setPen(QtGui.QColor("white"))
        self._draw_label(painter, title_rect, self.title, font, scale)
        painter.end()
