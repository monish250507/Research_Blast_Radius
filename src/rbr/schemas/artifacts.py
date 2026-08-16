"""Artifacts, experiments, runs (spec section 6.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from .core import RBREntity


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Artifact(RBREntity):
    artifact_id: str
    project_id: str
    type: str
    path: str
    content_hash: str
    size: int = 0
    mime_type: str | None = None
    snapshot_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Experiment(RBREntity):
    experiment_id: str
    project_id: str
    command: str
    config_hash: str | None = None
    run_id: str | None = None
    fingerprint: str | None = None


class Run(RBREntity):
    run_id: str
    project_id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    environment: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    trace_status: str = "not_traced"
