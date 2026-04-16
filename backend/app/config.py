"""Application configuration from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_model_reasoning: str = "claude-opus-4-6"
    demo_api_key: str = "demo-key-12345"
    database_path: str = "./data/rcm_demo.duckdb"
    seed_random_seed: int = 42
    mock_payer_base_url: str = "http://localhost:8000/mock"
    mock_payer_latency_ms: int = 150
    mock_payer_error_rate: float = 0.02
    agent_temperature: float = 0.0
    agent_max_tokens: int = 2048
    sse_keepalive_interval: int = 15
    log_level: str = "INFO"

    # Demo-only: when true, agents use scripted responses instead of calling the LLM.
    # Useful for CI and for running the demo without an Anthropic API key.
    agent_offline_mode: bool = False

    # LLM response cache: off | record | replay
    llm_cache_mode: str = "off"
    llm_cache_dir: str = "./data/llm_cache"

    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def db_path(self) -> Path:
        return Path(self.database_path).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
