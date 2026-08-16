"""Git adapter: fingerprint snapshots and produce deterministic diff evidence.

Uses the git CLI (subprocess) rather than a library so behaviour is stable and
dependency-free. All evidence is content-hashed and immutable.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from typing import Any

from ..logging import get_logger
from ..schemas import (
    Change,
    ChangeKind,
    CoverageLayer,
    Evidence,
    EvidenceSourceType,
    FileChangeStatus,
    FileDiff,
    Hunk,
    Snapshot,
    ids,
)
from .base import AdapterContext, AdapterOutput

log = get_logger(__name__)

_ZERO_SHA = "0" * 40


class GitError(RuntimeError):
    pass


def _git(repo_path: str, *args: str, cwd: str | None = None) -> str:
    cmd = ["git", "-C", repo_path, "-c", "core.quotepath=false", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, encoding="utf-8",
                          errors="replace")
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


class GitAdapter:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = os.path.abspath(repo_path)

    # --- fingerprints ---

    def repository_hash(self, commit: str) -> str:
        tree = _git(self.repo_path, "rev-parse", f"{commit}^{{tree}}").strip()
        return hashlib.sha256(tree.encode()).hexdigest()

    def commit_exists(self, commit: str) -> bool:
        try:
            _git(self.repo_path, "rev-parse", "--verify", f"{commit}^{{commit}}")
            return True
        except GitError:
            return False

    def snapshot(self, project_id: str, commit: str) -> Snapshot:
        return Snapshot.build(project_id, commit, self.repository_hash(commit))

    def files_at(self, commit: str) -> list[str]:
        out = _git(self.repo_path, "ls-tree", "-r", "--name-only", commit).splitlines()
        return [line for line in out if line.strip()]

    def blob_sha(self, commit: str, path: str) -> str:
        out = _git(self.repo_path, "rev-parse", f"{commit}:{path}").strip()
        return out if out else _ZERO_SHA

    def file_content(self, commit: str, path: str) -> bytes:
        proc = subprocess.run(
            ["git", "-C", self.repo_path, "show", f"{commit}:{path}"],
            capture_output=True, cwd=self.repo_path,
        )
        if proc.returncode != 0:
            raise GitError(f"git show failed for {path}: {proc.stderr.decode()[:200]}")
        return proc.stdout

    # --- diff ---

    def diff_files(self, from_sha: str, to_sha: str) -> list[FileDiff]:
        raw = _git(self.repo_path, "diff", "--raw", "-M", from_sha, to_sha)
        results: list[FileDiff] = []
        for line in raw.splitlines():
            if not line or not line.startswith(":"):
                continue
            meta, _, paths = line.partition("\t")
            meta = meta[1:]
            parts = meta.split()
            if len(parts) < 5:
                continue
            old_sha, new_sha, status = parts[2], parts[3], parts[4]
            path_list = [p for p in paths.split("\t") if p]
            path = path_list[0] if path_list else ""
            old_path = path_list[1] if len(path_list) > 1 and status in ("R", "C") else None

            status_enum = _map_status(status, path, new_sha)
            diff = self._file_diff(path, status_enum, old_sha, new_sha, old_path, from_sha, to_sha)
            results.append(diff)
        return results

    def _file_diff(self, path: str, status: FileChangeStatus, old_sha: str, new_sha: str,
                   old_path: str | None, from_sha: str, to_sha: str) -> FileDiff:
        added: list[int] = []
        removed: list[int] = []
        hunks: list[Hunk] = []
        if status not in (FileChangeStatus.ADDED, FileChangeStatus.DELETED):
            patch = _git(self.repo_path, "diff", "-U0", "--find-renames", "-M",
                         from_sha, to_sha, "--", path)
            added, removed, hunks = _parse_patch(patch)
        return FileDiff(path=path, status=status, old_path=old_path,
                        old_sha=old_sha if old_sha != _ZERO_SHA else None,
                        new_sha=new_sha if new_sha != _ZERO_SHA else None,
                        added_lines=added, removed_lines=removed, hunks=hunks)

    def build_change(self, project_id: str, kind: ChangeKind, from_sha: str, to_sha: str,
                     label: str = "", file_path: str | None = None,
                     line_range: tuple[int, int] | None = None,
                     snapshot_before: str | None = None) -> Change:
        files = self.diff_files(from_sha, to_sha) if kind != ChangeKind.FILE_LINE else []
        diff_hash = hashlib.sha256(
            _git(self.repo_path, "diff", from_sha, to_sha).encode()
        ).hexdigest()
        return Change(
            project_id=project_id,
            snapshot_before=snapshot_before,
            snapshot_after=f"snap:{to_sha[:12]}",
            kind=kind,
            label=label,
            from_sha=from_sha,
            to_sha=to_sha,
            file_path=file_path,
            line_range=line_range,
            diff_hash=diff_hash,
            files=files,
        )

    def to_evidence(self, change: Change, ctx: AdapterContext) -> AdapterOutput:
        """Deterministic diff evidence, one record per changed file plus one overall."""
        out = AdapterOutput()
        raw_all = _git(self.repo_path, "diff", change.from_sha or "", change.to_sha)
        all_hash = hashlib.sha256(raw_all.encode()).hexdigest()
        locator = f"git:diff:{change.from_sha}..{change.to_sha}"
        out.evidence.append(_make_evidence(
            ctx, EvidenceSourceType.GIT_DIFF, locator, all_hash,
            {"change_id": change.change_id, "files": [f.path for f in change.files],
             "diff_hash": change.diff_hash},
        ))
        for fd in change.files:
            patch = _git(self.repo_path, "diff", "-U0", "--find-renames", "-M",
                         change.from_sha or "", change.to_sha, "--", fd.path)
            h = hashlib.sha256(patch.encode()).hexdigest()
            file_loc = f"git:diff:{change.from_sha}..{change.to_sha}:{fd.path}"
            out.evidence.append(_make_evidence(
                ctx, EvidenceSourceType.GIT_DIFF, file_loc, h,
                {"change_id": change.change_id, "file": fd.path, "status": fd.status.value,
                 "added_lines": fd.added_lines, "removed_lines": fd.removed_lines,
                 "old_sha": fd.old_sha, "new_sha": fd.new_sha},
            ))
        cov = out.layer(CoverageLayer.CHANGE)
        cov.scanned = len(change.files)
        cov.parsed = len(change.files)
        return out


# --- helpers ----------------------------------------------------------------


def _make_evidence(ctx: AdapterContext, source_type: EvidenceSourceType, locator: str,
                   content_hash: str, payload: dict[str, Any]) -> Evidence:
    return Evidence(
        evidence_id=ids.evidence_id(source_type.value, locator, content_hash, ctx.extractor),
        project_id=ctx.project_id,
        source_type=source_type,
        locator=locator,
        content_hash=content_hash,
        extractor=ctx.extractor,
        payload=payload,
        snapshot_id=ctx.snapshot_id,
    )


def _map_status(raw: str, path: str, new_sha: str) -> FileChangeStatus:
    if raw.startswith("R"):
        return FileChangeStatus.RENAMED
    if raw.startswith("C"):
        return FileChangeStatus.COPIED
    if raw == "D":
        return FileChangeStatus.DELETED
    if raw == "A":
        return FileChangeStatus.ADDED
    if raw == "M":
        return FileChangeStatus.MODIFIED
    if raw == "T" or raw == "U":
        return FileChangeStatus.MODIFIED
    if raw == "?":
        return FileChangeStatus.ADDED
    if new_sha == _ZERO_SHA:
        return FileChangeStatus.DELETED
    return FileChangeStatus.MODIFIED


def _parse_patch(patch: str) -> tuple[list[int], list[int], list[Hunk]]:
    added: list[int] = []
    removed: list[int] = []
    hunks: list[Hunk] = []
    current_new = 0
    current_old = 0
    current_new_off = 0
    current_old_off = 0
    for line in patch.splitlines():
        if line.startswith("@@"):
            # e.g. @@ -3,2 +5,1 @@ ctx
            hunk_header = line.split("@@")[1].strip()
            parts = hunk_header.split(" ")
            old_spec, new_spec = parts[0], parts[1]
            old_start, old_len = _spec(old_spec)
            new_start, new_len = _spec(new_spec)
            hunks.append(Hunk(start=new_start, length=new_len,
                              old_start=old_start, old_length=old_len, text=line))
            current_old = old_start
            current_new = new_start
            current_old_off = old_start
            current_new_off = new_start
            continue
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("+"):
            added.append(current_new)
            current_new += 1
            current_old_off += 1
        elif line.startswith("-"):
            removed.append(current_old)
            current_old += 1
            current_new_off += 1
        else:
            current_old += 1
            current_new += 1
            current_old_off += 1
            current_new_off += 1
    return added, removed, hunks


def _spec(spec: str) -> tuple[int, int]:
    s = spec[1:]
    if "," in s:
        start_s, len_s = s.split(",")
        return int(start_s), int(len_s)
    return int(s), 1
