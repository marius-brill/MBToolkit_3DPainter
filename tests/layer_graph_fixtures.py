"""Small public-SDK double for testing the production Layer Graph adapter."""
from contextlib import contextmanager
from enum import Enum
from types import SimpleNamespace
from MBToolkit_3DPainter.features.layer_graph.adapter import Adapter


class Background(Enum):
    Black = 0
    White = 1


class Blend(Enum):
    Normal = 0
    Multiply = 1


class Position:
    @staticmethod
    def above_node(node):
        return ("above", node)

    @staticmethod
    def from_textureset_stack(stack):
        return ("root", stack)

    @staticmethod
    def inside_node(node, domain):
        return (domain, node)


class Effect:
    def __init__(self, host, kind, parent=None, domain="content"):
        self.host, self.kind, self.parent, self.domain = host, kind, parent, domain
        self.id = host.next_id
        host.next_id += 1
        host.nodes[self.id] = self
        self.name, self.visible = kind, True
        self.opacity, self.blend = 1., Blend.Normal
        self.source = None

    def uid(self):
        return self.id

    def get_type(self):
        return self.kind

    def get_name(self):
        return self.name

    def set_name(self, value):
        self.name = value

    def is_visible(self):
        return self.visible

    def set_visible(self, value):
        self.visible = value

    def get_stack(self):
        return self.host.stack

    def has_blending(self):
        return True

    def is_in_mask_stack(self):
        return self.domain == "mask"

    def get_opacity(self, channel):
        return self.opacity

    def get_blending_mode(self, channel):
        return self.blend

    def set_opacity(self, value, channel):
        self.opacity = value

    def set_blending_mode(self, mode, channel):
        self.blend = mode

    def set_source(self, channel, source):
        if self.host.fail_source:
            raise RuntimeError("source failed")
        self.source = source


class Layer(Effect):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.background = None
        self.effects, self.mask, self.children = [], [], []

    def has_mask(self):
        return self.background is not None

    def get_mask_background(self):
        return self.background

    def add_mask(self, background):
        assert not self.has_mask(), "Never replace a mask"
        self.background = background

    def remove_mask(self):
        for node in self.mask:
            self.host.nodes.pop(node.id)
        self.mask.clear()
        self.background = None

    def content_effects(self):
        return self.effects

    def mask_effects(self):
        return self.mask

    def sub_layers(self):
        return self.children


class Host:
    def __init__(self):
        self.opened, self.busy, self.epoch = True, False, 0
        self.nodes, self.roots, self.selected = {}, [], []
        self.next_id, self.fail_source = 1, False
        self.last_position = None
        self.modification_depth = 0
        self.material = SimpleNamespace(name=lambda: "Body")
        self.stack = SimpleNamespace(material=lambda: self.material, name=lambda: "Main", all_channels=lambda: ["BaseColor"])
        ls = SimpleNamespace(
            LayerNode=Layer, EffectNode=Effect, InsertPosition=Position,
            NodeStack=SimpleNamespace(Content="content", Mask="mask", Substack="layers"),
            SelectionType=SimpleNamespace(Content="content", Mask="mask"),
            MaskBackground=Background, BlendingMode=Blend,
            get_root_layer_nodes=lambda stack: self.roots,
            get_node_by_uid=lambda uid: self.nodes[uid],
            set_selected_nodes=self.select, set_selection_type=self.select_type,
            ScopedModification=self.transaction, delete_node=self.delete,
        )
        for name, kind in (("insert_group", "GroupLayer"), ("insert_fill", "Fill"), ("insert_paint", "Paint"),
                           ("insert_levels_effect", "LevelsEffect"), ("insert_compare_mask_effect", "CompareMaskEffect"),
                           ("insert_color_selection_effect", "ColorSelectionEffect"),
                           ("insert_filter_effect", "FilterEffect"), ("insert_generator_effect", "GeneratorEffect"),
                           ("insert_anchor_point_effect", "AnchorPointEffect"), ("instantiate", "InstanceLayer"),
                           ("insert_smart_material", "GroupLayer")):
            setattr(ls, name, lambda position, *args, k=kind: self.insert(position, k))
        ls.insert_smart_mask = lambda position, resource: [self.insert(position, "GeneratorEffect")]
        self.sp = SimpleNamespace(
            layerstack=ls, project=SimpleNamespace(is_open=lambda: self.opened, is_in_edition_state=lambda: self.opened,
                                                 is_busy=lambda: self.busy),
            textureset=SimpleNamespace(get_active_stack=lambda: self.stack),
            resource=SimpleNamespace(search=lambda query: []),
        )
        self.adapter = Adapter(self.sp, lambda: self.epoch)

    @contextmanager
    def transaction(self, name):
        self.modification_depth += 1
        try:
            yield
        finally:
            self.modification_depth -= 1

    def select(self, nodes):
        if self.modification_depth:
            raise RuntimeError("Selection forbidden inside ScopedModification")
        self.selected = nodes

    def select_type(self, node, mode):
        if self.modification_depth:
            raise RuntimeError("Selection forbidden inside ScopedModification")
        self.selection_type = mode

    def chain(self, node):
        if node.parent is None:
            return self.roots
        return {"layers": node.parent.children, "content": node.parent.effects, "mask": node.parent.mask}[node.domain]

    def insert(self, position, kind):
        self.last_position = position
        domain, target = position
        if domain == "above":
            parent, domain = target.parent, target.domain
            chain = self.chain(target)
            index = chain.index(target)
        elif domain == "root":
            parent, domain, chain, index = None, "layers", self.roots, 0
        else:
            parent, index = target, 0
            chain = {"layers": target.children, "content": target.effects, "mask": target.mask}[domain]
        if kind in ("Fill", "Paint"):
            kind += "Layer" if domain == "layers" else "Effect"
        cls = Layer if kind.endswith("Layer") else Effect
        node = cls(self, kind, parent, domain)
        chain.insert(index, node)
        return node

    def delete(self, node):
        self.chain(node).remove(node)
        if isinstance(node, Layer):
            for child in list(node.children + node.effects + node.mask):
                self.delete(child)
        self.nodes.pop(node.id)