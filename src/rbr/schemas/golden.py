"""Golden benchmark manifest + ground-truth schema (plugin slot, spec section 21)."""

from __future__ import annotations

from pydantic import Field

from .core import RBREntity


class GoldenManifest(RBREntity):
    """Per-project golden benchmark metadata. The golden repo is a pluggable slot:
    dropping in any repo means writing this file + ground_truth.json only."""

    name: str
    repo_url: str
    base_commit: str
    change_commit: str
    language: str = "python"
    expected_graph_file: str = "expected_graph.json"
    ground_truth_file: str = "ground_truth.json"
    supported: bool = True


class ExpectedEdge(RBREntity):
    source_ref: str
    target_ref: str
    relation: str


class ExpectedUnknown(RBREntity):
    node_ref: str
    reason: str = ""


class GroundTruth(RBREntity):
    """Hand-adjudicated ground truth used to score RBR output on a golden repo."""

    project_name: str
    change_commit: str
    expected_affected_artifact_refs: list[str] = Field(default_factory=list)
    expected_affected_claim_ids: list[str] = Field(default_factory=list)
    expected_edges: list[ExpectedEdge] = Field(default_factory=list)
    expected_unknowns: list[ExpectedUnknown] = Field(default_factory=list)
    expected_contradictions: list[str] = Field(default_factory=list)
    expected_status: str = "AFFECTED"
    notes: str = ""
