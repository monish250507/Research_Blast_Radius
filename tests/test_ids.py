"""Deterministic, content-addressed identifier tests."""

from rbr.schemas import ids


def test_node_id_deterministic():
    a = ids.node_id("FILE", "src/main.py")
    b = ids.node_id("FILE", "src/main.py")
    assert a == b
    assert a.startswith("node:FILE:")


def test_node_id_distinct_refs():
    assert ids.node_id("FILE", "src/main.py") != ids.node_id("FILE", "src/util.py")
    assert ids.node_id("FILE", "src/main.py") != ids.node_id("ARTIFACT", "src/main.py")


def test_evidence_id_content_addressed():
    loc = "src/main.py:12"
    h1 = ids.content_hash(b"x")
    h2 = ids.content_hash(b"y")
    e1 = ids.evidence_id("PY_AST", loc, h1, "py")
    e2 = ids.evidence_id("PY_AST", loc, h2, "py")
    e3 = ids.evidence_id("PY_AST", loc, h1, "py")
    assert e1 == e3
    assert e1 != e2
    assert e1.startswith("ev:")


def test_claim_and_edge_ids_deterministic():
    n1 = ids.node_id("ARTIFACT", "out.csv")
    n2 = ids.node_id("FILE", "src/a.py")
    e1 = ids.edge_id(n1, n2, "WRITES")
    e2 = ids.edge_id(n1, n2, "WRITES")
    assert e1 == e2
    assert e1.startswith("edge:")
    assert ids.claim_id("C1") == ids.claim_id("C1")
    assert ids.claim_id("C1") != ids.claim_id("C2")
