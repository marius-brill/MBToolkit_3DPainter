"""Pure ordering contracts and fail-closed host boundary; no invented move API."""
from dataclasses import FrozenInstanceError, replace
from itertools import combinations, permutations

import pytest

from layer_graph_fixtures import Host
from MBToolkit_3DPainter.features.layer_graph.model import ROOT, TYPES, Layout
from MBToolkit_3DPainter.features.layer_graph.ordering import (
    MoveIntent, NATIVE_MOVE, command_intent, dependency_reason, plan_move, revalidate_move, selection_roots,
)
from MBToolkit_3DPainter.features.anchor_manager.models import Coverage, GraphIndex, NodeKey, NodeRecord


def create(host, kind="fill", scope=ROOT):
    return host.adapter.create(TYPES[kind], host.adapter.context(), scope)


def intent(snapshot, selected, placement="start", target=None, destination=ROOT):
    return MoveIntent(snapshot.context, tuple(selected), destination, placement, target)


def test_exhaustive_same_chain_placements_preserve_ids_relative_order_and_snapshot():
    host = Host()
    ids = [create(host) for _ in range(4)]
    snapshot = host.adapter.scan()
    native = tuple(snapshot.chains[ROOT])
    count = 0
    for size in range(1, 5):
        for selected in combinations(ids, size):
            for clicked in permutations(selected):
                moved = tuple(uid for uid in native if uid in selected)
                remaining = tuple(uid for uid in native if uid not in selected)
                targets = [("start", None, len(remaining)), ("end", None, 0)]
                targets += [(placement, uid, i + (placement == "before"))
                            for i, uid in enumerate(remaining) for placement in ("before", "after")]
                for placement, target, index in targets:
                    plan = plan_move(snapshot, intent(snapshot, clicked, placement, target))
                    expected = remaining[:index] + moved + remaining[index:]
                    assert plan.moved == moved
                    assert plan.destination_after == expected
                    assert plan.source_after == expected
                    assert plan.noop == (expected == native)
                    assert len(expected) == len(set(expected)) == 4
                    assert revalidate_move(snapshot, plan) == plan
                    count += 1
    assert count > 200
    assert tuple(snapshot.chains[ROOT]) == native
    assert [str(node.uid()) for node in host.roots] == list(native)


def test_relative_commands_use_evaluation_not_click_or_screen_order():
    host = Host()
    a, b, c, d = [create(host) for _ in range(4)]
    snapshot = host.adapter.scan()
    earlier = plan_move(snapshot, command_intent(snapshot, (c, b), "earlier"))
    assert earlier.moved == (c, b)
    assert earlier.destination_after == (d, a, c, b)
    later = plan_move(snapshot, command_intent(snapshot, (c, b), "later"))
    assert later.destination_after == (c, b, d, a)
    for selected, command in (((a,), "earlier"), ((d,), "later")):
        with pytest.raises(ValueError, match="boundary"):
            command_intent(snapshot, selected, command)
    with pytest.raises(ValueError, match="Unknown"):
        command_intent(snapshot, (b,), "invalid")


def test_batch_reparent_preserves_order_and_selected_group_descendants_are_not_moved_twice():
    host = Host()
    group = create(host, "group")
    child = create(host, scope=(group, "layers"))
    effect = create(host, "levels", (child, "content"))
    a, b = create(host), create(host)
    snapshot = host.adapter.scan()
    plan = plan_move(snapshot, intent(snapshot, (a, b), "start", destination=(group, "layers")))
    assert plan.moved == (b, a)
    assert plan.source_after == (group,)
    assert plan.destination_after == (child, b, a)
    assert snapshot.nodes[a].scope == ROOT
    assert selection_roots(snapshot, (effect, child, group, group)) == (group,)
    plan = plan_move(snapshot, intent(snapshot, (group, child, effect), "end"))
    assert plan.moved == (group,)
    out = plan_move(snapshot, intent(snapshot, (child,), "after", a))
    assert out.source_after == ()
    assert out.destination_after == (b, child, a, group)


