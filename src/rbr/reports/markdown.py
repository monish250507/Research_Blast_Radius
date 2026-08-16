"""Markdown report generator with evidence drill-down.

Every material conclusion is rendered with its evidence_ids and the locators
those ids point to, so the reader can verify any claim (spec section 16/17).
"""

from __future__ import annotations

from ..logging import get_logger
from ..schemas import Assessment
from ..store.repository import Repository

log = get_logger(__name__)


def render_markdown(repo: Repository, assessment: Assessment) -> str:
    lines: list[str] = []
    lines.append("# Research Blast Radius — Impact Report")
    lines.append("")
    lines.append(f"- Assessment: `{assessment.assessment_id}`")
    lines.append(f"- Change: `{assessment.change_id}`")
    lines.append(f"- Status: **{assessment.status.value}**")
    lines.append(f"- Graph version: {assessment.graph_version}")
    lines.append("")

    lines.append("## Conclusions")
    lines.append("")
    if not assessment.conclusions:
        lines.append("No evidence-backed downstream impact was established for this change.")
        lines.append("")
    for c in assessment.conclusions:
        lines.append(f"### {c.conclusion_id} — {c.status.value}")
        lines.append("")
        lines.append(f"- Subject node: `{c.subject_node_id}`")
        if c.target_node_id:
            lines.append(f"- Target node: `{c.target_node_id}`")
        lines.append(f"- Rationale: {c.rationale}")
        lines.append(f"- Provenance used: {', '.join(c.provenance_used)}")
        lines.append(f"- Validated by arbiter: {c.validated}")
        lines.append("")
        _render_evidence(lines, repo, c.evidence_ids)
        if c.support_spans:
            lines.append("**Support spans:**")
            for span in c.support_spans:
                lines.append(f"  - `{span.evidence_id}`: {span.text[:200]}")
            lines.append("")

    lines.append("## Unknowns (never treated as unaffected)")
    lines.append("")
    if not assessment.unknowns:
        lines.append("None recorded.")
        lines.append("")
    for u in assessment.unknowns:
        lines.append(f"- `{u.node_id}` — {u.reason}")

    lines.append("")
    lines.append("## Contradictions")
    lines.append("")
    if not assessment.contradictions:
        lines.append("None detected deterministically.")
        lines.append("")
    for sig in assessment.contradictions:
        lines.append(f"- [{sig.kind}] {sig.description} (signal `{sig.signal_id}`)")

    lines.append("")
    lines.append("## Validation actions")
    lines.append("")
    if not assessment.validation_actions:
        lines.append("None required.")
        lines.append("")
    for action in assessment.validation_actions:
        lines.append(f"- {action.wording} (`{action.action_id}`)")

    lines.append("")
    lines.append("## Coverage by evidence layer")
    lines.append("")
    if assessment.coverage:
        for layer, cov in assessment.coverage.layers.items():
            lines.append(
                f"- **{layer.value}**: parsed {cov.parsed}/{cov.scanned}, "
                f"failed {cov.failed}, unknown {cov.unknown} (ratio {cov.ratio:.2f})"
            )
    else:
        lines.append("No coverage recorded.")
    lines.append("")

    lines.append("## Gating")
    lines.append("")
    for g in assessment.gating:
        lines.append(f"- {g.stage.value}: {'enabled' if g.enabled else 'disabled'} — {g.reason}")

    lines.append("")
    lines.append("## Agent calls")
    lines.append("")
    if not assessment.agent_calls:
        lines.append("None (short-circuit or no agent stage enabled).")
        lines.append("")
    else:
        for call_id in assessment.agent_calls:
            lines.append(f"- `{call_id}`")

    lines.append("")
    lines.append("---")
    lines.append(
        "*Research Blast Radius reports what the available evidence establishes. "
        "It does not claim completeness, causal sufficiency, or scientific truth.*"
    )
    return "\n".join(lines)


def _render_evidence(lines: list[str], repo: Repository, evidence_ids: list[str]) -> None:
    if not evidence_ids:
        lines.append("⚠ No evidence ids on this conclusion (arbiter would reject).")
        return
    lines.append("**Evidence:**")
    for eid in evidence_ids:
        ev = repo.get_evidence(eid)
        if ev is None:
            lines.append(f"  - `{eid}` — (evidence record not found)")
        else:
            lines.append(f"  - `{eid}` — {ev.source_type.value} @ {ev.locator}")
