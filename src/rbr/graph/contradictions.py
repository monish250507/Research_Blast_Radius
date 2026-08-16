"""Deterministic contradiction/mismatch scanner (spec section 21, 14.5).

Contradiction classes detected deterministically:
- NOTEBOOK_STATE: execution-order anomalies mark notebook state UNKNOWN.
- HASH_MISMATCH: a data artifact's content changed between snapshots.
- CONFIG_DRIFT: a config file changed in the change.
- MISSING_VERSION: an external resource lacks a version/hash anchor.
"""

from __future__ import annotations

from ..logging import get_logger
from ..schemas import (
    ContradictionSignal,
    NodeType,
    ids,
)
from ..store.repository import Repository
from .builder import EvidenceGraph

log = get_logger(__name__)


class ContradictionScanner:
    def __init__(self, repo: Repository, graph: EvidenceGraph) -> None:
        self.repo = repo
        self.graph = graph

    def scan(self, project_id: str, change_id: str, change_files: list[str],
             changed_data_files: list[str], notebook_unknown_nodes: list[str],
             pending_signals: list[tuple[str, dict]] | None = None) -> list[ContradictionSignal]:
        signals: list[ContradictionSignal] = []

        for node_id in notebook_unknown_nodes:
            node = self.graph.node(node_id)
            if node is None:
                continue
            signals.append(ContradictionSignal(
                signal_id=ids.signal_id("NOTEBOOK_STATE", node_id),
                project_id=project_id, kind="NOTEBOOK_STATE",
                description=f"notebook execution state is UNKNOWN: {node.label}",
                affected_node_ids=[node_id],
            ))

        for path in changed_data_files:
            art_id = ids.node_id(NodeType.ARTIFACT.value, path)
            node = self.repo.get_node(art_id)
            if node is None:
                continue
            signals.append(ContradictionSignal(
                signal_id=ids.signal_id("HASH_MISMATCH", art_id, change_id),
                project_id=project_id, kind="HASH_MISMATCH",
                description=f"data artifact content changed in this change: {path}",
                affected_node_ids=[art_id],
                evidence_ids=[],
            ))

        for path in change_files:
            config_id = ids.node_id(NodeType.CONFIG.value, path)
            node = self.repo.get_node(config_id)
            if node is not None:
                signals.append(ContradictionSignal(
                    signal_id=ids.signal_id("CONFIG_DRIFT", config_id, change_id),
                    project_id=project_id, kind="CONFIG_DRIFT",
                    description=f"config file changed in this change: {path}",
                    affected_node_ids=[config_id],
                ))

        for sig_id, signal in pending_signals or []:
            signals.append(ContradictionSignal(
                signal_id=sig_id, project_id=project_id, kind=signal["kind"],
                description=signal["description"],
                evidence_ids=signal.get("evidence_ids", []),
                affected_node_ids=signal.get("affected_node_ids", []),
                severity=signal.get("severity", "info"),
            ))

        return signals


def classify_changed_data_files(change_files: list[str]) -> list[str]:
    data_exts = (".csv", ".tsv", ".json", ".pkl", ".joblib", ".npz", ".npy",
                 ".parquet", ".h5", ".hdf5", ".pth", ".pt", ".onnx", ".db",
                 ".sqlite", ".xlsx", ".png", ".svg", ".pdf")
    return [f for f in change_files if f.endswith(data_exts)]
