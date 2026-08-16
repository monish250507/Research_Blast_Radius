"""Canonical core entities: Project, Snapshot, Change, diffs.

Frozen in v0.1.0. Bump the schema version via migration; do not edit in place.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import ChangeKind, FileChangeStatus
from .ids import change_id, project_id, snapshot_id


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RBREntity(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Project(RBREntity):
    project_id: str = Field(default_factory=project_id)
    owner: str
    repository: str
    supported_scope: str = "python+git+jupyter"
    created_at: datetime = Field(default_factory=_utcnow)


class Snapshot(RBREntity):
    snapshot_id: str
    project_id: str
    commit_sha: str
    repository_hash: str
    environment_fingerprint: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)

    @classmethod
    def build(cls, project_id: str, commit_sha: str, repository_hash: str) -> Snapshot:
        return cls(
            snapshot_id=snapshot_id(commit_sha),
            project_id=project_id,
            commit_sha=commit_sha,
            repository_hash=repository_hash,
        )


class Hunk(RBREntity):
    start: int
    length: int
    old_start: int | None = None
    old_length: int | None = None
    text: str = ""


class FileDiff(RBREntity):
    path: str
    status: FileChangeStatus
    old_path: str | None = None
    old_sha: str | None = None
    new_sha: str | None = None
    hunks: list[Hunk] = Field(default_factory=list)
    added_lines: list[int] = Field(default_factory=list)
    removed_lines: list[int] = Field(default_factory=list)


class Change(RBREntity):
    change_id: str = Field(default_factory=change_id)
    project_id: str
    snapshot_before: str | None = None
    snapshot_after: str
    kind: ChangeKind
    label: str = ""
    from_sha: str | None = None
    to_sha: str
    file_path: str | None = None
    line_range: tuple[int, int] | None = None
    diff_hash: str
    files: list[FileDiff] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
