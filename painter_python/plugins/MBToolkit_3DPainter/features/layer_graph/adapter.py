"""Public Painter API boundary. All access is on Painter's main Qt thread."""
from contextlib import nullcontext
from ..anchor_manager.painter_adapter import PainterAdapter, label
from .model import Node, Snapshot, ROOT, eligibility, connection_reason
from .ordering import NATIVE_MOVE, plan_move, revalidate_move, selection_roots


class Adapter:
    def __init__(self, sp, epoch=lambda: 0):
        self.sp = sp
        self.host = PainterAdapter(sp, epoch)
        # Session-only state: remember visibility, including intentionally disabled nodes.
        self.disconnected = {}
        self.connection_context = None

    def context(self):
        return self.host.context()

    def scan(self):
        result = Snapshot(self.context())
        if result.context != self.connection_context:
            self.disconnected.clear()
            self.connection_context = result.context
        if result.context is None:
            return result
        pending = [(ROOT, self.host.roots())]
        while pending:
            scope, nodes = pending.pop()
            result.chains[scope] = []
            for node in nodes:
                uid = str(node.uid())
                if uid in result.nodes:
                    raise ValueError("Duplicate node encountered in layer hierarchy")
                kind = label(node.get_type())
                layer = isinstance(node, self.sp.layerstack.LayerNode)
                mask = label(node.get_mask_background()) if layer and node.has_mask() else ""
                visible = node.is_visible()
                # A native enable/Undo takes precedence over our session-only bypass marker.
                if visible:
                    self.disconnected.pop(uid, None)
                result.nodes[uid] = Node(uid, node.get_name(), kind, scope, visible, mask,
                                         uid in self.disconnected)
                result.chains[scope].append(uid)
                if layer:
                    pending.append(((uid, "content"), node.content_effects()))
                    if mask:
                        pending.append(((uid, "mask"), node.mask_effects()))
                if kind == "GroupLayer":
                    pending.append(((uid, "layers"), node.sub_layers()))
        if self.context() != result.context:
            raise ValueError("Project or texture stack changed during scan; refresh")
        self.disconnected = {uid: state for uid, state in self.disconnected.items() if uid in result.nodes}
        return result

    def _ready(self, context, writable=True):
        if context is None or self.context() != context:
            raise ValueError("Project or texture stack changed; refresh before editing")
        if writable and self.sp.project.is_busy():
            raise ValueError("Painter is busy; wait before editing")

    def resolve(self, uid, context, writable=True):
        self._ready(context, writable)
        node = self.sp.layerstack.get_node_by_uid(int(uid))
        key = self.host.key(node)
        if (key.project_session, key.texture_set_key, key.stack_key) != context:
            raise ValueError("Node no longer belongs to this texture stack")
        return node

    def transaction(self, name):
        cls = getattr(self.sp.layerstack, "ScopedModification", None)
        return cls(name) if cls else nullcontext()

    def move_capability(self):
        """Do not infer move support from undocumented methods or host version numbers."""
        return NATIVE_MOVE

    def preview_move(self, intent):
        self._ready(intent.context)
        return plan_move(self.scan(), intent)

    def move(self, plan):
        """Fail closed until a public identity-preserving backend is verified.

        Keeping this boundary explicit prevents future UI code from substituting
        delete/recreate or optimistic snapshot edits for an actual native move.
        """
        self._ready(plan.intent.context)
        fresh = revalidate_move(self.scan(), plan)
        if fresh.noop:
            return False
        raise ValueError(self.move_capability().reason)

    def navigate_many(self, selected, context):
        """Hand off a single-scope selection in native order, outside undo macros."""
        self._ready(context, False)
        snapshot = self.scan()
        if snapshot.context != context:
            raise ValueError("Project or texture stack changed; refresh")
        roots = selection_roots(snapshot, selected)
        scope = snapshot.nodes[roots[0]].scope
        if any(snapshot.nodes[uid].scope != scope for uid in roots):
            raise ValueError("Select nodes from one native scope to reorder together")
        chosen = set(roots)
        ordered = [uid for uid in snapshot.chains.get(scope, ()) if uid in chosen]
        if len(ordered) != len(chosen):
            raise ValueError("Selected node is missing from its native chain; refresh")
        nodes = [self.resolve(uid, context, False) for uid in ordered]
        self.sp.layerstack.set_selected_nodes(nodes)
        if snapshot.nodes[ordered[0]].layer:
            for node in nodes:
                self.sp.layerstack.set_selection_type(node, self.sp.layerstack.SelectionType.Content)
        return tuple(ordered)

    def reason(self, item, snapshot, scope, selected):
        reason = eligibility(item, snapshot, scope, selected)
        if reason:
            return reason
        if item.operation and not callable(getattr(self.sp.layerstack, item.operation, None)):
            return "This Painter build does not expose " + item.operation
        return ""

    def resources(self, usage):
        return sorted(self.sp.resource.search("u:" + usage), key=lambda r: r.gui_name().casefold())

    def create(self, item, context, scope, selected=None, resource=None):
        self._ready(context)
        fresh = self.scan()
        if selected is not None and (selected not in fresh.nodes or fresh.nodes[selected].scope != scope):
            raise ValueError("Selected insertion target was deleted or moved; refresh before creating nodes")
        reason = self.reason(item, fresh, scope, selected)
        if reason:
            raise ValueError(reason)
        if item.resource and resource is None:
            raise ValueError("Choose a " + item.resource + " resource first")
        ls = self.sp.layerstack
        target_record = fresh.nodes.get(selected)
        target = self.resolve(selected, context) if target_record else None
        owner = self.resolve(scope[0], context) if scope[0] else None
        with self.transaction("Layer Graph: " + item.name):
            if item.category == "Masks":
                layer = target if target_record and target_record.layer else owner
                background = ls.MaskBackground.White if item.id == "white" else ls.MaskBackground.Black
                layer.add_mask(background)
                try:
                    if item.operation:
                        position = ls.InsertPosition.inside_node(layer, ls.NodeStack.Mask)
                        effect = getattr(ls, item.operation)(position)
                        if item.id == "bitmap":
                            effect.set_source(None, resource)
                except Exception:
                    layer.remove_mask()
                    raise
                created = layer
                domain = "mask"
            else:
                domain = "content"
                if target_record and target_record.scope == scope:
                    position = ls.InsertPosition.above_node(target)
                elif scope == ROOT:
                    position = ls.InsertPosition.from_textureset_stack(self.sp.textureset.get_active_stack())
                else:
                    stack = {"mask": ls.NodeStack.Mask, "content": ls.NodeStack.Content,
                             "layers": ls.NodeStack.Substack}[scope[1]]
                    position = ls.InsertPosition.inside_node(owner, stack)
                operation = getattr(ls, item.operation)
                if item.id == "instance":
                    created = operation(position, target)
                elif item.id == "anchor":
                    created = operation(position, "Anchor")
                elif item.resource:
                    created = operation(position, resource)
                else:
                    created = operation(position)
                if isinstance(created, list):
                    created = created[0] if created else None
        # Painter forbids selection changes inside ScopedModification.
        if created is not None:
            uid = str(created.uid())
            self.navigate(uid, context, domain)
            return uid
        return None

    def navigate(self, uid, context, domain="content"):
        node = self.resolve(uid, context, False)
        self.sp.layerstack.set_selected_nodes([node])
        if isinstance(node, self.sp.layerstack.LayerNode):
            mode = self.sp.layerstack.SelectionType.Mask if domain == "mask" else self.sp.layerstack.SelectionType.Content
            self.sp.layerstack.set_selection_type(node, mode)

    def rename(self, uid, context, name):
        name = name.strip()
        if not name:
            raise ValueError("Name cannot be empty")
        self.resolve(uid, context).set_name(name[:200])

    def visibility(self, uid, context, value):
        self.resolve(uid, context).set_visible(value)
        self.disconnected.pop(uid, None)

    def disconnect(self, uid, context):
        node = self.resolve(uid, context)
        if uid in self.disconnected:
            return
        visible = node.is_visible()
        with self.transaction("Layer Graph: disconnect node"):
            node.set_visible(False)
        self.disconnected[uid] = visible

    def connection_reason(self, uid, target, side, context, scope):
        """Commit validation always rereads Painter; hover uses the pure model helper."""
        self._ready(context)
        snapshot = self.scan()
        return connection_reason(snapshot, uid, target, side, context, scope)

    def reconnect(self, uid, target, side, context, scope):
        reason = self.connection_reason(uid, target, side, context, scope)
        if reason:
            raise ValueError(reason)
        node = self.resolve(uid, context)
        if uid in self.disconnected:
            with self.transaction("Layer Graph: reconnect node"):
                node.set_visible(self.disconnected[uid])
            self.disconnected.pop(uid, None)

    def delete(self, uid, context):
        self.sp.layerstack.delete_node(self.resolve(uid, context))

    def blending(self, uid, context):
        node = self.resolve(uid, context, False)
        if not node.has_blending():
            return []
        channels = [None] if node.is_in_mask_stack() else [
            ch.type() if callable(getattr(ch, "type", None)) else ch for ch in node.get_stack().all_channels()]
        return [(channel, node.get_opacity(channel), node.get_blending_mode(channel)) for channel in channels]

    def set_blending(self, uid, context, channel, opacity, mode):
        node = self.resolve(uid, context)
        if not node.has_blending():
            raise ValueError("Node no longer supports blending")
        with self.transaction("Layer Graph: channel blending"):
            node.set_opacity(opacity, channel)
            node.set_blending_mode(mode, channel)

    def blend_modes(self):
        cls = self.sp.layerstack.BlendingMode
        members = getattr(cls, "__members__", None)
        if members is not None:
            return list(members.values())
        return [getattr(cls, name) for name in dir(cls) if not name.startswith("_")
                and isinstance(getattr(cls, name), cls)]