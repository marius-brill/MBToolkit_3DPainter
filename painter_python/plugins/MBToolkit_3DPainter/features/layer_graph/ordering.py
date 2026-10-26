"""Pure native-order planning. Plans are not permissions to mutate Painter.

All chains here use Painter's top-first order. 'before'/'after' describe graph
evaluation, so before is below and after is above in the native Layers panel.
No host objects, global caches, or inferred/private SDK entry points are used.
"""
from dataclasses import dataclass
from .model import REORDER_REASON, Scope


@dataclass(frozen=True)
class MoveCapability:
    same_chain: bool = False
    batch: bool = False
    reparent: bool = False
    reason: str = REORDER_REASON


# A method name or version check is not proof of an identity-preserving move.
# Replace this gate only alongside an explicitly verified public SDK backend.
NATIVE_MOVE = MoveCapability()


def connection_move(snapshot, uid, target, side, context, scope):
    """Translate one port drop to a splice of Painter's linear evaluation chain."""
    if context is None or snapshot.context != context:
        raise ValueError("Project or texture stack changed; refresh")
    node = snapshot.nodes.get(uid)
    if node is None or node.scope != scope:
        raise ValueError("Connection source was deleted or moved; refresh")
    if side not in ("input", "output"):
        raise ValueError("Invalid port direction")
    if target == uid:
        raise ValueError("A node cannot connect to itself")
    boundary = "@input" if side == "input" else "@output"
    if target == boundary:
        placement, anchor = ("start" if side == "input" else "end"), None
    else:
        other = snapshot.nodes.get(target)
        if other is None or other.scope != scope:
            raise ValueError("Connect compatible ports within the same stack")
        if other.disconnected:
            raise ValueError("Reconnect the target node first")
        placement, anchor = ("after" if side == "input" else "before"), target
    return plan_move(snapshot, MoveIntent(context, (uid,), scope, placement, anchor))


def ui_move_reason(snapshot, plan):
    """Narrow scope proven by the Windows/Painter 11.0.3 native-drag experiment."""
    if plan.noop:
        return ""
    if plan.source != ("", "layers") or plan.intent.destination != plan.source:
        return "Experimental connection reorder currently supports root layers only"
    if any(node.kind == "AnchorPointEffect" for node in snapshot.nodes.values()):
        return "Anchor dependencies are not verified for experimental native dragging"
    if any(snapshot.nodes[uid].kind not in ("FillLayer", "PaintLayer") for uid in plan.source_before):
        return "Experimental connection reorder requires a root stack of Fill/Paint layers (no folders or instances)"
    names = [snapshot.nodes[uid].name for uid in plan.source_before]
    if len(set(names)) != len(names):
        return "Give root layers unique names before experimental connection reordering"
    return ""


@dataclass(frozen=True)
class MoveIntent:
    context: tuple | None
    selected: tuple[str, ...]
    destination: Scope
    placement: str
    target: str | None = None


@dataclass(frozen=True)
class MovePlan:
    intent: MoveIntent
    source: Scope
    moved: tuple[str, ...]
    source_before: tuple[str, ...]
    destination_before: tuple[str, ...]
    source_after: tuple[str, ...]
    destination_after: tuple[str, ...]
    structure: tuple

    @property
    def noop(self):
        return self.source == self.intent.destination and self.source_before == self.destination_after


def structure_signature(snapshot):
    """Discardable structural evidence, not a snapshot copy or material serialization."""
    return (snapshot.context,
            frozenset((uid, node.kind, node.scope, node.mask) for uid, node in snapshot.nodes.items()),
            frozenset((scope, tuple(chain)) for scope, chain in snapshot.chains.items()))


def selection_roots(snapshot, selected):
    """Drop selected descendants of selected groups; reject stale and cyclic input."""
    selected = tuple(dict.fromkeys(selected))
    if not selected:
        raise ValueError("Select at least one native node")
    if any(uid not in snapshot.nodes for uid in selected):
        raise ValueError("Selection contains deleted or virtual nodes; refresh")
    chosen = set(selected)
    result = []
    for uid in selected:
        owner, seen, covered = snapshot.nodes[uid].scope[0], {uid}, False
        while owner:
            if owner in seen or owner not in snapshot.nodes:
                raise ValueError("Invalid or cyclic native hierarchy; refresh")
            seen.add(owner)
            covered |= owner in chosen
            owner = snapshot.nodes[owner].scope[0]
        if not covered:
            result.append(uid)
    return tuple(result)


