"""Pure planning and action-boundary tests for the opt-in effect prototype."""
from types import SimpleNamespace

import pytest

from layer_graph_fixtures import Host
from MBToolkit_3DPainter.features.layer_graph import native_effect_order as backend
from MBToolkit_3DPainter.features.layer_graph.model import ROOT, TYPES
from MBToolkit_3DPainter.features.layer_graph.ordering import MoveIntent, plan_move


def setup_chain():
    host = Host()
    owner = host.adapter.create(TYPES["paint"], host.adapter.context(), ROOT)
    scope = (owner, "content")
    for _ in range(5):
        host.adapter.create(TYPES["levels"], host.adapter.context(), scope)
    snapshot = host.adapter.scan()
    return host, snapshot, scope, snapshot.chains[scope]


def plan(snapshot, scope, uid, placement, target=None):
    return plan_move(snapshot, MoveIntent(snapshot.context, (uid,), scope, placement, target))


@pytest.mark.parametrize("source,placement,target,label", [
    (4, "end", None, "Move effect(s) to top"),
    (0, "start", None, "Move effect(s) to bottom"),
    (2, "after", 1, "Move effect(s) up"),
    (2, "before", 3, "Move effect(s) down"),
])
def test_one_action_semantics(source, placement, target, label):
    _, snapshot, scope, chain = setup_chain()
    move = plan(snapshot, scope, chain[source], placement, chain[target] if target is not None else None)
    assert backend.command(snapshot, move) == label


def test_rejects_interior_jump_layers_anchors_and_stale_structure():
    host, snapshot, scope, chain = setup_chain()
    with pytest.raises(ValueError, match="single steps"):
        backend.command(snapshot, plan(snapshot, scope, chain[4], "after", chain[1]))
    owner = scope[0]
    host.adapter.create(TYPES["paint"], snapshot.context, ROOT)
    fresh = host.adapter.scan()
    with pytest.raises(ValueError, match="only moves effects"):
        backend.command(fresh, plan(fresh, ROOT, owner, "end"))
    move = plan(snapshot, scope, chain[4], "end")
    snapshot.nodes[chain[0]].kind = "AnchorPointEffect"
    with pytest.raises(ValueError, match="changed"):
        backend.command(snapshot, move)
    with pytest.raises(ValueError, match="Anchor"):
        backend.command(snapshot, plan(snapshot, scope, chain[4], "end"))


def test_gate_noop_and_failed_verification(monkeypatch):
    host, snapshot, scope, chain = setup_chain()
    monkeypatch.delenv("MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER", raising=False)
    sp = SimpleNamespace(application=SimpleNamespace(version_info=lambda: (11, 0, 3)))
    assert not backend.available(sp)
    monkeypatch.setenv("MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER", "1")
    assert backend.available(sp)
    sp.application.version_info = lambda: (11, 1, 0)
    assert not backend.available(sp)
    monkeypatch.setattr(backend, "available", lambda sp: True)
    assert backend.move(host.adapter, plan(snapshot, scope, chain[0], "end")) is False
    calls = []
    monkeypatch.setattr(backend, "_action", lambda sp, label: SimpleNamespace(trigger=lambda: calls.append(label)))
    with pytest.raises(ValueError, match="did not match"):
        backend.move(host.adapter, plan(snapshot, scope, chain[-1], "end"))
    assert calls == ["Move effect(s) to top"]


def test_successful_move_verifies_native_identity(monkeypatch):
    host, snapshot, scope, chain = setup_chain()
    move = plan(snapshot, scope, chain[-1], "end")
    monkeypatch.setattr(backend, "available", lambda sp: True)

    def trigger():
        effects = host.nodes[int(scope[0])].effects
        effects.insert(0, effects.pop())

    monkeypatch.setattr(backend, "_action", lambda sp, label: SimpleNamespace(trigger=trigger))
    assert backend.move(host.adapter, move)
    assert tuple(host.adapter.scan().chains[scope]) == move.destination_after