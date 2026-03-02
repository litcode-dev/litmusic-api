import pytest
from app.services.encryption_service import generate_key_and_iv, encrypt_bytes, decrypt_bytes


def test_encrypt_decrypt_roundtrip():
    plaintext = b"Hello, LitMusic!"
    key, iv = generate_key_and_iv()
    encrypted = encrypt_bytes(plaintext, key, iv)
    decrypted = decrypt_bytes(encrypted, key, iv)
    assert decrypted == plaintext


def test_different_keys_fail():
    from Crypto.Cipher import AES as _AES
    plaintext = b"test data"
    key, iv = generate_key_and_iv()
    wrong_key, _ = generate_key_and_iv()
    encrypted = encrypt_bytes(plaintext, key, iv)
    with pytest.raises(ValueError):
        decrypt_bytes(encrypted, wrong_key, iv)


def test_key_is_256_bits():
    import base64
    key, iv = generate_key_and_iv()
    assert len(base64.b64decode(key)) == 32


def test_encrypted_differs_from_plaintext():
    plaintext = b"audio data"
    key, iv = generate_key_and_iv()
    encrypted = encrypt_bytes(plaintext, key, iv)
    assert encrypted != plaintext
