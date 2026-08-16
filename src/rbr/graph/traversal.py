"""Blast-radius traversal (deterministic, spec section 14).

Propagates "affectedness" forward from the changed file nodes:
- incoming edges (consumer -> dependency): the consumer is affected.
- outgoing production edges (WRITES/GENERATES/PRODUCES/DERIVED_FROM/EXECUTED_AS):
  the produced artifact is affected, then its consumers via incoming edges.
- UNKNOWN-provenance edges and UNKNOWN_STATE nodes are never crossed as facts.
  A node reached ONLY via unknown edges is a boundary unknown (rule R2: unknown
  is never treated as unaffected). A node also reached via a factual path is
  affected, with the unknown gap recorded on its path.
"""

from __future__ import annotations

import uuid
from collections import deque

from ..logging import get_logger
from ..schemas import (
    PROVENANCE_STRENGTH,
    TRAVERSAL_RELATIONS,
    BlastPath,
    BlastRadius,
    GraphEdge,
    NodeType,
    ProvenanceType,
    ids,
)
from ..store.repository import Repository
from .builder import PRODUCTION_RELATIONS, EvidenceGraph

log = get_logger(__name__)

_NON_FACTUAL = {ProvenanceType.UNKNOWN, ProvenanceType.INFERRED}


class BlastRadiusTraversal:
    def __init__(self, graph: EvidenceGraph) -> None:
        self.graph = graph

    def compute(self, change_id: str, seed_node_ids: list[str],
                project_id: str) -> BlastRadius:
        result = BlastRadius(change_id=change_id, project_id=project_id,
                             traversal_relations=list(TRAVERSAL_RELATIONS))

        factually: set[str] = set()
        via_unknown: set[str] = set()
        parent: dict[str, tuple[str, str, list[str]]] = {}

        queue: deque[tuple[str, bool]] = deque()
        for seed in seed_node_ids:
            if self.graph.has_node(seed):
                factually.add(seed)
                queue.append((seed, False))

        while queue:
            node_id, unknown_mode = queue.popleft()
            edges = self._next_edges(node_id)
            for edge in edges:
                next_id = self._next_node(edge, node_id)
                if next_id is None:
                    continue
                non_factual = edge.provenance_type in _NON_FACTUAL or not edge.evidence_ids
                target = self.graph.node(next_id)
                is_unknown_state = target is not None and target.node_type == NodeType.UNKNOWN_STATE

                if unknown_mode or non_factual or is_unknown_state:
                    if next_id not in factually:
                        via_unknown.add(next_id)
                    continue

                if next_id in factually:
                    continue
                factually.add(next_id)
                parent[next_id] = (edge.source_id if edge.target_id == next_id else edge.target_id,
                                   edge.edge_id, edge.evidence_ids)
                queue.append((next_id, False))

        affected = sorted(factually - {s for s in seed_node_ids if s in factually})
        affected_full = sorted(factually)
        boundary = sorted(via_unknown - factually)

        result.affected_node_ids = affected_full
        result.downstream_node_ids = affected
        result.boundary_unknown_node_ids = boundary
        self._build_paths(result, list(seed_node_ids), parent)
        _ = affected
        return result

    def _next_edges(self, node_id: str) -> list[GraphEdge]:
        edges: list[GraphEdge] = []
        for edge in self.graph.incoming.get(node_id, []):
            if edge.relation in TRAVERSAL_RELATIONS:
                edges.append(edge)
        for edge in self.graph.outgoing.get(node_id, []):
            if edge.relation in PRODUCTION_RELATIONS:
                edges.append(edge)
        return edges

    def _next_node(self, edge: GraphEdge, current: str) -> str | None:
        if edge.target_id == current and edge.relation in TRAVERSAL_RELATIONS:
            return edge.source_id
        if edge.source_id == current and edge.relation in PRODUCTION_RELATIONS:
            return edge.target_id
        return None

    def _build_paths(self, result: BlastRadius, seeds: list[str], parent: dict) -> None:
        seed_set = set(seeds)
        for node_id in result.affected_node_ids:
            if node_id in seed_set:
                continue
            chain_ids: list[str] = []
            edge_ids: list[str] = []
            prov: list[ProvenanceType] = []
            evidence: list[str] = []
            current = node_id
            guard = 0
            while current not in seed_set and current in parent and guard < 1000:
                from_id, edge_id, ev_ids = parent[current]
                edge = next((e for e in self.graph.edges if e.edge_id == edge_id), None)
                if edge is None:
                    break
                chain_ids.append(current)
                edge_ids.append(edge_id)
                prov.append(edge.provenance_type)
                evidence.extend(ev_ids)
                current = from_id
                guard += 1
            if current not in seed_set:
                continue
            chain_ids.append(current)
            chain_ids.reverse()
            edge_ids.reverse()
            prov.reverse()
            strongest = max(prov, key=lambda p: PROVENANCE_STRENGTH[p]) if prov else ProvenanceType.UNKNOWN
            has_unknown = ProvenanceType.UNKNOWN in prov
            result.paths.append(BlastPath(
                path_id=f"path:{uuid.uuid4().hex[:10]}",
                source_id=current,
                target_id=node_id,
                node_ids=chain_ids,
                edge_ids=edge_ids,
                provenance_types=prov,
                strongest_provenance=strongest,
                has_unknown_gap=has_unknown,
                evidence_ids=sorted(set(evidence)),
                gaps=["unknown provenance on path"] if has_unknown else [],
            ))


def seed_nodes_for_change(repo: Repository, project_id: str, change_files: list[str]) -> list[str]:
    """Map changed file paths to FILE/ARTIFACT node ids (deterministic)."""
    seeds: list[str] = []
    for path in change_files:
        node_id = ids.node_id(NodeType.FILE.value, path)
        if repo.get_node(node_id) is not None:
            seeds.append(node_id)
        else:
            art_id = ids.node_id(NodeType.ARTIFACT.value, path)
            if repo.get_node(art_id) is not None:
                seeds.append(art_id)
    return seeds
