"""Blast-radius traversal tests: forward propagation, boundaries, unknowns."""

from rbr.graph import BlastRadiusTraversal
from rbr.graph.builder import EvidenceGraph
from rbr.schemas import (
    EdgeRelation,
    GraphEdge,
    GraphNode,
    NodeType,
    ProvenanceType,
    ids,
)


def _node(nt: NodeType, ref: str, pid: str = "p") -> GraphNode:
    return GraphNode(node_id=ids.node_id(nt.value, ref), project_id=pid,
                     node_type=nt, label=ref, ref=ref)


def _edge(src: GraphNode, tgt: GraphNode, rel: EdgeRelation, pid: str = "p",
          prov: ProvenanceType = ProvenanceType.STATIC,
          ev: str | None = "ev:static") -> GraphEdge:
    return GraphEdge(edge_id=ids.edge_id(src.node_id, tgt.node_id, rel.value),
                     project_id=pid, source_id=src.node_id, target_id=tgt.node_id,
                     relation=rel, provenance_type=prov,
                     evidence_ids=[ev] if ev else [], locator=f"{src.ref}:{tgt.ref}",
                     run_id="run:r" if prov == ProvenanceType.OBSERVED else None,
                     snapshot_id="snap:a", scope="static", extractor_version="1.0")


def _graph(nodes, edges) -> EvidenceGraph:
    g = EvidenceGraph()
    for n in nodes:
        g.add_node(n)
    for e in edges:
        g.add_edge(e)
    return g


def _traverse(g, seeds):
    return BlastRadiusTraversal(g).compute("chg:x", seeds, "p")


def test_forward_propagation_via_production_and_imports():
    src = _node(NodeType.FILE, "src/produce.py")
    art = _node(NodeType.ARTIFACT, "outputs/out.csv")
    consumer = _node(NodeType.FILE, "src/consume.py")
    g = _graph([src, art, consumer], [
        _edge(src, art, EdgeRelation.WRITES),
        _edge(consumer, src, EdgeRelation.IMPORTS),
    ])
    r = _traverse(g, [src.node_id])
    assert art.node_id in r.affected_node_ids
    assert consumer.node_id in r.affected_node_ids
    assert consumer.node_id in r.downstream_node_ids
    assert {p.target_id for p in r.paths} == {art.node_id, consumer.node_id}
    for p in r.paths:
        assert not p.has_unknown_gap
        assert p.evidence_ids


def test_no_downstream_impact():
    src = _node(NodeType.FILE, "src/isolated.py")
    g = _graph([src], [])
    r = _traverse(g, [src.node_id])
    assert r.downstream_node_ids == []
    assert r.affected_node_ids == [src.node_id]
    assert r.paths == []
    assert r.boundary_unknown_node_ids == []


def test_unknown_provenance_edge_is_boundary_not_affected():
    src = _node(NodeType.FILE, "src/a.py")
    downstream = _node(NodeType.ARTIFACT, "out.csv")
    g = _graph([src, downstream], [
        _edge(src, downstream, EdgeRelation.WRITES, prov=ProvenanceType.UNKNOWN),
    ])
    r = _traverse(g, [src.node_id])
    assert downstream.node_id not in r.affected_node_ids
    assert downstream.node_id in r.boundary_unknown_node_ids


def test_unknown_state_node_is_boundary():
    src = _node(NodeType.FILE, "src/a.py")
    nbs = _node(NodeType.UNKNOWN_STATE, "notebooks/x.ipynb:state")
    g = _graph([src, nbs], [
        _edge(src, nbs, EdgeRelation.WRITES, prov=ProvenanceType.UNKNOWN),
    ])
    r = _traverse(g, [src.node_id])
    assert nbs.node_id not in r.affected_node_ids
    assert nbs.node_id in r.boundary_unknown_node_ids


def test_strong_and_unknown_paths_resolve_to_affected():
    src = _node(NodeType.FILE, "src/a.py")
    b = _node(NodeType.FILE, "src/b.py")
    art = _node(NodeType.ARTIFACT, "out.csv")
    g = _graph([src, b, art], [
        _edge(src, b, EdgeRelation.IMPORTS, prov=ProvenanceType.UNKNOWN),
        _edge(b, art, EdgeRelation.WRITES, prov=ProvenanceType.UNKNOWN),
        _edge(src, art, EdgeRelation.WRITES),  # strong path reaches the artifact too
    ])
    r = _traverse(g, [src.node_id])
    assert art.node_id in r.affected_node_ids
    assert art.node_id not in r.boundary_unknown_node_ids


def test_observed_provenance_path():
    src = _node(NodeType.FILE, "src/run.py")
    art = _node(NodeType.ARTIFACT, "out.csv")
    g = _graph([src, art], [
        _edge(src, art, EdgeRelation.WRITES, prov=ProvenanceType.OBSERVED, ev="ev:obs"),
    ])
    r = _traverse(g, [src.node_id])
    p = r.path_for(art.node_id)[0]
    assert p.strongest_provenance == ProvenanceType.OBSERVED
