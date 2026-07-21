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

    # Schwab OAuth (Phase 12). No separate read-only scope exists (Docs/
    # DECISION_LOG.md's Phase 12 entry) — read-only is enforced by never
    # calling a trading endpoint, not by what the token itself permits.
    # redirect_uri is fixed by the registered developer app, not
    # reconfigurable per environment (unlike Google's).
    schwab_client_id: str | None = None
    schwab_client_secret: str | None = None
    schwab_redirect_uri: str = "https://127.0.0.1:8182"

    # Finnhub and SEC EDGAR were evaluated live in Phase 15
    # (scripts/provider_evaluation/) and adopted as real Research-domain
    # providers in Phase 16 (application/research_provider_factory.py) —
    # `fmp_api_key` stays evaluation-only (Phase 15 found its v3 API
    # deprecated for this key/plan; nothing adopts it). SEC EDGAR's
    # fair-access policy requires a descriptive User-Agent with a real,
    # reachable contact address (an anonymous one gets throttled or
    # rejected) — `research_contact_email` supplies that.
    finnhub_api_key: str | None = None
    fmp_api_key: str | None = None
    research_contact_email: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings singleton. Tests that need different values
    construct `Settings(...)` directly rather than mutating this cache."""
    return Settings()
