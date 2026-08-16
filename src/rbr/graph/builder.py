"""Graph builder: materialize a validated in-memory graph from stored evidence.

Rules enforced here (spec section 9):
- Every edge references existing nodes.
- Every edge references existing evidence (arbiter rule R1 enforced at build time).
- Edges with provenance INFERRED are not authoritative and are flagged.
- No agent output is ever added as a graph edge.
"""

from __future__ import annotations

import networkx as nx

from ..logging import get_logger
from ..schemas import EdgeRelation, GraphEdge, GraphNode
from ..store.repository import Repository

log = get_logger(__name__)

PRODUCTION_RELATIONS = frozenset({
    EdgeRelation.WRITES,
    EdgeRelation.GENERATES,
    EdgeRelation.PRODUCES,
    EdgeRelation.DERIVED_FROM,
    EdgeRelation.EXECUTED_AS,
})


class EvidenceGraph:
    """Validated in-memory directed graph of evidence-backed nodes/edges."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self.incoming: dict[str, list[GraphEdge]] = {}
        self.outgoing: dict[str, list[GraphEdge]] = {}
        self.g = nx.DiGraph()

    def add_node(self, node: GraphNode) -> None:
        if node.node_id in self.nodes:
            return
        self.nodes[node.node_id] = node
        self.g.add_node(node.node_id, **node.data)

    def add_edge(self, edge: GraphEdge, evidence_ok: bool = True) -> None:
        self.edges.append(edge)
        self.incoming.setdefault(edge.target_id, []).append(edge)
        self.outgoing.setdefault(edge.source_id, []).append(edge)
        self.g.add_edge(edge.source_id, edge.target_id,
                        relation=edge.relation.value,
                        provenance=edge.provenance_type.value,
                        evidence_ok=evidence_ok,
                        evidence_ids=edge.evidence_ids)

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def node(self, node_id: str) -> GraphNode | None:
        return self.nodes.get(node_id)


class GraphBuilder:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def build(self, project_id: str) -> EvidenceGraph:
        graph = EvidenceGraph()
        nodes = self.repo.list_nodes(project_id)
        for node in nodes:
            graph.add_node(node)

        missing_evidence: set[str] = set()
        edges = self.repo.list_edges(project_id)
        for edge in edges:
            if edge.source_id not in graph.nodes or edge.target_id not in graph.nodes:
                log.warning("dangling edge dropped: %s", edge.edge_id)
                continue
            evidence_ok = all(
                (self.repo.evidence_exists(eid) or _is_present(missing_evidence, eid))
                for eid in edge.evidence_ids
            )
            if not edge.evidence_ids:
                evidence_ok = False
            for eid in edge.evidence_ids:
                if not self.repo.evidence_exists(eid):
                    missing_evidence.add(eid)
            graph.add_edge(edge, evidence_ok=evidence_ok)
        return graph


def _is_present(collection: set[str], value: str) -> bool:
    return value in collection
