"""Skeptic agent.

Contract (spec section 11.3): tries to falsify the proposed assessment; searches
supplied evidence for counter-evidence, unaffected paths, hidden dependencies,
coverage gaps; never invents facts; classifies objections. In no-LLM mode the
skeptic surfaces deterministic contradiction signals and scope limitations.
"""

from __future__ import annotations

from ..schemas import (
    SkepticClassification,
    SkepticFinding,
    SkepticInput,
    SkepticOutput,
)
from .base import AgentResult, BaseAgent

SYSTEM_PROMPT = """You are the Skeptic for Research Blast Radius.

RULES
- Try to falsify the proposed impact assessment.
- Find the strongest reason it could be wrong.
- Classify every issue as CONTRADICTION, MISSING_EVIDENCE, SCOPE_LIMITATION,
  or NO_COUNTER_EVIDENCE_FOUND.
- Never invent missing facts. Every objection cites evidence_ids from the input
  or is explicitly marked UNKNOWN.
- You cannot rewrite evidence or conclusions; you only report findings.
- Return structured JSON matching the provided schema only."""


class SkepticAgent(BaseAgent[SkepticInput, SkepticOutput]):
    name = "skeptic"
    system_prompt = SYSTEM_PROMPT
    output_model = SkepticOutput

    def fallback(self) -> SkepticOutput:
        inp: SkepticInput = self._last_input
        findings: list[SkepticFinding] = []

        if inp.contradiction_signals:
            for sig in inp.contradiction_signals:
                findings.append(SkepticFinding(
                    classification=SkepticClassification.SCOPE_LIMITATION,
                    description=(
                        f"deterministic contradiction signal present: {sig}. "
                        "Conclusion status is resolved deterministically by the arbiter "
                        "for the affected nodes; this objection is untargeted."
                    ),
                ))
        if inp.gaps:
            findings.append(SkepticFinding(
                classification=SkepticClassification.MISSING_EVIDENCE,
                description=(
                    "coverage gaps present in the evidence subgraph; conclusions "
                    "over these regions are CONDITIONAL at best (no-LLM mode)."
                ),
            ))
            for gap in inp.gaps[:8]:
                findings.append(SkepticFinding(
                    classification=SkepticClassification.SCOPE_LIMITATION,
                    description=f"evidence gap: {gap}",
                ))
        if not findings:
            findings.append(SkepticFinding(
                classification=SkepticClassification.NO_COUNTER_EVIDENCE_FOUND,
                description=(
                    "no deterministic counter-evidence in the supplied evidence; "
                    "semantic falsification unavailable in no-LLM mode."
                ),
            ))
        return SkepticOutput(findings=findings)

    def run(self, project_id: str, user_input: SkepticInput) -> AgentResult[SkepticOutput]:
        self._last_input = user_input
        return super().run(project_id, user_input)
