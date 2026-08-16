"""Arbiter assembly tests: R10 evidence-id guard, support spans, skeptic."""

from rbr.arbiter.validator import Arbiter
from rbr.schemas import (
    BlastPath,
    BlastRadius,
    ClaimMapping,
    ContradictionSignal,
    ProvenanceType,
    SkepticClassification,
    SkepticFinding,
    SkepticOutput,
    ids,
)
from rbr.store import open_repository

PID = "proj-arb"


def _path(evidence: list[str] | None = None, gap: bool = False) -> BlastPath:
    return BlastPath(
        path_id="path:t",
        source_id=ids.node_id("FILE", "src/a.py"),
        target_id=ids.node_id("ARTIFACT", "out.csv"),
        node_ids=[ids.node_id("FILE", "src/a.py"),
                  ids.node_id("ARTIFACT", "out.csv")],
        edge_ids=["edge:e1"],
        provenance_types=[ProvenanceType.STATIC],
        strongest_provenance=ProvenanceType.STATIC,
        has_unknown_gap=gap,
        evidence_ids=evidence or ["ev:real"],
        gaps=[] if not gap else ["unknown provenance on path"],
    )


def _blast(paths: list[BlastPath]) -> BlastRadius:
    return BlastRadius(change_id="chg:x", project_id=PID, paths=paths,
                       affected_node_ids=[p.target_id for p in paths])


def _contradiction(target: str | None) -> list[ContradictionSignal]:
    if target is None:
        return []
    return [ContradictionSignal(
        signal_id=ids.signal_id("NOTEBOOK_STATE", "x"),
        project_id=PID, kind="NOTEBOOK_STATE",
        description="notebook state inconsistent",
        affected_node_ids=[target],
    )]


def _arbiter(db_path: str) -> Arbiter:
    repo = open_repository(f"sqlite+pysqlite:///{db_path}")
    repo.create_project(PID, "bench", "test", "python")
    from rbr.config import Settings
    from rbr.schemas import Evidence, EvidenceSourceType

    repo.add_evidence(Evidence(
        evidence_id="ev:real", project_id=PID,
        source_type=EvidenceSourceType.PYTHON_AST, locator="src/a.py:1",
        content_hash="h", extractor="test", payload={}, snapshot_id="snap:s",
    ))
    return Arbiter(repo, Settings())


def _assemble(arbiter, blast, contradictions=None, mappings=None, skeptic_out=None):
    known = {p.source_id for p in blast.paths} | {p.target_id for p in blast.paths}
    for mp in mappings or []:
        known.add(mp.claim_id)
    return arbiter.assemble(
        project_id=PID, change_id="chg:x", blast_radius=blast,
        contradictions=contradictions or [],
        agent_outputs={"skeptic": skeptic_out} if skeptic_out is not None else {},
        claim_mappings=mappings or [],
        known_node_ids=known,
        known_edge_ids={"edge:e1"},
        boundary_unknown=[], gaps=[], coverage=None,
        gating=[],
    )


def test_evidence_backed_path_is_affected(db_path: str):
    a = _arbiter(db_path)
    asmt = _assemble(a, _blast([_path()]))
    assert asmt.conclusions[0].status.value == "AFFECTED"


def test_invented_evidence_id_rejected(db_path: str):
    """R10: agent-cited evidence ids must exist in the store."""
    a = _arbiter(db_path)
    claim_id = ids.claim_id("C1")
    mappings = [ClaimMapping(
        claim_id=claim_id,
        artifact_id=ids.node_id("ARTIFACT", "out.csv"),
        provenance_type=ProvenanceType.INFERRED,
        rationale="invented evidence id should get this dropped",
        evidence_ids=["ev:invented-not-in-store"],
    )]
    asmt = _assemble(a, _blast([_path()]), mappings=mappings)
    claim_conc = [c for c in asmt.conclusions if c.subject_node_id == claim_id]
    assert claim_conc == []


def test_inferred_mapping_survives_with_real_reference(db_path: str):
    a = _arbiter(db_path)
    claim_id = ids.claim_id("C1")
    mappings = [ClaimMapping(
        claim_id=claim_id,
        artifact_id=ids.node_id("ARTIFACT", "out.csv"),
        provenance_type=ProvenanceType.INFERRED,
        rationale="the affected artifact supports the declared claim mapping",
    )]
    asmt = _assemble(a, _blast([_path()]), mappings=mappings)
    claim_conc = [c for c in asmt.conclusions if c.subject_node_id == claim_id]
    assert len(claim_conc) == 1
    assert claim_conc[0].status.value == "CONDITIONAL"


def test_mapping_cannot_upgrade_provenance(db_path: str):
    a = _arbiter(db_path)
    mappings = [ClaimMapping(
        claim_id=ids.claim_id("C1"),
        artifact_id=ids.node_id("ARTIFACT", "out.csv"),
        provenance_type=ProvenanceType.OBSERVED,  # upgrade attempt
        rationale="attempted upgrade to observed",
    )]
    asmt = _assemble(a, _blast([_path()]), mappings=mappings)
    assert len(asmt.conclusions) == 1  # only the path conclusion survives


def test_contradiction_on_path_disputes_conclusion(db_path: str):
    a = _arbiter(db_path)
    target = ids.node_id("ARTIFACT", "out.csv")
    asmt = _assemble(a, _blast([_path()]), contradictions=_contradiction(target))
    assert asmt.conclusions[0].status.value == "DISPUTED"


def test_skeptic_targets_conclusion_only(db_path: str):
    a = _arbiter(db_path)
    blast = _blast([_path()])
    conc_id = f"conc:{blast.paths[0].target_id.split(':')[-1][:16]}"
    skeptic_out = SkepticOutput(findings=[
        SkepticFinding(target_conclusion_id=conc_id,
                       classification=SkepticClassification.MISSING_EVIDENCE,
                       description="gaps present"),
    ])
    asmt = _assemble(a, blast, skeptic_out=skeptic_out)
    assert asmt.conclusions[0].status.value == "CONDITIONAL"
