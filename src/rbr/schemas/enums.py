"""Canonical enumerations for Research Blast Radius.

These are frozen product vocabulary. Any change is a schema migration, not an edit.
"""

from __future__ import annotations

from enum import StrEnum


class ProvenanceType(StrEnum):
    """How a piece of evidence / edge was established.

    Allowed use (spec section 6.2):
    - OBSERVED: directly observed in a specific execution/artifact (strongest).
    - STATIC: deterministically derived from source/config structure.
    - DECLARED: explicitly supplied by the researcher.
    - INFERRED: semantic relationship proposed by an agent (scientific mapping only).
    - UNKNOWN: could not be established; must propagate to relevant assessments.
    """

    OBSERVED = "OBSERVED"
    STATIC = "STATIC"
    DECLARED = "DECLARED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


# Strength ordering used for provenance propagation along a path.
PROVENANCE_STRENGTH: dict[ProvenanceType, int] = {
    ProvenanceType.OBSERVED: 5,
    ProvenanceType.STATIC: 4,
    ProvenanceType.DECLARED: 3,
    ProvenanceType.INFERRED: 2,
    ProvenanceType.UNKNOWN: 1,
}


class NodeType(StrEnum):
    CHANGE = "CHANGE"
    FILE = "FILE"
    SYMBOL = "SYMBOL"
    NOTEBOOK_CELL = "NOTEBOOK_CELL"
    CONFIG = "CONFIG"
    DATASET = "DATASET"
    MODEL = "MODEL"
    EXPERIMENT = "EXPERIMENT"
    RUN = "RUN"
    ARTIFACT = "ARTIFACT"
    FIGURE = "FIGURE"
    TABLE = "TABLE"
    CLAIM = "CLAIM"
    PAPER_SECTION = "PAPER_SECTION"
    EXTERNAL_RESOURCE = "EXTERNAL_RESOURCE"
    UNKNOWN_STATE = "UNKNOWN_STATE"


class EdgeRelation(StrEnum):
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    READS = "READS"
    WRITES = "WRITES"
    GENERATES = "GENERATES"
    USES = "USES"
    EXECUTED_AS = "EXECUTED_AS"
    PRODUCES = "PRODUCES"
    DERIVED_FROM = "DERIVED_FROM"
    REFERENCES = "REFERENCES"
    EVIDENCE_FOR = "EVIDENCE_FOR"
    CONTRADICTS = "CONTRADICTS"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    UNKNOWN_RELATION = "UNKNOWN_RELATION"


# Relations that traversal follows when computing blast radius (spec section 14).
TRAVERSAL_RELATIONS: frozenset[EdgeRelation] = frozenset(
    {
        EdgeRelation.IMPORTS,
        EdgeRelation.CALLS,
        EdgeRelation.READS,
        EdgeRelation.WRITES,
        EdgeRelation.GENERATES,
        EdgeRelation.USES,
        EdgeRelation.EXECUTED_AS,
        EdgeRelation.PRODUCES,
    }
)


class EvidenceSourceType(StrEnum):
    GIT_DIFF = "GIT_DIFF"
    GIT_BLOB = "GIT_BLOB"
    PYTHON_AST = "PYTHON_AST"
    NOTEBOOK = "NOTEBOOK"
    CONFIG = "CONFIG"
    ARTIFACT = "ARTIFACT"
    MANIFEST = "MANIFEST"
    RUNTIME_TRACE = "RUNTIME_TRACE"
    PAPER = "PAPER"
    CLAIM_EXTRACTION = "CLAIM_EXTRACTION"
    CLAIM_DECLARED = "CLAIM_DECLARED"
    AGENT = "AGENT"
    MANUAL = "MANUAL"
    OTHER = "OTHER"


class ChangeKind(StrEnum):
    COMMIT = "COMMIT"
    COMMIT_RANGE = "COMMIT_RANGE"
    BRANCH_DIFF = "BRANCH_DIFF"
    FILE_DIFF = "FILE_DIFF"
    FILE_LINE = "FILE_LINE"


class FileChangeStatus(StrEnum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"
    COPIED = "COPIED"


class ContradictionKind(StrEnum):
    HASH_MISMATCH = "HASH_MISMATCH"
    NOTEBOOK_STATE = "NOTEBOOK_STATE"
    CONFIG_DRIFT = "CONFIG_DRIFT"
    MISSING_VERSION = "MISSING_VERSION"
    CONFLICTING_CLAIM = "CONFLICTING_CLAIM"
    PROVENANCE_CONFLICT = "PROVENANCE_CONFLICT"
    OTHER = "OTHER"


class AssessmentStatus(StrEnum):
    AFFECTED = "AFFECTED"
    CONDITIONAL = "CONDITIONAL"
    DISPUTED = "DISPUTED"
    UNKNOWN = "UNKNOWN"
    NOT_EVIDENCED_AFFECTED = "NOT_EVIDENCED_AFFECTED"


class SkepticClassification(StrEnum):
    CONTRADICTION = "CONTRADICTION"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    SCOPE_LIMITATION = "SCOPE_LIMITATION"
    NO_COUNTER_EVIDENCE_FOUND = "NO_COUNTER_EVIDENCE_FOUND"


class StageName(StrEnum):
    IMPACT = "IMPACT"
    SCIENTIFIC = "SCIENTIFIC"
    SKEPTIC = "SKEPTIC"


class CoverageLayer(StrEnum):
    CHANGE = "CHANGE"
    STATIC = "STATIC"
    RUNTIME = "RUNTIME"
    ARTIFACT = "ARTIFACT"
    CLAIM = "CLAIM"
    EXTERNAL = "EXTERNAL"
    MANUAL = "MANUAL"


class ExtractionStatus(StrEnum):
    EXTRACTED = "EXTRACTED"
    PARTIAL = "PARTIAL"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_EXTRACTED = "NOT_EXTRACTED"


class RiskLabel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"
