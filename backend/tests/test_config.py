from app.core.config import ENV_FILE, Settings


def test_settings_load_postgres_password_from_backend_env(monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    settings = Settings()

    assert ENV_FILE == ENV_FILE.resolve()
    assert settings.POSTGRES_PASSWORD == "root"


def test_environment_postgres_password_overrides_backend_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "supplied-by-environment")

    settings = Settings()

    assert settings.POSTGRES_PASSWORD == "supplied-by-environment"
