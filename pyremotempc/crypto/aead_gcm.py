import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def derive_gcm_key(password: str, salt: bytes, iterations: int = 1000) -> bytes:
    """Derives a 256-bit AES-GCM key using PBKDF2-HMAC-SHA1 as done in mRemoteNG AEAD provider."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=32,  # 256 bits
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_aead_password(
    plain_text: str, password: str = "mR3m", iterations: int = 1000
) -> str:
    """
    Encrypts plain_text using mRemoteNG AEAD Provider (AES-256-GCM + PBKDF2).
    Format: Salt (16B) + Nonce (16B) + CipherText + MAC Tag (16B).
    Note: mRemoteNG passes Salt (16B) as Associated Authenticated Data (AAD).
    """
    if not plain_text or not password:
        return plain_text

    salt = os.urandom(16)
    nonce = os.urandom(16)
    key = derive_gcm_key(password, salt, iterations)

    aesgcm = AESGCM(key)
    # AESGCM.encrypt appends 16-byte tag at the end of ciphertext, using salt as AAD
    ciphertext = aesgcm.encrypt(nonce, plain_text.encode("utf-8"), salt)

    combined = salt + nonce + ciphertext
    return base64.b64encode(combined).decode("utf-8")


def decrypt_aead_password(
    ciphertext_b64: str, password: str = "mR3m", iterations: int = 1000
) -> str:
    """
    Decrypts mRemoteNG AEAD Provider string (AES-256-GCM + PBKDF2).
    """
    if not ciphertext_b64 or not password:
        return ciphertext_b64

    try:
        data = base64.b64decode(ciphertext_b64)
        if len(data) < 48:  # 16 salt + 16 nonce + 16 tag/data min
            return ciphertext_b64

        salt = data[:16]
        nonce = data[16:32]
        ciphertext = data[32:]

        key = derive_gcm_key(password, salt, iterations)
        aesgcm = AESGCM(key)
        # Pass salt as associated authenticated data (AAD)
        plain_bytes = aesgcm.decrypt(nonce, ciphertext, salt)
        return plain_bytes.decode("utf-8")
    except Exception:
        # If PBKDF2-SHA1 fails, try SHA256 fallback or return original string
        try:
            salt = data[:16]
            nonce = data[16:32]
            ciphertext = data[32:]

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=iterations,
            )
            key = kdf.derive(password.encode("utf-8"))
            aesgcm = AESGCM(key)
            plain_bytes = aesgcm.decrypt(nonce, ciphertext, salt)
            return plain_bytes.decode("utf-8")
        except Exception:
            return ciphertext_b64
