"""Qt/host-free layer graph catalog, ordered scopes and visual organization."""
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class NodeType:
    id: str
    name: str
    category: str
    operation: str = ""
    resource: str = ""
    mask_only: bool = False
    aliases: str = ""


CATALOG = (
    NodeType("paint", "Paint Layer", "Layers", "insert_paint", aliases="brush raster"),
    NodeType("fill", "Fill Layer", "Layers", "insert_fill", aliases="material solid"),
    NodeType("instance", "Instance Layer", "Layers", "instantiate", aliases="linked copy"),
    NodeType("group", "Material Group / Folder", "Organization", "insert_group", aliases="blueprint subgraph"),
    NodeType("frame", "Graph Frame", "Organization", aliases="comment backdrop organize"),
    NodeType("black", "Black Mask", "Masks", aliases="hide grayscale"),
    NodeType("white", "White Mask", "Masks", aliases="reveal grayscale"),
    NodeType("bitmap", "Bitmap Mask", "Masks", "insert_fill", "texture", aliases="image"),
    NodeType("color_mask", "Color Selection Mask", "Masks", "insert_color_selection_effect"),
    NodeType("height_mask", "Height Combination Mask", "Masks", "insert_compare_mask_effect"),
    NodeType("paint_fx", "Paint Effect", "Effects", "insert_paint"),
    NodeType("fill_fx", "Fill Effect", "Effects", "insert_fill", aliases="noise procedural"),
    NodeType("generator", "Generator", "Effects", "insert_generator_effect", "generator", aliases="edge wear dirt"),
    NodeType("filter", "Filter", "Effects", "insert_filter_effect", "filter", aliases="blur sharpen"),
    NodeType("levels", "Levels", "Effects", "insert_levels_effect", aliases="contrast remap"),
    NodeType("compare", "Compare Mask", "Effects", "insert_compare_mask_effect", mask_only=True),
    NodeType("color", "Color Selection", "Effects", "insert_color_selection_effect", mask_only=True, aliases="id"),
    NodeType("anchor", "Anchor Point", "Effects", "insert_anchor_point_effect", aliases="reference"),
    NodeType("smart_material", "Smart Material", "Presets", "insert_smart_material", "smartmaterial"),
    NodeType("smart_mask", "Smart Mask", "Presets", "insert_smart_mask", "smartmask", mask_only=True),
)
TYPES = {item.id: item for item in CATALOG}
Scope = tuple[str, str]  # owner uid (empty = root), layers/content/mask
ROOT = ("", "layers")
REORDER_REASON = ("No verified public native move API is available. Reorder existing nodes in Painter's "
                  "Layers panel; the graph follows native changes. Graph dragging only changes layout.")


@dataclass
class Node:
    id: str
    name: str
    kind: str
    scope: Scope = ROOT
    visible: bool = True
    mask: str = ""
    disconnected: bool = False

    @property
    def group(self):
        return self.kind == "GroupLayer"

    @property
    def layer(self):
        return self.kind.endswith("Layer")


@dataclass
class Snapshot:
    context: tuple | None = None
    nodes: dict[str, Node] = field(default_factory=dict)
    chains: dict[Scope, list[str]] = field(default_factory=dict)

    def members(self, scope):
        """Host chains are top-first; graph evaluation reads bottom-to-top."""
        return list(reversed(self.chains.get(scope, [])))

    def valid_scope(self, scope):
        if scope == ROOT:
            return True
        node = self.nodes.get(scope[0])
        return node is not None and ((scope[1] == "layers" and node.group) or
                                     (scope[1] == "content" and node.layer) or
                                     (scope[1] == "mask" and bool(node.mask)))

    def title(self, scope):
        if scope == ROOT:
            return "Texture Set"
        node = self.nodes.get(scope[0])
        return f"{node.name} / {scope[1].title()}" if node else "Deleted scope"


