"""Pure graph indexing, conservative validation, search and deterministic layout."""
from collections import defaultdict
from .models import Coverage, GraphIndex, Issue, Status


def rebuild(index: GraphIndex) -> GraphIndex:
    uses = defaultdict(list)
    names = defaultdict(list)
    issues = []
    for key, anchor in index.anchors.items():
        names[anchor.name.casefold()].append(key)
    for slot, ref in index.references.items():
        if ref.anchor_key in index.anchors:
            uses[ref.anchor_key].append(slot)
        elif ref.anchor_key is not None:
            # A resolved reference outside enumerated data is not proof of breakage.
            gap = "Resolved reference points to an anchor outside the enumerated hierarchy"
            if gap not in index.gaps:
                index.gaps.append(gap)
            index.coverage = Coverage.PARTIAL
            issues.append(Issue("SOURCE_NOT_FOUND", "warning", "unknown", gap, slot.consumer, slot))
        if ref.status is Status.BROKEN:
            issues.append(Issue("CONFIRMED_BROKEN_REFERENCE", "error", "confirmed", ref.reason,
                                slot.consumer, slot))
        elif ref.status is Status.UNKNOWN:
            issues.append(Issue("UNSUPPORTED_CONNECTION", "warning", "unknown", ref.reason,
                                slot.consumer, slot))
    for keys in names.values():
        if len(keys) > 1:
            issues.extend(Issue("DUPLICATE_ANCHOR_NAME", "warning", "confirmed",
                                "Different anchor identities share a label", key) for key in keys)
    if index.coverage is not Coverage.COMPLETE:
        issues.extend(Issue("INCOMPLETE_SCAN", "warning", "confirmed", gap) for gap in index.gaps)
    index.uses = dict(uses)
    for key, anchor in index.anchors.items():
        anchor.use_count_known = len(uses[key])
        anchor.usage_coverage = index.coverage if index.finished else Coverage.PARTIAL
        if index.is_unused(key):
            issues.append(Issue("UNUSED_ANCHOR", "info", "confirmed",
                                "No uses in completely scanned public source categories", key))
    index.issues = issues
    return index


def search(index: GraphIndex, text: str = "", mode: str = "All", sort: str = "Name",
           scope=None):
    query = text.casefold().strip()
    issue_nodes = {i.node for i in index.issues}
    result = []
    for anchor in index.anchors.values():
        node = anchor.node
        consumers = [index.nodes[s.consumer].name for s in index.uses.get(anchor.key, [])]
        if query and query not in " / ".join((*node.path, *consumers)).casefold():
            continue
        if scope is not None and scope not in (node.key, node.parent):
            continue
        if mode == "Used" and not anchor.use_count_known:
            continue
        if mode == "Unused" and not index.is_unused(anchor.key):
            continue
        if mode == "Issues" and node.key not in issue_nodes and index.coverage is Coverage.COMPLETE:
            continue
        result.append(anchor)
    primary = {"Name": lambda a: a.name.casefold(), "Uses": lambda a: -a.use_count_known,
               "Stack Order": lambda a: a.node.order, "Source Type": lambda a: a.node.domain}[sort]
    return sorted(result, key=lambda a: (primary(a), a.name.casefold(), a.key))


def layout(index: GraphIndex, focus=None, limit: int = 500):
    """Two lanes, shared consumers, bounded overview. Never implies evaluation order."""
    anchors = sorted(index.anchors) if focus is None else ([focus] if focus in index.anchors else [])
    anchors = anchors[:limit]
    rank = {key: i for i, key in enumerate(anchors)}
    consumers = defaultdict(list)
    for ref in index.references.values():
        if ref.anchor_key in rank:
            consumers[ref.slot.consumer].append(rank[ref.anchor_key])
    ordered = sorted(consumers, key=lambda k: (sum(consumers[k]) / len(consumers[k]), k))[:limit]
    positions = {key: (0, i * 100) for i, key in enumerate(anchors)}
    positions.update({key: (440, i * 110) for i, key in enumerate(ordered)})
    return positions