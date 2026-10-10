import os
import stat
import ftplib
from typing import List, Dict, Any, Optional, Callable
from pyremotempc.engine.file_transfer import BaseFileTransferEngine


class FTPEngine(BaseFileTransferEngine):
    """
    FTP / FTPS File Transfer Engine using Python standard library ftplib.
    Provides directory listing, file upload/download with progress callbacks,
    directory creation, deletion, and renaming.
    """

    def __init__(self, hostname: str, port: int = 21, username: str = "anonymous", password: str = "",
                 use_ssl: bool = False, log_callback: Optional[Callable[[str], None]] = None):
        self.hostname = hostname
        self.port = port if port else 21
        self.username = username or "anonymous"
        self.password = password or ""
        self.use_ssl = use_ssl
        self.log_callback = log_callback
        self._ftp: Optional[ftplib.FTP] = None
        self._connected = False

    def _log(self, message: str):
        if self.log_callback:
            self.log_callback(f"[FTP] {message}\n")

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ftp is not None

    def connect(self) -> bool:
        try:
            self._log(f"Connecting to FTP {self.hostname}:{self.port} as '{self.username}'...")
            if self.use_ssl:
                self._ftp = ftplib.FTP_TLS()
            else:
                self._ftp = ftplib.FTP()

            self._ftp.connect(self.hostname, self.port, timeout=15)
            self._ftp.login(self.username, self.password)

            if self.use_ssl and isinstance(self._ftp, ftplib.FTP_TLS):
                self._ftp.prot_p()

            self._connected = True
            self._log("FTP Connection established successfully.")
            return True
        except Exception as e:
            self._connected = False
            self._ftp = None
            self._log(f"FTP Connection Error: {e}")
            return False

    def disconnect(self):
        if self._ftp:
            try:
                self._ftp.quit()
            except Exception:
                try:
                    self._ftp.close()
                except Exception:
                    pass
        self._ftp = None
        self._connected = False
        self._log("FTP Session disconnected.")

    def get_current_dir(self) -> str:
        if not self._ftp:
            return "."
        try:
            return self._ftp.pwd()
        except Exception:
            return "."

    def list_remote_dir(self, remote_path: str = ".") -> List[Dict[str, Any]]:
        if not self._ftp:
            raise RuntimeError("FTP server not connected.")

        target_path = remote_path if remote_path else "."
        items = []

        # Attempt machine-readable MLSD first
        try:
            for entry in self._ftp.mlsd(target_path):
                name, facts = entry
                if name in (".", ".."):
                    continue
                entry_type = facts.get("type", "file")
                is_dir = entry_type in ("dir", "cdir", "pdir")
                size = int(facts.get("size", 0)) if not is_dir else 0
                perm_str = facts.get("perm", "")
                items.append({
                    "filename": name,
                    "is_dir": is_dir,
                    "st_size": size,
                    "st_mode": stat.S_IFDIR if is_dir else stat.S_IFREG,
                    "permissions": perm_str if perm_str else ("drwxr-xr-x" if is_dir else "-rw-r--r--")
                })
            return items
        except Exception:
            pass

        # Fallback to RETRLINES LIST output parsing
        lines = []
        try:
            self._ftp.retrlines(f"LIST {target_path}", lines.append)
        except Exception as e:
            self._log(f"Error listing directory '{target_path}': {e}")
            return items

        for line in lines:
            parts = line.split(maxsplit=8)
            if len(parts) < 9:
                continue
            perms = parts[0]
            name = parts[8]
            if name in (".", ".."):
                continue
            is_dir = perms.startswith("d")
            try:
                size = int(parts[4])
            except ValueError:
                size = 0
            items.append({
                "filename": name,
                "is_dir": is_dir,
                "st_size": size,
                "st_mode": stat.S_IFDIR if is_dir else stat.S_IFREG,
                "permissions": perms
            })

        return items

    def upload_file(self, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        if not self._ftp:
            raise RuntimeError("FTP server not connected.")

        file_size = os.path.getsize(local_path)
        transferred = 0

        with open(local_path, "rb") as fp:
            def callback(chunk):
                nonlocal transferred
                transferred += len(chunk)
                if progress_callback:
                    progress_callback(transferred, file_size)

            self._log(f"Uploading '{local_path}' -> '{remote_path}' ({file_size} bytes)")
            self._ftp.storbinary(f"STOR {remote_path}", fp, blocksize=8192, callback=callback)

    def download_file(self, remote_path: str, local_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        if not self._ftp:
            raise RuntimeError("FTP server not connected.")

        try:
            file_size = self._ftp.size(remote_path) or 0
        except Exception:
            file_size = 0

        transferred = 0

        with open(local_path, "wb") as fp:
            def callback(data):
                nonlocal transferred
                fp.write(data)
                transferred += len(data)
                if progress_callback and file_size > 0:
                    progress_callback(transferred, file_size)

            self._log(f"Downloading '{remote_path}' -> '{local_path}'")
            self._ftp.retrbinary(f"RETR {remote_path}", callback, blocksize=8192)

    def upload_directory(self, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        if not self._ftp:
            raise RuntimeError("FTP server not connected.")

        try:
            self._ftp.mkd(remote_path)
        except Exception:
            pass

        for root, dirs, files in os.walk(local_path):
            rel_root = os.path.relpath(root, local_path)
            target_remote_dir = os.path.normpath(os.path.join(remote_path, rel_root)).replace("\\", "/")

            try:
                self._ftp.mkd(target_remote_dir)
            except Exception:
                pass

            for file_name in files:
                l_file = os.path.join(root, file_name)
                r_file = os.path.join(target_remote_dir, file_name).replace("\\", "/")
                self.upload_file(l_file, r_file, progress_callback)

    def download_directory(self, remote_path: str, local_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        if not self._ftp:
            raise RuntimeError("FTP server not connected.")

        os.makedirs(local_path, exist_ok=True)
        items = self.list_remote_dir(remote_path)

        for item in items:
            name = item["filename"]
            r_item = f"{remote_path}/{name}".replace("//", "/")
            l_item = os.path.join(local_path, name)

            if item["is_dir"]:
                self.download_directory(r_item, l_item, progress_callback)
            else:
                self.download_file(r_item, l_item, progress_callback)

    def create_remote_dir(self, remote_path: str):
        if not self._ftp:
            raise RuntimeError("FTP server not connected.")
        self._log(f"Creating remote directory '{remote_path}'")
        self._ftp.mkd(remote_path)

    def remove_remote_file(self, remote_path: str):
        if not self._ftp:
            raise RuntimeError("FTP server not connected.")
        self._log(f"Deleting remote file '{remote_path}'")
        self._ftp.delete(remote_path)

    def remove_remote_dir(self, remote_path: str):
        if not self._ftp:
            raise RuntimeError("FTP server not connected.")
        self._log(f"Removing remote directory '{remote_path}'")
        self._ftp.rmd(remote_path)

    def rename_remote(self, old_path: str, new_path: str):
        if not self._ftp:
            raise RuntimeError("FTP server not connected.")
        self._log(f"Renaming '{old_path}' -> '{new_path}'")
        self._ftp.rename(old_path, new_path)
