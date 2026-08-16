"""Final assessment model (arbiter output) and validation actions."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from .agents import GatingDecision
from .core import RBREntity
from .enums import AssessmentStatus
from .evidence import Coverage, SupportSpan
from .graph import ContradictionSignal


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Conclusion(RBREntity):
    conclusion_id: str
    subject_node_id: str
    target_node_id: str | None = None
    status: AssessmentStatus
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    support_spans: list[SupportSpan] = Field(default_factory=list)
    provenance_used: list[str] = Field(default_factory=list)
    unresolved_evidence_ids: list[str] = Field(default_factory=list)
    validated: bool = True


class UnknownState(RBREntity):
    node_id: str
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)
    propagated_from: list[str] = Field(default_factory=list)


class ValidationAction(RBREntity):
    action_id: str
    target: str
    rationale: str
    wording: str
    unresolved_evidence_ids: list[str] = Field(default_factory=list)


class Assessment(RBREntity):
    assessment_id: str
    project_id: str
    change_id: str
    status: AssessmentStatus
    conclusions: list[Conclusion] = Field(default_factory=list)
    unknowns: list[UnknownState] = Field(default_factory=list)
    contradictions: list[ContradictionSignal] = Field(default_factory=list)
    hypotheses: list[object] = Field(default_factory=list)
    validation_actions: list[ValidationAction] = Field(default_factory=list)
    coverage: Coverage | None = None
    gating: list[GatingDecision] = Field(default_factory=list)
    agent_calls: list[str] = Field(default_factory=list)
    graph_version: str = "0.1.0"
    generated_at: datetime = Field(default_factory=_utcnow)
