"""Node-first canvas with ordered wires, nested scopes and visual-only frames."""
from PySide6 import QtCore, QtGui, QtWidgets
from .icons import draw as draw_icon
from .model import connection_reason


COLORS = {"layers": "#2FAAE8", "content": "#B394EB", "mask": "#BBC4CC"}


class Card(QtWidgets.QGraphicsRectItem):
    def __init__(self, view, uid, title, detail, position, domain="layers", movable=True):
        super().__init__(0, 0, 240, 100)
        self.view, self.uid = view, uid
        self.title, self.detail, self.domain = title, detail, domain
        self.node = view.panel.snapshot.nodes.get(uid)
        self.enabled = self.node is None or self.node.visible
        self.boundary_side = ("input" if uid == "@input" or uid.startswith("@input:") else
                              "output" if uid == "@output" or uid.startswith("@output:") else "")
        self.boundary = bool(self.boundary_side)
        self.mask_master = uid.startswith("@mask:") or (self.boundary_side == "input" and domain == "mask")
        self.hover_region = ""
        self.pressed_region = ""
        self.eye_rect = QtCore.QRectF(8, 7, 22, 22)
        self.arrow_rect = QtCore.QRectF(8, 76, 22, 20)
        self.mask_rect = QtCore.QRectF(204, 1, 35, 98) if self.node and self.node.mask else QtCore.QRectF()
        self.expandable = bool(self.node and self.node.layer and (self.node.group or self.node.mask or
                               view.panel.snapshot.chains.get((uid, "content"))))
        self.setAcceptHoverEvents(True)
        self.setBrush(QtGui.QColor("#195681" if self.boundary else "#252D36" if self.enabled else "#20252B"))
        self.setPen(QtGui.QPen(QtGui.QColor(COLORS[domain] if self.enabled else "#444B53"), 1.5))
        flags = self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemSendsGeometryChanges
        if movable:
            flags |= self.GraphicsItemFlag.ItemIsMovable
        self.setFlags(flags)
        self.setPos(*position)
        self.setToolTip(title + "\n" + detail)
        self.ports = {}
        for side, x in (("input", 0), ("output", 240)):
            if side == self.boundary_side:
                continue
            port = QtWidgets.QGraphicsEllipseItem(x - 5, 72, 10, 10, self)
            self.ports[side] = port
            port.setBrush(QtGui.QColor(COLORS[domain] if self.enabled else "#59616A"))
            port.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
            port.setToolTip("Drag to reconnect. Drop on empty space to bypass; Escape cancels.")

    def region(self, point):
        if self.node and self.eye_rect.contains(point):
            return "eye"
        if self.expandable and self.arrow_rect.contains(point):
            return "arrow"
        if self.mask_rect.contains(point):
            return "mask"
        return "body"

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.body_color())
        foreground = QtGui.QColor("#E9EEF3" if self.enabled else "#79818A")
        muted = QtGui.QColor("#9EAFBD" if self.enabled else "#68717A")
        if not self.mask_rect.isEmpty():
            painter.fillRect(self.mask_rect, QtGui.QColor("#326581" if self.hover_region == "mask" else
                                                        "#1C242C" if self.enabled else "#1B2025"))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(foreground)
            painter.drawRoundedRect(QtCore.QRectF(213, 40, 18, 22), 2, 2)
            painter.setBrush(QtGui.QColor("#11171D" if self.node.mask == "Black" else "#B7C6D1"))
            painter.drawEllipse(QtCore.QRectF(217, 46, 10, 10))
        painter.setPen(foreground)
        title_x = 36 if self.node else 12
        body_right = 202 if self.node and self.node.mask else 238
        metrics = painter.fontMetrics()
        painter.drawText(QtCore.QRectF(title_x, 7, body_right - title_x - 8, 25),
                         metrics.elidedText(self.title, QtCore.Qt.TextElideMode.ElideRight, body_right - title_x - 8))
        painter.setPen(muted)
        detail_width = body_right - (48 if self.node else 16)
        painter.drawText(QtCore.QRectF(12, 38, detail_width, 30),
                         metrics.elidedText(self.detail, QtCore.Qt.TextElideMode.ElideRight, detail_width))
        if self.node:
            painter.setPen(QtGui.QPen(foreground, 1.5))
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            eye = QtGui.QPainterPath(QtCore.QPointF(10, 18))
            eye.cubicTo(15, 10, 23, 10, 28, 18)
            eye.cubicTo(23, 26, 15, 26, 10, 18)
            painter.drawPath(eye)
            painter.setBrush(foreground)
            painter.drawEllipse(QtCore.QPointF(19, 18), 2.5, 2.5)
            if not self.enabled:
                painter.drawLine(QtCore.QPointF(10, 27), QtCore.QPointF(28, 9))
            draw_icon(painter, self.node.kind, body_right - 29, 39, foreground)
        elif self.mask_master:
            draw_icon(painter, "Mask", body_right - 29, 39, foreground)
        if self.boundary:
            painter.setPen(foreground)
            painter.drawText(QtCore.QRectF(12, 76, 180, 20), self.boundary_side.upper())
        if self.expandable:
            expanded = self.uid in self.view.panel.layout.expanded
            points = [(12, 82), (24, 82), (18, 90)] if expanded else [(14, 79), (22, 85), (14, 91)]
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(foreground)
            painter.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(*point) for point in points]))
        pen = QtGui.QPen(self.pen())
        if self.isSelected():
            pen.setWidthF(2.5)
        elif self.hover_region:
            pen.setColor(pen.color().lighter(115))
            pen.setWidthF(2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect())

    def body_color(self):
        color = self.brush().color()
        return color.lighter(115) if self.hover_region else color

    def hoverEnterEvent(self, event):
        self.hover_region = self.region(event.pos())
        self.update()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        self.hover_region = self.region(event.pos())
        hints = {"eye": "Enable / bypass node in Painter", "arrow": "Expand / collapse subgraph frame",
                 "mask": "Alt + click to preview mask; double-click to enter mask graph", "body": self.title + "\n" + self.detail}
        self.setToolTip(hints[self.hover_region])
        self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.hover_region = ""
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        region = self.region(event.pos())
        mask_uid = self.uid[6:] if self.uid.startswith("@mask:") else (
             self.view.boundary_scopes.get(self.uid, self.view.scope)[0] if self.mask_master else
             self.uid if region == "mask" else None)
        if (event.button() == QtCore.Qt.MouseButton.LeftButton and mask_uid and
                event.modifiers() & QtCore.Qt.KeyboardModifier.AltModifier):
            self.pressed_region = "preview"
            self.view.panel.preview_mask(mask_uid)
            event.accept()
            return
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.node and region in ("body", "mask"):
            self.view.panel.select_native(self.uid, "mask" if region == "mask" else self.node.scope[1])
            if region == "mask":
                if not event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
                    self.view.scene().clearSelection()
                self.setSelected(True)
        if event.button() == QtCore.Qt.MouseButton.LeftButton and region in ("eye", "arrow", "mask"):
            self.pressed_region = region
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.pressed_region:
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        region, self.pressed_region = self.pressed_region, ""
        if region:
            if event.button() == QtCore.Qt.MouseButton.LeftButton and self.region(event.pos()) == region:
                if region == "eye":
                    self.view.panel.toggle_enabled(self.uid)
                elif region == "arrow":
                    # Defer scene rebuild until Qt has finished dispatching this event.
                    panel, uid = self.view.panel, self.uid
                    QtCore.QTimer.singleShot(0, lambda: None if panel.disposed else panel.toggle(uid))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == self.GraphicsItemChange.ItemPositionHasChanged and self.uid in self.view.cards:
            old = self.view.panel.layout.positions.get((self.view.scope, self.uid), (self.x(), self.y()))
            delta = value - QtCore.QPointF(*old)
            self.view.panel.layout.positions[(self.view.scope, self.uid)] = (value.x(), value.y())
            for child in self.view.branch_children.get(self.uid, []):
                self.view.cards[child].moveBy(delta.x(), delta.y())
            self.view.update_edges()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        region = self.region(event.pos())
        if region in ("eye", "arrow"):
            event.accept()
            return
        node = self.view.panel.snapshot.nodes.get(self.uid)
        if node:
            if region == "mask":
                self.view.panel.open_scope((node.id, "mask"))
            elif node.group:
                self.view.panel.open_scope((node.id, "layers"))
            elif node.layer:
                self.view.panel.open_scope((node.id, "content"))
            else:
                self.view.panel.navigate(node.id, self.view.scope[1])
        elif self.uid.startswith("@frame:"):
            self.view.toggle_frame(self.uid[7:])
        elif self.mask_master:
            scope = self.view.boundary_scopes.get(self.uid, self.view.scope)
            self.view.panel.navigate(scope[0], "mask")
        event.accept()


class FrameItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, view, frame, bounds):
        super().__init__(0, 0, bounds.width(), bounds.height())
        self.view, self.frame = view, frame
        self.setPos(bounds.topLeft())
        self.setZValue(-2)
        self.setBrush(QtGui.QColor(61, 76, 102, 65))
        self.setPen(QtGui.QPen(QtGui.QColor("#627696"), 1.5))
        self.setFlags(self.GraphicsItemFlag.ItemIsMovable | self.GraphicsItemFlag.ItemIsSelectable |
                      self.GraphicsItemFlag.ItemSendsGeometryChanges)
        title = QtWidgets.QGraphicsSimpleTextItem(frame.name + " · double-click to collapse", self)
        title.setBrush(QtGui.QColor("#B8C9E0"))
        title.setPos(12, 8)
        self.previous = self.pos()

    def itemChange(self, change, value):
        if change == self.GraphicsItemChange.ItemPositionHasChanged and hasattr(self, "previous"):
            delta = value - self.previous
            self.previous = value
            for uid in self.frame.members:
                card = self.view.cards.get(uid)
                if card:
                    card.moveBy(delta.x(), delta.y())
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        self.view.toggle_frame(self.frame.id)
        event.accept()


class BranchFrameItem(QtWidgets.QGraphicsRectItem):
    """Auto-sized backdrop for a disclosed scope; it never edits the host stack."""
    def __init__(self, view, owner, domain, members):
        super().__init__()
        self.view, self.owner, self.domain, self.members = view, owner, domain, members
        self.setZValue(-3)
        self.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self.setBrush(QtGui.QColor("#252D36"))
        self.setPen(QtGui.QPen(QtGui.QColor(COLORS[view.cards[owner].domain]), 1))
        self.label = QtWidgets.QGraphicsSimpleTextItem(
            view.panel.snapshot.title((owner, domain)).rsplit(" / ", 1)[0] + " / " + domain.upper(), self)
        self.label.setBrush(QtGui.QColor("#B8C9E0"))
        self.label.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)

    def update_bounds(self):
        bounds = QtCore.QRectF()
        pending = list(self.members)
        visited = set()
        while pending:
            uid = pending.pop()
            if uid in visited:
                continue
            visited.add(uid)
            bounds = bounds.united(self.view.cards[uid].sceneBoundingRect())
            pending.extend(self.view.branch_children.get(uid, []))
            for scope, frame in self.view.branch_frames.items():
                if scope[0] == uid:
                    bounds = bounds.united(frame.rect())
        origin = self.view.cards[self.owner].pos()
        top = self.view.cards[self.members[0]].y() - 40
        self.setRect(QtCore.QRectF(origin.x(), top,
                                  max(290, bounds.right() + 25 - origin.x()),
                                  max(220, bounds.bottom() + 25 - top)))
        self.label.setPos(self.rect().topLeft() + QtCore.QPointF(12, 8))

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setPen(QtGui.QColor("#B8C9E0"))
        kind = "Mask" if self.domain == "mask" else self.view.panel.snapshot.nodes[self.owner].kind
        x = self.rect().left() + 22 + self.label.boundingRect().width()
        draw_icon(painter, kind, x, self.rect().top() + 5, QtGui.QColor("#B8C9E0"))


