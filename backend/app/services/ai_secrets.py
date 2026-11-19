"""Server-side encryption for Admin-managed AI provider API keys.

Plaintext provider keys are accepted only in the create-config request. They
are encrypted with a server-held Fernet key before storage and are never
returned by the API, written to audit metadata, or copied into an operation
snapshot. Only a boolean and a short display hint leave the backend.
"""
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class AISecretError(ValueError):
    """The supplied API key, or its stored ciphertext, is unusable."""


class AISecretConfigurationError(AISecretError):
    """The server-side encryption key is missing or invalid."""


def _fernet() -> Fernet:
    key = (settings.AI_CONFIG_ENCRYPTION_KEY or "").strip()
    if not key:
        raise AISecretConfigurationError(
            "Server chưa cấu hình AI_CONFIG_ENCRYPTION_KEY để lưu API key."
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise AISecretConfigurationError(
            "AI_CONFIG_ENCRYPTION_KEY không phải là khóa Fernet hợp lệ."
        ) from None


def encryption_ready() -> bool:
    try:
        _fernet()
    except AISecretError:
        return False
    return True


def normalize_api_key(value: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if (
        not 8 <= len(normalized) <= 500
        or not normalized.isascii()
        or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise AISecretError(
            "API key không hợp lệ; nhập khóa ASCII không chứa khoảng trắng, dài 8–500 ký tự."
        )
    return normalized


def encrypt_api_key(value: str) -> str:
    normalized = normalize_api_key(value)
    return _fernet().encrypt(normalized.encode("ascii")).decode("ascii")


def decrypt_api_key(ciphertext: str) -> str:
    fernet = _fernet()
    try:
        return fernet.decrypt(ciphertext.encode("ascii")).decode("ascii")
    except (InvalidToken, UnicodeEncodeError, ValueError):
        raise AISecretError(
            "Không thể giải mã API key đã lưu; hãy tạo phiên bản cấu hình mới với API key hợp lệ."
        ) from None


def api_key_hint(value: str) -> str:
    normalized = normalize_api_key(value)
    return f"••••{normalized[-4:]}"
