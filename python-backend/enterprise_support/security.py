from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


REDACTED = "[REDACTED]"
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*[^\s,;]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b"),
)
_EMAIL_PATTERN = re.compile(r"\b([A-Za-z0-9._%+-])[^@\s]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_PHONE_PATTERN = re.compile(r"(?<!\d)(\+?\d{0,3})[ -]?(\d{3})[ -]?(\d{4})[ -]?(\d{4})(?!\d)")


def redact_text(value: str, *, mask_personal_data: bool = False) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    if mask_personal_data:
        redacted = _EMAIL_PATTERN.sub(r"\1***\2", redacted)
        redacted = _PHONE_PATTERN.sub(lambda match: f"{match.group(1)}***{match.group(4)}", redacted)
    return redacted


def redact_data(value: Any, *, mask_personal_data: bool = False) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
                result[key] = REDACTED
            else:
                result[key] = redact_data(item, mask_personal_data=mask_personal_data)
        return result
    if isinstance(value, list):
        return [redact_data(item, mask_personal_data=mask_personal_data) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_data(item, mask_personal_data=mask_personal_data) for item in value)
    if isinstance(value, str):
        return redact_text(value, mask_personal_data=mask_personal_data)
    return value


def payload_hash(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PayloadCipher:
    """Encrypt sensitive draft payloads while keeping local development easy to run."""

    def __init__(self, key: str | None = None, *, production: bool | None = None) -> None:
        is_production = production if production is not None else os.getenv("APP_ENV", "development") == "production"
        configured_key = key or os.getenv("DATA_ENCRYPTION_KEY")
        if is_production and not configured_key:
            raise RuntimeError("DATA_ENCRYPTION_KEY is required in production")
        if not configured_key:
            digest = hashlib.sha256(b"enterprise-agent-local-development-only").digest()
            configured_key = base64.urlsafe_b64encode(digest).decode("ascii")
        try:
            self._fernet = Fernet(configured_key.encode("ascii"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("DATA_ENCRYPTION_KEY must be a valid Fernet key") from exc

    def encrypt_json(self, value: Any) -> str:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return self._fernet.encrypt(serialized).decode("ascii")

    def decrypt_json(self, value: str) -> Any:
        try:
            plaintext = self._fernet.decrypt(value.encode("ascii"))
        except InvalidToken as exc:
            raise ValueError("Encrypted payload cannot be decrypted") from exc
        return json.loads(plaintext.decode("utf-8"))