class View(QtWidgets.QGraphicsView):
    def __init__(self, panel, scope):
        super().__init__()
        self.panel, self.scope = panel, scope
        self.cards, self.links, self.wires = {}, [], []
        self.branch_children = {}
        self.branch_frames = {}
        self.boundary_scopes = {}
        self.building = False
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.scene().selectionChanged.connect(self.selection_changed)
        self.setBackgroundBrush(QtGui.QColor("#333333"))
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.setDragMode(self.DragMode.RubberBandDrag)
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumSize(300, 250)
        self.pan = None
        self.connection_drag = None
        self.drag_wire = None
        self.drop_port = None
        self.layout_drag = False

    def end_layout_drag(self):
        """Release interaction protection without changing the user's placement."""
        if not self.layout_drag:
            return
        self.layout_drag = False
        if self.panel.pending_refresh:
            self.panel.request_refresh()

    def cancel_layout_drag(self):
        self.end_layout_drag()
        grabber = self.scene().mouseGrabberItem()
        if grabber is not None:
            grabber.ungrabMouse()

    def event(self, event):
        if event.type() in (QtCore.QEvent.Type.WindowDeactivate, QtCore.QEvent.Type.Hide):
            if getattr(self, "layout_drag", False):
                self.cancel_layout_drag()
        return super().event(event)

    def viewportEvent(self, event):
        if event.type() == QtCore.QEvent.Type.UngrabMouse and getattr(self, "layout_drag", False):
            self.end_layout_drag()
        return super().viewportEvent(event)

    def selected_ids(self):
        return [item.uid for item in self.scene().selectedItems()
                if isinstance(item, Card) and item.uid in self.panel.snapshot.nodes]

    def selection_changed(self):
        if not self.building and self.panel.view() is self:
            ids = self.selected_ids()
            self.panel.inspect(ids[0] if len(ids) == 1 else None)

    def rebuild(self):
        if self.layout_drag:
            self.panel.pending_refresh = True
            return
        self.cancel_connection()
        selected = self.selected_ids()
        self.building = True
        self.cards, self.links, self.wires = {}, [], []
        self.branch_children = {}
        self.branch_frames = {}
        self.boundary_scopes = {}
        self.scene().clear()
        snapshot, layout = self.panel.snapshot, self.panel.layout
        if snapshot.context is None:
            self.building = False
            return
        members = snapshot.members(self.scope)
        represented = {}
        frames = [f for f in layout.frames.values() if f.scope == self.scope]
        for frame in frames:
            if any(snapshot.nodes[key].disconnected for key in frame.members if key in snapshot.nodes):
                frame.collapsed = False
            if frame.collapsed:
                for uid in frame.members:
                    represented[uid] = "@frame:" + frame.id
        stream = []
        for uid in members:
            proxy = represented.get(uid, uid)
            # Noncontiguous members keep separate boundary wires, not invented order.
            if not stream or stream[-1] != proxy:
                stream.append(proxy)
        owner = snapshot.nodes.get(self.scope[0])
        input_title = owner.mask + " Background" if owner and self.scope[1] == "mask" else "Material Input"
        self.add_card("@input", input_title, self.scope[1].title() + " stream", (-310, 0))
        for index, uid in enumerate(dict.fromkeys(stream)):
            position = layout.positions.get((self.scope, uid), (index * 340, 0))
            if uid.startswith("@frame:"):
                frame = layout.frames[uid[7:]]
                self.add_card(uid, frame.name, f"Frame · {len(frame.members)} nodes · double-click to expand", position)
                continue
            node = snapshot.nodes[uid]
            content_count = len(snapshot.chains.get((uid, "content"), []))
            detail = node.kind + (" · disconnected" if node.disconnected else " · bypassed" if not node.visible else "")
            if node.layer:
                detail = f"Content: {content_count} fx · Mask: {node.mask or 'none'}"
                if node.disconnected:
                    detail += " · disconnected"
            self.add_card(uid, node.name, detail, position)
            if uid in layout.expanded:
                self.expand_under(uid)
        output = (len(dict.fromkeys(stream)) * 340, 0)
        self.add_card("@output", "Mask Output" if self.scope[1] == "mask" else "Material Output",
                      "Painter evaluates this ordered stream", output)
        chain = ["@input", *stream, "@output"]
        chain = [key for key in chain if not (key in snapshot.nodes and snapshot.nodes[key].disconnected)]
        self.links.extend((a, b, self.scope[1]) for a, b in zip(chain, chain[1:]) if a != b)
        for frame in frames:
            if not frame.collapsed:
                bounds = QtCore.QRectF()
                for uid in frame.members:
                    if uid in self.cards:
                        bounds = bounds.united(self.cards[uid].sceneBoundingRect())
                self.scene().addItem(FrameItem(self, frame, bounds.adjusted(-25, -45, 25, 25)))
        self.update_edges()
        for uid in selected:
            if uid in self.cards:
                self.cards[uid].setSelected(True)
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-500, -500, 500, 500))
        self.building = False

    def expand_under(self, owner):
        node = self.panel.snapshot.nodes[owner]
        y = self.cards[owner].y() + 140
        for domain in ("layers", "content", "mask"):
            if domain == "layers" and not node.group or domain == "mask" and not node.mask:
                continue
            members = self.panel.snapshot.members((owner, domain))
            if members or domain == "mask" or (domain == "layers" and node.group):
                y = self.branch(owner, members, y, domain, node.mask)
        return y

    def branch(self, owner, members, y, domain, background=""):
        origin = self.cards[owner].pos()
        children = self.branch_children.setdefault(owner, [])
        scope = (owner, domain)
        input_uid, output_uid = (f"@{side}:{domain}:{owner}" for side in ("input", "output"))
        title = background + " Background" if domain == "mask" else domain.title() + " Input"
        self.add_card(input_uid, title, "Subgraph input", (origin.x() + 30, y), domain)
        self.boundary_scopes[input_uid] = scope
        row = [input_uid]
        bottom = y + 100
        previous = input_uid
        for index, uid in enumerate(members, 1):
            node = self.panel.snapshot.nodes[uid]
            position = (origin.x() + 30 + index * 340, y)
            if uid not in self.cards:
                self.add_card(uid, node.name, node.kind, position, domain)
            row.append(uid)
            if not node.disconnected:
                self.links.append((previous, uid, domain))
                previous = uid
            if uid in self.panel.layout.expanded and node.layer:
                bottom = max(bottom, self.expand_under(uid))
        self.add_card(output_uid, domain.title() + " Output", "Subgraph output",
                      (origin.x() + 30 + (len(members) + 1) * 340, y), domain)
        self.boundary_scopes[output_uid] = scope
        row.append(output_uid)
        children.extend(row)
        self.links.append((previous, output_uid, domain))
        frame = BranchFrameItem(self, owner, domain, row)
        self.branch_frames[scope] = frame
        self.scene().addItem(frame)
        frame.update_bounds()
        return max(bottom, frame.rect().bottom()) + 40

    def add_card(self, uid, title, detail, position, domain=None):
        # Generated layout is only a fallback, including inline and boundary cards.
        position = self.panel.layout.positions.get((self.scope, uid), position)
        card = Card(self, uid, title, detail, position, domain or self.scope[1])
        self.scene().addItem(card)
        self.cards[uid] = card
        self.panel.layout.positions[(self.scope, uid)] = position
        return card

    def update_edges(self):
        # Nested frames are inserted before their ancestors. Normalize each owner's
        # sections together so Content and Mask share one aligned dropdown width.
        for frame in self.branch_frames.values():
            frame.update_bounds()
            siblings = [item for item in self.branch_frames.values() if item.owner == frame.owner]
            width = max(item.rect().width() for item in siblings)
            for sibling in siblings:
                rect = sibling.rect()
                rect.setWidth(width)
                sibling.setRect(rect)
        for wire in self.wires:
            self.scene().removeItem(wire)
        self.wires = []
        for a, b, domain in self.links:
            if any(key in self.panel.snapshot.nodes and self.panel.snapshot.nodes[key].disconnected
                   for key in (a, b)):
                continue
            start = self.cards[a].pos() + QtCore.QPointF(240, 77)
            end = self.cards[b].pos() + QtCore.QPointF(0, 77)
            path = QtGui.QPainterPath(start)
            offset = max(80, abs(end.x() - start.x()) * .5)
            path.cubicTo(start + QtCore.QPointF(offset, 0), end - QtCore.QPointF(offset, 0), end)
            wire = self.scene().addPath(path, QtGui.QPen(QtGui.QColor(COLORS[domain]), 2))
            wire.setZValue(-1)
            wire.setData(0, (a, b, domain))
            wire.setToolTip("Drag this connection or its endpoints to disconnect / reconnect")
            self.wires.append(wire)

    def port_at(self, position):
        point = self.mapToScene(position)
        radius = 12 / self.transform().m11()
        for card in self.cards.values():
            for side, port in card.ports.items():
                if QtCore.QLineF(point, port.mapToScene(port.rect().center())).length() <= radius:
                    return card.uid, side
        return None

    def begin_connection(self, uid, side, point):
        node = self.panel.snapshot.nodes.get(uid)
        if node is None:
            return False
        self.connection_drag = (uid, side, node.scope, self.panel.snapshot.context)
        self.drag_wire = self.scene().addPath(QtGui.QPainterPath(), QtGui.QPen(QtGui.QColor("#EAC76B"), 3))
        self.drag_wire.setZValue(10)
        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
        self.move_connection(point)
        return True

    def move_connection(self, point):
        uid, side, scope, context = self.connection_drag
        start = self.cards[uid].mapToScene(QtCore.QPointF(0 if side == "input" else 240, 77))
        end = self.mapToScene(point)
        path = QtGui.QPainterPath(start)
        offset = max(80, abs(end.x() - start.x()) * .5) * (-1 if side == "input" else 1)
        path.cubicTo(start + QtCore.QPointF(offset, 0), end - QtCore.QPointF(offset, 0), end)
        self.drag_wire.setPath(path)
        self.clear_drop_port()
        target = self.port_at(point)
        if target:
            reason = self.drop_reason(target)
            port = self.cards[target[0]].ports[target[1]]
            self.drop_port = port
            port.setBrush(QtGui.QColor("#E46D72" if reason else "#63D99C"))
            self.setToolTip(reason or "Release to connect / reorder native layers (experimental)")
        else:
            self.setToolTip("Release on empty space to bypass this node; Escape cancels")

    def drop_reason(self, target):
        uid, side, scope, context = self.connection_drag
        if target[1] == side:
            return "Connect an output to an input."
        target_uid = target[0]
        if target_uid in self.boundary_scopes:
            if self.boundary_scopes[target_uid] != scope:
                return "Connect ports within the same subgraph."
            target_uid = "@" + self.cards[target_uid].boundary_side
        elif target_uid in ("@input", "@output") and scope != self.scope:
            return "Connect ports within the same subgraph."
        reason = connection_reason(self.panel.snapshot, uid, target_uid, side, context, scope)
        if reason.startswith("This drop requires reordering"):
            from .ordering import connection_move, ui_move_reason
            from .native_drag import available
            try:
                sp = getattr(self.panel.adapter, "sp", None)
                from . import native_effect_order
                if sp is not None and hasattr(sp, "application") and scope[1] in ("content", "mask"):
                    if native_effect_order.available(sp):
                        native_effect_order.command(self.panel.snapshot,
                                                   connection_move(self.panel.snapshot, uid, target_uid, side, context, scope))
                        return ""
                if sp is None or not hasattr(sp, "application") or not available(sp):
                    return reason
                return ui_move_reason(self.panel.snapshot,
                                      connection_move(self.panel.snapshot, uid, target_uid, side, context, scope))
            except ValueError as exc:
                return str(exc)
        return reason

    def clear_drop_port(self):
        if self.drop_port is not None:
            card = self.drop_port.parentItem()
            self.drop_port.setBrush(QtGui.QColor(COLORS[card.domain] if card.enabled else "#59616A"))
            self.drop_port = None

    def cancel_connection(self):
        self.clear_drop_port()
        if self.drag_wire is not None:
            self.scene().removeItem(self.drag_wire)
        self.drag_wire = None
        self.connection_drag = None
        self.unsetCursor()
        self.setToolTip("")

    def finish_connection(self, point):
        uid, side, scope, context = self.connection_drag
        target = self.port_at(point)
        reason = self.drop_reason(target) if target else ""
        # Dropping on a card body or another wire is not an empty-space disconnect.
        blocked = target is None and any(item is not self.drag_wire and
                                         not isinstance(item, (FrameItem, BranchFrameItem)) for item in self.items(point))
        self.cancel_connection()
        if reason or blocked:
            self.panel.status.setText(reason or "Drop on a compatible port or empty canvas.")
            if self.panel.pending_refresh:
                self.panel.request_refresh()
            return
        # Rebuilding the scene inside an item mouse dispatch can invalidate Qt pointers.
        panel = self.panel
        target_uid = target[0] if target else None
        if target_uid in self.boundary_scopes:
            target_uid = "@" + self.cards[target_uid].boundary_side
        QtCore.QTimer.singleShot(0, lambda: None if panel.disposed else
                                panel.edit_connection(uid, target_uid, side, scope, context))

    def hideEvent(self, event):
        self.cancel_connection()
        super().hideEvent(event)

    def toggle_frame(self, uid):
        frame = self.panel.layout.frames[uid]
        if not frame.collapsed:
            chain = self.panel.snapshot.members(frame.scope)
            indices = sorted(chain.index(key) for key in frame.members)
            if indices != list(range(indices[0], indices[-1] + 1)):
                self.panel.status.setText("This frame contains nonconsecutive nodes after a native edit; it cannot be collapsed.")
                return
        proxy = self.cards.get("@frame:" + uid)
        if frame.collapsed and proxy:
            old = self.panel.layout.positions.get((self.scope, "@frame:" + uid), (proxy.x(), proxy.y()))
            positions = [self.panel.layout.positions.get((self.scope, key), (i * 340, 0))
                         for i, key in enumerate(self.panel.snapshot.members(self.scope)) if key in frame.members]
            if positions:
                dx, dy = proxy.x() - min(p[0] for p in positions), proxy.y() - min(p[1] for p in positions)
                for key in frame.members:
                    pos = self.panel.layout.positions.get((self.scope, key), old)
                    self.panel.layout.positions[(self.scope, key)] = (pos[0] + dx, pos[1] + dy)
        elif not frame.collapsed:
            positions = [self.cards[key].pos() for key in frame.members if key in self.cards]
            if positions:
                self.panel.layout.positions[(self.scope, "@frame:" + uid)] = (min(p.x() for p in positions), min(p.y() for p in positions))
                for key in frame.members:
                    if key in self.cards:
                        p = self.cards[key].pos()
                        self.panel.layout.positions[(self.scope, key)] = (p.x(), p.y())
        frame.collapsed = not frame.collapsed
        self.rebuild()

    def context_target(self, point):
        """Resolve creation from the cursor, including nested inline backdrops."""
        frames = []
        for hit in self.items(point):
            item = hit
            while item and not isinstance(item, (Card, FrameItem, BranchFrameItem)):
                item = item.parentItem()
            if isinstance(item, Card):
                node = self.panel.snapshot.nodes.get(item.uid)
                if node and node.layer:
                    region = item.region(item.mapFromScene(self.mapToScene(point)))
                    return item, None, (node.id, "mask" if region == "mask" else "content")
                if node:
                    return item, node.id, node.scope
                return item, None, self.boundary_scopes.get(item.uid, self.scope)
            if isinstance(item, FrameItem):
                return item, None, item.frame.scope
            if isinstance(item, BranchFrameItem):
                frames.append(item)
        if frames:
            # Backdrops share a Z value, so stacking order alone cannot identify
            # the innermost branch. Nested scopes have the deepest owner path.
            def depth(frame):
                owner, seen = frame.owner, set()
                while owner in self.panel.snapshot.nodes and owner not in seen:
                    seen.add(owner)
                    owner = self.panel.snapshot.nodes[owner].scope[0]
                return len(seen)
            frame = max(frames, key=depth)
            return frame, None, (frame.owner, frame.domain)
        return None, None, self.scope

    def contextMenuEvent(self, event):
        item, selected, scope = self.context_target(event.pos())
        uid = item.uid if isinstance(item, Card) else None
        node = self.panel.snapshot.nodes.get(uid)
        if not event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
            self.panel.browser(self, self.mapToScene(event.pos()), selected, scope)
            event.accept()
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction("Add Node…", lambda: self.panel.browser(self, self.mapToScene(event.pos()), selected, scope))
        menu.addAction("Refresh", self.panel.refresh)
        menu.addAction("Fit Graph", self.fit)
        menu.addAction("Arrange by Evaluation Order (Layout Only)", lambda: self.panel.arrange(self))
        menu.addAction("100%", self.resetTransform)
        if node:
            if not item.isSelected():
                self.scene().clearSelection()
                item.setSelected(True)
            menu.addSeparator()
            menu.addAction("Select in Painter / Native Properties", lambda: self.panel.navigate(uid, node.scope[1]))
            order = menu.addMenu("Evaluation Order")
            order.setToolTipsVisible(True)
            capability = self.panel.adapter.move_capability()
            for label in ("Evaluate Earlier — Below in Painter", "Evaluate Later — Above in Painter",
                          "Move to Start / Bottom", "Move to End / Top"):
                action = order.addAction(label)
                action.setEnabled(False)
                action.setToolTip(capability.reason)
            order.addSeparator()
            action = order.addAction("Select in Painter to Reorder…", lambda: self.panel.reorder_native(uid))
            action.setToolTip(capability.reason)
            if len(self.selected_ids()) > 1:
                order.addAction("Select All in Painter to Reorder…",
                                lambda: self.panel.reorder_selection_native(self.selected_ids()))
            menu.addAction("Rename…", lambda: self.panel.rename(uid))
            menu.addAction("Channel Blending…", lambda: self.panel.channel_popup(uid))
            if node.layer:
                if node.group:
                    menu.addAction("Open Group in New Tab", lambda: self.panel.open_scope((uid, "layers")))
                menu.addAction("Open Content Effects in New Tab", lambda: self.panel.open_scope((uid, "content")))
                if node.mask:
                    menu.addAction("Open Mask in New Tab", lambda: self.panel.open_scope((uid, "mask")))
            menu.addSeparator()
            menu.addAction("Delete…", lambda: self.panel.delete(uid))
        frame = item.frame if isinstance(item, FrameItem) else (
            self.panel.layout.frames.get(uid[7:]) if uid and uid.startswith("@frame:") else None)
        if frame:
            menu.addAction("Expand Frame" if frame.collapsed else "Collapse Frame", lambda: self.toggle_frame(frame.id))
            menu.addAction("Rename Frame…", lambda: self.panel.rename_frame(frame))
            menu.addAction("Remove Frame (keep nodes)", lambda: self.panel.remove_frame(frame.id))
        if self.selected_ids():
            menu.addAction("Frame Selected Nodes…", lambda: self.panel.frame(self))
        try:
            menu.exec(event.globalPos())
        finally:
            menu.deleteLater()

    def fit(self):
        if self.cards:
            self.fitInView(self.scene().itemsBoundingRect().adjusted(-40, -40, 40, 40),
                           QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            self.zoom(1)

    def zoom(self, factor):
        current = self.transform().m11()
        target = max(.15, min(2.5, current * factor))
        self.scale(target / current, target / current)

    def wheelEvent(self, event):
        self.zoom(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            point = event.position().toPoint()
            port = self.port_at(point)
            if port:
                uid, side = port
                if uid not in self.panel.snapshot.nodes:
                    # Boundary ports manipulate the attached real node, never the boundary itself.
                    matches = [(b, "input") if self.cards[uid].boundary_side == "input" else (a, "output")
                               for a, b, _domain in self.links if uid in (a, b)]
                    uid, side = matches[0] if len(matches) == 1 else (uid, side)
                if self.begin_connection(uid, side, point):
                    event.accept()
                    return
            else:
                for item in self.items(point):
                    if item in self.wires:
                        a, b, _domain = item.data(0)
                        uid, side = (a, "output") if a in self.panel.snapshot.nodes else (b, "input")
                        if self.begin_connection(uid, side, point):
                            event.accept()
                            return
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self.pan = event.position()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                # Protect before scene dispatch: native selection can emit refresh events.
                # Include marquee selection so a rebuild cannot interrupt Qt's gesture.
                self.layout_drag = True
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.connection_drag is not None:
            self.move_connection(event.position().toPoint())
            event.accept()
        elif self.pan is not None:
            delta = event.position() - self.pan
            self.pan = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.connection_drag is not None and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.finish_connection(event.position().toPoint())
            event.accept()
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self.pan = None
            self.unsetCursor()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                # Refresh asynchronously, after Qt finishes releasing its scene item.
                self.end_layout_drag()

    def keyPressEvent(self, event):
        if self.layout_drag:
            if event.key() == QtCore.Qt.Key.Key_Escape:
                self.cancel_layout_drag()
            event.accept()
        elif self.connection_drag is not None:
            if event.key() == QtCore.Qt.Key.Key_Escape:
                self.cancel_connection()
                if self.panel.pending_refresh:
                    self.panel.request_refresh()
            event.accept()
        elif event.key() == QtCore.Qt.Key.Key_F2:
            ids = self.selected_ids()
            if len(ids) == 1:
                self.panel.rename(ids[0])
            event.accept()
        elif event.key() == QtCore.Qt.Key.Key_Delete:
            if not event.isAutoRepeat():
                self.panel.delete_selected(self)
            event.accept()
        elif event.key() == QtCore.Qt.Key.Key_F:
            items = self.scene().selectedItems()
            if items:
                self.centerOn(items[0])
            else:
                self.fit()
        elif event.key() in (QtCore.Qt.Key.Key_Tab, QtCore.Qt.Key.Key_Space):
            ids = self.selected_ids()
            self.panel.browser(self, self.mapToScene(self.viewport().rect().center()), ids[0] if len(ids) == 1 else None)
        else:
            super().keyPressEvent(event)