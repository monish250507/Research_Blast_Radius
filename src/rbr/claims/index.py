"""Structured claim representation + deterministic extraction from declared sources.

Claims supplied by the researcher (claims.yaml) or extracted from a report are
typed Claim objects with preserved qualifiers and exact evidence locations
(spec section 13). Semantic judgment about claim relevance is left to the
Scientific Evidence Analyst (INFERRED); the deterministic index only links
claims to the artifacts they explicitly reference.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..logging import get_logger
from ..schemas import (
    Claim,
    EdgeRelation,
    Evidence,
    EvidenceSourceType,
    ExtractionStatus,
    GraphEdge,
    GraphNode,
    NodeType,
    ProvenanceType,
    ids,
)
from ..store.repository import Repository

log = get_logger(__name__)


class ClaimLoader:
    """Loads structured claims from a YAML manifest (researcher-declared)."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id

    def load_yaml(self, path: str | Path) -> list[Claim]:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        raw_claims = data.get("claims", [])
        claims: list[Claim] = []
        for raw in raw_claims:
            ref = raw.get("id", raw.get("claim_id", raw.get("text", ""))[:32])
            text = raw.get("text") or raw.get("normalized_text") or ""
            claim = Claim(
                claim_id=ids.claim_id(f"{ref}:{text}"),
                project_id=self.project_id,
                normalized_text=text,
                subject=raw.get("subject"),
                intervention=raw.get("intervention"),
                comparator=raw.get("comparator"),
                metric=raw.get("metric"),
                magnitude=raw.get("magnitude"),
                population=raw.get("population"),
                dataset=raw.get("dataset"),
                condition=raw.get("condition"),
                qualifiers=[str(q) for q in raw.get("qualifiers", [])],
                evidence_locations=[str(e) for e in raw.get("evidence_locations", [])],
                source_section=raw.get("source_section"),
                source="declared",
                extraction_status=(
                    ExtractionStatus(raw.get("extraction_status", "EXTRACTED").upper())
                    if raw.get("extraction_status")
                    else ExtractionStatus.EXTRACTED
                ),
            )
            claims.append(claim)
        return claims


class ClaimIndex:
    """Persists claims + their reference evidence, links them to nodes, finds candidates."""

    def __init__(self, repo: Repository, project_id: str) -> None:
        self.repo = repo
        self.project_id = project_id

    def ingest_claims(self, claims: list[Claim]) -> None:
        for claim in claims:
            self.repo.upsert_claim(claim)
            ev = self._claim_evidence(claim)
            self.repo.add_evidence(ev)
            node = GraphNode(node_id=claim.claim_id, project_id=self.project_id,
                             node_type=NodeType.CLAIM, label=claim.normalized_text[:200],
                             ref=claim.claim_id, data={"qualifiers": claim.qualifiers})
            self.repo.upsert_node(node)
            for loc in claim.evidence_locations:
                for node_type in (NodeType.ARTIFACT, NodeType.FIGURE, NodeType.FILE,
                                  NodeType.TABLE):
                    target_id = ids.node_id(node_type.value, loc)
                    if self.repo.get_node(target_id) is None:
                        continue
                    edge = GraphEdge(
                        edge_id=ids.edge_id(claim.claim_id, target_id,
                                            EdgeRelation.REFERENCES.value),
                        project_id=self.project_id, source_id=claim.claim_id,
                        target_id=target_id, relation=EdgeRelation.REFERENCES,
                        provenance_type=ProvenanceType.DECLARED,
                        evidence_ids=[ev.evidence_id],
                        locator=f"claim:{claim.claim_id}:{loc}",
                        extractor_version="0.1.0",
                    )
                    self.repo.add_edge(edge)

    def load_claims(self) -> list[Claim]:
        return self.repo.list_claims(self.project_id)

    def add_reference_edges(self, graph_nodes: set[str]) -> int:
        """(Kept for compatibility; reference edges are created at ingest time.)"""
        return 0

    def deterministic_candidates(self, affected_node_ids: list[str]) -> list[str]:
        """Claims whose declared evidence-location nodes are in the affected set."""
        affected = set(affected_node_ids)
        candidates: set[str] = set()
        for claim in self.load_claims():
            for loc in claim.evidence_locations:
                for node_type in (NodeType.ARTIFACT, NodeType.FIGURE, NodeType.FILE,
                                  NodeType.TABLE):
                    if ids.node_id(node_type.value, loc) in affected:
                        candidates.add(claim.claim_id)
                        break
        return sorted(candidates)

    def _claim_evidence(self, claim: Claim) -> Evidence:
        import hashlib

        payload_hash = hashlib.sha256(
            "\n".join(claim.evidence_locations).encode()
        ).hexdigest()
        locator = f"claim:{claim.claim_id}"
        return Evidence(
            evidence_id=ids.evidence_id(EvidenceSourceType.CLAIM_DECLARED.value,
                                        locator, payload_hash, "0.1.0"),
            project_id=self.project_id, source_type=EvidenceSourceType.CLAIM_DECLARED,
            locator=locator, content_hash=payload_hash, extractor="0.1.0",
            payload={
                "claim_id": claim.claim_id,
                "text": claim.normalized_text,
                "qualifiers": claim.qualifiers,
                "evidence_locations": claim.evidence_locations,
            },
        )
