import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError


@pytest.fixture
def encryption_key(monkeypatch):
    from app.core.config import settings

    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "AI_CONFIG_ENCRYPTION_KEY", key)
    return key


def test_provider_api_key_is_encrypted_and_only_hint_is_exposed(encryption_key):
    from app.services.ai_secrets import (
        api_key_hint,
        decrypt_api_key,
        encrypt_api_key,
        encryption_ready,
    )

    provider_key = "provider-key-1234567890wxyz"
    ciphertext = encrypt_api_key(provider_key)

    assert encryption_ready() is True
    assert ciphertext != provider_key
    assert provider_key not in ciphertext
    assert decrypt_api_key(ciphertext) == provider_key
    assert api_key_hint(provider_key) == "••••wxyz"


def test_provider_api_key_requires_server_encryption_key(monkeypatch):
    from app.core.config import settings
    from app.services.ai_secrets import (
        AISecretConfigurationError,
        encrypt_api_key,
        encryption_ready,
    )

    monkeypatch.setattr(settings, "AI_CONFIG_ENCRYPTION_KEY", "")

    assert encryption_ready() is False
    with pytest.raises(AISecretConfigurationError):
        encrypt_api_key("provider-key-1234567890")


def test_openai_compatible_runtime_allows_custom_name_base_and_model(monkeypatch):
    from app.core.config import settings
    from app.services.ai_config import AIConfigError, validate_runtime

    monkeypatch.setattr(settings, "LLM_ALLOWED_MODELS", ["approved-only"])
    monkeypatch.setattr(settings, "LLM_ALLOWED_API_BASES", [])
    monkeypatch.setattr(settings, "LLM_API_BASE", "http://127.0.0.1:11434/v1")

    runtime = validate_runtime({
        "provider": "compatible",
        "provider_name": " OpenRouter ",
        "model_name": "vendor/custom-model",
        "api_base": "https://openrouter.ai/api/v1/",
        "temperature_default": 0.2,
    }, require_provider_name=True)

    assert runtime["provider_name"] == "OpenRouter"
    assert runtime["model_name"] == "vendor/custom-model"
    assert runtime["api_base"] == "https://openrouter.ai/api/v1"

    with pytest.raises(AIConfigError):
        validate_runtime({
            "provider": "compatible",
            "provider_name": " ",
            "model_name": "vendor/custom-model",
            "api_base": "https://openrouter.ai/api/v1",
            "temperature_default": 0.2,
        }, require_provider_name=True)


