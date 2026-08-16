"""Analysis orchestrator: gating, agent dispatch, arbiter assembly.

Deterministic core runs first (graph -> blast radius -> contradictions ->
claim candidates). Gating decides which agents run and with what budget.
Arbiter assembles the final auditable assessment. No step depends on a live
LLM: the provider may be a stub in no-LLM mode.
"""

from __future__ import annotations

from typing import Any

from ..agents import (
    AgentProvider,
    ImpactMapperAgent,
    ScientificAnalystAgent,
    SkepticAgent,
    build_provider,
)
from ..agents.base import AgentResult
from ..arbiter.validator import Arbiter
from ..claims import ClaimIndex
from ..config import Settings
from ..graph import (
    BlastRadiusTraversal,
    ContradictionScanner,
    GraphBuilder,
    classify_changed_data_files,
    seed_nodes_for_change,
)
from ..logging import get_logger
from ..schemas import (
    BlastRadius,
    Claim,
    Coverage,
    GatingDecision,
    ImpactMapperInput,
    NodeType,
    ScientificAnalystInput,
    SkepticInput,
    StageName,
    ids,
)
from ..store.repository import Repository

log = get_logger(__name__)


class AnalyzeError(RuntimeError):
    pass


class AnalyzeService:
    def __init__(self, repo: Repository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings
        self.provider: AgentProvider = build_provider(settings)

    def run(self, project_id: str, change_id: str,
            claims: list[Claim] | None = None) -> dict[str, Any]:
        change = self.repo.get_change(change_id)
        if change is None:
            raise AnalyzeError(f"change not found: {change_id}")

        if claims:
            ClaimIndex(self.repo, project_id).ingest_claims(claims)

        graph = GraphBuilder(self.repo).build(project_id)
        known_node_ids = set(graph.nodes.keys())
        known_edge_ids = {e.edge_id for e in graph.edges}

        changed_paths = [f.path for f in change.files]
        if not changed_paths and change.file_path:
            changed_paths = [change.file_path]

        seeds = seed_nodes_for_change(self.repo, project_id, changed_paths)
        blast = BlastRadiusTraversal(graph).compute(change_id, seeds, project_id)
        coverage = self.repo.get_coverage(project_id, change_id)

        changed_data = classify_changed_data_files(changed_paths)
        notebook_unknown = [
            nid for nid, node in graph.nodes.items()
            if node.node_type == NodeType.UNKNOWN_STATE
        ]
        signals = ContradictionScanner(self.repo, graph).scan(
            project_id, change_id, changed_paths, changed_data, notebook_unknown
        )

        gaps = self._collect_gaps(graph, coverage, notebook_unknown)

        claim_index = ClaimIndex(self.repo, project_id)
        candidate_ids = claim_index.deterministic_candidates(
            blast.affected_node_ids + blast.boundary_unknown_node_ids
        )
        candidate_claims = [c for c in claim_index.load_claims() if c.claim_id in candidate_ids]

        gating = self._gate(change_id, project_id, blast, candidate_ids, signals, gaps)

        agent_outputs: dict[str, Any] = {}
        agent_calls: list[str] = []

        impact_enabled = next((g for g in gating if g.stage == StageName.IMPACT), None)
        impact_hypotheses: list = []
        if impact_enabled and impact_enabled.enabled:
            impact_input = ImpactMapperInput(
                change_id=change_id, project_id=project_id,
                change_label=change.label, change_files=changed_paths,
                affected_node_ids=blast.affected_node_ids,
                paths=blast.paths, gaps=gaps,
                coverage_summary=self._coverage_summary(coverage),
            )
            impact_res = ImpactMapperAgent(self.provider, self.settings).run(project_id, impact_input)
            agent_outputs["impact_mapper"] = impact_res.output
            agent_calls.append(self._persist_call(impact_res))
            impact_hypotheses = list(impact_res.output.hypotheses)

        scientific_enabled = next((g for g in gating if g.stage == StageName.SCIENTIFIC), None)
        claim_mappings = []
        if scientific_enabled and scientific_enabled.enabled:
            sci_input = ScientificAnalystInput(
                change_id=change_id, project_id=project_id,
                affected_artifact_refs=[graph.nodes[n].ref for n in blast.affected_node_ids],
                claims=candidate_claims,
            )
            sci_res = ScientificAnalystAgent(self.provider, self.settings).run(project_id, sci_input)
            agent_outputs["scientific_analyst"] = sci_res.output
            agent_calls.append(self._persist_call(sci_res))
            claim_mappings = sci_res.output.mappings

        skeptic_enabled = next((g for g in gating if g.stage == StageName.SKEPTIC), None)
        if skeptic_enabled and skeptic_enabled.enabled:
            draft_conclusions = self._draft_conclusions(blast, claim_mappings)
            skeptic_input = SkepticInput(
                change_id=change_id, project_id=project_id,
                conclusions=draft_conclusions,
                affected_node_ids=blast.affected_node_ids,
                contradiction_signals=[s.description for s in signals],
                change_summary=change.label or " ".join(changed_paths),
                gaps=gaps,
            )
            skeptic_res = SkepticAgent(self.provider, self.settings).run(project_id, skeptic_input)
            agent_outputs["skeptic"] = skeptic_res.output
            agent_calls.append(self._persist_call(skeptic_res))

        arbiter = Arbiter(self.repo, self.settings)
        assessment = arbiter.assemble(
            project_id=project_id, change_id=change_id,
            blast_radius=blast, contradictions=signals,
            agent_outputs=agent_outputs, claim_mappings=claim_mappings,
            known_node_ids=known_node_ids, known_edge_ids=known_edge_ids,
            boundary_unknown=blast.boundary_unknown_node_ids + notebook_unknown,
            gaps=gaps, coverage=coverage, gating=gating,
        )
        assessment.agent_calls = agent_calls
        assessment.hypotheses = impact_hypotheses
        self.repo.save_assessment(assessment)
        for decision in gating:
            self.repo.add_gating(decision.model_dump(mode="json"))
        return {"assessment": assessment, "blast_radius": blast, "gaps": gaps,
                "signals": signals}

    # --- helpers ---

    def _gate(self, change_id: str, project_id: str, blast: BlastRadius,
              candidate_ids: list[str], signals: list, gaps: list[str]) -> list[GatingDecision]:
        decisions: list[GatingDecision] = []
        has_impact = bool(blast.downstream_node_ids)
        has_gaps = bool(blast.boundary_unknown_node_ids or gaps or signals)

        if not has_impact and not has_gaps:
            for stage in StageName:
                decisions.append(GatingDecision(
                    gating_id=ids.gating_id(), project_id=project_id, change_id=change_id,
                    stage=stage, enabled=False,
                    reason="no affected nodes and no evidence gaps; short-circuit",
                ))
            return decisions

        decisions.append(GatingDecision(
            gating_id=ids.gating_id(), project_id=project_id, change_id=change_id,
            stage=StageName.IMPACT, enabled=has_impact,
            reason="affected nodes present" if has_impact else "no affected nodes",
            budget_tokens=min(self.settings.max_agent_budget_tokens,
                              max(1, len(blast.paths)) * 64),
        ))
        decisions.append(GatingDecision(
            gating_id=ids.gating_id(), project_id=project_id, change_id=change_id,
            stage=StageName.SCIENTIFIC, enabled=bool(candidate_ids),
            reason=f"{len(candidate_ids)} candidate claims referenced by affected artifacts",
        ))
        decisions.append(GatingDecision(
            gating_id=ids.gating_id(), project_id=project_id, change_id=change_id,
            stage=StageName.SKEPTIC, enabled=has_gaps or bool(candidate_ids),
            reason="gaps/contradictions present or claim mappings to attack",
        ))
        return decisions

    def _collect_gaps(self, graph, coverage: Coverage | None,
                      notebook_unknown: list[str]) -> list[str]:
        gaps: list[str] = []
        for edge in graph.edges:
            if not edge.evidence_ids:
                gaps.append(f"edge {edge.edge_id} has no evidence ids")
        if coverage:
            for layer_cov in coverage.layers.values():
                if layer_cov.failed:
                    gaps.append(f"{layer_cov.layer.value}: {layer_cov.failed} parse failures")
                if layer_cov.unknown:
                    gaps.append(f"{layer_cov.layer.value}: {layer_cov.unknown} unknown/gap items")
        for nid in notebook_unknown:
            gaps.append(f"notebook state unknown: {nid}")
        return sorted(set(gaps))

    def _draft_conclusions(self, blast: BlastRadius, claim_mappings: list) -> list:
        from ..schemas import ConclusionDraft

        drafts: list[ConclusionDraft] = []
        for path in blast.paths:
            drafts.append(ConclusionDraft(
                conclusion_id=f"conc:{path.target_id.split(':')[-1][:16]}",
                subject_node_id=path.source_id, target_node_id=path.target_id,
                status="CONDITIONAL" if path.has_unknown_gap else "AFFECTED",
                rationale=" -> ".join(path.node_ids),
                evidence_ids=path.evidence_ids,
            ))
        for mapping in claim_mappings:
            drafts.append(ConclusionDraft(
                conclusion_id=f"conc:{mapping.claim_id.split(':')[-1][:16]}",
                subject_node_id=mapping.claim_id, target_node_id=mapping.artifact_id,
                status="CONDITIONAL", rationale=mapping.rationale,
                evidence_ids=mapping.evidence_ids,
            ))
        return drafts

    def _coverage_summary(self, coverage: Coverage | None) -> str:
        if coverage is None:
            return "no coverage recorded"
        parts = []
        for layer_cov in coverage.layers.values():
            parts.append(f"{layer_cov.layer.value}: {layer_cov.parsed}/{layer_cov.scanned}"
                         f" (failed={layer_cov.failed}, unknown={layer_cov.unknown})")
        return "; ".join(parts)

    def _persist_call(self, result: AgentResult) -> str:
        self.repo.add_agent_call(result.record.model_dump(mode="json"))
        return result.record.call_id
