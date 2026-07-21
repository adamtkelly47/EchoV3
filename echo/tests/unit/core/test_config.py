from core.config.settings import Settings


def test_settings_have_sane_defaults(monkeypatch) -> None:
    # Isolated from whatever the real process environment happens to have
    # set (e.g. a developer's local .env exporting DATABASE_URL) — this test
    # asserts Settings' own defaults, not the ambient environment.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("ECHO_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = Settings(_env_file=None)
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.ollama_base_url == "http://ollama:11434"
    assert settings.echo_env == "development"
    assert settings.log_level == "INFO"
    assert settings.database_url is None


def test_settings_read_from_env(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql://example/db"
    assert settings.log_level == "DEBUG"
