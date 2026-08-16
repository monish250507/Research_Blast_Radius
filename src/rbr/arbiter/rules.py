"""Deterministic assessment rules R1-R12 (spec section 12)."""

from __future__ import annotations

import re

from ..schemas import (
    AssessmentStatus,
    Coverage,
    CoverageLayer,
    ProvenanceType,
    SkepticClassification,
)

_CAUSAL_RE = re.compile(
    r"\b(proves?|proven|causes?|caused\s+by|guarantees?|therefore\s+it\s+is\s+certain|"
    r"definitively|without\s+doubt|conclusively)\b",
    re.IGNORECASE,
)

_SUFFICIENT_RE = re.compile(
    r"\b(sufficient\s+to\s+rerun|rerunning\s+(all|everything)|all\s+affected\s+results|"
    r"completely\s+covers|fully\s+validated|no\s+other\s+results?\s+(affected|exist))\b",
    re.IGNORECASE,
)


def r1_has_evidence(evidence_ids: list[str]) -> bool:
    """R1: No evidence ID -> conclusion rejected."""
    return len(evidence_ids) > 0


def r2_unknown_not_unaffected(gap_on_path: bool, boundary_touched: bool) -> bool:
    """R2: An unknown dependency means the downstream node cannot be called unaffected."""
    return gap_on_path or boundary_touched


def r3_run_scoped(run_id: str | None) -> bool:
    """R3: An OBSERVED runtime edge must be scoped to its run ID."""
    return run_id is not None


def r4_static_not_observed(provenance: ProvenanceType, presented_as: ProvenanceType) -> bool:
    """R4: A STATIC edge cannot be presented as runtime-observed."""
    return not (presented_as == ProvenanceType.OBSERVED and provenance != ProvenanceType.OBSERVED)


def r5_inferred_not_direct(provenance: ProvenanceType) -> bool:
    """R5: An INFERRED claim mapping cannot be presented as direct evidence."""
    return provenance in (ProvenanceType.OBSERVED, ProvenanceType.STATIC)


def r6_contradiction_disputed(has_contradiction: bool, current: AssessmentStatus) -> AssessmentStatus:
    """R6: Contradictory evidence -> DISPUTED, never averaged."""
    if has_contradiction:
        return AssessmentStatus.DISPUTED
    return current


def r7_missing_external_version() -> str:
    """R7: Missing external version -> evidence boundary marked PARTIAL."""
    return "PARTIAL"


def r8_causal_blocked(text: str) -> bool:
    """R8: Causal wording blocked."""
    return _CAUSAL_RE.search(text) is not None


def r9_sufficient_blocked(text: str) -> bool:
    """R9: 'Sufficient rerun' wording blocked."""
    return _SUFFICIENT_RE.search(text) is not None


def r10_agent_ids_exist(ids_in_output: list[str], known_ids: set[str]) -> bool:
    """R10: Any agent-created ID must exist in the evidence graph."""
    return all(i in known_ids for i in ids_in_output)


def r11_notebook_state_unknown() -> AssessmentStatus:
    """R11: Inconsistent notebook execution state -> state UNKNOWN."""
    return AssessmentStatus.UNKNOWN


def r12_coverage_not_confidence(coverage: Coverage | None, threshold: float = 0.5) -> bool:
    """R12: If analysis coverage falls below threshold, report coverage, not confidence."""
    if coverage is None:
        return True
    static = coverage.layers.get(CoverageLayer.STATIC)
    if static is None:
        return True
    return static.ratio < threshold


# Skeptic finding resolution table (spec: objection class -> status adjustment).
def resolve_skeptic(classification: SkepticClassification,
                    current: AssessmentStatus) -> AssessmentStatus:
    if classification == SkepticClassification.CONTRADICTION:
        return AssessmentStatus.DISPUTED
    if classification == SkepticClassification.MISSING_EVIDENCE:
        return AssessmentStatus.CONDITIONAL
    if classification == SkepticClassification.SCOPE_LIMITATION:
        # scope limitation affects coverage reporting, not a single conclusion status
        return current
    return current  # NO_COUNTER_EVIDENCE_FOUND: retain status
