"""Golden benchmark harness.

Runs the full deterministic pipeline (ingest -> graph -> blast radius ->
agents(stub) -> arbiter) against a fixture repo and scores it against the
fixture's ground truth. The harness is repo-agnostic: swapping in a real
research repo requires only manifest.toml + ground_truth.json, no code change.
"""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from rbr.claims import ClaimIndex, ClaimLoader
from rbr.config import Settings
from rbr.evidence import IngestionPipeline, persist
from rbr.orchestrator import AnalyzeService
from rbr.schemas import ids
from rbr.store import open_repository

PROJECTS_ROOT = Path(__file__).parent / "golden_projects"


@dataclass
class GoldenResult:
    metrics: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)
    assessment = None


def run_golden(name: str, db_path: str) -> GoldenResult:
    project_dir = PROJECTS_ROOT / name
    with open(project_dir / "manifest.toml", "rb") as fh:
        manifest = tomllib.load(fh)
    with open(project_dir / "ground_truth.json", encoding="utf-8") as fh:
        ground = json.load(fh)

    os.environ["RBR_DB_URL"] = f"sqlite+pysqlite:///{db_path}"
    settings = Settings()
    repo = open_repository(settings.db_url)
    pid = f"proj-{name}"
    repo.create_project(pid, owner="bench", repository=name, scope="python+git+jupyter")

    repo_dir = project_dir / manifest["repo_dir"]
    claims_file = project_dir / manifest["claims_file"]

    pipeline = IngestionPipeline(str(repo_dir))
    res = pipeline.ingest_commit_range(
        pid, manifest["base_commit"], manifest["change_commit"]
    )
    persist(repo, res)

    claims = ClaimLoader(pid).load_yaml(str(claims_file))
    ClaimIndex(repo, pid).ingest_claims(claims)

    out = AnalyzeService(repo, settings).run(pid, res.change.change_id)
    assessment = out["assessment"]
    graph = out["blast_radius"]

    result = GoldenResult()
    result.assessment = assessment
    result.details["change_id"] = res.change.change_id
    result.details["project_id"] = pid
    _score(result, repo, assessment, graph, ground, pid, claims_file)
    return result


def _node_ref(repo, node_id: str) -> str:
    node = repo.get_node(node_id)
    return node.ref if node else node_id


def _score(result: GoldenResult, repo, assessment, blast, ground, pid: str,
           claims_file: Path) -> None:
    m = result.metrics

    # edges: expected subset of actual (recall), and precision vs expected set
    actual_edges = {
        (_node_ref(repo, e.source_id), _node_ref(repo, e.target_id), e.relation.value)
        for e in repo.list_edges(pid)
    }
    expected_edges = {tuple(t) for t in ground["expected_edges"]}
    recall = len(expected_edges & actual_edges) / len(expected_edges)
    m["edge_recall"] = recall
    m["edge_precision"] = len(expected_edges & actual_edges) / len(actual_edges) \
        if actual_edges else 0.0

    for src, tgt, rel in ground.get("assert_no_edges", []):
        m["no_false_edges"] = m.get("no_false_edges", True) and (src, tgt, rel) not in actual_edges

    # affected artifacts
    affected_refs = {_node_ref(repo, nid) for nid in blast.affected_node_ids}
    expected_artifacts = set(ground["expected_affected_artifact_refs"])
    m["artifact_recall"] = len(expected_artifacts & affected_refs) / len(expected_artifacts)
    m["artifact_precision"] = len(expected_artifacts & affected_refs) / len(affected_refs) \
        if affected_refs else 0.0

    # claims: declared ids -> computed claim ids must appear in conclusions
    declared_to_claim: dict[str, str] = {}
    with open(claims_file, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    for rc in raw.get("claims", []):
        ref = rc.get("id", "")
        text = rc.get("text", "")
        declared_to_claim[ref] = ids.claim_id(f"{ref}:{text}")
    conclusion_claim_ids = {c.subject_node_id for c in assessment.conclusions}
    expected_claim_ids = {declared_to_claim[i] for i in ground["expected_affected_claim_declared_ids"]}
    m["claim_recall"] = len(expected_claim_ids & conclusion_claim_ids) / len(expected_claim_ids)

    # unknowns
    unknown_refs = {_node_ref(repo, u.node_id) for u in assessment.unknowns}
    expected_unknowns = set(ground["expected_unknown_refs"])
    m["unknown_recall"] = len(expected_unknowns & unknown_refs) / len(expected_unknowns)

    # contradictions
    kinds = {s.kind for s in assessment.contradictions}
    m["contradiction_recall"] = len(set(ground["expected_contradiction_kinds"]) & kinds) / \
        len(ground["expected_contradiction_kinds"])

    # status
    m["status_match"] = assessment.status.value == ground["expected_status"]
    m["short_circuit_match"] = ground["expected_no_impact"] == (len(assessment.agent_calls) == 0)

    result.details["actual_edges"] = sorted(actual_edges)
    result.details["affected_refs"] = sorted(affected_refs)
    result.details["unknowns"] = sorted(unknown_refs)
    result.details["contradictions"] = sorted(kinds)
    result.details["conclusion_statuses"] = [c.status.value for c in assessment.conclusions]
