from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
from pyremotempc.engine.sftp_engine import SFTPEngine, NativePTYSFTPEngine


class BaseFileTransferEngine(ABC):
    """Abstract Base Class for file transfer engines (SFTP, SCP1, FTP)."""

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def list_remote_dir(self, remote_path: str = ".") -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        pass

    @abstractmethod
    def download_file(self, remote_path: str, local_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        pass

    @abstractmethod
    def upload_directory(self, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        pass

    @abstractmethod
    def download_directory(self, remote_path: str, local_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        pass

    @abstractmethod
    def create_remote_dir(self, remote_path: str):
        pass

    @abstractmethod
    def remove_remote_file(self, remote_path: str):
        pass

    @abstractmethod
    def remove_remote_dir(self, remote_path: str):
        pass

    @abstractmethod
    def rename_remote(self, old_path: str, new_path: str):
        pass


class UnifiedFileTransferEngine(BaseFileTransferEngine):
    """
    Unified File Transfer Engine.
    Detects whether the connection protocol is SSH1, SSH2/SFTP, or FTP, and routes
    operations automatically between Paramiko/Native SFTP, SCP1, or FTPEngine.
    """

    def __init__(self, hostname: str, port: int = 22, username: str = "", password: str = "",
                 key_filename: Optional[str] = None, ssh_version: str = "SSH2",
                 ssh_engine: Optional[Any] = None, log_callback: Optional[Callable[[str], None]] = None):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.ssh_version = ssh_version.upper()
        self.ssh_engine = ssh_engine
        self.log_callback = log_callback

        if self.ssh_version == "FTP":
            from pyremotempc.engine.ftp_engine import FTPEngine
            self._engine = FTPEngine(
                hostname=hostname, port=port if port else 21, username=username, password=password,
                log_callback=log_callback
            )
        elif self.ssh_version in ("SSH1", "SCP"):
            # SSH1 and SCP use SCP native CLI wrapper engine (NativePTYSFTPEngine)
            self._engine = NativePTYSFTPEngine(
                hostname=hostname, port=port, username=username, password=password,
                key_filename=key_filename, log_callback=log_callback
            )
        else:
            # SSH2 / SFTP uses SFTPEngine (Paramiko + fallback)
            self._engine = SFTPEngine(
                hostname=hostname, port=port, username=username, password=password,
                key_filename=key_filename, ssh_engine=ssh_engine, log_callback=log_callback
            )

    @property
    def is_connected(self) -> bool:
        return getattr(self._engine, "is_connected", False)

    def connect(self) -> bool:
        return self._engine.connect()

    def disconnect(self):
        self._engine.disconnect()

    def list_remote_dir(self, remote_path: str = ".") -> List[Dict[str, Any]]:
        return self._engine.list_remote_dir(remote_path)

    def get_current_dir(self) -> str:
        if hasattr(self._engine, "get_current_dir"):
            return self._engine.get_current_dir()
        return "."

    def upload_file(self, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        self._engine.upload_file(local_path, remote_path, progress_callback)

    def download_file(self, remote_path: str, local_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        self._engine.download_file(remote_path, local_path, progress_callback)

    def upload_directory(self, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        self._engine.upload_directory(local_path, remote_path, progress_callback)

    def download_directory(self, remote_path: str, local_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        self._engine.download_directory(remote_path, local_path, progress_callback)

    def create_remote_dir(self, remote_path: str):
        if hasattr(self._engine, "create_remote_dir"):
            self._engine.create_remote_dir(remote_path)
        else:
            raise NotImplementedError("Directory creation not supported on this protocol engine.")

    def remove_remote_file(self, remote_path: str):
        if hasattr(self._engine, "remove_remote_file"):
            self._engine.remove_remote_file(remote_path)
        else:
            raise NotImplementedError("File removal not supported on this protocol engine.")

    def remove_remote_dir(self, remote_path: str):
        if hasattr(self._engine, "remove_remote_dir"):
            self._engine.remove_remote_dir(remote_path)
        else:
            raise NotImplementedError("Directory removal not supported on this protocol engine.")

    def rename_remote(self, old_path: str, new_path: str):
        if hasattr(self._engine, "rename_remote"):
            self._engine.rename_remote(old_path, new_path)
        else:
            raise NotImplementedError("Rename operation not supported on this protocol engine.")

    def remote_exists(self, remote_path: str) -> bool:
        if hasattr(self._engine, "remote_exists"):
            return self._engine.remote_exists(remote_path)
        return False

