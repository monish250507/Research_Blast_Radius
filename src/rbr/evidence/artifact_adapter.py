"""Artifact adapter: content-hash + manifest for observed files.

Never infers that two same-named files are the same artifact without hash
evidence (spec section 7.5). Config/source files handled by their own adapters.
"""

from __future__ import annotations

import hashlib
import os
import posixpath

from ..logging import get_logger
from ..schemas import (
    CoverageLayer,
    Evidence,
    EvidenceSourceType,
    GraphNode,
    NodeType,
    ids,
)
from .base import AdapterContext, AdapterOutput

log = get_logger(__name__)

_DATA_EXTS = (".csv", ".tsv", ".json", ".pkl", ".joblib", ".npz", ".npy", ".png",
              ".svg", ".pdf", ".txt", ".parquet", ".h5", ".hdf5", ".pth", ".pt",
              ".onnx", ".db", ".sqlite", ".log", ".html", ".ipynb", ".xlsx", ".zip")

_MIME = {
    ".csv": "text/csv", ".json": "application/json", ".png": "image/png",
    ".svg": "image/svg+xml", ".pdf": "application/pdf", ".pkl": "application/octet-stream",
    ".joblib": "application/octet-stream", ".npy": "application/octet-stream",
    ".npz": "application/octet-stream", ".parquet": "application/octet-stream",
    ".h5": "application/x-hdf5", ".hdf5": "application/x-hdf5", ".pth": "application/octet-stream",
    ".pt": "application/octet-stream", ".onnx": "application/octet-stream",
    ".txt": "text/plain", ".log": "text/plain", ".tsv": "text/tab-separated-values",
    ".yaml": "application/yaml", ".yml": "application/yaml", ".db": "application/octet-stream",
    ".sqlite": "application/octet-stream", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".html": "text/html", ".zip": "application/zip", ".ipynb": "application/json",
}


class ArtifactAdapter:
    def __init__(self, repo_root: str, exclude_paths: set[str] | None = None,
                 data_exts: tuple[str, ...] = _DATA_EXTS) -> None:
        self.repo_root = repo_root
        self.exclude = exclude_paths or set()
        self.data_exts = data_exts

    def scan(self, files: list[str], ctx: AdapterContext) -> AdapterOutput:
        def _fetch(norm: str) -> bytes:
            abs_path = os.path.normpath(os.path.join(self.repo_root, *norm.split("/")))
            return _read(abs_path)

        return self.scan_with(files, ctx, _fetch)

    def scan_with(self, files: list[str], ctx: AdapterContext,
                  fetch: object) -> AdapterOutput:
        out = AdapterOutput()
        cov = out.layer(CoverageLayer.ARTIFACT)
        hashes: dict[str, str] = {}
        for relpath in files:
            norm = relpath.replace("\\", "/")
            if norm in self.exclude:
                continue
            if norm.endswith((".py", ".pyc")) or norm.endswith((".ini", ".cfg", ".toml")):
                continue
            if norm.startswith(".git/"):
                continue
            if not norm.endswith(self.data_exts):
                continue
            cov.scanned += 1
            try:
                blob = fetch(norm)  # type: ignore[operator]
            except Exception:
                continue
            h = hashlib.sha256(blob).hexdigest()
            hashes[norm] = h
            mime = _MIME.get(posixpath.splitext(norm)[1].lower(), "application/octet-stream")
            node = GraphNode(
                node_id=ids.node_id(NodeType.ARTIFACT.value, norm),
                project_id=ctx.project_id, node_type=NodeType.ARTIFACT,
                label=norm, ref=norm,
                data={"content_hash": h, "size": len(blob), "mime": mime},
            )
            out.nodes.append(node)
            cov.parsed += 1

        if hashes:
            manifest_hash = hashlib.sha256(
                "\n".join(f"{k}:{v}" for k, v in sorted(hashes.items())).encode()
            ).hexdigest()
            out.evidence.append(Evidence(
                evidence_id=ids.evidence_id(EvidenceSourceType.MANIFEST.value,
                                            "artifact:manifest", manifest_hash, ctx.extractor),
                project_id=ctx.project_id, source_type=EvidenceSourceType.MANIFEST,
                locator="artifact:manifest", content_hash=manifest_hash,
                extractor=ctx.extractor, payload={"artifacts": hashes},
                snapshot_id=ctx.snapshot_id,
            ))
        return out


def _read(abs_path: str) -> bytes:
    with open(abs_path, "rb") as f:
        return f.read()
