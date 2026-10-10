import hashlib
import os
from pyremotempc.config.settings import SettingsManager


def hash_master_key(password: str, salt: bytes, iterations: int = 200000) -> str:
    """Computes PBKDF2-HMAC-SHA256 hash of master password with salt."""
    key = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt,
        iterations=iterations
    )
    return key.hex()


class MasterKeyManager:
    """
    Securely manages Master Password verification and storage.
    Zero plain-text password leakage: Only salted PBKDF2-HMAC-SHA256 hashes are persisted to disk.
    """

    def __init__(self, settings_manager: SettingsManager):
        self.settings = settings_manager

    def is_master_key_set(self) -> bool:
        salt = self.settings.get("master_key_salt", "")
        hash_val = self.settings.get("master_key_hash", "")
        return bool(salt and hash_val)

    def set_master_key(self, password: str):
        """Sets and persists a new master password hash and salt."""
        salt = os.urandom(16)
        hash_hex = hash_master_key(password, salt)
        self.settings.set("master_key_salt", salt.hex())
        self.settings.set("master_key_hash", hash_hex)

    def reset_to_default(self):
        """Clears custom master key, resetting to unconfigured default state."""
        self.settings.set("master_key_salt", "")
        self.settings.set("master_key_hash", "")

    def verify_master_key(self, password: str) -> bool:
        """Verifies given password against stored salt and hash."""
        salt_hex = self.settings.get("master_key_salt", "")
        stored_hash = self.settings.get("master_key_hash", "")
        if not salt_hex or not stored_hash:
            # Default fallback if not set yet: default password is "mR3m" or empty string
            return password == "mR3m" or password == ""

        try:
            salt = bytes.fromhex(salt_hex)
            computed_hash = hash_master_key(password, salt)
            return computed_hash == stored_hash
        except Exception:
            return False
