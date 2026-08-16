"""Deterministic identifier generation.

Evidence/node/edge IDs are content-addressed so repeated analysis of the same
evidence produces identical IDs (spec requirement: reproducible deterministic graph).
Entity IDs that are inherently non-deterministic (projects, assessments) use UUIDs.
"""

from __future__ import annotations

import hashlib
import uuid

_PREFIXES = {
    "project": "prj",
    "snapshot": "snap",
    "change": "chg",
    "evidence": "ev",
    "node": "node",
    "edge": "edge",
    "artifact": "art",
    "experiment": "exp",
    "run": "run",
    "claim": "clm",
    "signal": "sig",
    "assessment": "asmt",
    "agent_call": "call",
    "gating": "gate",
    "action": "act",
    "conclusion": "conc",
}


def _digest(*parts: str, length: int = 20) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8", errors="replace"))
        h.update(b"\x00")
    return h.hexdigest()[:length]


def content_hash(data: bytes) -> str:
    """Content hash used for artifacts and evidence payloads."""
    return hashlib.sha256(data).hexdigest()


def project_id() -> str:
    return f"prj:{uuid.uuid4().hex}"


def snapshot_id(commit_sha: str) -> str:
    return f"snap:{commit_sha[:12]}"


def change_id() -> str:
    return f"chg:{uuid.uuid4().hex}"


def evidence_id(source_type: str, locator: str, payload_hash: str, extractor: str) -> str:
    return f"ev:{_digest(source_type, locator, payload_hash, extractor)}"


def node_id(node_type: str, ref: str) -> str:
    return f"node:{node_type}:{_digest(ref, node_type)}"


def edge_id(source_id: str, target_id: str, relation: str) -> str:
    return f"edge:{_digest(source_id, target_id, relation)}"


def artifact_id(path: str, blob_hash: str) -> str:
    return f"art:{_digest(path, blob_hash)}"


def claim_id(ref: str) -> str:
    return f"clm:{_digest(ref)}"


def run_id() -> str:
    return f"run:{uuid.uuid4().hex}"


def experiment_id(command: str, config_hash: str) -> str:
    return f"exp:{_digest(command, config_hash)}"


def assessment_id() -> str:
    return f"asmt:{uuid.uuid4().hex}"


def signal_id(kind: str, *parts: str) -> str:
    return f"sig:{_digest(kind, *parts)}"


def agent_call_id() -> str:
    return f"call:{uuid.uuid4().hex}"


def gating_id() -> str:
    return f"gate:{uuid.uuid4().hex}"


def action_id() -> str:
    return f"act:{uuid.uuid4().hex}"
