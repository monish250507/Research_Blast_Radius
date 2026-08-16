"""Shared collector for adapter output: evidence, nodes, edges, coverage, gaps.

Adapters are deterministic. They produce typed records only; the graph builder
validates that every edge references existing nodes and evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..schemas import CoverageLayer, Evidence, GraphEdge, GraphNode, LayerCoverage


@dataclass
class AdapterOutput:
    evidence: list[Evidence] = field(default_factory=list)
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    coverage: dict[CoverageLayer, LayerCoverage] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)

    def layer(self, name: CoverageLayer) -> LayerCoverage:
        if name not in self.coverage:
            self.coverage[name] = LayerCoverage(layer=name)
        return self.coverage[name]


@dataclass
class AdapterContext:
    project_id: str
    snapshot_id: str | None = None
    extractor: str = "0.1.0"
    meta: dict[str, Any] = field(default_factory=dict)