def plan_move(snapshot, intent):
    """Calculate expected chains without changing snapshot, layout, or host state."""
    if intent.context is None or snapshot.context != intent.context:
        raise ValueError("Project or texture stack changed; refresh")
    if intent.placement not in ("before", "after", "start", "end"):
        raise ValueError("Unknown move placement")
    if not snapshot.valid_scope(intent.destination):
        raise ValueError("Destination scope no longer exists")
    roots = selection_roots(snapshot, intent.selected)
    scopes = {snapshot.nodes[uid].scope for uid in roots}
    if len(scopes) != 1:
        raise ValueError("Move selection must belong to one native scope")
    source = scopes.pop()
    if not snapshot.valid_scope(source):
        raise ValueError("Source scope no longer exists")
    if source != intent.destination and (source[1] != "layers" or intent.destination[1] != "layers"):
        raise ValueError("Effects cannot transfer between owners, content stacks or masks")
    chosen = set(roots)
    owner, seen = intent.destination[0], set()
    while owner:
        if owner in chosen:
            raise ValueError("A group cannot move into itself or its descendants")
        if owner in seen or owner not in snapshot.nodes:
            raise ValueError("Invalid or cyclic destination hierarchy")
        seen.add(owner)
        owner = snapshot.nodes[owner].scope[0]
    before = tuple(snapshot.chains.get(source, ()))
    destination = tuple(snapshot.chains.get(intent.destination, ()))
    for scope, chain in ((source, before), (intent.destination, destination)):
        if (len(chain) != len(set(chain)) or any(uid not in snapshot.nodes or snapshot.nodes[uid].scope != scope
                                               for uid in chain)):
            raise ValueError("Inconsistent native chain; refresh")
    moved = tuple(uid for uid in before if uid in chosen)
    if len(moved) != len(chosen):
        raise ValueError("Selected node is missing from its native chain; refresh")
    if any(snapshot.nodes[uid].layer != (intent.destination[1] == "layers") for uid in moved):
        raise ValueError("Layers and effects cannot exchange domains")
    remaining = tuple(uid for uid in destination if uid not in chosen)
    if intent.placement in ("before", "after"):
        if intent.target in chosen:
            raise ValueError("Destination target is part of the move selection")
        if intent.target not in remaining:
            raise ValueError("Destination target was deleted or moved; refresh")
        # Graph-before means native-below; graph-after means native-above.
        index = remaining.index(intent.target) + (intent.placement == "before")
    else:
        if intent.target is not None:
            raise ValueError("Scope boundary placement must not specify a target")
        index = len(remaining) if intent.placement == "start" else 0
    after = remaining[:index] + moved + remaining[index:]
    source_after = after if source == intent.destination else tuple(uid for uid in before if uid not in chosen)
    return MovePlan(intent, source, moved, before, destination, source_after, after, structure_signature(snapshot))


def revalidate_move(snapshot, plan):
    """Reject structural changes anywhere, including moved subtrees and outside consumers."""
    if structure_signature(snapshot) != plan.structure:
        raise ValueError("Native hierarchy changed since preview; plan the move again")
    fresh = plan_move(snapshot, plan.intent)
    if fresh != plan:
        raise ValueError("Move plan no longer matches the native hierarchy")
    return fresh


def dependency_reason(snapshot, plan, index):
    """Conservative gate, not an unverified nested-group dependency evaluator.

An Anchor Manager index covers scanned public source categories, not every
possible native dependency. Any binding or anchor remains blocked until a
host-validated evaluation-order checker exists. Empty, complete discovery can
rule out discovered anchor dependencies, but cannot enable a move backend.
"""
    revalidate_move(snapshot, plan)
    if plan.noop:
        return ""
    if index is None or not index.finished or index.coverage.value != "complete" or index.gaps:
        return "Dependency discovery is incomplete; reorder in Painter"
    if any((key.project_session, key.texture_set_key, key.stack_key) != snapshot.context for key in index.nodes):
        return "Dependency discovery belongs to another project or stack"
    if {str(key.host_uid) for key in index.nodes} != set(snapshot.nodes):
        return "Dependency discovery is stale; refresh before moving"
    records_by_scope = {}
    for key, record in index.nodes.items():
        node = snapshot.nodes[str(key.host_uid)]
        parent = str(record.parent.host_uid) if record.parent else ""
        domain = "layers" if record.domain == "layer" else record.domain
        if (record.kind, domain, parent) != (node.kind, node.scope[1], node.scope[0]):
            return "Dependency hierarchy is stale; refresh before moving"
        records_by_scope.setdefault(node.scope, []).append(record)
    for scope, records in records_by_scope.items():
        if (len({record.order for record in records}) != len(records) or
                tuple(str(record.key.host_uid) for record in sorted(records, key=lambda record: record.order)) !=
                tuple(snapshot.chains.get(scope, ()))):
            return "Dependency order is stale; refresh before moving"
    if index.anchors or index.references or any(node.kind == "AnchorPointEffect" for node in snapshot.nodes.values()):
        return "Anchor evaluation eligibility is not host-validated; reorder in Painter"
    return ""


def command_intent(snapshot, selected, command):
    """Shared menu/keyboard semantics; selection click order never controls stacking."""
    roots = selection_roots(snapshot, selected)
    source = snapshot.nodes[roots[0]].scope
    if any(snapshot.nodes[uid].scope != source for uid in roots):
        raise ValueError("Move selection must belong to one native scope")
    chain = snapshot.members(source)
    chosen = set(roots)
    positions = [i for i, uid in enumerate(chain) if uid in chosen]
    if not positions or len(positions) != len(chosen):
        raise ValueError("Selected node is missing from its native chain; refresh")
    if command in ("start", "end"):
        return MoveIntent(snapshot.context, roots, source, command)
    if command not in ("earlier", "later"):
        raise ValueError("Unknown order command")
    candidates = chain[:min(positions)] if command == "earlier" else chain[max(positions) + 1:]
    if not candidates:
        # Already at this boundary. Preserve a no-op even for scattered selections.
        raise ValueError("Selection is already at the evaluation boundary")
    target = candidates[-1] if command == "earlier" else candidates[0]
    return MoveIntent(snapshot.context, roots, source, "before" if command == "earlier" else "after", target)