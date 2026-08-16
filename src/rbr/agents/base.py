"""Shared agent base: schema-constrained single-shot reasoning with fallback."""

from __future__ import annotations

import json
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import Settings
from ..logging import get_logger
from ..schemas import AgentCallRecord, ids
from .provider import (
    AgentProvider,
    AgentProviderError,
    StubMode,
    prompt_hash,
    subgraph_hash,
)

log = get_logger(__name__)

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentResult(Generic[OutputT]):
    def __init__(self, output: OutputT, record: AgentCallRecord) -> None:
        self.output: OutputT = output
        self.record: AgentCallRecord = record


class BaseAgent(Generic[InputT, OutputT]):
    name: str = "agent"
    system_prompt: str = ""
    output_model: type[OutputT]

    def __init__(self, provider: AgentProvider, settings: Settings) -> None:
        self.provider = provider
        self.settings = settings
        self._last_input: Any = None

    def run(self, project_id: str, user_input: InputT) -> AgentResult[OutputT]:
        user_json = json.dumps(user_input.model_dump(mode="json"), indent=2, default=str)
        schema_json = json.dumps(self.output_model.model_json_schema(), default=str)
        call_id = ids.agent_call_id()
        p_hash = prompt_hash(self.system_prompt, user_json, schema_json)
        i_hash = subgraph_hash(user_json)
        model_name = getattr(self.provider, "model", "stub")

        output, status, usage = self._execute(call_id, user_json, schema_json)
        record = AgentCallRecord(
            call_id=call_id, project_id=project_id, agent_name=self.name,
            provider=self.provider.name, model=model_name,
            temperature=self.settings.llm_temperature,
            prompt_hash=p_hash, input_subgraph_hash=i_hash,
            output_json=output.model_dump(mode="json"),
            status=status, usage=usage,
        )
        return AgentResult(output=output, record=record)

    def _execute(self, call_id: str, user_json: str, schema_json: str) -> tuple[OutputT, str, dict]:
        if _is_stub(self.provider):
            return self.fallback(), "stub", {}

        try:
            raw = self.provider.complete(self.system_prompt, user_json, json.loads(schema_json))
            output = self.output_model.model_validate(raw)
            return output, "ok", self.provider.usage()
        except (AgentProviderError, StubMode, ValidationError, ValueError, KeyError) as exc:
            log.warning("agent %s first call failed: %s; retrying once", self.name, exc)
        try:
            raw = self.provider.complete(self.system_prompt, user_json, json.loads(schema_json))
            output = self.output_model.model_validate(raw)
            return output, "ok", self.provider.usage()
        except (AgentProviderError, StubMode, ValidationError, ValueError, KeyError) as exc:
            log.warning("agent %s retry failed: %s; using deterministic fallback", self.name, exc)
            return self.fallback(), "fallback", {}

    def fallback(self) -> OutputT:
        """Deterministic, evidence-derived output used in no-LLM mode. Must never
        invent facts: unknowns are labelled UNKNOWN."""
        raise NotImplementedError

    def user_prompt(self, user_input: InputT) -> str:
        return json.dumps(user_input.model_dump(mode="json"), indent=2, default=str)


def _is_stub(provider: Any) -> bool:
    return getattr(provider, "name", "") == "stub"
