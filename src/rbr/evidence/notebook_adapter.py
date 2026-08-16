"""Notebook adapter: nbformat parsing, cell imports/outputs, state anomalies.

Execution-order anomalies (missing/repeated/out-of-order counts) are treated as
UNKNOWN state per rule R11, never silently repaired.
"""

from __future__ import annotations

import hashlib

import nbformat

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
from .python_adapter import ModuleResolver, PythonAdapter

log = get_logger(__name__)

NB_MAX_BYTES = 2_000_000


class NotebookAdapter:
    def __init__(self, resolver: ModuleResolver) -> None:
        self.python = PythonAdapter()
        self.resolver = resolver

    def parse_notebook(self, relpath: str, raw: bytes, ctx: AdapterContext) -> AdapterOutput:
        out = AdapterOutput()
        cov = out.layer(CoverageLayer.STATIC)
        cov.scanned += 1
        try:
            nb = nbformat.reads(raw.decode("utf-8", errors="replace"), as_version=4)
        except Exception as exc:  # malformed notebook
            cov.failed += 1
            out.gaps.append(f"{relpath}: malformed notebook: {exc}")
            return out
        cov.parsed += 1

        nb_node = GraphNode(node_id=ids.node_id(NodeType.FILE.value, relpath),
                            project_id=ctx.project_id, node_type=NodeType.FILE,
                            label=relpath, ref=relpath)
        out.nodes.append(nb_node)

        nb_ev = self._notebook_evidence(ctx, relpath, nb)
        out.evidence.append(nb_ev)

        counts: list[tuple[int, int | None]] = []
        for idx, cell in enumerate(nb.cells):
            cell_id = str(cell.get("id", f"cell_{idx}"))
            count = cell.get("execution_count")
            counts.append((idx, count))
            cell_node = GraphNode(
                node_id=ids.node_id(NodeType.NOTEBOOK_CELL.value, f"{relpath}:{cell_id}"),
                project_id=ctx.project_id, node_type=NodeType.NOTEBOOK_CELL,
                label=f"{relpath}:cell:{idx}", ref=f"{relpath}:{cell_id}",
                data={"cell_type": cell.cell_type, "index": idx},
            )
            out.nodes.append(cell_node)
            out.edges.append(self._edge(ctx, nb_node, cell_node, EdgeRelation.EXECUTED_AS,
                                        ProvenanceType.STATIC, [nb_ev.evidence_id],
                                        locator=f"nb:{relpath}:{idx}"))

            if cell.cell_type != "code":
                continue

            cell_ev = self._cell_evidence(ctx, relpath, cell_id, idx, cell.source, cell)
            out.evidence.append(cell_ev)
            result = self.python.parse(cell.source)
            if result.error:
                cov.failed += 1
                continue

            for gap in result.dynamic_gaps:
                out.gaps.append(f"{relpath}:cell:{idx}: dynamic/{gap.kind}: {gap.detail}")
                cov.unknown += 1

            for imp in result.imports:
                target_path = self.resolver.resolve(imp.module)
                if target_path is None:
                    continue
                target_id = ids.node_id(NodeType.FILE.value, target_path)
                target_node = GraphNode(node_id=target_id, project_id=ctx.project_id,
                                        node_type=NodeType.FILE, label=target_path,
                                        ref=target_path)
                out.nodes.append(target_node)
                out.edges.append(self._edge(ctx, cell_node, target_node,
                                            EdgeRelation.IMPORTS, ProvenanceType.STATIC,
                                            [cell_ev.evidence_id], locator=f"nb:{relpath}:{idx}"))

            for ref in result.file_refs:
                resolved = self._resolve_ref(relpath, ref.path)
                if resolved is None:
                    out.gaps.append(
                        f"{relpath}:cell:{idx}: unresolved file ref {ref.path!r}"
                    )
                    cov.unknown += 1
                    continue
                rel = EdgeRelation.READS if ref.mode != "WRITE" else EdgeRelation.WRITES
                target_id = ids.node_id(NodeType.ARTIFACT.value, resolved)
                target_node = GraphNode(node_id=target_id,
                                        project_id=ctx.project_id,
                                        node_type=NodeType.ARTIFACT,
                                        label=resolved, ref=resolved)
                out.nodes.append(target_node)
                out.edges.append(self._edge(ctx, cell_node, target_node,
                                            rel, ProvenanceType.STATIC,
                                            [cell_ev.evidence_id], locator=f"nb:{relpath}:{idx}"))

            # output images -> figure artifact refs (best effort, STATIC)
            for output in cell.get("outputs", []):
                self._link_output_figure(ctx, out, cell_node, output, relpath, idx, cell_ev)

        anomalies = _detect_anomalies(counts)
        if anomalies:
            signal_id = ids.signal_id("NOTEBOOK_STATE", relpath)
            unknown_node = GraphNode(
                node_id=ids.node_id(NodeType.UNKNOWN_STATE.value, f"{relpath}:state"),
                project_id=ctx.project_id, node_type=NodeType.UNKNOWN_STATE,
                label=f"{relpath}:execution-state", ref=f"{relpath}:state",
                data={"anomalies": anomalies},
            )
            out.nodes.append(unknown_node)
            out.edges.append(self._edge(ctx, nb_node, unknown_node, EdgeRelation.UNKNOWN_RELATION,
                                        ProvenanceType.UNKNOWN, [nb_ev.evidence_id],
                                        locator=f"nb:{relpath}:state"))
            out.gaps.append(f"{relpath}: notebook execution state UNKNOWN: {'; '.join(anomalies)}")
            self._note_signal(out, signal_id, relpath, anomalies, [nb_ev.evidence_id],
                              [unknown_node.node_id])
        return out

    def _link_output_figure(self, ctx: AdapterContext, out: AdapterOutput, cell_node: GraphNode,
                            output: dict, relpath: str, idx: int, cell_ev: Evidence) -> None:
        if output.get("output_type") not in ("display_data", "execute_result"):
            return
        data = output.get("data", {}) or {}
        if "image/png" in data or "image/svg+xml" in data:
            ref = f"{relpath}:cell:{idx}:figure"
            fig_node = GraphNode(node_id=ids.node_id(NodeType.FIGURE.value, ref),
                                 project_id=ctx.project_id, node_type=NodeType.FIGURE,
                                 label=ref, ref=ref)
            out.nodes.append(fig_node)
            out.edges.append(self._edge(ctx, cell_node, fig_node, EdgeRelation.GENERATES,
                                        ProvenanceType.STATIC, [cell_ev.evidence_id],
                                        locator=f"nb:{relpath}:{idx}"))

    def _notebook_evidence(self, ctx: AdapterContext, relpath: str, nb) -> Evidence:
        raw = nbformat.writes(nb).encode("utf-8")
        h = hashlib.sha256(raw).hexdigest()
        locator = f"nb:file:{relpath}"
        return Evidence(evidence_id=ids.evidence_id(EvidenceSourceType.NOTEBOOK.value,
                                                    locator, h, ctx.extractor),
                        project_id=ctx.project_id, source_type=EvidenceSourceType.NOTEBOOK,
                        locator=locator, content_hash=h, extractor=ctx.extractor,
                        payload={"cells": len(nb.cells), "language": nb.metadata.get(
                            "kernelspec", {}).get("language", "python")},
                        snapshot_id=ctx.snapshot_id)

    def _cell_evidence(self, ctx: AdapterContext, relpath: str, cell_id: str, idx: int,
                       source: str, cell) -> Evidence:
        h = hashlib.sha256(source.encode("utf-8")).hexdigest()
        locator = f"nb:cell:{relpath}:{idx}"
        return Evidence(evidence_id=ids.evidence_id(EvidenceSourceType.NOTEBOOK.value,
                                                    locator, h, ctx.extractor),
                        project_id=ctx.project_id, source_type=EvidenceSourceType.NOTEBOOK,
                        locator=locator, content_hash=h, extractor=ctx.extractor,
                        payload={"cell_id": cell_id, "index": idx,
                                 "execution_count": cell.get("execution_count"),
                                 "output_types": [o.get("output_type")
                                                  for o in cell.get("outputs", [])]},
                        snapshot_id=ctx.snapshot_id)

    def _resolve_ref(self, relpath: str, ref: str) -> str | None:
        import posixpath

        ref = ref.replace("\\", "/").lstrip("/")
        base = posixpath.dirname(relpath)
        return posixpath.normpath(posixpath.join(base, ref)) if ref else None

    def _edge(self, ctx: AdapterContext, src: GraphNode, tgt: GraphNode,
              relation: EdgeRelation, provenance: ProvenanceType, evidence_ids: list[str],
              locator: str = "") -> GraphEdge:
        return GraphEdge(edge_id=ids.edge_id(src.node_id, tgt.node_id, f"{relation.value}|{locator}"),
                         project_id=ctx.project_id, source_id=src.node_id,
                         target_id=tgt.node_id, relation=relation, provenance_type=provenance,
                         evidence_ids=evidence_ids, locator=locator,
                         snapshot_id=ctx.snapshot_id, extractor_version=ctx.extractor)

    def _note_signal(self, out: AdapterOutput, signal_id: str, relpath: str,
                     anomalies: list[str], evidence_ids: list[str], nodes: list[str]) -> None:
        out.gaps.append(f"signal:{signal_id}")


def _detect_anomalies(counts: list[tuple[int, int | None]]) -> list[str]:
    anomalies: list[str] = []
    seen: set[int] = set()
    prev: int | None = None
    has_any = any(c is not None for _, c in counts)
    for idx, count in counts:
        if count is None:
            if has_any:
                anomalies.append(f"cell {idx}: missing execution count")
            continue
        if count in seen:
            anomalies.append(f"cell {idx}: repeated execution count {count}")
        seen.add(count)
        if prev is not None and count < prev:
            anomalies.append(f"cell {idx}: out-of-order execution ({prev} -> {count})")
        prev = count
    return anomalies
