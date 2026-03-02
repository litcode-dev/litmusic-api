import base64
import os
from Crypto.Cipher import AES


def generate_key_and_iv() -> tuple[str, str]:
    """Generate a fresh AES-256-GCM key and IV. Returns (key_b64, iv_b64)."""
    key = os.urandom(32)  # 256-bit
    iv = os.urandom(16)
    return base64.b64encode(key).decode(), base64.b64encode(iv).decode()


def encrypt_bytes(plaintext: bytes, key_b64: str, iv_b64: str) -> bytes:
    key = base64.b64decode(key_b64)
    iv = base64.b64decode(iv_b64)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    # Prepend tag for verification on decrypt
    return tag + ciphertext


def decrypt_bytes(ciphertext_with_tag: bytes, key_b64: str, iv_b64: str) -> bytes:
    key = base64.b64decode(key_b64)
    iv = base64.b64decode(iv_b64)
    tag = ciphertext_with_tag[:16]
    ciphertext = ciphertext_with_tag[16:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    return cipher.decrypt_and_verify(ciphertext, tag)
