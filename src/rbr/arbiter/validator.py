"""Deterministic arbiter: assembles the final Assessment from evidence.

Checks (spec section 10.1):
- every conclusion has >=1 evidence id and those ids exist (R1)
- provenance consistency (R4/R5), run-scoping (R3)
- support-span lexical overlap for agent citations
- no causal / no 'sufficient rerun' wording (R8/R9)
- agent outputs cannot introduce node/edge ids absent from the graph (R10)
- contradictions -> DISPUTED (R6); notebook state -> UNKNOWN (R11)
- final status comes from explicit rules, never an agent vote.
"""

from __future__ import annotations

import re

from ..config import Settings
from ..logging import get_logger
from ..schemas import (
    Assessment,
    AssessmentStatus,
    Conclusion,
    Coverage,
    GraphEdge,
    ProvenanceType,
    SupportSpan,
    UnknownState,
    ValidationAction,
    ids,
)
from ..store.repository import Repository
from .rules import (
    r1_has_evidence,
    r4_static_not_observed,
    r8_causal_blocked,
    r9_sufficient_blocked,
    resolve_skeptic,
)

log = get_logger(__name__)

_PUNCT = re.compile(r"[^\w\s]")
_SAFE_WORDING = {
    AssessmentStatus.AFFECTED: "Evidence-backed path exists; targeted validation is recommended.",
    AssessmentStatus.CONDITIONAL: "Evidence gap present; status conditional on resolving the gap.",
    AssessmentStatus.DISPUTED: "Contradictory evidence present; resolution required before reliance.",
    AssessmentStatus.UNKNOWN: "Evidence could not be established.",
}


def lexical_overlap(a: str, b: str, n: int = 2) -> float:
    """Jaccard overlap of character n-grams between two texts."""
    if not a or not b:
        return 0.0
    a = _PUNCT.sub("", a.lower())
    b = _PUNCT.sub("", b.lower())

    def ngrams(s: str) -> set[str]:
        return {s[i : i + n] for i in range(max(0, len(s) - n + 1))}

    ga = ngrams(a)
    gb = ngrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


