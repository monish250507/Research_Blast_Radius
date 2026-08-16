"""Golden benchmark: synthetic_pipeline must meet recall/precision targets."""

import pytest

from harness import run_golden


@pytest.fixture(scope="module")
def golden(tmp_path_factory):
    return run_golden("synthetic_pipeline", str(tmp_path_factory.mktemp("golden") / "golden.db"))


def test_status_matches(golden):
    assert golden.metrics["status_match"], golden.details


def test_edge_recall_perfect(golden):
    assert golden.metrics["edge_recall"] == 1.0, golden.details["actual_edges"]


def test_artifact_recall_perfect(golden):
    assert golden.metrics["artifact_recall"] == 1.0, golden.details["affected_refs"]


def test_claim_recall_perfect(golden):
    assert golden.metrics["claim_recall"] == 1.0


def test_unknown_surfaced(golden):
    assert golden.metrics["unknown_recall"] == 1.0, golden.details["unknowns"]


def test_contradiction_detected(golden):
    assert golden.metrics["contradiction_recall"] == 1.0, golden.details["contradictions"]


def test_no_false_edges(golden):
    assert golden.metrics["no_false_edges"], golden.details["actual_edges"]
