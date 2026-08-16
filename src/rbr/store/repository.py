"""Repository: append-only, immutable evidence store with a dialect-agnostic interface.

Enforced properties:
- Evidence records are immutable (add-only, conflict detection).
- Evidence IDs are content-addressed and deterministic.
- All writes go through the repository; no ad-hoc session access.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..schemas import (
    Artifact,
    Assessment,
    ChangeKind,
    Claim,
    Coverage,
    EdgeRelation,
    Evidence,
    EvidenceSourceType,
    ExtractionStatus,
    GraphEdge,
    GraphNode,
    NodeType,
    ProvenanceType,
)
from . import models as m

_json_defaults = {"json_serializer": lambda v: __import__("json").dumps(v),
                  "json_deserializer": lambda v: __import__("json").loads(v)}


def create_engine_from_url(url: str, echo: bool = False) -> Engine:
    kwargs: dict[str, Any] = dict(echo=echo, future=True)
    if url.startswith("sqlite"):
        kwargs.update(connect_args={"check_same_thread": False})
        kwargs.update(_json_defaults)
    else:
        kwargs.update(_json_defaults)
    return create_engine(url, **kwargs)


class Repository:
    """Thin, typed facade over SQLAlchemy sessions."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    @contextlib.contextmanager
    def session(self) -> Iterator[Session]:
        with self._session_factory() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    def create_all(self) -> None:
        m.Base.metadata.create_all(self.engine)

    # --- projects / snapshots / changes ---

    def create_project(self, project_id: str, owner: str, repository: str, scope: str) -> None:
        from sqlalchemy import text

        with self.session() as s:
            s.execute(text(
                "INSERT INTO projects (project_id, owner, repository, supported_scope) "
                "VALUES (:pid, :owner, :repository, :scope) ON CONFLICT DO NOTHING"
            ), {"pid": project_id, "owner": owner, "repository": repository, "scope": scope})

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.session() as s:
            row = s.get(m.ProjectRow, project_id)
            return _row_dict(row) if row else None

    def get_change(self, change_id: str) -> Any | None:
        from ..schemas import Change, FileDiff

        with self.session() as s:
            row = s.get(m.ChangeRow, change_id)
            if row is None:
                return None
            files = [FileDiff.model_validate(f) for f in (row.files or [])]
            line_range = tuple(row.line_range) if row.line_range else None
            return Change(
                change_id=row.change_id, project_id=row.project_id,
                snapshot_before=row.snapshot_before, snapshot_after=row.snapshot_after,
                kind=ChangeKind(row.kind), label=row.label, from_sha=row.from_sha, to_sha=row.to_sha,
                file_path=row.file_path, line_range=line_range, diff_hash=row.diff_hash,
                files=files,
            )

    def create_snapshot(self, snapshot_id: str, project_id: str, commit_sha: str,
                        repository_hash: str, env_fingerprint: str | None) -> None:
        with self.session() as s:
            s.add(m.SnapshotRow(snapshot_id=snapshot_id, project_id=project_id,
                                commit_sha=commit_sha, repository_hash=repository_hash,
                                environment_fingerprint=env_fingerprint))

    # --- evidence (immutable) ---

    def add_evidence(self, evidence: Evidence) -> bool:
        """Add an evidence record. Returns True if created, False if identical exists.

        Raises ValueError if a different record already uses the same evidence_id.
        """
        with self.session() as s:
            existing = s.get(m.EvidenceRow, evidence.evidence_id)
            if existing is not None:
                if existing.content_hash == evidence.content_hash:
                    return False
                raise ValueError(f"evidence id collision: {evidence.evidence_id}")
            s.add(_evidence_row(evidence))
            return True

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        with self.session() as s:
            row = s.get(m.EvidenceRow, evidence_id)
            return _evidence_from_row(row) if row else None

    def evidence_exists(self, evidence_id: str) -> bool:
        with self.session() as s:
            return s.get(m.EvidenceRow, evidence_id) is not None

    def list_evidence(self, project_id: str, limit: int = 10000) -> list[Evidence]:
        with self.session() as s:
            rows = s.scalars(
                select(m.EvidenceRow).where(m.EvidenceRow.project_id == project_id).limit(limit)
            ).all()
            return [_evidence_from_row(r) for r in rows]

    def add_evidence_bulk(self, items: list[Evidence]) -> int:
        created = 0
        for ev in items:
            if self.add_evidence(ev):
                created += 1
        return created

    # --- nodes / edges ---

    def upsert_node(self, node: GraphNode) -> bool:
        """Insert node if absent. Returns True if created."""
        with self.session() as s:
            existing = s.get(m.NodeRow, node.node_id)
            if existing is not None:
                return False
            s.add(m.NodeRow(node_id=node.node_id, project_id=node.project_id,
                            node_type=node.node_type.value, label=node.label, ref=node.ref,
                            data=node.data))
            return True

    def get_node(self, node_id: str) -> GraphNode | None:
        with self.session() as s:
            row = s.get(m.NodeRow, node_id)
            return _node_from_row(row) if row else None

    def list_nodes(self, project_id: str) -> list[GraphNode]:
        with self.session() as s:
            rows = s.scalars(select(m.NodeRow).where(m.NodeRow.project_id == project_id)).all()
            return [_node_from_row(r) for r in rows]

    def add_edge(self, edge: GraphEdge) -> bool:
        with self.session() as s:
            existing = s.get(m.EdgeRow, edge.edge_id)
            if existing is not None:
                return False
            s.add(m.EdgeRow(edge_id=edge.edge_id, project_id=edge.project_id,
                            source_id=edge.source_id, target_id=edge.target_id,
                            relation=edge.relation.value,
                            provenance_type=edge.provenance_type.value,
                            evidence_ids=edge.evidence_ids, locator=edge.locator,
                            run_id=edge.run_id, snapshot_id=edge.snapshot_id,
                            scope=edge.scope, extractor_version=edge.extractor_version))
            return True

    def list_edges(self, project_id: str) -> list[GraphEdge]:
        with self.session() as s:
            rows = s.scalars(select(m.EdgeRow).where(m.EdgeRow.project_id == project_id)).all()
            return [_edge_from_row(r) for r in rows]

    def edges_from(self, project_id: str, node_id: str) -> list[GraphEdge]:
        with self.session() as s:
            rows = s.scalars(
                select(m.EdgeRow).where(m.EdgeRow.project_id == project_id,
                                        m.EdgeRow.source_id == node_id)
            ).all()
            return [_edge_from_row(r) for r in rows]

    # --- claims ---

    def upsert_claim(self, claim: Claim) -> bool:
        with self.session() as s:
            existing = s.get(m.ClaimRow, claim.claim_id)
            if existing is not None:
                return False
            s.add(m.ClaimRow(
                claim_id=claim.claim_id, project_id=claim.project_id,
                normalized_text=claim.normalized_text, subject=claim.subject,
                intervention=claim.intervention, comparator=claim.comparator,
                metric=claim.metric, magnitude=claim.magnitude,
                population=claim.population, dataset=claim.dataset,
                condition=claim.condition, qualifiers=claim.qualifiers,
                evidence_locations=claim.evidence_locations,
                source_section=claim.source_section, source=claim.source,
                extraction_status=claim.extraction_status.value,
            ))
            return True

    def list_claims(self, project_id: str) -> list[Claim]:
        with self.session() as s:
            rows = s.scalars(select(m.ClaimRow).where(m.ClaimRow.project_id == project_id)).all()
            return [_claim_from_row(r) for r in rows]

    def get_claim(self, claim_id: str) -> Claim | None:
        with self.session() as s:
            row = s.get(m.ClaimRow, claim_id)
            return _claim_from_row(row) if row else None

    # --- signals / artifacts / assessments / calls / gating / coverage ---

    def add_signal(self, signal_id: str, project_id: str, kind: str, description: str,
                   evidence_ids: list[str], affected_node_ids: list[str], severity: str) -> None:
        with self.session() as s:
            s.add(m.SignalRow(signal_id=signal_id, project_id=project_id, kind=kind,
                              description=description, evidence_ids=evidence_ids,
                              affected_node_ids=affected_node_ids, severity=severity))

    def list_signals(self, project_id: str) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = s.scalars(select(m.SignalRow).where(m.SignalRow.project_id == project_id)).all()
            return [_row_dict(r) for r in rows]

    def save_assessment(self, assessment: Assessment) -> None:
        with self.session() as s:
            s.add(m.AssessmentRow(assessment_id=assessment.assessment_id,
                                  project_id=assessment.project_id,
                                  change_id=assessment.change_id,
                                  body=assessment.model_dump(mode="json"),
                                  status=assessment.status.value))

    def get_assessment(self, assessment_id: str) -> Assessment | None:
        with self.session() as s:
            row = s.get(m.AssessmentRow, assessment_id)
            if row is None:
                return None
            return Assessment.model_validate(row.body)

    def add_agent_call(self, record: dict[str, Any]) -> None:
        with self.session() as s:
            s.add(m.AgentCallRow(call_id=record["call_id"], project_id=record["project_id"],
                                 agent_name=record["agent_name"], provider=record["provider"],
                                 model=record["model"], temperature=record["temperature"],
                                 prompt_hash=record["prompt_hash"],
                                 input_subgraph_hash=record.get("input_subgraph_hash", ""),
                                 output_json=record.get("output_json", {}),
                                 status=record.get("status", "ok"),
                                 usage=record.get("usage", {})))

    def add_gating(self, record: dict[str, Any]) -> None:
        with self.session() as s:
            s.add(m.GatingRow(gating_id=record["gating_id"], project_id=record["project_id"],
                              change_id=record["change_id"], stage=record["stage"],
                              enabled=record["enabled"], reason=record.get("reason", ""),
                              budget_tokens=record.get("budget_tokens", 0)))

    def save_coverage(self, project_id: str, change_id: str, coverage: Coverage) -> None:
        with self.session() as s:
            s.add(m.CoverageRow(project_id=project_id, change_id=change_id,
                                body=coverage.model_dump(mode="json")))

    def get_coverage(self, project_id: str, change_id: str) -> Coverage | None:
        with self.session() as s:
            row = s.scalar(select(m.CoverageRow).where(m.CoverageRow.project_id == project_id,
                                                       m.CoverageRow.change_id == change_id))
            return Coverage.model_validate(row.body) if row else None

    def upsert_artifact(self, artifact: Artifact) -> bool:
        with self.session() as s:
            existing = s.get(m.ArtifactRow, artifact.artifact_id)
            if existing is not None:
                return False
            s.add(m.ArtifactRow(artifact_id=artifact.artifact_id, project_id=artifact.project_id,
                                type=artifact.type, path=artifact.path,
                                content_hash=artifact.content_hash, size=artifact.size,
                                mime_type=artifact.mime_type, snapshot_id=artifact.snapshot_id))
            return True

    def get_artifact(self, artifact_id: str) -> Artifact | None:
        with self.session() as s:
            row = s.get(m.ArtifactRow, artifact_id)
            if row is None:
                return None
            return Artifact.model_validate(_row_dict(row))


