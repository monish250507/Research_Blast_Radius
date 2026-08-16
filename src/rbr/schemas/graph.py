"""Graph node/edge model and blast-radius traversal result (spec section 9, 14)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from .core import RBREntity
from .enums import EdgeRelation, NodeType, ProvenanceType


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GraphNode(RBREntity):
    node_id: str
    project_id: str
    node_type: NodeType
    label: str
    ref: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(RBREntity):
    edge_id: str
    project_id: str
    source_id: str
    target_id: str
    relation: EdgeRelation
    provenance_type: ProvenanceType
    evidence_ids: list[str] = Field(default_factory=list)
    locator: str = ""
    run_id: str | None = None
    snapshot_id: str | None = None
    scope: str = "project"
    extractor_version: str = "0.1.0"
    created_at: datetime = Field(default_factory=_utcnow)


class BlastPath(RBREntity):
    """One evidence-backed path from the change to a downstream node."""

    path_id: str
    source_id: str
    target_id: str
    node_ids: list[str]
    edge_ids: list[str]
    provenance_types: list[ProvenanceType]
    strongest_provenance: ProvenanceType
    has_unknown_gap: bool
    evidence_ids: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class BlastRadius(RBREntity):
    """Deterministic result of change-local traversal. Agents do not compute this."""

    change_id: str
    project_id: str
    affected_node_ids: list[str] = Field(default_factory=list)
    downstream_node_ids: list[str] = Field(default_factory=list)
    paths: list[BlastPath] = Field(default_factory=list)
    boundary_unknown_node_ids: list[str] = Field(default_factory=list)
    traversal_relations: list[EdgeRelation] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=_utcnow)

    def path_for(self, target_id: str) -> list[BlastPath]:
        return [p for p in self.paths if p.target_id == target_id]


class ContradictionSignal(RBREntity):
    signal_id: str
    project_id: str
    kind: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)
    affected_node_ids: list[str] = Field(default_factory=list)
    severity: str = "info"
