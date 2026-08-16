"""SQLAlchemy ORM mapping. One distribution, dialect-agnostic via JSON columns."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner: Mapped[str] = mapped_column(String(255), default="")
    repository: Mapped[str] = mapped_column(String(2048), default="")
    supported_scope: Mapped[str] = mapped_column(String(64), default="python+git+jupyter")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SnapshotRow(Base):
    __tablename__ = "snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    commit_sha: Mapped[str] = mapped_column(String(64))
    repository_hash: Mapped[str] = mapped_column(String(64))
    environment_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChangeRow(Base):
    __tablename__ = "changes"

    change_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    snapshot_before: Mapped[str | None] = mapped_column(String(40), nullable=True)
    snapshot_after: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(1024), default="")
    from_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_sha: Mapped[str] = mapped_column(String(64))
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    line_range: Mapped[list | None] = mapped_column(JSON, nullable=True)
    diff_hash: Mapped[str] = mapped_column(String(64))
    files: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceRow(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    locator: Mapped[str] = mapped_column(String(2048))
    content_hash: Mapped[str] = mapped_column(String(64))
    extractor: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NodeRow(Base):
    __tablename__ = "nodes"

    node_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    node_type: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(1024))
    ref: Mapped[str] = mapped_column(String(2048))
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class EdgeRow(Base):
    __tablename__ = "edges"

    edge_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    target_id: Mapped[str] = mapped_column(String(80), index=True)
    relation: Mapped[str] = mapped_column(String(32))
    provenance_type: Mapped[str] = mapped_column(String(16))
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    locator: Mapped[str] = mapped_column(String(2048), default="")
    run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scope: Mapped[str] = mapped_column(String(64), default="project")
    extractor_version: Mapped[str] = mapped_column(String(16), default="0.1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    artifact_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    type: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(String(2048))
    content_hash: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClaimRow(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    normalized_text: Mapped[str] = mapped_column(String(4096))
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    intervention: Mapped[str | None] = mapped_column(String(512), nullable=True)
    comparator: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metric: Mapped[str | None] = mapped_column(String(512), nullable=True)
    magnitude: Mapped[str | None] = mapped_column(String(512), nullable=True)
    population: Mapped[str | None] = mapped_column(String(512), nullable=True)
    dataset: Mapped[str | None] = mapped_column(String(512), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(512), nullable=True)
    qualifiers: Mapped[list] = mapped_column(JSON, default=list)
    evidence_locations: Mapped[list] = mapped_column(JSON, default=list)
    source_section: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="declared")
    extraction_status: Mapped[str] = mapped_column(String(32), default="EXTRACTED")


class SignalRow(Base):
    __tablename__ = "contradiction_signals"

    signal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(4096))
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    affected_node_ids: Mapped[list] = mapped_column(JSON, default=list)
    severity: Mapped[str] = mapped_column(String(16), default="info")


class AssessmentRow(Base):
    __tablename__ = "assessments"

    assessment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    change_id: Mapped[str] = mapped_column(String(40), index=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentCallRow(Base):
    __tablename__ = "agent_calls"

    call_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    agent_name: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128), default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    prompt_hash: Mapped[str] = mapped_column(String(64))
    input_subgraph_hash: Mapped[str] = mapped_column(String(64), default="")
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GatingRow(Base):
    __tablename__ = "gating_decisions"

    gating_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    change_id: Mapped[str] = mapped_column(String(40), index=True)
    stage: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str] = mapped_column(String(2048), default="")
    budget_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CoverageRow(Base):
    __tablename__ = "coverage"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(40), index=True)
    change_id: Mapped[str] = mapped_column(String(40), index=True)
    body: Mapped[dict] = mapped_column(JSON, default=dict)
