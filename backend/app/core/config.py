"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings for the ResearchPilot backend."""

    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+asyncpg://researchpilot:researchpilot@localhost:5432/researchpilot",
        alias="DATABASE_URL",
    )
    data_dir: str = Field(default="../data", alias="DATA_DIR")
    reports_dir: str = Field(default="../reports", alias="REPORTS_DIR")
    llm_provider: Literal["mock", "openai", "anthropic", "ollama"] = Field(
        default="mock",
        alias="LLM_PROVIDER",
    )
    llm_model: str = Field(default="mock-model", alias="LLM_MODEL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    log_llm_prompts: bool = Field(default=False, alias="LOG_LLM_PROMPTS")
    tool_timeout_seconds: int = Field(default=30, alias="TOOL_TIMEOUT_SECONDS")
    max_tool_retries: int = Field(default=3, alias="MAX_TOOL_RETRIES")
    max_replans: int = Field(default=2, alias="MAX_REPLANS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"], alias="CORS_ORIGINS"
    )

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        """Accept either a CSV string or a list for CORS origins."""
        if value is None:
            return ["http://localhost:5173"]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @property
    def data_root(self) -> Path:
        """Return the configured data directory as an absolute path."""
        path = Path(self.data_dir)
        if path.is_absolute():
            return path.resolve()
        return (Path(__file__).resolve().parents[2] / path).resolve()

    @property
    def reports_root(self) -> Path:
        """Return the configured reports directory as an absolute path."""
        path = Path(self.reports_dir)
        if path.is_absolute():
            return path.resolve()
        return (Path(__file__).resolve().parents[2] / path).resolve()


settings = Settings()
