"""Centralized configuration (CONSTITUTION.md: "Configuration is data. Not
code... should never be scattered throughout implementation."). Every app
reads settings from here — never `os.environ.get(...)` directly outside
this module.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    database_url: str | None = None
    redis_url: str = "redis://redis:6379/0"
    ollama_base_url: str = "http://ollama:11434"
    echo_env: str = "development"
    log_level: str = "INFO"

    # Model gateway (Phase 7). `default_model_provider` is a plain string,
    # not providers.models.contracts.Provider, so core/ never imports from
    # providers/ (CONSTITUTION.md dependency direction: providers depend on
    # core, never the reverse) — the gateway converts it to the enum itself.
    anthropic_api_key: str | None = None
    claude_model_name: str = "claude-sonnet-5"
    ollama_model_name: str = "llama3.2:1b"
    default_model_provider: str = "ollama"

    # Google Calendar OAuth (Phase 10). Read-only scope only (Docs/SECURITY.md:
    # "Read integrations ... request read-only scopes; write scopes are never
    # requested until the corresponding write phase ... is reached").
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str = "http://localhost:8000/calendar/oauth/callback"

    # Symmetric key for encrypting secrets at rest (Docs/SECURITY.md) — a
    # Fernet key, not domain-specific, so it lives at the top level rather
    # than under a per-domain settings block.
    secret_encryption_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings singleton. Tests that need different values
    construct `Settings(...)` directly rather than mutating this cache."""
    return Settings()
