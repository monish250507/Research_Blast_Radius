"""Evidence model, support spans and coverage model (spec section 6, 15)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from .core import RBREntity
from .enums import CoverageLayer, EvidenceSourceType


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Evidence(RBREntity):
    """Immutable, content-addressed evidence record."""

    evidence_id: str
    project_id: str
    source_type: EvidenceSourceType
    locator: str
    content_hash: str
    extractor: str
    payload: dict[str, Any] = Field(default_factory=dict)
    snapshot_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class SupportSpan(RBREntity):
    """A quoted span that anchors a statement to a specific piece of evidence.

    The arbiter runs a lexical-overlap check between an agent statement and the
    cited span; citations that do not support their statement are rejected.
    """

    evidence_id: str
    text: str
    anchor: str = ""
    start_offset: int | None = None
    end_offset: int | None = None


class LayerCoverage(RBREntity):
    layer: CoverageLayer
    scanned: int = 0
    parsed: int = 0
    failed: int = 0
    unknown: int = 0
    notes: list[str] = Field(default_factory=list)

    @property
    def ratio(self) -> float:
        if self.scanned == 0:
            return 1.0
        return self.parsed / self.scanned


class Coverage(RBREntity):
    """Per-layer coverage, never a single opaque confidence score (spec section 15)."""

    project_id: str
    change_id: str
    layers: dict[CoverageLayer, LayerCoverage] = Field(default_factory=dict)

    def layer(self, name: CoverageLayer) -> LayerCoverage:
        return self.layers.setdefault(name, LayerCoverage(layer=name))
