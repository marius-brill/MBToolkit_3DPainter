from dataclasses import replace
import pytest
from anchor_fixtures import FakeHost, Node, Reference, Substance, Channel
from MBToolkit_3DPainter.features.anchor_manager.discovery import collect, Discovery
from MBToolkit_3DPainter.features.anchor_manager.index import search, rebuild, layout
from MBToolkit_3DPainter.features.anchor_manager.models import Coverage, Status
from MBToolkit_3DPainter.features.anchor_manager.operations import Operations, eligibility
from MBToolkit_3DPainter.core.models import clean_config


def test_recursive_discovery_duplicate_names_and_per_slot_edges():
    host = FakeHost()
    mask_anchor = Node(host, 6, "Mask anchor", "AnchorPointEffect", host.layer, "mask")
    host.layer.mask = [mask_anchor]
    index = collect(host.adapter)
    assert len(index.anchors) == 3
    assert len(index.references) == 2
    assert index.anchors[host.adapter.key(host.anchor)].use_count_known == 2
    assert len({s.consumer for s in index.references}) == 1
    assert len({s.channel for s in index.references}) == 2
    assert any("Mask" in a.node.path for a in index.anchors.values())
    assert sum(i.code == "DUPLICATE_ANCHOR_NAME" for i in index.issues) == 2
    assert index.coverage is Coverage.COMPLETE
    assert index.is_unused(host.adapter.key(host.alternative))


def test_partial_never_unused_and_generator_image_inputs_are_scanned():
    host = FakeHost()
    generator = Node(host, 6, "Generator", "GeneratorEffect", host.layer, "mask")
    generator.sources[None] = Substance({"mask": Reference(host.alternative)})
    host.layer.mask = [generator]
    index = collect(host.adapter)
    assert index.coverage is Coverage.PARTIAL
    assert len(index.references) == 3
    assert next(r for r in index.references.values() if r.slot.source_path).writable is False
    assert search(index, mode="Unused") == []
    assert all("known" in a.usage_label for a in index.anchors.values())


def test_unobservable_is_not_broken_but_explicit_dangling_is():
    host = FakeHost()
    class Unreadable:
        def __call__(self, *args):
            raise RuntimeError("source inaccessible")
    host.consumer.get_source = Unreadable()
    index = collect(host.adapter)
    assert index.coverage is Coverage.PARTIAL
    assert not any(i.code == "CONFIRMED_BROKEN_REFERENCE" for i in index.issues)
    host.consumer.get_source = lambda channel: Reference(None)
    index = collect(host.adapter)
    assert all(r.status is Status.BROKEN for r in index.references.values())


def test_rename_search_refresh_and_stale_session():
    host = FakeHost()
    index = collect(host.adapter)
    key = host.adapter.key(host.anchor)
    result = Operations(host.adapter).rename(index, key, "  Scratch  ")
    assert search(result.index, "scratch")[0].key == key
    assert not any(i.code == "DUPLICATE_ANCHOR_NAME" for i in result.index.issues)
    host.epoch += 1
    with pytest.raises(ValueError, match="STALE_NODE"):
        host.adapter.resolve(key, True)


def test_replace_preflight_mapping_preservation_failure_and_batch():
    host = FakeHost()
    index = collect(host.adapter)
    ops = Operations(host.adapter)
    target = host.adapter.key(host.alternative)
    previews = ops.preview(index, list(index.references), target)
    assert all(p.eligible for p in previews)
    result = ops.replace(index, previews)
    assert result.completed == 2
    assert not result.failed
    assert all(r.anchor_key == target for r in result.index.references.values())
    assert host.consumer.sources[Channel.BaseColor].levels == (.1, .8)
    assert host.consumer.sources[Channel.BaseColor].alpha_matte == "preserve-alpha"
    previews = ops.preview(result.index, list(result.index.references), host.adapter.key(host.anchor))
    host.fail = True
    failed = ops.replace(result.index, previews)
    assert failed.completed == 0 and len(failed.failed) == 2
    assert all(r.anchor_key == target for r in failed.index.references.values())


def test_preflight_rejects_cross_stack_missing_and_unknown_order():
    host = FakeHost()
    index = collect(host.adapter)
    slot = next(iter(index.references))
    key = host.adapter.key(host.alternative)
    other_key = replace(key, texture_set_key="Other")
    index.anchors[other_key] = replace(index.anchors[key], node=replace(index.nodes[key], key=other_key))
    assert not eligibility(index, slot, other_key)[0]
    assert not eligibility(index, replace(slot, slot_id="missing"), key)[0]
    host.alternative.parent = host.group
    host.layer.effects.remove(host.alternative)
    host.group.effects.append(host.alternative)
    index = collect(host.adapter)
    assert not eligibility(index, slot, key)[0]


def test_deletion_only_complete_unused_rechecks_host():
    host = FakeHost()
    index = collect(host.adapter)
    key = host.adapter.key(host.alternative)
    # A native edit after the preview adds a consumer; fresh preflight blocks deletion.
    host.consumer.sources[Channel.BaseColor] = Reference(host.alternative)
    with pytest.raises(ValueError, match="Deletion blocked"):
        Operations(host.adapter).delete(index, key)
    host.consumer.sources[Channel.BaseColor] = Reference(host.anchor)
    result = Operations(host.adapter).delete(collect(host.adapter), key)
    assert result.completed == 1 and key not in result.index.anchors