def connection_reason(snapshot, uid, target, side, context, scope):
    """Preview only: use the current snapshot, without host access or a second cache."""
    if context is None or snapshot.context != context:
        return "Project or texture stack changed; refresh before editing."
    node = snapshot.nodes.get(uid)
    if node is None or node.scope != scope:
        return "Connection source was deleted or moved; refresh."
    if side not in ("input", "output"):
        return "Invalid port direction."
    if target == uid:
        return "A node cannot connect to itself."
    boundary = "@input" if side == "input" else "@output"
    if target != boundary:
        other = snapshot.nodes.get(target)
        if other is None or other.scope != scope:
            return "Connect compatible ports in the same layer, content or mask stack."
        if other.disconnected:
            return "Reconnect the target node first."
    chain = ["@input", *[key for key in snapshot.members(scope)
                         if key == uid or not snapshot.nodes[key].disconnected], "@output"]
    if uid not in chain:
        return "Connection source is missing from its stack; refresh."
    expected = chain[chain.index(uid) + (-1 if side == "input" else 1)]
    if target != expected:
        return "This drop requires reordering Painter's stack. " + REORDER_REASON
    return ""


@dataclass
class Frame:
    id: str
    name: str
    scope: Scope
    members: list[str]
    collapsed: bool = False


@dataclass
class Layout:
    """Session-only view state. Never stores host objects or changes composition."""
    positions: dict = field(default_factory=dict)
    expanded: set = field(default_factory=set)
    frames: dict[str, Frame] = field(default_factory=dict)

    def frame(self, scope, members, name="Frame"):
        members = list(dict.fromkeys(members))
        if not members:
            raise ValueError("Select nodes to put in a frame")
        occupied = {key for f in self.frames.values() for key in f.members}
        if occupied.intersection(members):
            raise ValueError("A node can belong to only one graph frame")
        frame = Frame(uuid4().hex, name, scope, members)
        self.frames[frame.id] = frame
        return frame

    def prune(self, snapshot):
        self.positions = {key: value for key, value in self.positions.items()
                          if snapshot.valid_scope(key[0]) and (key[1] in snapshot.nodes or key[1].startswith("@"))}
        self.expanded.intersection_update(snapshot.nodes)
        for key, frame in list(self.frames.items()):
            frame.members[:] = [uid for uid in frame.members if uid in snapshot.nodes
                                and snapshot.nodes[uid].scope == frame.scope]
            if not frame.members or not snapshot.valid_scope(frame.scope):
                del self.frames[key]
            elif frame.collapsed:
                chain = snapshot.members(frame.scope)
                indices = sorted(chain.index(uid) for uid in frame.members)
                if indices != list(range(indices[0], indices[-1] + 1)):
                    # Native insertion can split a frame; never hide an intervening layer.
                    frame.collapsed = False

    def arrange(self, scope):
        """Reset only this view's positions; rebuilding derives native evaluation order.

        Expanded state, frames, other tabs and Painter's hierarchy are untouched.
        """
        self.positions = {key: value for key, value in self.positions.items() if key[0] != scope}


def search(query):
    words = query.casefold().split()
    return [item for item in CATALOG if all(word in f"{item.name} {item.category} {item.aliases}".casefold()
                                            for word in words)]


def eligibility(item, snapshot, scope, selected=None):
    """Shared browser/commit validation; no optimistic ghost nodes."""
    if item.id == "frame":
        return "" if selected in snapshot.nodes else "Select nodes to frame first"
    if snapshot.context is None:
        return "Open an editable Painter project"
    if not snapshot.valid_scope(scope):
        return "This graph scope no longer exists"
    node = snapshot.nodes.get(selected)
    owner = snapshot.nodes.get(scope[0])
    target = node if node and node.layer else owner
    if item.category == "Masks":
        if not target or not target.layer:
            return "Select a layer or open its mask graph"
        if target.mask:
            return "Layer already has a mask; existing masks are never replaced"
        return ""
    if item.id == "instance":
        return "" if node and node.layer and not node.group and scope[1] == "layers" else "Select a non-folder layer to instance"
    if item.mask_only and scope[1] != "mask":
        return "Open a mask graph first"
    if item.category == "Effects" and scope[1] == "layers":
        return "Open a layer's Content Effects or Mask graph first"
    if item.category in ("Layers", "Organization") or item.id == "smart_material":
        return "" if scope[1] == "layers" else "Layers belong in the material graph, not an effect chain"
    return ""