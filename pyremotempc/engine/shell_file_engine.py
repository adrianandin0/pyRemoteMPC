import re
from typing import List, Dict, Any, Optional, Callable
import paramiko

class ShellFileEngine:
    """
    Fallback File Engine that uses standard shell commands (ls -la) over a Paramiko SSH channel.
    Used when the server does not support the SFTP subsystem (e.g. Cisco routers, restricted Linux).
    """

    def __init__(self, transport: paramiko.Transport, log_callback: Optional[Callable[[str], None]] = None):
        self.transport = transport
        self.log_callback = log_callback
        self.is_connected = True

    def log(self, msg: str):
        if self.log_callback:
            self.log_callback(f"[ShellFileEngine] {msg}\n")

    def get_current_dir(self) -> str:
        try:
            chan = self.transport.open_session()
            chan.exec_command("pwd")
            stdout = chan.makefile("r", -1)
            pwd = stdout.read().decode("utf-8").strip()
            chan.close()
            return pwd if pwd else "/"
        except Exception:
            return "/"

    def list_remote_dir(self, remote_path: str = ".") -> List[Dict[str, Any]]:
        self.log(f"Listing directory '{remote_path}' via shell 'ls -la'...")
        try:
            chan = self.transport.open_session()
            # Use ls -la to get detailed listing
            chan.exec_command(f"ls -la \"{remote_path}\"")
            stdout = chan.makefile("r", -1)
            stderr = chan.makefile_stderr("r", -1)
            
            out = stdout.read().decode("utf-8", errors="ignore")
            err = stderr.read().decode("utf-8", errors="ignore")
            
            chan.close()
            
            if err and not out:
                raise Exception(err.strip())
                
            items = []
            for line in out.splitlines():
                line = line.strip()
                if not line or line.startswith("total "):
                    continue
                    
                tokens = line.split()
                if len(tokens) >= 8 and tokens[0][0] in ('-', 'd', 'l', 'c', 'b'):
                    perms = tokens[0]
                    is_dir = perms.startswith("d")

                    name_idx = 8 if len(tokens) >= 9 else 7
                    name = " ".join(tokens[name_idx:])
                    if " -> " in name:
                        name = name.split(" -> ")[0].strip()

                    if name in (".", "..") or not name:
                        continue

                    try:
                        size = int(tokens[4])
                    except Exception:
                        size = 0

                    items.append({
                        "name": name,
                        "size": size if not is_dir else 0,
                        "is_dir": is_dir,
                        "permissions": perms,
                        "mtime": 0
                    })
            
            items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            self.log(f"Shell listing successful: {len(items)} items.")
            return items
        except Exception as e:
            self.log(f"Shell list error: {str(e)}")
            raise e

    def upload_file(self, local_path: str, remote_path: str, progress_callback=None):
        raise Exception("Upload not supported without SFTP subsystem.")

    def download_file(self, remote_path: str, local_path: str, progress_callback=None):
        raise Exception("Download not supported without SFTP subsystem.")
        
    def disconnect(self):
        self.is_connected = False
