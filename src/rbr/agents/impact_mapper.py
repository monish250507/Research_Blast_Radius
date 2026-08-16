"""Impact Mapper agent.

Contract (spec section 11.1): reasons only over supplied evidence; selects paths
already present in the precomputed blast radius; never invents edges or claims
scientific truth; every statement cites evidence_ids; distinguishes provenance.
"""

from __future__ import annotations

from ..schemas import ImpactFinding, ImpactMapperInput, ImpactMapperOutput, RiskLabel
from .base import AgentResult, BaseAgent

SYSTEM_PROMPT = """You are the Impact Mapper for Research Blast Radius.

RULES
- The blast radius (affected paths) was computed deterministically. You do NOT find paths.
- Reason only over the supplied evidence objects and paths.
- You may label/prioritize the supplied paths and propose hypotheses.
- Every statement must cite evidence_ids from the input.
- Distinguish OBSERVED, STATIC, DECLARED, INFERRED and UNKNOWN provenance.
- Do not use causal language. Do not claim completeness or sufficiency.
- Hypotheses are proposals that need confirmation; mark them INFERRED.
- Return structured JSON matching the provided schema only."""


class ImpactMapperAgent(BaseAgent[ImpactMapperInput, ImpactMapperOutput]):
    name = "impact_mapper"
    system_prompt = SYSTEM_PROMPT
    output_model = ImpactMapperOutput

    def fallback(self) -> ImpactMapperOutput:
        inp: ImpactMapperInput = self._last_input
        findings: list[ImpactFinding] = []
        for path in inp.paths:
            findings.append(_finding_for_path(path))
        return ImpactMapperOutput(findings=findings, hypotheses=[])

    def run(self, project_id: str, user_input: ImpactMapperInput) -> AgentResult[ImpactMapperOutput]:
        self._last_input = user_input
        return super().run(project_id, user_input)


def _finding_for_path(path) -> ImpactFinding:
    rationale = (
        "Evidence-backed path from the change to this node; semantic risk "
        "assessment unavailable in no-LLM mode, labelled UNKNOWN."
    )
    hint = "Validate by re-running the producing step and checking the affected artifact hash."
    return ImpactFinding(
        target_node_id=path.target_id,
        path_id=path.path_id,
        risk=RiskLabel.UNKNOWN,
        rationale=rationale,
        evidence_ids=path.evidence_ids,
        validation_hint=hint,
    )
