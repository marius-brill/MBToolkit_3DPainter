import pytest
from layer_graph_fixtures import Host, Position, Background, Blend
from MBToolkit_3DPainter.features.layer_graph.model import Layout, ROOT, TYPES, search, eligibility, connection_reason


def create(host, kind, scope=ROOT, selected=None, resource=None):
    return host.adapter.create(TYPES[kind], host.adapter.context(), scope, selected, resource)


def test_catalog_and_context_rules():
    host = Host()
    assert search("folder")[0].id == "group"
    assert search("edge wear")[0].id == "generator"
    assert search("black mask")[0].id == "black"
    assert not search("nonexistent")
    snapshot = host.adapter.scan()
    assert eligibility(TYPES["levels"], snapshot, ROOT)
    assert eligibility(TYPES["black"], snapshot, ROOT)
    host.opened = False
    assert "editable" in eligibility(TYPES["fill"], host.adapter.scan(), ROOT)


def test_group_children_use_substack_and_preserve_order():
    host = Host()
    group = create(host, "group")
    a = create(host, "fill", (group, "layers"))
    assert host.last_position[0] == "layers"
    b = create(host, "paint", (group, "layers"), a)
    snapshot = host.adapter.scan()
    assert snapshot.members(ROOT) == [group]
    assert snapshot.members((group, "layers")) == [a, b]
    assert snapshot.nodes[a].scope == (group, "layers")
    assert snapshot.valid_scope((group, "layers"))
    assert not snapshot.valid_scope((a, "layers"))


def test_black_mask_effects_and_never_replace():
    host = Host()
    layer = create(host, "fill")
    assert create(host, "black", selected=layer) == layer
    assert host.selection_type == "mask"
    assert host.nodes[int(layer)].background is Background.Black
    generator = create(host, "generator", (layer, "mask"), resource="generator-resource")
    levels = create(host, "levels", (layer, "mask"), generator)
    snapshot = host.adapter.scan()
    assert snapshot.members((layer, "mask")) == [generator, levels]
    assert snapshot.nodes[layer].mask == "Black"
    with pytest.raises(ValueError, match="already has a mask"):
        create(host, "white", selected=layer)
    assert snapshot.nodes[levels].scope == (layer, "mask")
    with pytest.raises(ValueError, match="mask graph"):
        create(host, "compare", (layer, "content"))


def test_failed_bitmap_removes_only_new_mask():
    host = Host()
    layer = create(host, "paint")
    host.fail_source = True
    with pytest.raises(RuntimeError, match="source failed"):
        create(host, "bitmap", selected=layer, resource="image")
    assert not host.nodes[int(layer)].has_mask()
    assert host.adapter.scan().members(ROOT) == [layer]
    assert len(host.nodes) == 1


def test_stale_context_busy_deleted_and_resource_validation():
    host = Host()
    layer = create(host, "fill")
    context = host.adapter.context()
    host.epoch += 1
    with pytest.raises(ValueError, match="changed"):
        host.adapter.rename(layer, context, "Old project")
    host.busy = True
    with pytest.raises(ValueError, match="busy"):
        create(host, "paint")
    host.busy = False
    with pytest.raises(ValueError, match="resource"):
        create(host, "filter", (layer, "content"))
    host.delete(host.nodes[int(layer)])
    with pytest.raises(ValueError, match="no longer exists"):
        create(host, "levels", (layer, "content"))


def test_real_adapter_rename_visibility_blending_navigation_delete():
    host = Host()
    uid = create(host, "fill")
    context = host.adapter.context()
    host.adapter.rename(uid, context, "Metal")
    host.adapter.visibility(uid, context, False)
    assert host.adapter.blending(uid, context) == [("BaseColor", 1., Blend.Normal)]
    host.adapter.set_blending(uid, context, "BaseColor", .42, Blend.Multiply)
    assert host.adapter.blending(uid, context) == [("BaseColor", .42, Blend.Multiply)]
    host.adapter.navigate(uid, context)
    assert host.selected == [host.nodes[int(uid)]]
    assert host.selection_type == "content"
    assert host.adapter.scan().nodes[uid].name == "Metal"
    assert not host.adapter.scan().nodes[uid].visible
    host.adapter.delete(uid, context)
    assert not host.adapter.scan().nodes


