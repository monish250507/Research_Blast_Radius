"""Structured scientific claim representation and claim mappings (spec section 13)."""

from __future__ import annotations

from pydantic import Field

from .core import RBREntity
from .enums import ExtractionStatus, ProvenanceType


class Claim(RBREntity):
    claim_id: str
    project_id: str
    normalized_text: str
    subject: str | None = None
    intervention: str | None = None
    comparator: str | None = None
    metric: str | None = None
    magnitude: str | None = None
    population: str | None = None
    dataset: str | None = None
    condition: str | None = None
    qualifiers: list[str] = Field(default_factory=list)
    evidence_locations: list[str] = Field(default_factory=list)
    source_section: str | None = None
    source: str = "declared"
    extraction_status: ExtractionStatus = ExtractionStatus.EXTRACTED


class ClaimMapping(RBREntity):
    """Candidate mapping from an affected artifact to a documented claim.

    Semantic mappings must be labelled INFERRED; the arbiter never upgrades them.
    """

    claim_id: str
    artifact_id: str
    provenance_type: ProvenanceType
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    support_spans: list[str] = Field(default_factory=list)
    uncertainty: str = ""
    qualifiers_preserved: bool = True
