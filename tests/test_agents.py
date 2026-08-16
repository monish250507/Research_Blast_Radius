"""Agent fallback behavior (no-LLM/stub mode) tests."""

from rbr.agents import (
    ImpactMapperAgent,
    ScientificAnalystAgent,
    SkepticAgent,
    build_provider,
)
from rbr.config import Settings
from rbr.schemas import (
    Claim,
    ImpactMapperInput,
    ProvenanceType,
    ScientificAnalystInput,
    SkepticClassification,
    SkepticInput,
)

PID = "proj-agents"


def _settings(db_path: str) -> Settings:
    import os

    os.environ["RBR_DB_URL"] = f"sqlite+pysqlite:///{db_path}"
    return Settings()


def test_stub_provider_is_deterministic(db_path: str):
    s = _settings(db_path)
    p = build_provider(s)
    assert p.name == "stub"
    assert p.usage() == {}


def test_scientific_analyst_maps_only_with_evidence(db_path: str):
    s = _settings(db_path)
    agent = ScientificAnalystAgent(build_provider(s), s)
    claim = Claim(claim_id="clm:c1", project_id=PID, normalized_text="acc improves",
                  evidence_locations=["outputs/accuracy.json"])
    out = agent.run(PID, ScientificAnalystInput(
        change_id="chg:x", project_id=PID,
        affected_artifact_refs=["outputs/accuracy.json"],
        claims=[claim],
    )).output
    assert len(out.mappings) == 1
    assert out.mappings[0].provenance_type == ProvenanceType.INFERRED
    assert out.mappings[0].claim_id == claim.claim_id


def test_scientific_analyst_no_mapping_without_overlap(db_path: str):
    s = _settings(db_path)
    agent = ScientificAnalystAgent(build_provider(s), s)
    claim = Claim(claim_id="clm:c1", project_id=PID, normalized_text="acc improves",
                  evidence_locations=["outputs/other.json"])
    out = agent.run(PID, ScientificAnalystInput(
        change_id="chg:x", project_id=PID,
        affected_artifact_refs=["outputs/accuracy.json"],
        claims=[claim],
    )).output
    assert out.mappings == []


def test_skeptic_contradiction_is_scope_limitation(db_path: str):
    s = _settings(db_path)
    agent = SkepticAgent(build_provider(s), s)
    out = agent.run(PID, SkepticInput(
        change_id="chg:x", project_id=PID,
        contradiction_signals=["NOTEBOOK_STATE"],
    )).output
    classes = [f.classification for f in out.findings]
    assert SkepticClassification.SCOPE_LIMITATION in classes
    assert SkepticClassification.CONTRADICTION not in classes


def test_skeptic_gaps_are_missing_evidence(db_path: str):
    s = _settings(db_path)
    agent = SkepticAgent(build_provider(s), s)
    out = agent.run(PID, SkepticInput(
        change_id="chg:x", project_id=PID, gaps=["static: 1 unknown items"],
    )).output
    classes = [f.classification for f in out.findings]
    assert SkepticClassification.MISSING_EVIDENCE in classes


def test_skeptic_no_counter_evidence_when_clean(db_path: str):
    s = _settings(db_path)
    agent = SkepticAgent(build_provider(s), s)
    out = agent.run(PID, SkepticInput(
        change_id="chg:x", project_id=PID,
    )).output
    assert out.findings[0].classification == SkepticClassification.NO_COUNTER_EVIDENCE_FOUND


def test_impact_mapper_stub_runs(db_path: str):
    s = _settings(db_path)
    agent = ImpactMapperAgent(build_provider(s), s)
    out = agent.run(PID, ImpactMapperInput(
        change_id="chg:x", project_id=PID, change_label="scale change",
    )).output
    assert out.hypotheses == []
