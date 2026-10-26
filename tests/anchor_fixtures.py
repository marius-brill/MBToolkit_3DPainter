"""Fake public Painter surface exercises the real adapter, not a second discovery implementation."""
from contextlib import contextmanager
from enum import Enum
from types import SimpleNamespace
from MBToolkit_3DPainter.features.anchor_manager.painter_adapter import PainterAdapter


class Channel(Enum):
    BaseColor = 1
    Roughness = 2


class Node:
    def __init__(self, host, uid, name, kind, parent=None, domain="content"):
        self.host, self.id, self.name, self.kind = host, uid, name, kind
        self.parent, self.domain = parent, domain
        self.effects, self.mask, self.layers = [], [], []
        self.source_mode = None
        self.sources = {}
        self.material_source = None
        self.stack = host.stack
        host.nodes[uid] = self

    def uid(self):
        return self.id

    def get_type(self):
        return self.kind

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = name

    def get_stack(self):
        return self.stack

    def get_parent(self):
        return self.parent

    def is_in_mask_stack(self):
        return self.domain == "mask"

    def has_mask(self):
        return bool(self.mask)

    def content_effects(self):
        return self.effects

    def mask_effects(self):
        return self.mask

    def sub_layers(self):
        return self.layers

    def get_source(self, channel=None):
        return self.sources.get(channel)

    def get_material_source(self):
        return self.material_source

    def set_source(self, channel, anchor):
        if self.host.fail:
            raise RuntimeError("Simulated host failure")
        ref = Reference(anchor)
        self.sources[channel] = ref
        return ref

    def set_material_source(self, anchor):
        ref = Reference(anchor)
        self.material_source = ref
        return ref


class Reference:
    def __init__(self, anchor):
        self.anchor = anchor
        self.referenced_channel = Channel.BaseColor
        self.channel_mapping = {Channel.BaseColor: Channel.Roughness}
        self.alpha_matte = "preserve-alpha"
        self.levels = (0.1, 0.8)

    def get_levels(self):
        return self.levels

    def set_levels(self, levels):
        self.levels = levels


class Substance:
    def __init__(self, inputs):
        self.inputs = inputs

    @property
    def image_inputs(self):
        return list(self.inputs)

    def get_source(self, identifier):
        return self.inputs[identifier]


class FakeHost:
    def __init__(self):
        self.epoch, self.opened, self.busy, self.fail = 0, True, False, False
        self.selected = []
        self.nodes = {}
        self.root = []
        self.transactions = []
        material = SimpleNamespace(name=lambda: "Body")
        self.stack = SimpleNamespace(name=lambda: "", material=lambda: material,
                                     all_channels=lambda: {c: None for c in Channel})

        @contextmanager
        def transaction(name):
            self.transactions.append(name)
            yield

        self.sp = SimpleNamespace(
            project=SimpleNamespace(is_open=lambda: self.opened, is_in_edition_state=lambda: self.opened,
                                    is_busy=lambda: self.busy),
            textureset=SimpleNamespace(get_active_stack=lambda: self.stack, ChannelType=Channel),
            layerstack=SimpleNamespace(Node=Node, get_root_layer_nodes=lambda stack: self.root,
                get_node_by_uid=lambda uid: self.nodes[uid], get_selected_nodes=lambda stack: self.selected,
                set_selected_nodes=self.select, ScopedModification=transaction, delete_node=self.delete),
            source=SimpleNamespace(SourceReference=Reference, SourceSubstance=Substance),
            application=SimpleNamespace(version_info=lambda: (11, 0, 3)))
        self.adapter = PainterAdapter(self.sp, lambda: self.epoch)
        self.adapter.context()
        self.group = Node(self, 1, "Group", "GroupLayer")
        self.layer = Node(self, 2, "Base", "FillLayer", self.group)
        self.anchor = Node(self, 3, "Wear", "AnchorPointEffect", self.layer)
        self.alternative = Node(self, 4, "Wear", "AnchorPointEffect", self.layer)
        self.consumer = Node(self, 5, "Overlay", "FillLayer", self.group)
        self.consumer.source_mode = SimpleNamespace(name="Split")
        self.consumer.sources = {Channel.BaseColor: Reference(self.anchor), Channel.Roughness: Reference(self.anchor)}
        self.group.layers = [self.layer, self.consumer]
        self.layer.effects = [self.anchor, self.alternative]
        self.root = [self.group]
        self.sp.layerstack.LayerNode = Node
        self.sp.layerstack.EffectNode = Node
        self.sp.layerstack.NodeStack = SimpleNamespace(Content="content", Mask="mask")
        self.sp.layerstack.InsertPosition = SimpleNamespace(inside_node=lambda node, domain: (node, domain),
                                                            above_node=lambda node: (node.parent, node.domain))
        self.sp.layerstack.insert_anchor_point_effect = self.create_anchor

    def select(self, nodes):
        self.selected = nodes

    def create_anchor(self, position, name):
        parent, domain = position
        node = Node(self, max(self.nodes) + 1, name, "AnchorPointEffect", parent, domain)
        (parent.mask if domain == "mask" else parent.effects).insert(0, node)
        return node

    def delete(self, node):
        self.nodes.pop(node.uid())
        for parent in self.nodes.values():
            for children in (parent.effects, parent.mask, parent.layers):
                if node in children:
                    children.remove(node)