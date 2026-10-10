import os
from typing import Optional, List, Tuple, Any
import paramiko


class KeyLoader:
    """Helper for loading and managing SSH private keys and ssh-agent identities."""

    @staticmethod
    def is_key_encrypted(key_path: str) -> bool:
        """Check if a private key file is passphrase protected without loading it completely."""
        if not os.path.isfile(key_path):
            return False
        
        # Try loading with empty/None passphrase and catch PasswordRequiredException
        for key_cls in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.DSSKey):
            try:
                key_cls.from_private_key_file(key_path, password=None)
                return False  # Unencrypted key loaded successfully
            except paramiko.PasswordRequiredException:
                return True  # Encrypted key
            except Exception:
                continue
        return False

    @staticmethod
    def load_private_key(key_path: str, passphrase: Optional[str] = None) -> Tuple[Optional[paramiko.PKey], Optional[str]]:
        """
        Attempts to load a private key from the given path.
        Returns (pkey_object, error_message).
        """
        if not os.path.exists(key_path):
            return None, f"File not found: {key_path}"

        key_classes = [
            paramiko.RSAKey,
            paramiko.Ed25519Key,
            paramiko.ECDSAKey,
            paramiko.DSSKey,
        ]

        last_error = "Unknown key format"
        for key_cls in key_classes:
            try:
                pkey = key_cls.from_private_key_file(key_path, password=passphrase)
                return pkey, None
            except paramiko.PasswordRequiredException:
                return None, "Passphrase required"
            except Exception as e:
                last_error = str(e)

        return None, f"Failed to load key: {last_error}"

    @staticmethod
    def get_agent_keys() -> List[Tuple[str, str]]:
        """
        Retrieves active keys from SSH_AUTH_SOCK (ssh-agent).
        Returns a list of tuples: (fingerprint_hex, comment/name).
        """
        agent_keys = []
        try:
            agent = paramiko.Agent()
            keys = agent.get_keys()
            for key in keys:
                fingerprint = key.get_fingerprint().hex()
                comment = getattr(key, "comment", "Agent Key")
                agent_keys.append((fingerprint, f"{key.get_name()} ({fingerprint[:12]}...) - {comment}"))
        except Exception:
            pass
        return agent_keys
