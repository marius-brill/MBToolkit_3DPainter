"""All Painter access lives here. Calls run on the caller's host/Qt thread only."""
from contextlib import nullcontext
from uuid import uuid4
from .capabilities import probe
from .models import NodeKey, NodeRecord, ReferenceRecord, Status


def label(value) -> str:
    return getattr(value, "name", str(value))


class PainterAdapter:
    def __init__(self, sp, epoch=lambda: 0):
        self.sp = sp
        self.epoch = epoch
        self.last_epoch = None
        self.session = ""
        self.was_open = False
        self.capabilities = probe(sp)

    def context(self):
        opened = self.sp.project.is_open()
        epoch = self.epoch()
        if epoch != self.last_epoch or opened != self.was_open:
            self.session = uuid4().hex
            self.last_epoch, self.was_open = epoch, opened
        if not opened or not self.sp.project.is_in_edition_state():
            return None
        stack = self.sp.textureset.get_active_stack()
        return (self.session, stack.material().name(), stack.name())

    def key(self, node) -> NodeKey:
        stack = node.get_stack()
        return NodeKey(self.session, stack.material().name(), stack.name(), node.uid())

    def roots(self):
        if self.context() is None:
            return []
        return self.sp.layerstack.get_root_layer_nodes(self.sp.textureset.get_active_stack())

    def record(self, node, path, parent, domain, order):
        return NodeRecord(self.key(node), node.get_name(), (*path, node.get_name()),
                          label(node.get_type()), domain, parent, order)

    def children(self, node):
        """Yield each branch independently so one unreadable branch cannot hide others."""
        for method, domain in (("content_effects", "content"), ("mask_effects", "mask"),
                               ("sub_layers", "layer")):
            if callable(getattr(node, method, None)):
                yield method, domain, lambda m=method: getattr(node, m)()

    def source_slots(self, node):
        kind = label(node.get_type())
        if kind in ("FillLayer", "FillEffect"):
            mode = node.source_mode
            if mode is None:
                yield "mono", "source", "", (), lambda: node.get_source(None)
            elif label(mode) == "Material":
                yield "material", "material", "", (), node.get_material_source
            else:
                # Include disabled channels too: hidden assignments may still be references.
                for channel in node.get_stack().all_channels():
                    ch = channel.type() if callable(getattr(channel, "type", None)) else channel
                    yield "split", label(ch), label(ch), (), lambda c=ch: node.get_source(c)
        elif kind in ("GeneratorEffect", "FilterEffect"):
            yield "procedural", "substance", "", (), node.get_source

    def inspect_source(self, source, slot):
        if isinstance(source, self.sp.source.SourceReference):
            anchor = source.anchor
            ref = ReferenceRecord(slot, self.key(anchor) if anchor is not None else None)
            if anchor is None:
                ref.status, ref.reason = Status.BROKEN, "Public SourceReference.anchor explicitly returned None"
            else:
                ref.status, ref.reason = Status.VALID, "Host resolves anchor; evaluation order not independently validated"
            try:
                if slot.source_mode == "material" and not slot.source_path:
                    mapping = source.channel_mapping
                    ref.channel_mapping = {label(k): label(mapping[k]) for k in mapping}
                elif anchor is not None and not anchor.is_in_mask_stack():
                    ref.source_channel = label(source.referenced_channel)
                ref.settings_signature = (repr(source.get_levels()), repr(source.alpha_matte))
                ref.writable = slot.source_mode in ("mono", "split", "material") and not slot.source_path
            except Exception as exc:
                if ref.status is not Status.BROKEN:
                    ref.status, ref.reason = Status.UNKNOWN, f"Anchor resolved but reference metadata unavailable: {exc}"
            return ref, []
        if isinstance(source, self.sp.source.SourceSubstance):
            children = [(identifier, lambda i=identifier: source.get_source(i))
                        for identifier in source.image_inputs]
            return None, children
        return None, []

    def source_gaps(self, source):
        if isinstance(source, self.sp.source.SourceSubstance):
            return ["Procedural image inputs scanned; completeness of other embedded parameter references unverified"]
        if source is None or isinstance(source, self.sp.source.SourceReference):
            return []
        known = tuple(cls for name in ("SourceBitmap", "SourceUniformColor", "SourceFont", "SourceVectorial")
                      if isinstance(cls := getattr(self.sp.source, name, None), type))
        return [] if isinstance(source, known) else [f"Unscanned source category: {type(source).__name__}"]

    def stack_choices(self):
        if self.context() is None:
            return []
        return [(material.name(), stack.name()) for material in self.sp.textureset.all_texture_sets()
                for stack in material.all_stacks()]

    def activate_stack(self, material, stack):
        target = self.sp.textureset.TextureSet.from_name(material).get_stack(stack)
        self.sp.textureset.set_active_stack(target)

    def can_write(self):
        return self.context() is not None and not self.sp.project.is_busy()

    def gaps_for(self, node):
        kind = label(node.get_type())
        if kind in ("GeneratorEffect", "FilterEffect"):
            return [f"{node.get_name()}: procedural image inputs observable; other embedded parameters unverified"]
        if kind in ("PaintLayer", "PaintEffect", "InstanceLayer"):
            return [f"{node.get_name()}: {kind} embedded/instanced inputs are not enumerated"]
        known = {"FillLayer", "FillEffect", "GroupLayer", "AnchorPointEffect", "LevelsEffect",
                 "CompareMaskEffect", "ColorSelectionEffect"}
        return [] if kind in known else [f"{kind}: unknown source category"]

    def resolve(self, key: NodeKey, writable=False):
        if self.context() != (key.project_session, key.texture_set_key, key.stack_key):
            raise ValueError("STALE_NODE: project or active texture stack changed; refresh")
        if writable and self.sp.project.is_busy():
            raise ValueError("Painter is busy; wait before editing")
        node = self.sp.layerstack.get_node_by_uid(key.host_uid)
        if self.key(node) != key:
            raise ValueError("STALE_NODE: node identity no longer matches")
        return node

    def navigate(self, key):
        self.sp.layerstack.set_selected_nodes([self.resolve(key)])

    def selected_key(self):
        if self.context() is None:
            return None
        nodes = self.sp.layerstack.get_selected_nodes(self.sp.textureset.get_active_stack())
        return self.key(nodes[0]) if len(nodes) == 1 else None

    def transaction(self, name):
        cls = getattr(self.sp.layerstack, "ScopedModification", None)
        return cls(name) if cls else nullcontext()

    def rename(self, key, name):
        self.resolve(key, True).set_name(name)

    def delete(self, key):
        self.sp.layerstack.delete_node(self.resolve(key, True))

    def insertion_sites(self, key):
        node = self.resolve(key, True)
        ls = self.sp.layerstack
        if isinstance(node, ls.LayerNode):
            sites = ["content"]
            if node.has_mask():
                sites.append("mask")
            return sites
        if isinstance(node, ls.EffectNode):
            return ["above effect"]
        return []

    def create(self, key, site, name):
        if site not in self.insertion_sites(key):
            raise ValueError("Insertion site is no longer eligible")
        node = self.resolve(key, True)
        ls = self.sp.layerstack
        position = (ls.InsertPosition.above_node(node) if site == "above effect" else
                    ls.InsertPosition.inside_node(node, ls.NodeStack.Mask if site == "mask" else ls.NodeStack.Content))
        return self.key(ls.insert_anchor_point_effect(position, name))

    def _channel(self, name):
        return getattr(self.sp.textureset.ChannelType, name) if name else None

    def _source(self, node, slot):
        if slot.source_path:
            raise ValueError("Procedural reference editing is read-only")
        mode = label(node.source_mode) if node.source_mode is not None else "mono"
        if mode.casefold() != slot.source_mode:
            raise ValueError("Source mode changed while operation was open")
        return (node.get_material_source() if slot.source_mode == "material" else
                node.get_source(self._channel(slot.channel)))

    def replace(self, ref, target):
        node = self.resolve(ref.slot.consumer, True)
        anchor = self.resolve(target, True)
        old = self._source(node, ref.slot)
        if not isinstance(old, self.sp.source.SourceReference) or old.anchor is None or self.key(old.anchor) != ref.anchor_key:
            raise ValueError("Binding changed since preview; refresh")
        current, _ = self.inspect_source(old, ref.slot)
        if current != ref:
            raise ValueError("Reference settings changed since preview; refresh")
        # Snapshot all public reference settings before performing any mutation.
        levels, alpha = old.get_levels(), old.alpha_matte
        mapping = old.channel_mapping if ref.slot.source_mode == "material" else None
        mapping_values = {k: mapping[k] for k in mapping} if mapping is not None else {}
        channel = old.referenced_channel if ref.source_channel else None
        try:
            new = (node.set_material_source(anchor) if ref.slot.source_mode == "material" else
                   node.set_source(self._channel(ref.slot.channel), anchor))
            new.set_levels(levels)
            new.alpha_matte = alpha
            for dst, src in mapping_values.items():
                new.channel_mapping[dst] = src
            if channel is not None:
                new.referenced_channel = channel
            if new.anchor is None or self.key(new.anchor) != target:
                raise RuntimeError("Host did not confirm the requested binding")
        except Exception as exc:
            # No claim of atomic rollback: host may already have changed the binding.
            raise RuntimeError(f"Replacement failed; host may be partially changed. Inspect/Undo: {exc}") from exc

    def diagnostic(self):
        return {"host_version": str(self.sp.application.version_info()),
                "capabilities": {k: {"state": v.state.value, "reason": v.reason}
                                 for k, v in self.capabilities.items()}}