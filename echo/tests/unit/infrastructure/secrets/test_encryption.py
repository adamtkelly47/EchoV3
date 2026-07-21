import pytest
from cryptography.fernet import Fernet

from core.errors import ConfigurationError
from infrastructure.secrets.encryption import SecretCipher, SecretDecryptionError


def test_encrypt_then_decrypt_round_trips() -> None:
    cipher = SecretCipher(Fernet.generate_key().decode("utf-8"))
    ciphertext = cipher.encrypt("super-secret-token")
    assert ciphertext != "super-secret-token"
    assert cipher.decrypt(ciphertext) == "super-secret-token"


def test_invalid_key_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        SecretCipher("not-a-valid-fernet-key")


def test_ciphertext_from_a_different_key_fails_to_decrypt() -> None:
    cipher_a = SecretCipher(Fernet.generate_key().decode("utf-8"))
    cipher_b = SecretCipher(Fernet.generate_key().decode("utf-8"))
    ciphertext = cipher_a.encrypt("token")
    with pytest.raises(SecretDecryptionError):
        cipher_b.decrypt(ciphertext)