def test_invalid_inputs_domains_cycles_and_targets_are_rejected():
    host = Host()
    group = create(host, "group")
    nested = create(host, "group", (group, "layers"))
    child = create(host, scope=(nested, "layers"))
    layer = create(host)
    effect = create(host, "levels", (layer, "content"))
    host.adapter.create(TYPES["black"], host.adapter.context(), ROOT, layer)
    snapshot = host.adapter.scan()
    cases = [
        ((), "start", None, ROOT, "Select"),
        (("@input",), "start", None, ROOT, "virtual"),
        ((layer, child), "start", None, ROOT, "one native scope"),
        ((group,), "start", None, (nested, "layers"), "descendants"),
        ((group,), "start", None, (group, "layers"), "itself"),
        ((effect,), "start", None, (layer, "mask"), "Effects cannot transfer"),
        ((layer,), "start", None, (layer, "content"), "Effects cannot transfer"),
        ((layer,), "before", layer, ROOT, "part of"),
        ((layer,), "after", "999", ROOT, "deleted or moved"),
        ((layer,), "end", group, ROOT, "must not specify"),
        ((layer,), "bad", None, ROOT, "Unknown"),
        ((layer,), "start", None, ("999", "layers"), "no longer exists"),
    ]
    for selected, placement, target, destination, message in cases:
        with pytest.raises(ValueError, match=message):
            plan_move(snapshot, intent(snapshot, selected, placement, target, destination))
    with pytest.raises(ValueError, match="changed"):
        plan_move(snapshot, replace(intent(snapshot, (layer,)), context=None))
    snapshot.nodes[group].scope = (nested, "layers")
    with pytest.raises(ValueError, match="cyclic"):
        selection_roots(snapshot, (child,))


def test_effect_chain_moves_and_noops():
    host = Host()
    layer = create(host)
    a, b = [create(host, "levels", (layer, "content")) for _ in range(2)]
    snapshot = host.adapter.scan()
    plan = plan_move(snapshot, intent(snapshot, (b,), "before", a, (layer, "content")))
    assert plan.destination_after == (a, b)
    assert not plan.noop
    assert plan_move(snapshot, intent(snapshot, (a,), "start", destination=(layer, "content"))).noop


def test_immutable_plan_stale_context_chain_subtree_and_mask_changes():
    host = Host()
    a, b = create(host), create(host)
    snapshot = host.adapter.scan()
    plan = plan_move(snapshot, intent(snapshot, (a,), "end"))
    with pytest.raises(FrozenInstanceError):
        plan.moved = (b,)
    host.roots.reverse()
    with pytest.raises(ValueError, match="changed"):
        revalidate_move(host.adapter.scan(), plan)
    host.roots.reverse()
    create(host, "levels", (b, "content"))
    with pytest.raises(ValueError, match="changed"):
        revalidate_move(host.adapter.scan(), plan)
    fresh = host.adapter.scan()
    plan = plan_move(fresh, intent(fresh, (a,), "end"))
    host.nodes[int(b)].add_mask(host.sp.layerstack.MaskBackground.Black)
    with pytest.raises(ValueError, match="changed"):
        revalidate_move(host.adapter.scan(), plan)
    host.epoch += 1
    with pytest.raises(ValueError, match="changed"):
        revalidate_move(host.adapter.scan(), plan)


def test_corrupt_native_chain_is_not_interpreted_as_a_move():
    host = Host()
    a = create(host)
    snapshot = host.adapter.scan()
    snapshot.chains[ROOT].append(a)
    with pytest.raises(ValueError, match="Inconsistent"):
        plan_move(snapshot, intent(snapshot, (a,)))
    snapshot.chains[ROOT] = []
    with pytest.raises(ValueError, match="missing"):
        plan_move(snapshot, intent(snapshot, (a,)))


