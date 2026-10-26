"""Preview/preflight/commit/reread services. No optimistic graph mutations."""
from dataclasses import dataclass, field
from .discovery import collect
from .models import GraphIndex, InputSlotKey, NodeKey, ReferenceRecord, Status


@dataclass(frozen=True)
class Replacement:
    reference: ReferenceRecord
    target: NodeKey
    eligible: bool
    reason: str


@dataclass
class Result:
    completed: int = 0
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    index: GraphIndex | None = None
    created: NodeKey | None = None


def eligibility(index: GraphIndex, slot: InputSlotKey, target: NodeKey) -> tuple[bool, str]:
    ref = index.references.get(slot)
    if ref is None or slot.consumer not in index.nodes:
        return False, "Missing consumer/input; refresh"
    if target not in index.anchors or ref.anchor_key not in index.anchors:
        return False, "Missing source anchor; refresh"
    if target == ref.anchor_key:
        return False, "Already uses this anchor"
    if (target.project_session, target.texture_set_key, target.stack_key) != (
            slot.consumer.project_session, slot.consumer.texture_set_key, slot.consumer.stack_key):
        return False, "Cross-session/texture-set/stack reference prohibited"
    if not ref.writable or ref.status is not Status.VALID:
        return False, "Read-only or unresolved source context"
    old, new = index.anchors[ref.anchor_key].node, index.anchors[target].node
    if old.parent is None or old.parent != new.parent or old.domain != new.domain:
        return False, "Ordering/channel eligibility unknown: only same-chain adjacent anchors are verified"
    between = [n for n in index.nodes.values() if n.parent == old.parent and n.domain == old.domain
               and min(old.order, new.order) < n.order < max(old.order, new.order)]
    if any(n.kind != "AnchorPointEffect" for n in between):
        return False, "Intervening effects: evaluation eligibility is not proven"
    return True, "Same chain, anchor-only interval; preserve channels, levels and alpha matte"


class Operations:
    def __init__(self, adapter):
        self.adapter = adapter

    def preview(self, index, slots, target):
        return [Replacement(index.references[slot], target, *eligibility(index, slot, target))
                for slot in slots if slot in index.references]

    def _fresh(self, index, keys):
        fresh = collect(self.adapter, index.revision + 1)
        for key in keys:
            before, after = index.nodes.get(key), fresh.nodes.get(key)
            if before is None or after is None or (before.name, before.path, before.kind, before.parent) != (
                    after.name, after.path, after.kind, after.parent):
                raise ValueError("STALE_NODE: target changed or disappeared; refresh and preview again")
        return fresh

    @staticmethod
    def _name(name):
        name = name.strip()
        if not name:
            raise ValueError("Anchor name cannot be empty")
        return name

    def rename(self, index, key, name):
        name = self._name(name)
        fresh = self._fresh(index, [key])
        if key not in fresh.anchors:
            raise ValueError("Only anchor nodes can be renamed")
        with self.adapter.transaction("MBToolkit: Rename anchor"):
            self.adapter.rename(key, name)
        result = collect(self.adapter, fresh.revision + 1)
        if key not in result.anchors or result.anchors[key].name != name:
            raise RuntimeError("Host did not confirm the rename; inspect/Undo")
        return Result(1, index=result)

    def create(self, index, key, site, name):
        name = self._name(name)
        self._fresh(index, [key])
        with self.adapter.transaction("MBToolkit: Create anchor"):
            created = self.adapter.create(key, site, name)
        result = collect(self.adapter)
        if created not in result.anchors:
            raise RuntimeError("Created anchor could not be reread; refresh")
        return Result(1, index=result, created=created)

    def delete(self, index, key):
        fresh = self._fresh(index, [key])
        if key not in fresh.anchors or not fresh.is_unused(key):
            raise ValueError("Deletion blocked: uses exist or discovery coverage is incomplete")
        with self.adapter.transaction("MBToolkit: Delete unused anchor"):
            self.adapter.delete(key)
        result = collect(self.adapter, fresh.revision + 1)
        if key in result.anchors:
            raise RuntimeError("Host did not confirm deletion")
        return Result(1, index=result)

    def replace(self, index, previews):
        result = Result()
        keys = {p.target for p in previews} | {p.reference.slot.consumer for p in previews}
        keys |= {p.reference.anchor_key for p in previews if p.reference.anchor_key is not None}
        fresh = self._fresh(index, keys)
        ready = []
        for preview in previews:
            ref = fresh.references.get(preview.reference.slot)
            safe, reason = eligibility(fresh, preview.reference.slot, preview.target)
            if not preview.eligible or not safe:
                result.skipped.append(reason)
            elif ref != preview.reference:
                result.failed.append("Binding/settings changed since preview; re-open operation")
            else:
                ready.append(preview)
        try:
            with self.adapter.transaction("MBToolkit: Replace anchor references"):
                for preview in ready:
                    try:
                        self.adapter.replace(preview.reference, preview.target)
                        result.completed += 1
                    except Exception as exc:
                        result.failed.append(str(exc))
        finally:
            result.index = collect(self.adapter, fresh.revision + 1)
        return result