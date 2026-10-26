"""Discardable, session-scoped graph records; never store host objects here."""
from dataclasses import dataclass, field
from enum import Enum


class Coverage(Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class Status(Enum):
    VALID = "valid"
    WARNING = "warning"
    BROKEN = "broken"
    UNKNOWN = "unknown"


@dataclass(frozen=True, order=True)
class NodeKey:
    project_session: str
    texture_set_key: str
    stack_key: str
    host_uid: int


@dataclass(frozen=True, order=True)
class InputSlotKey:
    consumer: NodeKey
    source_mode: str
    slot_id: str
    channel: str = ""
    # Procedural input path, not a source UID. Re-resolved on every operation.
    source_path: tuple[str, ...] = ()


@dataclass
class NodeRecord:
    key: NodeKey
    name: str
    path: tuple[str, ...]
    kind: str
    domain: str
    parent: NodeKey | None
    order: int


@dataclass
class AnchorRecord:
    node: NodeRecord
    use_count_known: int = 0
    usage_coverage: Coverage = Coverage.UNKNOWN

    @property
    def key(self) -> NodeKey:
        return self.node.key

    @property
    def name(self) -> str:
        return self.node.name

    @property
    def usage_label(self) -> str:
        if self.usage_coverage is Coverage.COMPLETE:
            return f"{self.use_count_known} uses (scanned categories)"
        return f"≥{self.use_count_known} known uses · scan {self.usage_coverage.value}"


@dataclass
class ReferenceRecord:
    slot: InputSlotKey
    anchor_key: NodeKey | None
    source_channel: str = ""
    channel_mapping: dict[str, str] = field(default_factory=dict)
    status: Status = Status.UNKNOWN
    reason: str = "Not validated by host"
    writable: bool = False
    discovery_method: str = "public source API"
    settings_signature: tuple[str, ...] = ()


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    confidence: str
    evidence: str
    node: NodeKey | None = None
    slot: InputSlotKey | None = None
    action: str = "Refresh or inspect in Painter"


@dataclass
class GraphIndex:
    nodes: dict[NodeKey, NodeRecord] = field(default_factory=dict)
    anchors: dict[NodeKey, AnchorRecord] = field(default_factory=dict)
    references: dict[InputSlotKey, ReferenceRecord] = field(default_factory=dict)
    uses: dict[NodeKey, list[InputSlotKey]] = field(default_factory=dict)
    coverage: Coverage = Coverage.UNKNOWN
    coverage_by_kind: dict[str, Coverage] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    revision: int = 0
    scanned_nodes: int = 0
    finished: bool = False

    def is_unused(self, key: NodeKey) -> bool:
        return self.finished and self.coverage is Coverage.COMPLETE and not self.uses.get(key)