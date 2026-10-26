"""Port-to-native-order semantics, independent of native UI automation."""
import pytest
from MBToolkit_3DPainter.features.layer_graph.model import Node, Snapshot, ROOT
from MBToolkit_3DPainter.features.layer_graph.ordering import connection_move, ui_move_reason


def snapshot():
    result = Snapshot((1, "texture", "stack"))
    result.nodes = {uid: Node(uid, uid, "FillLayer", ROOT) for uid in "cba"}
    result.chains[ROOT] = list("cba")
    return result


@pytest.mark.parametrize("uid,target,side,expected", [
    ("c", "b", "output", "bca"),
    ("a", "b", "input", "cab"),
    ("a", "@output", "output", "acb"),
    ("c", "@input", "input", "bac"),
    ("b", "c", "output", "cba"),
    ("b", "a", "input", "cba"),
])
def test_drop_splices_chain_without_changing_snapshot(uid, target, side, expected):
    current = snapshot()
    plan = connection_move(current, uid, target, side, current.context, ROOT)
    assert plan.destination_after == tuple(expected)
    assert current.chains[ROOT] == list("cba")
    assert not ui_move_reason(current, plan)


@pytest.mark.parametrize("target,side,reason", [
    ("a", "output", "itself"), ("missing", "input", "same stack"),
    ("@output", "input", "same stack"), ("b", "wrong", "direction"),
])
def test_bad_drop_rejected(target, side, reason):
    current = snapshot()
    with pytest.raises(ValueError, match=reason):
        connection_move(current, "a", target, side, current.context, ROOT)


def test_unsafe_ui_scope_dependencies_and_ambiguous_names():
    current = snapshot()
    plan = connection_move(current, "a", "@output", "output", current.context, ROOT)
    current.nodes["b"].name = "a"
    assert "unique names" in ui_move_reason(current, plan)
    current.nodes["b"].name = "b"
    current.nodes["b"].kind = "GroupLayer"
    assert "no folders" in ui_move_reason(current, plan)
    current.nodes["b"].kind = "AnchorPointEffect"
    assert "Anchor" in ui_move_reason(current, plan)


def test_stale_and_disconnected_targets():
    current = snapshot()
    with pytest.raises(ValueError, match="changed"):
        connection_move(current, "a", "b", "input", None, ROOT)
    current.nodes["b"].disconnected = True
    with pytest.raises(ValueError, match="Reconnect"):
        connection_move(current, "a", "b", "input", current.context, ROOT)


def test_unreliable_ui_bridge_requires_explicit_opt_in(monkeypatch):
    from types import SimpleNamespace
    from MBToolkit_3DPainter.features.layer_graph import native_drag
    sp = SimpleNamespace(application=SimpleNamespace(version_info=lambda: (11, 0, 3)))
    monkeypatch.setattr(native_drag.sys, "platform", "win32")
    monkeypatch.delenv("MBTOOLKIT_EXPERIMENTAL_REORDER", raising=False)
    assert not native_drag.available(sp)
    monkeypatch.setenv("MBTOOLKIT_EXPERIMENTAL_REORDER", "1")
    assert native_drag.available(sp)
    sp.application.version_info = lambda: (11, 1, 0)
    assert not native_drag.available(sp)