"""Config adapter: YAML/JSON/TOML/INI -> CONFIG nodes + READS edges + drift signal.

Path-like string values are resolved against the repo deterministically; anything
ambiguous is recorded as a coverage gap, never guessed.
"""

from __future__ import annotations

import configparser
import hashlib
import json
import posixpath
import tomllib
from typing import Any

import yaml

from ..logging import get_logger
from ..schemas import (
    CoverageLayer,
    EdgeRelation,
    Evidence,
    EvidenceSourceType,
    GraphEdge,
    GraphNode,
    NodeType,
    ProvenanceType,
    ids,
)
from .base import AdapterContext, AdapterOutput

log = get_logger(__name__)

CONFIG_EXTS = (".yaml", ".yml", ".json", ".toml", ".ini", ".cfg")

_FILE_EXTS = (".csv", ".json", ".yaml", ".yml", ".png", ".pkl", ".joblib", ".npz",
              ".npy", ".txt", ".parquet", ".h5", ".hdf5", ".pth", ".pt", ".onnx", ".log")


class ConfigAdapter:
    def __init__(self, repo_files: list[str]) -> None:
        self.repo_files = set(repo_files)

    def parse_file(self, relpath: str, raw: bytes, ctx: AdapterContext) -> AdapterOutput:
        out = AdapterOutput()
        cov = out.layer(CoverageLayer.STATIC)
        cov.scanned += 1
        data: Any = None
        try:
            text = raw.decode("utf-8")
            if relpath.endswith((".yaml", ".yml")):
                data = yaml.safe_load(text)
            elif relpath.endswith(".json"):
                data = json.loads(text)
            elif relpath.endswith(".toml"):
                data = tomllib.loads(text)
            elif relpath.endswith((".ini", ".cfg")):
                parser = configparser.ConfigParser()
                parser.read_string(text)
                data = {s: dict(parser.items(s)) for s in parser.sections()}
            else:
                data = text
        except Exception as exc:
            cov.failed += 1
            out.gaps.append(f"{relpath}: config parse failed: {exc}")
            return out
        cov.parsed += 1

        h = hashlib.sha256(raw).hexdigest()
        node = GraphNode(node_id=ids.node_id(NodeType.CONFIG.value, relpath),
                         project_id=ctx.project_id, node_type=NodeType.CONFIG,
                         label=relpath, ref=relpath, data={"content_hash": h})
        out.nodes.append(node)

        ev = Evidence(evidence_id=ids.evidence_id(EvidenceSourceType.CONFIG.value,
                                                  f"config:{relpath}", h, ctx.extractor),
                      project_id=ctx.project_id, source_type=EvidenceSourceType.CONFIG,
                      locator=f"config:{relpath}", content_hash=h, extractor=ctx.extractor,
                      payload={"keys": _collect_keys(data), "paths": _collect_paths(data)},
                      snapshot_id=ctx.snapshot_id)
        out.evidence.append(ev)

        for path_val in _collect_paths(data):
            resolved = self._resolve_path(relpath, path_val)
            if resolved is None:
                cov.unknown += 1
                out.gaps.append(f"{relpath}: config path {path_val!r} unresolved")
                continue
            if resolved in self.repo_files and resolved.endswith((".py", ".ipynb")):
                target = GraphNode(node_id=ids.node_id(NodeType.FILE.value, resolved),
                                   project_id=ctx.project_id, node_type=NodeType.FILE,
                                   label=resolved, ref=resolved)
            else:
                target = GraphNode(node_id=ids.node_id(NodeType.ARTIFACT.value, resolved),
                                   project_id=ctx.project_id, node_type=NodeType.ARTIFACT,
                                   label=resolved, ref=resolved)
            out.nodes.append(target)
            out.edges.append(GraphEdge(
                edge_id=ids.edge_id(node.node_id, target.node_id, EdgeRelation.READS.value),
                project_id=ctx.project_id, source_id=node.node_id, target_id=target.node_id,
                relation=EdgeRelation.READS, provenance_type=ProvenanceType.STATIC,
                evidence_ids=[ev.evidence_id], locator=f"config:{relpath}",
                snapshot_id=ctx.snapshot_id, extractor_version=ctx.extractor))
        return out

    def drift_signal(self, relpath: str, change_evidence_id: str) -> dict[str, Any] | None:
        if not relpath.endswith(CONFIG_EXTS):
            return None
        return {
            "kind": "CONFIG_DRIFT",
            "description": f"config file changed in this change: {relpath}",
            "evidence_ids": [change_evidence_id],
            "affected_node_ids": [ids.node_id(NodeType.CONFIG.value, relpath)],
            "severity": "warn",
        }

    def _resolve_path(self, from_rel: str, ref: str) -> str | None:
        if not ref or len(ref) > 500:
            return None
        ref = ref.replace("\\", "/")
        if not (any(c in ref for c in ("/",)) or ref.endswith(_FILE_EXTS)):
            return None
        ref = ref.lstrip("/")
        base = posixpath.dirname(from_rel)
        for cand in (posixpath.normpath(posixpath.join(base, ref)), ref):
            if cand in self.repo_files:
                return cand
        return None


def _collect_keys(data: Any, prefix: str = "", depth: int = 0) -> list[str]:
    keys: list[str] = []
    if depth > 6 or data is None:
        return keys
    if isinstance(data, dict):
        for k, v in data.items():
            keys.append(f"{prefix}{k}")
            keys.extend(_collect_keys(v, f"{prefix}{k}.", depth + 1))
    return keys


def _collect_paths(data: Any, depth: int = 0) -> list[str]:
    out: list[str] = []
    if depth > 6 or data is None:
        return out
    if isinstance(data, dict):
        for v in data.values():
            out.extend(_collect_paths(v, depth + 1))
    elif isinstance(data, list):
        for v in data:
            out.extend(_collect_paths(v, depth + 1))
    elif isinstance(data, str) and data and (
            ("/" in data and not data.startswith(("http://", "https://")))
            or data.endswith(_FILE_EXTS)):
        out.append(data)
    return out
