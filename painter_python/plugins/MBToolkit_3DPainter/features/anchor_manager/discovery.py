"""Incremental traversal. Adapter is the only owner of host interaction."""
from .models import GraphIndex, AnchorRecord, Coverage, InputSlotKey
from .index import rebuild


class Discovery:
    def __init__(self, adapter, revision=0):
        self.adapter = adapter
        self.context = adapter.context()
        self.index = GraphIndex(revision=revision)

    def steps(self):
        if self.context is None:
            self.index.finished = True
            return
        index, adapter = self.index, self.adapter
        index.coverage = Coverage.PARTIAL
        stack = [(n, self.context[1:], None, "layer") for n in reversed(adapter.roots())]
        seen = set()
        while stack:
            if adapter.context() != self.context:
                raise ValueError("Scan abandoned: project/texture stack changed")
            node, path, parent, domain = stack.pop()
            try:
                record = adapter.record(node, path, parent, domain, len(index.nodes))
                if record.key in seen:
                    index.gaps.append("Repeated hierarchy identity; branch skipped")
                    continue
                seen.add(record.key)
                index.nodes[record.key] = record
                index.scanned_nodes += 1
                if record.kind == "AnchorPointEffect":
                    index.anchors[record.key] = AnchorRecord(record)
                index.gaps.extend(adapter.gaps_for(node))
                for method, child_domain, getter in adapter.children(node):
                    try:
                        children = getter()
                        stack.extend((child, (*record.path, child_domain.title()), record.key, child_domain)
                                     for child in reversed(children))
                    except Exception as exc:
                        index.gaps.append(f"{record.name} / {method}: {exc}")
                try:
                    for mode, identifier, channel, source_path, getter in adapter.source_slots(node):
                        slot = InputSlotKey(record.key, mode, identifier, channel, source_path)
                        yield from self._source(getter, slot, set())
                        index.coverage_by_kind.setdefault(mode, Coverage.COMPLETE)
                except Exception as exc:
                    index.gaps.append(f"{record.name}: source slots unavailable: {exc}")
            except Exception as exc:
                index.gaps.append(f"Unreadable stack node: {exc}")
            yield None
        index.finished = True
        index.coverage = Coverage.PARTIAL if index.gaps else Coverage.COMPLETE
        if index.gaps:
            # Per-kind completeness is not established after any failed enumeration.
            index.coverage_by_kind = {k: Coverage.PARTIAL for k in index.coverage_by_kind}
        rebuild(index)

    def _source(self, getter, slot, ancestors):
        try:
            if len(slot.source_path) > 32:
                raise ValueError("Procedural input depth limit reached")
            source = getter()
            self.index.gaps.extend(self.adapter.source_gaps(source))
            # id is only used to detect cycles inside this scan, never persisted.
            identity = source.uid() if callable(getattr(source, "uid", None)) else id(source)
            if identity in ancestors:
                raise ValueError("Procedural source cycle")
            ref, children = self.adapter.inspect_source(source, slot)
            if ref is not None:
                self.index.references[slot] = ref
                if ref.status.value == "unknown":
                    self.index.gaps.append(ref.reason)
            for identifier, child_getter in children:
                child_slot = InputSlotKey(slot.consumer, slot.source_mode, slot.slot_id, slot.channel,
                                          (*slot.source_path, identifier))
                yield from self._source(child_getter, child_slot, ancestors | {identity})
        except Exception as exc:
            self.index.gaps.append(f"Input {slot.slot_id} {'/'.join(slot.source_path)}: {exc}")
        yield None


def collect(adapter, revision=0):
    scan = Discovery(adapter, revision)
    for _ in scan.steps():
        pass
    return scan.index