def test_non_compatible_runtime_still_uses_environment_allowlists(monkeypatch):
    from app.core.config import settings
    from app.services.ai_config import AIConfigError, validate_runtime

    monkeypatch.setattr(settings, "LLM_ALLOWED_MODELS", ["approved-only"])
    monkeypatch.setattr(settings, "LLM_ALLOWED_API_BASES", [])
    monkeypatch.setattr(settings, "LLM_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(settings, "LLM_MODEL_NAME", "approved-only")

    with pytest.raises(AIConfigError):
        validate_runtime({
            "provider": "openai",
            "model_name": "custom-model",
            "api_base": "https://api.openai.com/v1",
            "temperature_default": 0.1,
        })


def test_public_runtime_and_snapshot_never_include_provider_secret():
    from app.services.ai_config import public_runtime, runtime_snapshot

    runtime = {
        "source": "database",
        "config_id": "00000000-0000-0000-0000-000000000001",
        "provider": "compatible",
        "provider_name": "OpenRouter",
        "model_name": "vendor/custom-model",
        "api_base": "https://openrouter.ai/api/v1",
        "temperature_default": 0.1,
        "api_key": "provider-key-1234567890",
        "api_key_ciphertext": "ciphertext-value",
        "api_key_hint": "••••7890",
    }

    for value in (public_runtime(runtime), runtime_snapshot(runtime)):
        assert "api_key" not in value
        assert "api_key_ciphertext" not in value
        assert value["api_key_configured"] is True
        assert value["api_key_hint"] == "••••7890"


def test_admin_request_accepts_write_only_openai_compatible_fields():
    from app.api.admin import AIConfigUpdateRequest

    request = AIConfigUpdateRequest(
        provider="compatible",
        provider_name=" OpenRouter ",
        model_name=" vendor/custom-model ",
        api_base=" https://openrouter.ai/api/v1 ",
        api_key=" provider-key-1234567890 ",
        temperature_default=0.2,
    )

    assert request.provider_name == "OpenRouter"
    assert request.model_name == "vendor/custom-model"
    assert request.api_base == "https://openrouter.ai/api/v1"
    assert request.api_key == "provider-key-1234567890"

    with pytest.raises(ValidationError):
        AIConfigUpdateRequest(
            provider="compatible",
            provider_name="OpenRouter",
            model_name="vendor/custom-model",
            api_base="https://openrouter.ai/api/v1",
            unexpected="value",
        )


@pytest.mark.asyncio
async def test_llm_client_uses_config_key_and_does_not_leak_environment_key(monkeypatch):
    from app.core.config import settings
    from app.services.llm_client import LLMClient

    captured = []

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}

    class Transport:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            captured.append((url, kwargs))
            return Reply()

    monkeypatch.setattr("app.services.llm_client.httpx.AsyncClient", Transport)
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", False)
    monkeypatch.setattr(settings, "LLM_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(settings, "LLM_API_KEY", "environment-key-1234567890")
    monkeypatch.setattr(settings, "LLM_MODEL_NAME", "environment-model")

    runtime = {
        "source": "database",
        "config_id": "00000000-0000-0000-0000-000000000001",
        "provider": "compatible",
        "provider_name": "Local Compatible",
        "model_name": "custom-model",
        "api_base": "http://127.0.0.1:11435/v1",
        "temperature_default": 0.1,
        "api_key_configured": True,
        "api_key": "provider-key-1234567890",
    }
    monkeypatch.setattr("app.services.llm_client.get_active_runtime", lambda db: runtime)

    assert await LLMClient()._call_llm("system", "synthetic") == {"ok": True}
    assert captured[-1][0] == "http://127.0.0.1:11435/v1/chat/completions"
    assert captured[-1][1]["headers"]["Authorization"] == "Bearer provider-key-1234567890"
    assert captured[-1][1]["json"]["model"] == "custom-model"

    runtime_without_key = {**runtime, "api_key_configured": False}
    runtime_without_key.pop("api_key")
    monkeypatch.setattr("app.services.llm_client.get_active_runtime", lambda db: runtime_without_key)

    assert await LLMClient()._call_llm("system", "synthetic") == {"ok": True}
    assert "Authorization" not in captured[-1][1]["headers"]


@pytest.mark.asyncio
async def test_provider_connection_test_uses_entered_key_and_reports_status(monkeypatch):
    from app.core.config import settings
    from app.services.llm_client import LLMClient

    captured = []

    class Reply:
        status_code = 200

        @property
        def is_success(self):
            return True

        def json(self):
            return {"model": "returned-model", "choices": [{"message": {"content": "OK"}}]}

    class Transport:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            captured.append((url, kwargs))
            return Reply()

    monkeypatch.setattr("app.services.llm_client.httpx.AsyncClient", Transport)
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", False)
    monkeypatch.setattr(settings, "LLM_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(settings, "LLM_API_KEY", "environment-key-1234567890")

    runtime = {
        "source": "connection_test",
        "provider": "compatible",
        "provider_name": "Local Compatible",
        "model_name": "custom-model",
        "api_base": "http://127.0.0.1:11435/v1",
        "temperature_default": 0.1,
        "api_key_configured": True,
        "api_key": "provider-key-1234567890",
    }

    result = await LLMClient().test_provider_connection(runtime)

    assert result["ok"] is True
    assert result["status_code"] == 200
    assert result["provider_returned_model"] == "returned-model"
    assert result["latency_ms"] >= 0
    assert captured[-1][0] == "http://127.0.0.1:11435/v1/chat/completions"
    assert captured[-1][1]["headers"]["Authorization"] == "Bearer provider-key-1234567890"
    assert captured[-1][1]["json"]["model"] == "custom-model"
    assert "response_format" not in captured[-1][1]["json"]
    assert "candidate" not in str(captured[-1][1]["json"]).lower()


@pytest.mark.asyncio
async def test_provider_connection_test_reports_auth_failure_without_raising(monkeypatch):
    from app.core.config import settings
    from app.services.llm_client import LLMClient

    class Reply:
        status_code = 401

        @property
        def is_success(self):
            return False

        def json(self):
            return {"error": {"message": "invalid api key"}}

    class Transport:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            return Reply()

    monkeypatch.setattr("app.services.llm_client.httpx.AsyncClient", Transport)
    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_API", False)
    monkeypatch.setattr(settings, "LLM_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(settings, "LLM_API_KEY", None)

    result = await LLMClient().test_provider_connection({
        "source": "connection_test",
        "provider": "compatible",
        "provider_name": "Local Compatible",
        "model_name": "custom-model",
        "api_base": "http://127.0.0.1:11435/v1",
        "temperature_default": 0.1,
        "api_key_configured": True,
        "api_key": "provider-key-1234567890",
    })

    assert result["ok"] is False
    assert result["status_code"] == 401
    assert result["error_code"] == "AUTH_FAILED"
    assert "provider-key-1234567890" not in str(result)
