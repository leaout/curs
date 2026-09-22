# coding: utf-8
"""Typed application settings.

Environment variables always take precedence over values loaded from ``.env``.
Every setting uses the ``TRADING_V2_`` prefix so the new service can run next to
the legacy application without configuration collisions.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from trading_v2.domain.enums import TradingMode


class AppSettings(BaseSettings):
    """Runtime configuration for the standalone V2 API."""

    model_config = SettingsConfigDict(
        env_prefix="TRADING_V2_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "curs-trading-v2"
    service_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = Field(default=8010, ge=1, le=65535)
    api_prefix: str = "/api/v2"
    trading_mode: TradingMode = TradingMode.OBSERVE
    docs_enabled: bool = True
    cors_origins: list[str] = Field(default_factory=list)
    event_history_size: int = Field(default=2_000, ge=1, le=100_000)
    event_subscriber_queue_size: int = Field(default=500, ge=1, le=10_000)
    cpptdx_base_url: str = "http://127.0.0.1:8022"
    cpptdx_timeout_seconds: float = Field(default=3.0, gt=0, le=60)
    cpptdx_snapshot_interval_ms: int = Field(default=1_000, ge=200, le=60_000)
    database_url: str = "sqlite:///data/trading_v2.db"
    model_enabled: bool = False
    model_provider: str = "deepseek"
    model_name: str = "deepseek-chat"
    model_api_key_env: str = "DEEPSEEK_API_KEY"
    model_base_url: str = ""
    model_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    model_max_tokens: int = Field(default=1_500, ge=256, le=16_000)

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith("/"):
            raise ValueError("api_prefix must start with '/'")
        return normalized

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("environment cannot be empty")
        return normalized

    @field_validator("cpptdx_base_url")
    @classmethod
    def normalize_cpptdx_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("cpptdx_base_url must use http or https")
        return normalized

    @field_validator("model_provider")
    @classmethod
    def validate_model_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"openai", "deepseek", "anthropic", "openai_compatible"}
        if normalized not in allowed:
            raise ValueError(f"model_provider must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("model_name", "model_api_key_env")
    @classmethod
    def non_empty_model_setting(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model name and API key environment variable cannot be empty")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the process-level settings instance."""

    return AppSettings()
