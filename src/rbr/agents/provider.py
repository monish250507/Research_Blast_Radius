"""Agent provider abstraction. Provider-agnostic, with a deterministic stub.

The stub provider is the default: agents return bounded, evidence-derived
fallback outputs labelled UNKNOWN where semantic judgment would be required.
No repository content is ever sent outside the process unless a real provider
is configured by the operator.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..config import Settings
from ..logging import get_logger

log = get_logger(__name__)


class AgentProviderError(RuntimeError):
    pass


class AgentProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def complete(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a dict validated against `schema` (JSON Schema)."""

    @abstractmethod
    def usage(self) -> dict[str, int]:
        return {}


class StubProvider(AgentProvider):
    """Deterministic no-LLM provider. Raises StubMode; agents emit fallbacks."""

    name = "stub"

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        raise StubMode()

    def usage(self) -> dict[str, int]:
        return {}


class StubMode(RuntimeError):
    pass


class OpenAICompatProvider(AgentProvider):
    """Minimal OpenAI-compatible chat completions client (httpx)."""

    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        self.base_url = (settings.llm_base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model or "gpt-4o-mini"
        self.temperature = settings.llm_temperature
        self._last_usage: dict[str, int] = {}

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise AgentProviderError("no api key configured for llm provider")
        url = f"{self.base_url}/chat/completions"
        body = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            resp = httpx.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=120.0,
            )
            resp.raise_for_status()
        except Exception as exc:
            raise AgentProviderError(f"provider call failed: {exc}") from exc
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise AgentProviderError(f"unexpected provider response: {data}") from exc
        usage = data.get("usage", {})
        self._last_usage = {k: int(v) for k, v in usage.items() if isinstance(v, (int, float))}
        from typing import cast
        return cast(dict[str, Any], json.loads(content))

    def usage(self) -> dict[str, int]:
        return self._last_usage


def build_provider(settings: Settings) -> AgentProvider:
    provider = settings.llm_provider.lower()
    if provider in ("", "stub"):
        return StubProvider()
    if provider in ("openai", "anthropic", "openai_compatible"):
        return OpenAICompatProvider(settings)
    raise AgentProviderError(f"unknown provider: {provider}")


def prompt_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", errors="replace"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def subgraph_hash(input_json: str) -> str:
    return hashlib.sha256(input_json.encode("utf-8")).hexdigest()
