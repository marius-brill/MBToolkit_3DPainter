"""Bounded two-lane graphics scene with actual per-slot selectable edges."""
from PySide6 import QtCore, QtGui, QtWidgets
from ..index import layout
from ..models import Status


class Card(QtWidgets.QGraphicsRectItem):
    def __init__(self, graph, node, anchor=False):
        super().__init__(0, 0, 260, 72)
        self.graph, self.key = graph, node.key
        self.setBrush(QtGui.QColor("#252D36"))
        self.setPen(QtGui.QPen(QtGui.QColor("#2FAAE8" if anchor else "#3A4652"), 1.5))
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsFocusable)
        text = QtWidgets.QGraphicsSimpleTextItem(node.name[:34], self)
        text.setBrush(QtGui.QColor("#E9EEF3"))
        text.setPos(10, 8)
        detail = QtWidgets.QGraphicsSimpleTextItem((node.domain if anchor else node.kind) + " · " + "/".join(node.path[-3:-1])[:28], self)
        detail.setBrush(QtGui.QColor("#9EAFBD"))
        detail.setPos(10, 36)
        self.setToolTip(" / ".join(node.path))
        self.setAcceptHoverEvents(True)

    def mousePressEvent(self, event):
        self.graph.controller.select(self.key)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.graph.navigate_requested.emit(self.key)
        event.accept()


class Edge(QtWidgets.QGraphicsPathItem):
    def __init__(self, graph, ref, start, end):
        path = QtGui.QPainterPath(start)
        path.cubicTo(start + QtCore.QPointF(80, 0), end - QtCore.QPointF(80, 0), end)
        super().__init__(path)
        self.graph, self.ref = graph, ref
        self.setZValue(-1)
        color = "#E5675F" if ref.status is Status.BROKEN else "#2FAAE8" if ref.status is Status.VALID else "#F4A340"
        self.base_pen = QtGui.QPen(QtGui.QColor(color), 1.6)
        if ref.status is not Status.VALID:
            self.base_pen.setStyle(QtCore.Qt.PenStyle.DashLine)
        self.setPen(self.base_pen)
        self.setAcceptHoverEvents(True)
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)
        self.setToolTip(f"Input: {ref.slot.slot_id} / {' / '.join(ref.slot.source_path)}\n"
                        f"Channel: {ref.slot.channel or 'mono/material'} ← {ref.source_channel}\n"
                        f"Mapping: {ref.channel_mapping}\n{ref.status.value}: {ref.reason}")

    def shape(self):
        stroker = QtGui.QPainterPathStroker()
        stroker.setWidth(12)
        return stroker.createStroke(self.path())

    def hoverEnterEvent(self, event):
        pen = QtGui.QPen(self.base_pen)
        pen.setWidthF(3)
        self.setPen(pen)

    def hoverLeaveEvent(self, event):
        self.setPen(self.base_pen)

    def mousePressEvent(self, event):
        self.graph.controller.select(self.ref.slot)
        super().mousePressEvent(event)


class GraphView(QtWidgets.QGraphicsView):
    navigate_requested = QtCore.Signal(object)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.mode = "Focus"
        self.focus_anchor = None
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setBackgroundBrush(QtGui.QColor("#161B21"))
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.setDragMode(self.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumSize(240, 180)
        self.cards = {}
        self.edges = {}
        controller.changed.connect(self.rebuild)
        controller.selection_changed.connect(self.highlight)
        self.setToolTip("Wheel: zoom · drag background: pan · double-click: navigate · F: center selection")

    def rebuild(self):
        self.scene().clear()
        self.cards, self.edges = {}, {}
        index = self.controller.index
        selected = self.controller.selection
        if selected in index.anchors:
            self.focus_anchor = selected
        if self.focus_anchor not in index.anchors:
            self.focus_anchor = next(iter(index.anchors), None)
        focus = self.focus_anchor if self.mode == "Focus" else None
        positions = layout(index, focus, limit=200)
        if self.mode == "Issues":
            affected = {i.node for i in index.issues if i.node}
            affected |= {r.anchor_key for r in index.references.values() if r.slot.consumer in affected}
            positions = {k: p for k, p in positions.items() if k in affected}
        for key, pos in positions.items():
            card = Card(self, index.nodes[key], key in index.anchors)
            self.scene().addItem(card)
            card.setPos(*pos)
            self.cards[key] = card
        slots_by_consumer = {}
        for slot, ref in sorted(index.references.items()):
            if ref.anchor_key not in self.cards or slot.consumer not in self.cards:
                continue
            count = slots_by_consumer.get(slot.consumer, 0)
            slots_by_consumer[slot.consumer] = count + 1
            start = self.cards[ref.anchor_key].pos() + QtCore.QPointF(260, 35)
            end = self.cards[slot.consumer].pos() + QtCore.QPointF(0, 16 + (count % 8) * 6)
            edge = Edge(self, ref, start, end)
            self.scene().addItem(edge)
            self.edges[slot] = edge
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-40, -40, 40, 40))
        self.highlight()

    def highlight(self):
        selected = self.controller.selection
        if self.mode == "Focus" and selected in self.controller.index.anchors and selected != self.focus_anchor:
            self.rebuild()
            return
        for key, card in self.cards.items():
            card.setSelected(key == selected)
            card.setPen(QtGui.QPen(QtGui.QColor("#249ADB" if key == selected else "#3A4652"),
                                  3 if key == selected else 1.5))
        for slot, edge in self.edges.items():
            edge.setSelected(slot == selected)
            edge.setOpacity(1 if selected not in self.controller.index.anchors or edge.ref.anchor_key == selected else .22)

    def zoom(self, factor):
        target = max(.25, min(2.5, self.transform().m11() * factor))
        self.scale(target / self.transform().m11(), target / self.transform().m11())

    def wheelEvent(self, event):
        self.zoom(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
        event.accept()

    def fit(self):
        if self.scene().items():
            self.fitInView(self.scene().sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            self.zoom(1)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_F:
            key = self.controller.selection
            if key in self.cards:
                self.centerOn(self.cards[key])
        else:
            super().keyPressEvent(event)


class GraphWorkspace(QtWidgets.QWidget):
    def __init__(self, controller, navigate, parent=None):
        super().__init__(parent)
        outer = QtWidgets.QVBoxLayout(self)
        toolbar = QtWidgets.QHBoxLayout()
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(["Focus", "Overview", "Issues"])
        toolbar.addWidget(self.mode)
        self.view = GraphView(controller)
        self.view.navigate_requested.connect(navigate)
        self.mode.currentTextChanged.connect(self._mode)
        for title, callback in (("Fit", self.view.fit), ("100%", self.view.resetTransform),
                                ("+", lambda: self.view.zoom(1.2)), ("−", lambda: self.view.zoom(1 / 1.2)),
                                ("Reset", self.view.rebuild)):
            button = QtWidgets.QPushButton(title)
            button.setToolTip(title + " graph")
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        outer.addLayout(toolbar)
        self.banner = QtWidgets.QLabel("Layout shows references, not evaluation order. Overview capped at 200 nodes per lane.")
        self.banner.setWordWrap(True)
        outer.addWidget(self.banner)
        outer.addWidget(self.view)

    def _mode(self, mode):
        self.view.mode = mode
        self.view.rebuild()