def test_binding_changes_during_modal_and_uid_reuse_are_rejected():
    host = FakeHost()
    index = collect(host.adapter)
    ops = Operations(host.adapter)
    previews = ops.preview(index, list(index.references), host.adapter.key(host.alternative))
    host.consumer.sources[Channel.BaseColor] = Reference(host.alternative)
    result = ops.replace(index, previews)
    assert result.completed == 1 and result.skipped
    host.anchor.name = "New object with reused UID"
    with pytest.raises(ValueError, match="STALE_NODE"):
        ops.rename(index, host.adapter.key(host.anchor), "Should not rename")


def test_scan_incremental_and_context_change_abandons():
    host = FakeHost()
    scan = Discovery(host.adapter)
    steps = scan.steps()
    next(steps)
    assert not scan.index.finished
    rebuild(scan.index)
    assert not search(scan.index, mode="Unused")
    host.epoch += 1
    with pytest.raises(ValueError, match="abandoned"):
        list(steps)


def test_large_layout_is_deterministic_separated_and_bounded():
    host = FakeHost()
    for i in range(100):
        anchor = Node(host, 1000 + i, f"A{i}", "AnchorPointEffect", host.layer)
        host.layer.effects.append(anchor)
        for j in range(5):
            consumer = Node(host, 2000 + i * 5 + j, f"C{i}-{j}", "FillLayer", host.group)
            consumer.sources[None] = Reference(anchor)
            host.group.layers.append(consumer)
    index = collect(host.adapter)
    positions = layout(index)
    assert positions == layout(index)
    assert len(set(positions.values())) == len(positions)
    assert len(positions) <= 1000


def test_settings_persist_only_valid_ui_state():
    cfg = clean_config({"anchor_manager": {"filter": "Unused", "splitter": [200, 500, 250],
                                            "host_uid": 123, "auto_refresh": False}})
    assert clean_config(cfg) == cfg
    assert "host_uid" not in cfg["anchor_manager"]
    assert cfg["anchor_manager"]["filter"] == "Unused"
    assert cfg["features"]["anchor_manager"]["enabled"] is False


def test_create_requires_stable_target_and_valid_location():
    host = FakeHost()
    index = collect(host.adapter)
    key = host.adapter.key(host.layer)
    result = Operations(host.adapter).create(index, key, "content", " New Anchor ")
    assert result.index.anchors[result.created].name == "New Anchor"
    with pytest.raises(ValueError, match="Insertion site"):
        Operations(host.adapter).create(result.index, key, "mask", "Invalid")
    with pytest.raises(ValueError, match="empty"):
        Operations(host.adapter).create(result.index, key, "content", " ")


def test_material_reference_preserves_mapping_and_changed_levels_block_preview():
    host = FakeHost()
    host.consumer.source_mode = type("Mode", (), {"name": "Material"})()
    host.consumer.material_source = Reference(host.anchor)
    index = collect(host.adapter)
    ops = Operations(host.adapter)
    previews = ops.preview(index, list(index.references), host.adapter.key(host.alternative))
    host.consumer.material_source.levels = (.2, .9)
    result = ops.replace(index, previews)
    assert result.completed == 0 and result.failed
    fresh = result.index
    previews = ops.preview(fresh, list(fresh.references), host.adapter.key(host.alternative))
    result = ops.replace(fresh, previews)
    assert result.completed == 1
    assert host.consumer.material_source.channel_mapping == {Channel.BaseColor: Channel.Roughness}
    assert host.consumer.material_source.levels == (.2, .9)


def test_resolved_unenumerated_anchor_and_unreadable_metadata_are_not_unused():
    host = FakeHost()
    foreign = Node(host, 30, "Not enumerated", "AnchorPointEffect", host.layer)
    host.consumer.sources[Channel.BaseColor] = Reference(foreign)
    index = collect(host.adapter)
    assert index.coverage is Coverage.PARTIAL
    assert not search(index, mode="Unused")
    assert any(i.code == "SOURCE_NOT_FOUND" for i in index.issues)
    assert not any(i.code == "CONFIRMED_BROKEN_REFERENCE" for i in index.issues)
    class UnreadableReference(Reference):
        def get_levels(self):
            raise RuntimeError("metadata unavailable")
    host.consumer.sources[Channel.BaseColor] = UnreadableReference(host.anchor)
    index = collect(host.adapter)
    ref = next(r for r in index.references.values() if r.slot.channel == "BaseColor")
    assert ref.anchor_key == host.adapter.key(host.anchor)
    assert ref.status is Status.UNKNOWN and not ref.writable


def test_native_texture_switch_invalidates_keys_and_busy_blocks_writes():
    from types import SimpleNamespace
    host = FakeHost()
    key = host.adapter.key(host.anchor)
    host.busy = True
    with pytest.raises(ValueError, match="busy"):
        host.adapter.resolve(key, True)
    host.busy = False
    host.stack = SimpleNamespace(material=lambda: SimpleNamespace(name=lambda: "Other"), name=lambda: "")
    with pytest.raises(ValueError, match="STALE_NODE"):
        host.adapter.resolve(key)