import pytest

from app.core.settings_service import get_env_settings_schema, validate_startup_environment


@pytest.mark.unit
def test_env_schema_has_required_and_optional_groups():
    schema = get_env_settings_schema()
    assert "required" in schema
    assert "optional" in schema
    assert "details" in schema
    assert "OPENAI_API_KEY" in schema["required"]
    assert "OPENAI_MODEL" in schema["optional"]
    assert "ELEKTRA_API_BASE_URL" in schema["optional"]
    assert "WEBHOOK_URL" in schema["optional"]


@pytest.mark.unit
def test_validate_startup_environment_raises_when_openai_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        validate_startup_environment()
    assert "OPENAI_API_KEY" in str(exc.value)


@pytest.mark.unit
def test_validate_startup_environment_passes_when_openai_key_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    missing = validate_startup_environment()
    assert missing == []