class Arbiter:
    def __init__(self, repo: Repository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    def assemble(
        self,
        project_id: str,
        change_id: str,
        blast_radius,
        contradictions: list,
        agent_outputs: dict,
        claim_mappings: list,
        known_node_ids: set[str],
        known_edge_ids: set[str],
        boundary_unknown: list[str],
        gaps: list[str],
        coverage: Coverage | None,
        gating: list,
    ) -> Assessment:
        conclusions: list[Conclusion] = []
        unknowns: list[UnknownState] = []
        hypotheses: list[object] = []

        contradiction_node_ids = {
            nid for sig in contradictions for nid in sig.affected_node_ids
        }
        contradiction_targets: dict[str, bool] = {}
        for path in blast_radius.paths:
            contradiction_targets[path.target_id] = bool(
                set(path.node_ids) & contradiction_node_ids
            )

        known_evidence_ids = {ev.evidence_id for ev in self.repo.list_evidence(project_id)}
        known_ids = known_node_ids | known_evidence_ids

        def evidence_ok(evidence_ids: list[str]) -> bool:
            return all(e in known_ids for e in evidence_ids)

        # --- deterministic conclusions from blast-radius paths ---
        for path in blast_radius.paths:
            status = AssessmentStatus.AFFECTED
            if path.has_unknown_gap:
                status = AssessmentStatus.CONDITIONAL
            touched = set(path.node_ids) & contradiction_node_ids
            if touched:
                status = AssessmentStatus.DISPUTED
            rationale = (
                "Evidence-backed path: " + " -> ".join(path.node_ids)
                + f" (strongest provenance {path.strongest_provenance.value})"
            )
            if not r1_has_evidence(path.evidence_ids):
                continue  # R1
            if not evidence_ok(path.evidence_ids):
                log.warning("R10: path conclusion cites unknown evidence; dropped: %s",
                            path.path_id)
                continue
            conclusions.append(Conclusion(
                conclusion_id=_conc_id(path.target_id),
                subject_node_id=path.source_id,
                target_node_id=path.target_id,
                status=status,
                rationale=rationale,
                evidence_ids=path.evidence_ids,
                provenance_used=[p.value for p in path.provenance_types],
                unresolved_evidence_ids=[] if path.has_unknown_gap else [],
                validated=self._check_wording(rationale),
            ))

        # --- claim conclusions from scientific mappings (INFERRED, R5) ---
        for mapping in claim_mappings:
            if mapping.claim_id not in known_node_ids:
                continue
            if mapping.provenance_type != ProvenanceType.INFERRED:
                # never allow an agent to upgrade an inferred mapping
                continue
            if not evidence_ok(mapping.evidence_ids):
                log.warning("R10: claim mapping cites unknown evidence; dropped: %s",
                            mapping.claim_id)
                continue
            status = AssessmentStatus.CONDITIONAL
            if contradiction_targets.get(mapping.artifact_id):
                status = AssessmentStatus.DISPUTED
            rationale = mapping.rationale
            validated = self._check_wording(rationale)
            if validated and not self._support_spans_ok(rationale, mapping.support_spans):
                validated = False
            conclusions.append(Conclusion(
                conclusion_id=_conc_id(mapping.claim_id),
                subject_node_id=mapping.claim_id,
                target_node_id=mapping.artifact_id,
                status=status,
                rationale=rationale,
                evidence_ids=mapping.evidence_ids or [mapping.claim_id],
                provenance_used=[mapping.provenance_type.value],
                unresolved_evidence_ids=[],
                validated=validated,
            ))

        # --- skeptic resolution ---
        skeptic_out = agent_outputs.get("skeptic")
        skeptic_findings = skeptic_out.findings if skeptic_out is not None else []
        for finding in skeptic_findings:
            if finding.target_conclusion_id:
                for c in conclusions:
                    if c.conclusion_id == finding.target_conclusion_id:
                        c.status = resolve_skeptic(finding.classification, c.status)
            elif finding.classification == "CONTRADICTION":
                for c in conclusions:
                    c.status = resolve_skeptic(finding.classification, c.status)

        # --- unknowns (R2/R11: unknown is never unaffected) ---
        for nid in boundary_unknown:
            unknowns.append(UnknownState(
                node_id=nid,
                reason="only reachable through unknown/unevidenced edges; not treated as unaffected",
            ))

        # --- validation actions ---
        actions: list[ValidationAction] = []
        for c in conclusions:
            wording = _validation_wording(c)
            if self._check_wording(wording):
                actions.append(ValidationAction(
                    action_id=ids.action_id(),
                    target=c.target_node_id or c.subject_node_id,
                    rationale=c.rationale,
                    wording=wording,
                    unresolved_evidence_ids=c.unresolved_evidence_ids,
                ))

        # --- final status ---
        statuses = {c.status for c in conclusions}
        if AssessmentStatus.DISPUTED in statuses:
            final = AssessmentStatus.DISPUTED
        elif AssessmentStatus.AFFECTED in statuses:
            final = AssessmentStatus.AFFECTED
        elif AssessmentStatus.CONDITIONAL in statuses:
            final = AssessmentStatus.CONDITIONAL
        elif AssessmentStatus.UNKNOWN in statuses:
            final = AssessmentStatus.UNKNOWN
        elif conclusions:
            final = AssessmentStatus.NOT_EVIDENCED_AFFECTED
        elif boundary_unknown or gaps:
            final = AssessmentStatus.UNKNOWN
        else:
            final = AssessmentStatus.NOT_EVIDENCED_AFFECTED

        if coverage is None:
            final = AssessmentStatus.UNKNOWN

        return Assessment(
            assessment_id=ids.assessment_id(),
            project_id=project_id,
            change_id=change_id,
            status=final,
            conclusions=conclusions,
            unknowns=unknowns,
            contradictions=list(contradictions),
            hypotheses=hypotheses,
            validation_actions=actions,
            coverage=coverage,
            gating=list(gating),
            agent_calls=list(agent_outputs.keys()),
        )

    def _check_wording(self, text: str) -> bool:
        if r8_causal_blocked(text) or r9_sufficient_blocked(text):
            log.warning("blocked wording in arbiter output: %s", text[:120])
            return False
        return True

    def _support_spans_ok(self, statement: str, spans: list[SupportSpan]) -> bool:
        if not spans:
            return True
        for span in spans:
            if lexical_overlap(statement, span.text) < self.settings.support_span_min_overlap:
                return False
        return True


def _conc_id(target_id: str) -> str:
    return f"conc:{target_id.split(':')[-1][:16]}"


def _validation_wording(c: Conclusion) -> str:
    target = c.target_node_id or c.subject_node_id
    if c.status == AssessmentStatus.AFFECTED:
        return f"Re-run the producing step for {target} and verify the output hash."
    if c.status == AssessmentStatus.CONDITIONAL:
        return f"Resolve the evidence gap for {target} before relying on this path."
    if c.status == AssessmentStatus.DISPUTED:
        return f"Resolve the contradictory evidence involving {target} before reliance."
    return f"Establish evidence for {target}."


def validate_edge_provenance(edge: GraphEdge) -> bool:
    """R3/R4: provenance consistency of a graph edge."""
    return not (edge.provenance_type == ProvenanceType.OBSERVED and not edge.run_id)


def r4_static_not_observed_call(provenance: ProvenanceType) -> bool:
    return r4_static_not_observed(provenance, ProvenanceType.OBSERVED)
