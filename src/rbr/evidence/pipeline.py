"""Ingestion pipeline: deterministic evidence acquisition for a change.

Order: git fingerprint -> change -> full-repo static parse -> config -> artifacts
-> notebook -> graph records. All edges are evidence-backed; dynamic constructs
are recorded as coverage gaps. No LLM is involved anywhere in this stage.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field

from ..logging import get_logger
from ..schemas import (
    Change,
    ChangeKind,
    Coverage,
    CoverageLayer,
    EdgeRelation,
    GraphEdge,
    GraphNode,
    LayerCoverage,
    NodeType,
    ProvenanceType,
    Snapshot,
    ids,
)
from ..store.repository import Repository
from .artifact_adapter import ArtifactAdapter
from .base import AdapterContext, AdapterOutput
from .config_adapter import CONFIG_EXTS, ConfigAdapter
from .git_adapter import GitAdapter
from .notebook_adapter import NotebookAdapter
from .python_adapter import ModuleResolver, PythonAdapter, PythonGraphExtractor

log = get_logger(__name__)

Fetch = Callable[[str], bytes]


@dataclass
class IngestResult:
    project_id: str
    change: Change
    snapshot_before: Snapshot | None = None
    snapshot_after: Snapshot | None = None
    output: AdapterOutput = field(default_factory=AdapterOutput)
    config_paths: list[str] = field(default_factory=list)
    signals: list[tuple[str, dict]] = field(default_factory=list)
    coverage: Coverage | None = None


class IngestionPipeline:
    def __init__(self, repo_path: str, repo_root: str | None = None) -> None:
        self.repo_path = os.path.abspath(repo_path)
        self.git = GitAdapter(repo_path)
        self.python = PythonAdapter()

    def ingest_commit_range(self, project_id: str, from_sha: str, to_sha: str) -> IngestResult:
        before = self.git.snapshot(project_id, from_sha)
        after = self.git.snapshot(project_id, to_sha)
        change = self.git.build_change(project_id, ChangeKind.COMMIT_RANGE, from_sha, to_sha,
                                       snapshot_before=before.snapshot_id)
        return self._run(project_id, change, before, after)

    def ingest_commit(self, project_id: str, commit: str) -> IngestResult:
        parents = _git_parents(self.repo_path, commit)
        if not parents:
            raise GitParentError(f"commit {commit} has no parent; cannot compute a diff")
        from_sha = parents[0]
        return self.ingest_commit_range(project_id, from_sha, commit)

    def ingest_file_lines(self, project_id: str, commit: str, file_path: str,
                          line_start: int, line_end: int) -> IngestResult:
        after = self.git.snapshot(project_id, commit)
        change = Change(project_id=project_id, snapshot_after=after.snapshot_id,
                        kind=ChangeKind.FILE_LINE, label=f"{file_path}:{line_start}-{line_end}",
                        to_sha=commit, file_path=file_path, line_range=(line_start, line_end),
                        diff_hash=ids.content_hash(f"{file_path}:{line_start}-{line_end}".encode()))
        return self._run(project_id, change, None, after)

    def _run(self, project_id: str, change: Change, before: Snapshot | None,
             after: Snapshot) -> IngestResult:
        ctx = AdapterContext(project_id=project_id, snapshot_id=after.snapshot_id)
        result = IngestResult(project_id=project_id, change=change,
                              snapshot_before=before, snapshot_after=after)

        files = self.git.files_at(change.to_sha)
        changed = {f.path for f in change.files}
        if change.kind == ChangeKind.FILE_LINE and change.file_path:
            changed = {change.file_path}

        def fetch(path: str) -> bytes:
            return self.git.file_content(change.to_sha, path)

        # 1) change-level diff evidence
        diff_out = self.git.to_evidence(change, ctx)
        result.output.evidence.extend(diff_out.evidence)
        result.output.layer(CoverageLayer.CHANGE).scanned = diff_out.layer(CoverageLayer.CHANGE).scanned
        result.output.layer(CoverageLayer.CHANGE).parsed = diff_out.layer(CoverageLayer.CHANGE).parsed

        change_node = GraphNode(node_id=ids.node_id(NodeType.CHANGE.value, change.change_id),
                                project_id=project_id, node_type=NodeType.CHANGE,
                                label=change.label or change.change_id, ref=change.change_id)
        result.output.nodes.append(change_node)
        change_ev_id = diff_out.evidence[0].evidence_id if diff_out.evidence else ""
        for relpath in changed:
            file_node_id = ids.node_id(NodeType.FILE.value, relpath)
            result.output.edges.append(GraphEdge(
                edge_id=ids.edge_id(change_node.node_id, file_node_id,
                                    EdgeRelation.ASSOCIATED_WITH.value),
                project_id=project_id, source_id=change_node.node_id,
                target_id=file_node_id, relation=EdgeRelation.ASSOCIATED_WITH,
                provenance_type=ProvenanceType.STATIC, evidence_ids=[change_ev_id] if change_ev_id else [],
                locator=f"git:change:{change.change_id}:{relpath}",
                snapshot_id=after.snapshot_id, extractor_version=ctx.extractor))

        # 2) python files (all, for a complete dependency graph)
        py_files = [f for f in files if f.endswith(".py") and not f.startswith(".git/")]
        extractor = PythonGraphExtractor(files, repo_root="")
        for relpath in py_files:
            try:
                src = fetch(relpath).decode("utf-8", errors="replace")
            except Exception:
                src = ""
            extractor.add_parse(relpath, self.python.parse(src))
        py_out = extractor.extract(ctx)
        _merge(result.output, py_out)

        # 3) notebooks
        nb_files = [f for f in files if f.endswith(".ipynb") and not f.startswith(".git/")]
        nb_adapter = NotebookAdapter(ModuleResolver(py_files))
        for relpath in nb_files:
            raw = fetch(relpath)
            _merge(result.output, nb_adapter.parse_notebook(relpath, raw, ctx))

        # 4) configs (skip generated/output dirs so artifacts aren't misread as configs)
        _OUTPUT_DIRS = ("outputs/", "results/", "figures/", "data/", "models/",
                        "checkpoints/", "artifacts/", "logs/")
        config_adapter = ConfigAdapter(files)
        config_paths: list[str] = []
        for relpath in files:
            if relpath.startswith(".git/") or relpath.endswith(".py") or relpath.endswith(".ipynb"):
                continue
            if relpath.startswith(_OUTPUT_DIRS):
                continue
            if relpath.endswith(CONFIG_EXTS):
                config_paths.append(relpath)
                _merge(result.output, config_adapter.parse_file(relpath, fetch(relpath), ctx))
        result.config_paths = config_paths

        # config drift signals for changed configs
        for relpath in changed:
            signal = config_adapter.drift_signal(relpath, change_ev_id)
            if signal:
                sig_id = ids.signal_id(signal["kind"], relpath, change.change_id)
                result.output.gaps.append(f"signal:{sig_id}:{signal['description']}")
                result.signals.append((sig_id, signal))

        # 5) artifacts
        art_adapter = ArtifactAdapter(repo_root=self.repo_path, exclude_paths=set(config_paths))
        _merge(result.output, art_adapter.scan_with(files, ctx, fetch))

        # 6) coverage
        coverage = _build_coverage(project_id, change.change_id, result.output.coverage)
        result.coverage = coverage
        return result


class GitParentError(RuntimeError):
    pass


def _git_parents(repo_path: str, commit: str) -> list[str]:
    import subprocess

    proc = subprocess.run(["git", "-C", repo_path, "rev-parse", f"{commit}^"],
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        return []
    return [proc.stdout.strip()]


def _merge(dst: AdapterOutput, src: AdapterOutput) -> None:
    dst.evidence.extend(src.evidence)
    dst.nodes.extend(src.nodes)
    dst.edges.extend(src.edges)
    dst.gaps.extend(src.gaps)
    for layer, cov in src.coverage.items():
        cur = dst.layer(layer)
        cur.scanned += cov.scanned
        cur.parsed += cov.parsed
        cur.failed += cov.failed
        cur.unknown += cov.unknown
        cur.notes.extend(cov.notes)


def _build_coverage(project_id: str, change_id: str,
                    layers: dict[CoverageLayer, LayerCoverage]) -> Coverage:
    return Coverage(project_id=project_id, change_id=change_id, layers=layers)


def persist(repo: Repository, result: IngestResult) -> None:
    """Write an ingest result to the store (idempotent, append-only)."""
    repo.create_project(result.project_id, owner="", repository="", scope="python+git+jupyter")
    if result.snapshot_before:
        snap = result.snapshot_before
        repo.create_snapshot(snap.snapshot_id, snap.project_id, snap.commit_sha,
                             snap.repository_hash, snap.environment_fingerprint)
    if result.snapshot_after:
        snap_after = result.snapshot_after
        repo.create_snapshot(snap_after.snapshot_id, snap_after.project_id,
                             snap_after.commit_sha, snap_after.repository_hash,
                             snap_after.environment_fingerprint)

    change = result.change
    from sqlalchemy import text

    with repo.session() as s:
        s.execute(text(
            "INSERT INTO changes (change_id, project_id, snapshot_before, snapshot_after, "
            "kind, label, from_sha, to_sha, file_path, line_range, diff_hash, files) "
            "VALUES (:cid, :pid, :sb, :sa, :kind, :label, :fs, :ts, :fp, :lr, :dh, :files) "
            "ON CONFLICT DO NOTHING"
        ), {
            "cid": change.change_id, "pid": change.project_id,
            "sb": change.snapshot_before, "sa": change.snapshot_after,
            "kind": change.kind.value, "label": change.label,
            "fs": change.from_sha, "ts": change.to_sha, "fp": change.file_path,
            "lr": list(change.line_range) if change.line_range else None,
            "dh": change.diff_hash,
            "files": json.dumps([f.model_dump(mode="json") for f in change.files]),
        })

    repo.add_evidence_bulk(result.output.evidence)
    for node in result.output.nodes:
        repo.upsert_node(node)
    for edge in result.output.edges:
        repo.add_edge(edge)
    for sig_id, signal in result.signals:
        repo.add_signal(sig_id, result.project_id, signal["kind"], signal["description"],
                        signal.get("evidence_ids", []), signal.get("affected_node_ids", []),
                        signal.get("severity", "info"))
    if result.coverage:
        repo.save_coverage(result.project_id, change.change_id, result.coverage)
