"""Scientific Evidence Analyst agent.

Contract (spec section 11.2): does not decide whether a claim is true; preserves
qualifiers/conditions/comparator/metric; maps artifacts to claims only when
supplied paper evidence supports the mapping; labels semantic mappings INFERRED;
ambiguous evidence returns UNKNOWN.
"""

from __future__ import annotations

from ..schemas import (
    Ambiguity,
    ClaimMapping,
    ProvenanceType,
    ScientificAnalystInput,
    ScientificAnalystOutput,
)
from .base import AgentResult, BaseAgent

SYSTEM_PROMPT = """You are the Scientific Evidence Analyst for Research Blast Radius.

RULES
- Do not decide whether any scientific claim is true or false.
- Preserve claim qualifiers, conditions, population, comparator and metric.
- Map affected artifacts to claims ONLY when the supplied claim evidence locations
  and the affected artifacts support the mapping.
- Label every semantic mapping INFERRED. Never upgrade INFERRED to OBSERVED/STATIC.
- If evidence is ambiguous, return the claim in ambiguities with status UNKNOWN
  instead of choosing a likely mapping.
- Every mapping must cite evidence_ids present in the input.
- Return structured JSON matching the provided schema only."""


class ScientificAnalystAgent(BaseAgent[ScientificAnalystInput, ScientificAnalystOutput]):
    name = "scientific_analyst"
    system_prompt = SYSTEM_PROMPT
    output_model = ScientificAnalystOutput

    def fallback(self) -> ScientificAnalystOutput:
        inp: ScientificAnalystInput = self._last_input
        mappings: list[ClaimMapping] = []
        ambiguities: list[Ambiguity] = []
        affected = set(inp.affected_artifact_refs)
        for claim in inp.claims:
            overlapping = [
                loc for loc in claim.evidence_locations
                if _loc_matches_affected(loc, affected)
            ]
            if not overlapping:
                continue
            mappings.append(ClaimMapping(
                claim_id=claim.claim_id,
                artifact_id=overlapping[0],
                provenance_type=ProvenanceType.INFERRED,
                rationale=(
                    "Deterministic candidate: the claim declares evidence location "
                    f"{overlapping[0]}, which is in the affected set. Semantic mapping "
                    "labelled INFERRED; no-LLM mode."
                ),
                uncertainty="semantic analysis unavailable (no-LLM mode)",
                qualifiers_preserved=True,
            ))
            # also flag claims with qualifiers as needing human confirmation
            if claim.qualifiers:
                for loc in overlapping[1:]:
                    mappings.append(ClaimMapping(
                        claim_id=claim.claim_id, artifact_id=loc,
                        provenance_type=ProvenanceType.INFERRED,
                        rationale="deterministic candidate via declared evidence location",
                        uncertainty="confirm qualifier preservation manually",
                        qualifiers_preserved=True,
                    ))
        return ScientificAnalystOutput(mappings=mappings, ambiguities=ambiguities)

    def run(self, project_id: str, user_input: ScientificAnalystInput) -> AgentResult[ScientificAnalystOutput]:
        self._last_input = user_input
        return super().run(project_id, user_input)


def _loc_matches_affected(loc: str, affected_refs: set[str]) -> bool:
    return loc in affected_refs
