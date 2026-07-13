import base64
import os

import pytest

from enterprise_support.security import PayloadCipher, payload_hash, redact_data, redact_text


def test_redaction_removes_secrets_and_masks_personal_data() -> None:
    value = {
        "api_key": "secret-value",
        "message": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz user@example.com",
    }

    redacted = redact_data(value, mask_personal_data=True)

    assert redacted["api_key"] == "[REDACTED]"
    assert "abcdefghijklmnopqrstuvwxyz" not in redacted["message"]
    assert "user@example.com" not in redacted["message"]


def test_payload_cipher_round_trip_and_hash_stability() -> None:
    key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    cipher = PayloadCipher(key)
    payload = {"b": 2, "a": "sensitive"}

    encrypted = cipher.encrypt_json(payload)

    assert "sensitive" not in encrypted
    assert cipher.decrypt_json(encrypted) == payload
    assert payload_hash(payload) == payload_hash({"a": "sensitive", "b": 2})


def test_production_cipher_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("DATA_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError):
        PayloadCipher(production=True)