@pytest.mark.parametrize("visible", [True, False])
def test_disconnect_reconnect_preserves_visibility_and_changes_host(visible):
    host = Host()
    a, b, c = (create(host, "fill") for _ in range(3))
    adapter, context = host.adapter, host.adapter.context()
    adapter.visibility(b, context, visible)
    adapter.disconnect(b, context)
    adapter.disconnect(b, context)
    assert not host.nodes[int(b)].visible
    assert adapter.scan().nodes[b].disconnected
    adapter.reconnect(b, c, "output", context, ROOT)
    assert host.nodes[int(b)].visible is visible
    assert not adapter.scan().nodes[b].disconnected
    assert adapter.scan().members(ROOT) == [a, b, c]


def test_connection_validation_and_native_enable_override():
    host = Host()
    a, b, c = (create(host, "fill") for _ in range(3))
    adapter, context = host.adapter, host.adapter.context()
    adapter.disconnect(b, context)
    for target, side, message in [(a, "output", "reordering"), (b, "input", "itself"),
                                  ("@output", "input", "same"), (c, "invalid", "direction")]:
        with pytest.raises(ValueError, match=message):
            adapter.reconnect(b, target, side, context, ROOT)
        assert adapter.scan().nodes[b].disconnected
    adapter.reconnect(b, a, "input", context, ROOT)
    adapter.disconnect(b, context)
    host.nodes[int(b)].set_visible(True)
    assert not adapter.scan().nodes[b].disconnected
    adapter.disconnect(b, context)
    host.epoch += 1
    with pytest.raises(ValueError, match="changed"):
        adapter.reconnect(b, a, "input", context, ROOT)
    assert not adapter.scan().nodes[b].disconnected


def test_disconnected_boundary_and_scope_rules():
    host = Host()
    layer = create(host, "fill")
    other = create(host, "fill")
    effect = create(host, "levels", (layer, "content"))
    adapter, context = host.adapter, host.adapter.context()
    adapter.disconnect(effect, context)
    with pytest.raises(ValueError, match="same"):
        adapter.reconnect(effect, other, "input", context, (layer, "content"))
    adapter.reconnect(effect, "@input", "input", context, (layer, "content"))
    adapter.disconnect(effect, context)
    adapter.reconnect(effect, "@output", "output", context, (layer, "content"))
    adapter.disconnect(effect, context)
    adapter.visibility(effect, context, False)
    assert not adapter.scan().nodes[effect].disconnected


def test_layout_prunes_deleted_nodes_and_frames_without_host_changes():
    host = Host()
    a, b = create(host, "fill"), create(host, "paint")
    layout = Layout()
    frame = layout.frame(ROOT, [a, b], "Surface")
    layout.positions[(ROOT, a)] = (100, 200)
    layout.expanded.add(a)
    with pytest.raises(ValueError, match="only one"):
        layout.frame(ROOT, [a])
    frame.collapsed = True
    assert host.adapter.scan().members(ROOT) == [a, b]
    host.delete(host.nodes[int(a)])
    layout.prune(host.adapter.scan())
    assert frame.members == [b]
    assert not layout.expanded and not layout.positions
    host.delete(host.nodes[int(b)])
    layout.prune(host.adapter.scan())
    assert not layout.frames


def test_instance_and_presets_are_real_host_operations():
    host = Host()
    layer = create(host, "paint")
    instance = create(host, "instance", selected=layer)
    assert host.adapter.scan().nodes[instance].kind == "InstanceLayer"
    material = create(host, "smart_material", resource="preset")
    assert host.adapter.scan().nodes[material].group
    create(host, "white", selected=layer)
    mask = create(host, "smart_mask", (layer, "mask"), resource="preset")
    assert host.adapter.scan().nodes[mask].kind == "GeneratorEffect"
    assert host.adapter.scan().nodes[layer].mask == "White"
    # An unreadable hierarchy must not produce a partial editable graph.
    host.nodes[int(layer)].content_effects = lambda: (_ for _ in ()).throw(RuntimeError("unreadable"))
    with pytest.raises(RuntimeError, match="unreadable"):
        host.adapter.scan()


