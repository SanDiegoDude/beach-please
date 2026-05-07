"""Environment-driven settings for Beach, Please."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = "sk-not-set"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    cors_origins: str = "http://localhost:5757,http://127.0.0.1:5757,http://localhost:3000,http://127.0.0.1:3000"

    # Regex applied in addition to cors_origins. The default matches any
    # localhost or RFC1918 LAN address (10/8, 172.16/12, 192.168/16) plus
    # mDNS *.local hostnames, on any port, http or https. This is what makes
    # "open it on your phone" work without per-IP config -- the frontend at
    # http://<lan-ip>:5757 calling http://<lan-ip>:8765 is a same-LAN-only
    # cross-origin request that we trust.
    cors_origin_regex: str = (
        r"^https?://("
        r"localhost|"
        r"127\.0\.0\.1|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"\[::1\]|"
        r"[a-zA-Z0-9-]+\.local"
        r")(:\d+)?$"
    )

    cache_ttl_seconds: int = 600
    request_timeout_seconds: float = 20.0

    # Many local models (LM Studio, Ollama) ship with chat templates that
    # don't handle the OpenAI `tool` role correctly. When True, we send tool
    # results back as user messages instead. Safe on OpenAI as well.
    tool_results_as_user: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
