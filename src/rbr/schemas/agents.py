"""Agent contracts (inputs/outputs), call records and gating decisions.

Agents are stateless single-shot roles. Their outputs are schema-constrained and
validated by the deterministic arbiter before any use.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field

from .claims import Claim, ClaimMapping
from .core import RBREntity
from .enums import RiskLabel, SkepticClassification, StageName
from .evidence import SupportSpan
from .graph import BlastPath


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --- Impact Mapper -----------------------------------------------------------


class ImpactFinding(RBREntity):
    """A risk-labelled statement about a precomputed blast-radius path."""

    target_node_id: str
    path_id: str | None = None
    risk: RiskLabel = RiskLabel.UNKNOWN
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    support_spans: list[SupportSpan] = Field(default_factory=list)
    validation_hint: str = ""


class ImpactHypothesis(RBREntity):
    """An INFERRED proposal by the Impact Mapper.

    Hypotheses never enter the graph; they are recorded in the assessment as
    explicitly INFERRED so the researcher can decide whether to confirm them.
    """

    description: str
    target_node_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    support_spans: list[SupportSpan] = Field(default_factory=list)
    needs_confirmation: bool = True


class ImpactMapperInput(RBREntity):
    change_id: str
    project_id: str
    change_label: str = ""
    change_files: list[str] = Field(default_factory=list)
    affected_node_ids: list[str] = Field(default_factory=list)
    paths: list[BlastPath] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    coverage_summary: str = ""


class ImpactMapperOutput(RBREntity):
    findings: list[ImpactFinding] = Field(default_factory=list)
    hypotheses: list[ImpactHypothesis] = Field(default_factory=list)


# --- Scientific Evidence Analyst ---------------------------------------------


class ScientificAnalystInput(RBREntity):
    change_id: str
    project_id: str
    affected_artifact_refs: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)


class Ambiguity(RBREntity):
    claim_id: str
    reason: str
    status: Literal["UNKNOWN"] = "UNKNOWN"


class ScientificAnalystOutput(RBREntity):
    mappings: list[ClaimMapping] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)


# --- Skeptic -----------------------------------------------------------------


class ConclusionDraft(RBREntity):
    conclusion_id: str
    subject_node_id: str
    target_node_id: str | None = None
    status: str = ""
    rationale: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class SkepticInput(RBREntity):
    change_id: str
    project_id: str
    conclusions: list[ConclusionDraft] = Field(default_factory=list)
    affected_node_ids: list[str] = Field(default_factory=list)
    contradiction_signals: list[str] = Field(default_factory=list)
    change_summary: str = ""
    gaps: list[str] = Field(default_factory=list)


class SkepticFinding(RBREntity):
    target_conclusion_id: str | None = None
    classification: SkepticClassification
    description: str
    evidence_ids: list[str] = Field(default_factory=list)
    support_spans: list[SupportSpan] = Field(default_factory=list)


class SkepticOutput(RBREntity):
    findings: list[SkepticFinding] = Field(default_factory=list)


# --- Records -----------------------------------------------------------------


class AgentCallRecord(RBREntity):
    call_id: str
    project_id: str
    agent_name: str
    provider: str
    model: str
    temperature: float
    prompt_hash: str
    input_subgraph_hash: str = ""
    output_json: dict[str, Any] = Field(default_factory=dict)
    status: str = "ok"
    usage: dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


class GatingDecision(RBREntity):
    gating_id: str
    project_id: str
    change_id: str
    stage: StageName
    enabled: bool
    reason: str
    budget_tokens: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