def test_missing_host_operation_is_explained():
    host = Host()
    del host.sp.layerstack.insert_group
    assert "does not expose" in host.adapter.reason(TYPES["group"], host.adapter.scan(), ROOT, None)
    assert Position.from_textureset_stack(host.stack)[0] == "root"


def test_deleted_insertion_target_never_falls_back_to_stack_top():
    host = Host()
    layer = create(host, "fill")
    host.delete(host.nodes[int(layer)])
    with pytest.raises(ValueError, match="insertion target"):
        create(host, "paint", selected=layer)
    assert not host.nodes


def test_native_insertion_splits_and_expands_collapsed_frame():
    host = Host()
    a, b = create(host, "fill"), create(host, "paint")
    layout = Layout()
    frame = layout.frame(ROOT, [a, b])
    frame.collapsed = True
    create(host, "fill", selected=a)
    layout.prune(host.adapter.scan())
    assert not frame.collapsed
    assert frame.members == [a, b]


def test_noniterable_pybind_style_blend_enum():
    host = Host()
    class Modes:
        pass
    Modes.Normal = Modes()
    Modes.Multiply = Modes()
    host.sp.layerstack.BlendingMode = Modes
    assert set(host.adapter.blend_modes()) == {Modes.Normal, Modes.Multiply}
    host.sp.layerstack.BlendingMode = Blend
    assert host.adapter.blend_modes() == [Blend.Normal, Blend.Multiply]


def test_creation_selection_is_outside_modification_scope():
    host = Host()
    layer = create(host, "fill")
    assert host.selected == [host.nodes[int(layer)]]
    create(host, "black", selected=layer)
    assert host.selection_type == "mask"
    effect = create(host, "levels", (layer, "mask"))
    assert host.selected == [host.nodes[int(effect)]]
    assert host.modification_depth == 0
    with host.transaction("Enforce native selection restriction"):
        with pytest.raises(RuntimeError, match="Selection forbidden"):
            host.sp.layerstack.set_selected_nodes([])
        with pytest.raises(RuntimeError, match="Selection forbidden"):
            host.sp.layerstack.set_selection_type(host.nodes[int(layer)], "content")
    assert host.modification_depth == 0


def test_snapshot_preview_has_no_host_access_and_commit_rejects_native_reorder(monkeypatch):
    host = Host()
    a, b, c = (create(host, "fill") for _ in range(3))
    adapter, context = host.adapter, host.adapter.context()
    adapter.disconnect(b, context)
    snapshot = adapter.scan()
    with monkeypatch.context() as patch:
        patch.setattr(adapter, "scan", lambda: pytest.fail("Preview scanned Painter"))
        patch.setattr(adapter, "context", lambda: pytest.fail("Preview queried Painter"))
        for _ in range(100):
            assert not connection_reason(snapshot, b, c, "output", context, ROOT)
        assert "reordering" in connection_reason(snapshot, b, a, "output", context, ROOT)
        assert "changed" in connection_reason(snapshot, b, c, "output", None, ROOT)
    # The preview is advisory: native changes after capture must be caught at commit.
    host.roots[:] = [host.nodes[int(b)], host.nodes[int(c)], host.nodes[int(a)]]
    with pytest.raises(ValueError, match="reordering"):
        adapter.reconnect(b, c, "output", context, ROOT)
    assert not host.nodes[int(b)].visible
    assert b in adapter.disconnected


def test_native_reparent_prunes_old_frame_membership_without_losing_unrelated_layout():
    host = Host()
    a, b, group = create(host, "fill"), create(host, "paint"), create(host, "group")
    layout = Layout()
    frame = layout.frame(ROOT, [a, b])
    layout.positions[(ROOT, b)] = (123, 456)
    node = host.nodes[int(a)]
    host.roots.remove(node)
    node.parent = host.nodes[int(group)]
    node.parent.children.append(node)
    snapshot = host.adapter.scan()
    layout.prune(snapshot)
    assert snapshot.nodes[a].scope == (group, "layers")
    assert snapshot.members((group, "layers")) == [a]
    assert frame.members == [b]
    assert layout.positions[(ROOT, b)] == (123, 456)