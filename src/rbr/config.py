from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RBR_", env_file=".env", extra="ignore")

    # Storage. Defaults to sqlite so the pipeline works with zero infrastructure;
    # point RBR_DB_URL at postgres for the hosted profile (docker compose up -d db).
    db_url: str = "sqlite+pysqlite:///./rbr_local.db"

    # Agent provider. stub => deterministic no-LLM mode (always safe to run).
    llm_provider: str = Field(default="stub", description="stub|openai|anthropic|openai_compatible")
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.0

    log_level: str = "INFO"

    # Arbiter tuning
    support_span_min_overlap: float = 0.25
    max_agent_budget_tokens: int = 4096


settings = Settings()
