"""Deterministic rule tests (R1-R12)."""

from rbr.arbiter.rules import (
    r1_has_evidence,
    r2_unknown_not_unaffected,
    r3_run_scoped,
    r4_static_not_observed,
    r6_contradiction_disputed,
    r8_causal_blocked,
    r9_sufficient_blocked,
    r10_agent_ids_exist,
    resolve_skeptic,
)
from rbr.arbiter.validator import lexical_overlap
from rbr.schemas import AssessmentStatus, ProvenanceType, SkepticClassification


def test_r1_evidence_required():
    assert not r1_has_evidence([])
    assert r1_has_evidence(["ev:abc"])


def test_r2_unknown_not_unaffected():
    assert r2_unknown_not_unaffected(True, False)
    assert r2_unknown_not_unaffected(False, True)
    assert not r2_unknown_not_unaffected(False, False)


def test_r3_observed_must_be_run_scoped():
    assert not r3_run_scoped(None)
    assert r3_run_scoped("run:abc")


def test_r4_static_not_presented_as_observed():
    assert r4_static_not_observed(ProvenanceType.STATIC, ProvenanceType.STATIC)
    assert r4_static_not_observed(ProvenanceType.OBSERVED, ProvenanceType.OBSERVED)
    assert not r4_static_not_observed(ProvenanceType.STATIC, ProvenanceType.OBSERVED)


def test_r6_contradiction_disputed():
    assert r6_contradiction_disputed(True, AssessmentStatus.AFFECTED) == AssessmentStatus.DISPUTED
    assert r6_contradiction_disputed(False, AssessmentStatus.AFFECTED) == AssessmentStatus.AFFECTED


def test_r8_causal_wording_blocked():
    assert r8_causal_blocked("This proves the model is better")
    assert r8_causal_blocked("definitively affected")
    assert not r8_causal_blocked("Evidence-backed path exists; targeted validation recommended")


def test_r9_sufficient_rerun_blocked():
    assert r9_sufficient_blocked("sufficient to rerun all affected results")
    assert r9_sufficient_blocked("completely covers the blast radius")
    assert not r9_sufficient_blocked("targeted validation is recommended")


def test_r10_agent_ids_must_exist():
    known = {"ev:a", "node:FILE:x"}
    assert r10_agent_ids_exist(["ev:a"], known)
    assert not r10_agent_ids_exist(["ev:a", "ev:invented"], known)


def test_resolve_skeptic_table():
    assert resolve_skeptic(SkepticClassification.CONTRADICTION,
                           AssessmentStatus.AFFECTED) == AssessmentStatus.DISPUTED
    assert resolve_skeptic(SkepticClassification.MISSING_EVIDENCE,
                           AssessmentStatus.AFFECTED) == AssessmentStatus.CONDITIONAL
    assert resolve_skeptic(SkepticClassification.SCOPE_LIMITATION,
                           AssessmentStatus.AFFECTED) == AssessmentStatus.AFFECTED
    assert resolve_skeptic(SkepticClassification.NO_COUNTER_EVIDENCE_FOUND,
                           AssessmentStatus.AFFECTED) == AssessmentStatus.AFFECTED


def test_lexical_overlap():
    assert lexical_overlap("the quick brown fox", "the quick brown fox") == 1.0
    assert lexical_overlap("zzzz qqqq", "mmmm nnnn") == 0.0
    assert lexical_overlap("accuracy improves on validation set",
                           "accuracy improves on validation set") == 1.0