# --- row/object converters ---------------------------------------------------

def _row_dict(row: Any) -> dict[str, Any]:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def _evidence_row(ev: Evidence) -> m.EvidenceRow:
    return m.EvidenceRow(evidence_id=ev.evidence_id, project_id=ev.project_id,
                         source_type=ev.source_type.value, locator=ev.locator,
                         content_hash=ev.content_hash, extractor=ev.extractor,
                         payload=ev.payload, snapshot_id=ev.snapshot_id)


def _evidence_from_row(row: m.EvidenceRow) -> Evidence:
    return Evidence(evidence_id=row.evidence_id, project_id=row.project_id,
                    source_type=EvidenceSourceType(row.source_type), locator=row.locator,
                    content_hash=row.content_hash, extractor=row.extractor,
                    payload=row.payload or {}, snapshot_id=row.snapshot_id)


def _node_from_row(row: m.NodeRow) -> GraphNode:
    return GraphNode(node_id=row.node_id, project_id=row.project_id,
                     node_type=NodeType(row.node_type), label=row.label, ref=row.ref,
                     data=row.data or {})


def _edge_from_row(row: m.EdgeRow) -> GraphEdge:
    return GraphEdge(edge_id=row.edge_id, project_id=row.project_id,
                     source_id=row.source_id, target_id=row.target_id,
                     relation=EdgeRelation(row.relation), provenance_type=ProvenanceType(row.provenance_type),
                     evidence_ids=row.evidence_ids or [], locator=row.locator or "",
                     run_id=row.run_id, snapshot_id=row.snapshot_id, scope=row.scope,
                     extractor_version=row.extractor_version)


def _claim_from_row(row: m.ClaimRow) -> Claim:
    return Claim(claim_id=row.claim_id, project_id=row.project_id,
                 normalized_text=row.normalized_text, subject=row.subject,
                 intervention=row.intervention, comparator=row.comparator,
                 metric=row.metric, magnitude=row.magnitude, population=row.population,
                 dataset=row.dataset, condition=row.condition,
                 qualifiers=row.qualifiers or [], evidence_locations=row.evidence_locations or [],
                 source_section=row.source_section, source=row.source,
                 extraction_status=ExtractionStatus(row.extraction_status))


def open_repository(url: str) -> Repository:
    engine = create_engine_from_url(url)
    repo = Repository(engine)
    repo.create_all()
    return repo
