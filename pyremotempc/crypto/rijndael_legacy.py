import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding


def get_legacy_key(password: str) -> bytes:
    """Derives a 128-bit key from password using MD5 hash (mRemoteNG legacy mode)."""
    return hashlib.md5(password.encode("utf-8")).digest()


def encrypt_legacy_password(plain_text: str, password: str = "mR3m") -> str:
    """
    Encrypts plain_text using mRemoteNG Legacy Rijndael provider (AES-128-CBC + MD5 key).
    The IV (16 bytes) is prepended to the ciphertext before Base64 encoding.
    """
    if not plain_text or not password:
        return plain_text

    key = get_legacy_key(password)
    import os
    iv = os.urandom(16)

    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plain_text.encode("utf-8")) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    result = iv + ciphertext
    return base64.b64encode(result).decode("utf-8")


def decrypt_legacy_password(ciphertext_b64: str, password: str = "mR3m") -> str:
    """
    Decrypts mRemoteNG Legacy Rijndael encrypted string (AES-128-CBC + MD5 key).
    """
    if not ciphertext_b64 or not password:
        return ciphertext_b64

    try:
        data = base64.b64decode(ciphertext_b64)
        if len(data) < 16:
            return ciphertext_b64

        iv = data[:16]
        encrypted_bytes = data[16:]

        key = get_legacy_key(password)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_plain = decryptor.update(encrypted_bytes) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        plain_bytes = unpadder.update(padded_plain) + unpadder.finalize()
        return plain_bytes.decode("utf-8")
    except Exception:
        # Fallback if decryption fails or string was not encrypted
        return ciphertext_b64
