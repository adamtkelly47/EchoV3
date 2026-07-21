"""Symmetric encryption for secrets at rest (Docs/SECURITY.md: "Secrets
(OAuth tokens, API keys, database credentials) ... are stored in secure
secret management ... and encrypted at rest"). Uses Fernet (AES-128-CBC +
HMAC-SHA256, from the `cryptography` package) rather than hand-rolled
crypto — CONSTITUTION.md's general anti-invention posture applies to
cryptographic primitives more than anywhere else.

This is cross-cutting platform infrastructure, not a domain concept or a
swappable vendor integration, so it lives under infrastructure/ rather than
behind a Protocol port the way external providers (Google Calendar, Claude,
Ollama) are — domains depend on it directly, the same way
domains/approvals/service.py depends on infrastructure/database's
AuditRepository directly.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from core.errors import ConfigurationError, EchoError, Severity


class SecretDecryptionError(EchoError):
    """The ciphertext could not be decrypted with the configured key —
    e.g. the key rotated without re-encrypting stored secrets, or the
    stored value was corrupted. Never silently returns garbage plaintext."""

    code = "secret_decryption_failed"
    retryable = False
    severity = Severity.CRITICAL


class SecretCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except ValueError as exc:
            raise ConfigurationError(
                "SECRET_ENCRYPTION_KEY is not a valid Fernet key "
                "(generate one with Fernet.generate_key())"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretDecryptionError("stored secret could not be decrypted") from exc