def test_backend_gate_cannot_be_enabled_by_plausible_method_names(monkeypatch):
    host = Host()
    a, b = create(host), create(host)
    for name in ("move", "move_node", "move_nodes", "reorder", "reparent"):
        monkeypatch.setattr(host.sp.layerstack, name, lambda *args: pytest.fail("Unverified API invoked"), raising=False)
    snapshot = host.adapter.scan()
    assert host.adapter.move_capability() == NATIVE_MOVE
    assert not any((NATIVE_MOVE.same_chain, NATIVE_MOVE.batch, NATIVE_MOVE.reparent))
    plan = host.adapter.preview_move(intent(snapshot, (a,), "end"))
    with pytest.raises(ValueError, match="No verified"):
        host.adapter.move(plan)
    assert [str(node.uid()) for node in host.roots] == [b, a]
    noop = host.adapter.preview_move(intent(snapshot, (a,), "start"))
    assert host.adapter.move(noop) is False
    host.busy = True
    with pytest.raises(ValueError, match="busy"):
        host.adapter.move(plan)


def test_native_multiselection_is_ordered_and_mixed_scope_failure_preserves_selection():
    host = Host()
    a, b, group = create(host), create(host), create(host, "group")
    child = create(host, scope=(group, "layers"))
    context = host.adapter.context()
    assert host.adapter.navigate_many((a, b), context) == (b, a)
    assert [str(node.uid()) for node in host.selected] == [b, a]
    with pytest.raises(ValueError, match="one native scope"):
        host.adapter.navigate_many((a, child), context)
    assert [str(node.uid()) for node in host.selected] == [b, a]
    assert host.adapter.navigate_many((child, group), context) == (group,)
    host.epoch += 1
    with pytest.raises(ValueError, match="changed"):
        host.adapter.navigate_many((a,), context)


def test_dependency_gate_rejects_unknown_stale_and_anchor_discovery():
    host = Host()
    a = create(host)
    create(host)
    snapshot = host.adapter.scan()
    plan = plan_move(snapshot, intent(snapshot, (a,), "end"))
    assert "incomplete" in dependency_reason(snapshot, plan, None)
    index = GraphIndex(finished=True, coverage=Coverage.COMPLETE)
    assert "stale" in dependency_reason(snapshot, plan, index)
    for uid, node in snapshot.nodes.items():
        key = NodeKey(*snapshot.context, int(uid))
        index.nodes[key] = NodeRecord(key, node.name, (), node.kind, "layer", None, snapshot.chains[ROOT].index(uid))
    assert not dependency_reason(snapshot, plan, index)
    records = list(index.nodes.values())
    records[0].order, records[1].order = records[1].order, records[0].order
    assert "order is stale" in dependency_reason(snapshot, plan, index)
    records[0].order, records[1].order = records[1].order, records[0].order
    index.gaps.append("Unreadable procedural input")
    assert "incomplete" in dependency_reason(snapshot, plan, index)
    index.gaps.clear()
    index.references["unknown"] = object()
    assert "not host-validated" in dependency_reason(snapshot, plan, index)
    index.references.clear()
    index.nodes[next(iter(index.nodes))].domain = "mask"
    assert "stale" in dependency_reason(snapshot, plan, index)
    noop = plan_move(snapshot, intent(snapshot, (a,), "start"))
    assert not dependency_reason(snapshot, noop, None)


def test_arrange_resets_only_current_scope_positions_without_material_changes():
    host = Host()
    a = create(host)
    layout = Layout()
    layout.positions[(ROOT, a)] = (1000, -30)
    layout.positions[((a, "content"), "@input")] = (40, 50)
    layout.expanded.add(a)
    frame = layout.frame(ROOT, [a])
    snapshot = host.adapter.scan()
    layout.arrange(ROOT)
    assert layout.positions == {((a, "content"), "@input"): (40, 50)}
    assert layout.expanded == {a} and frame.id in layout.frames
    assert host.adapter.scan() == snapshot