import os
import stat
import socket
import shutil
import subprocess
import datetime
import threading
import time
import re
import paramiko
from typing import List, Dict, Any, Optional, Callable
from pyremotempc.engine.ssh_engine import configure_security_options
from pyremotempc.engine.shell_file_engine import ShellFileEngine


class NativePTYSFTPEngine:


    """
    Native CLI Fallback SFTP Engine using Linux OpenSSH sftp & scp binaries (sshpass, sftp, scp).
    Executes real binary SFTP subsystem batch commands (sftp -b -).
    Parses strictly UNIX file permissions ('-', 'd', 'l'), filtering out MOTD / shell banners completely.
    """

    def __init__(self, hostname: str, port: int = 22, username: str = "", password: str = "",
                 key_filename: Optional[str] = None, log_callback: Optional[Callable[[str], None]] = None):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.log_callback = log_callback
        self.is_connected = False

    def log(self, msg: str):
        if self.log_callback:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.log_callback(f"[{ts}] [Native SFTP] {msg}\n")

    def connect(self) -> bool:
        """Verify remote host reachability via native SSH port test."""
        self.log(f"Testing TCP connection to {self.hostname}:{self.port}...")
        try:
            s = socket.create_connection((self.hostname, self.port), timeout=5)
            s.close()
            self.log("TCP connection successful. Testing native SSH command execution...")
        except Exception as e:
            self.is_connected = False
            self.log(f"TCP connection failed: {str(e)}")
            raise Exception(f"Native SFTP Host unreachable: {str(e)}")

        try:
            items = self.list_remote_dir(".")
            self.is_connected = True
            self.log("Native SFTP/SSH connection verified successfully.")
            return True
        except Exception as e:
            self.is_connected = False
            self.log(f"Native SFTP/SSH verification failed: {str(e)}")
            raise Exception(f"Native SFTP failed: {str(e)}")

    def get_current_dir(self) -> str:
        return "."

    def _get_legacy_options(self) -> List[str]:
        return [
            "-o", "KexAlgorithms=+diffie-hellman-group1-sha1,diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha1,diffie-hellman-group14-sha256",
            "-o", "HostKeyAlgorithms=+ssh-rsa,rsa-sha2-256,rsa-sha2-512,ssh-ed25519",
            "-o", "Ciphers=aes128-cbc,3des-cbc,aes192-cbc,aes256-cbc,aes128-ctr,aes192-ctr,aes256-ctr",
            "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa,rsa-sha2-256,rsa-sha2-512",
            "-o", "ConnectTimeout=10"
        ]

    def _build_cmd(self, tool: str) -> Tuple[List[str], Dict[str, str]]:
        env = os.environ.copy()
        cmd = []
        sshpass = shutil.which("sshpass")
        if sshpass and self.password:
            cmd.extend([sshpass, "-e"])
            env["SSHPASS"] = self.password
        cmd.append(tool)
        return cmd, env

    def list_remote_dir(self, remote_path: str = ".") -> List[Dict[str, Any]]:
        """Lists remote directory using real OpenSSH sftp binary batch execution."""
        target = f"{self.username}@{self.hostname}" if self.username else self.hostname

        self.log(f"Listing remote directory '{remote_path}' via ssh ls...")

        cmd, env = self._build_cmd("ssh")
        cmd.extend([
            "-F", "/dev/null",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null"
        ])
        
        if self.key_filename:
            cmd.extend(["-i", self.key_filename])

        cmd.extend(self._get_legacy_options())
        cmd.extend([
            "-p", str(self.port),
            target,
            f"ls -la \"{remote_path}\""
        ])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=env)
            lines = res.stdout.splitlines()
            items = []
            for line in lines:
                line_str = line.strip()
                if not line_str or line_str.startswith("total "):
                    continue

                tokens = line_str.split()
                if len(tokens) >= 8 and tokens[0][0] in ('-', 'd', 'l', 'c', 'b'):
                    perms = tokens[0]
                    is_dir = perms.startswith("d")

                    t_idx = -1
                    for idx in range(5, min(10, len(tokens))):
                        if re.match(r'^\d{1,2}:\d{2}$', tokens[idx]) or re.match(r'^\d{4}$', tokens[idx]):
                            t_idx = idx
                            break

                    if t_idx != -1 and t_idx + 1 < len(tokens):
                        name = " ".join(tokens[t_idx + 1:])
                    else:
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
            self.log(f"Listing completed: {len(items)} items found.")
            
            if res.returncode != 0:
                self.log(f"Native SFTP returned code {res.returncode}:\n{res.stderr}\n{res.stdout}")
                if len(items) == 0:
                    raise Exception(f"SFTP Error ({res.returncode}): {res.stderr.strip() or res.stdout.strip()}")
                
            if len(items) == 0 and (res.stdout or res.stderr):
                self.log(f"SFTP Output Raw:\n{res.stdout}\n{res.stderr}")
            return items
        except Exception as e:
            self.log(f"Native SFTP list error: {str(e)}")
            raise Exception(f"Native SFTP list error: {str(e)}")

    def upload_file(self, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Uploads file using native SCP with progress monitoring."""
        target = f"{self.username}@{self.hostname}:{remote_path}" if self.username else f"{self.hostname}:{remote_path}"

        self.log(f"Uploading '{local_path}' to '{remote_path}' via scp...")
        cmd, env = self._build_cmd("scp")
        cmd.extend([
            "-F", "/dev/null",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null"
        ])
        if self.key_filename:
            cmd.extend(["-i", self.key_filename])
        cmd.extend(self._get_legacy_options())
        cmd.extend([
            "-P", str(self.port),
            local_path,
            target
        ])

        # Remove existing remote target file so stat -c %s measures actual new file growth from 0 B
        try:
            self._run_ssh_cmd(f"rm -f \"{remote_path}\"")
        except Exception:
            pass

        local_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)

        while proc.poll() is None:
            if progress_callback and local_size > 0:
                try:
                    res = self._run_ssh_cmd(f"stat -c %s \"{remote_path}\"")
                    if res.returncode == 0 and res.stdout.strip().isdigit():
                        curr_size = int(res.stdout.strip())
                        progress_callback(curr_size, local_size)
                except Exception:
                    pass
            time.sleep(0.2)

        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            self.log(f"SCP Upload error: {stderr}")
            raise Exception(f"Native SCP Upload Error: {stderr}")
        if progress_callback and local_size > 0:
            progress_callback(local_size, local_size)
        self.log("Upload completed successfully.")

    def download_file(self, remote_path: str, local_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Downloads file using native SCP with progress monitoring."""
        source = f"{self.username}@{self.hostname}:{remote_path}" if self.username else f"{self.hostname}:{remote_path}"

        self.log(f"Downloading '{remote_path}' to '{local_path}' via scp...")
        cmd, env = self._build_cmd("scp")
        cmd.extend([
            "-F", "/dev/null",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null"
        ])
        if self.key_filename:
            cmd.extend(["-i", self.key_filename])
        cmd.extend(self._get_legacy_options())
        cmd.extend([
            "-P", str(self.port),
            source,
            local_path
        ])

        remote_size = 0
        try:
            res = self._run_ssh_cmd(f"stat -c %s \"{remote_path}\"")
            if res.returncode == 0 and res.stdout.strip().isdigit():
                remote_size = int(res.stdout.strip())
        except Exception:
            pass

        # Remove existing local target file so os.path.getsize measures actual new file growth from 0 B
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)

        while proc.poll() is None:
            if progress_callback and os.path.exists(local_path):
                try:
                    curr_size = os.path.getsize(local_path)
                    progress_callback(curr_size, remote_size if remote_size > 0 else curr_size)
                except Exception:
                    pass
            time.sleep(0.1)

        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            self.log(f"SCP Download error: {stderr}")
            raise Exception(f"Native SCP Download Error: {stderr}")
        if progress_callback and os.path.exists(local_path):
            final_size = os.path.getsize(local_path)
            progress_callback(final_size, remote_size if remote_size > 0 else final_size)
        self.log("Download completed successfully.")

    def upload_directory(self, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Uploads a directory recursively using native SCP."""
        target = f"{self.username}@{self.hostname}:{remote_path}" if self.username else f"{self.hostname}:{remote_path}"

        self.log(f"Uploading directory '{local_path}' to '{remote_path}' via scp -r...")
        cmd, env = self._build_cmd("scp")
        cmd.append("-r")
        cmd.extend([
            "-F", "/dev/null",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null"
        ])
        if self.key_filename:
            cmd.extend(["-i", self.key_filename])
        cmd.extend(self._get_legacy_options())
        cmd.extend([
            "-P", str(self.port),
            local_path,
            target
        ])

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        if res.returncode != 0:
            self.log(f"SCP Directory Upload error: {res.stderr}")
            raise Exception(f"Native SCP Directory Upload Error: {res.stderr}")
        self.log("Directory upload completed successfully.")

    def download_directory(self, remote_path: str, local_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Downloads a directory recursively using native SCP."""
        source = f"{self.username}@{self.hostname}:{remote_path}" if self.username else f"{self.hostname}:{remote_path}"

        self.log(f"Downloading directory '{remote_path}' to '{local_path}' via scp -r...")
        cmd, env = self._build_cmd("scp")
        cmd.append("-r")
        cmd.extend([
            "-F", "/dev/null",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null"
        ])
        if self.key_filename:
            cmd.extend(["-i", self.key_filename])
        cmd.extend(self._get_legacy_options())
        cmd.extend([
            "-P", str(self.port),
            source,
            local_path
        ])

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        if res.returncode != 0:
            self.log(f"SCP Directory Download error: {res.stderr}")
            raise Exception(f"Native SCP Directory Download Error: {res.stderr}")
    def _run_ssh_cmd(self, ssh_args: str) -> subprocess.CompletedProcess:
        target = f"{self.username}@{self.hostname}" if self.username else self.hostname
        cmd, env = self._build_cmd("ssh")
        cmd.extend([
            "-F", "/dev/null",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null"
        ])
        if self.key_filename:
            cmd.extend(["-i", self.key_filename])
        cmd.extend(self._get_legacy_options())
        cmd.extend([
            "-p", str(self.port),
            target,
            ssh_args
        ])
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=env)

    def create_remote_dir(self, remote_path: str):
        res = self._run_ssh_cmd(f"mkdir -p \"{remote_path}\"")
        if res.returncode != 0:
            raise Exception(f"Native SFTP mkdir failed: {res.stderr}")

    def remove_remote_file(self, remote_path: str):
        res = self._run_ssh_cmd(f"rm -f \"{remote_path}\"")
        if res.returncode != 0:
            raise Exception(f"Native SFTP remove_file failed: {res.stderr}")

    def remove_remote_dir(self, remote_path: str):
        res = self._run_ssh_cmd(f"rm -rf \"{remote_path}\"")
        if res.returncode != 0:
            raise Exception(f"Native SFTP remove_dir failed: {res.stderr}")

    def rename_remote(self, old_path: str, new_path: str):
        res = self._run_ssh_cmd(f"mv \"{old_path}\" \"{new_path}\"")
        if res.returncode != 0:
            raise Exception(f"Native SFTP rename failed: {res.stderr}")

    def remote_exists(self, remote_path: str) -> bool:
        res = self._run_ssh_cmd(f"test -e \"{remote_path}\"")
        return res.returncode == 0

    def disconnect(self):
        self.is_connected = False



class SFTPEngine:
    """
    Dedicated Universal SFTP Client Engine using Paramiko with Active Transport Reuse and Native OpenSSH SFTP Fallback.
    Provides diagnostic log output callback.
    """

    def __init__(self, hostname: str, port: int = 22, username: str = "", password: str = "",
                 key_filename: Optional[str] = None, ssh_engine: Optional[Any] = None,
                 log_callback: Optional[Callable[[str], None]] = None):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.ssh_engine = ssh_engine
        self.log_callback = log_callback

        self.transport: Optional[paramiko.Transport] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        self.shell_engine: Optional[ShellFileEngine] = None
        self.native_sftp: Optional[NativePTYSFTPEngine] = None
        self.is_connected = False
        self._lock = threading.RLock()


    def log(self, msg: str):
        if self.log_callback:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.log_callback(f"[{ts}] [SFTP Engine] {msg}\n")

    def _get_native_sftp(self) -> NativePTYSFTPEngine:
        if not self.native_sftp:
            self.native_sftp = NativePTYSFTPEngine(
                hostname=self.hostname, port=self.port, username=self.username, password=self.password,
                key_filename=self.key_filename, log_callback=self.log_callback
            )
        return self.native_sftp

    def connect(self) -> bool:
        """Connects to remote server and initializes SFTP subsystem using a dedicated socket connection."""
        self.log(f"Initiating SFTP Connection to {self.username}@{self.hostname}:{self.port}...")

        # 1. Prioritize establishing dedicated Paramiko Transport socket (prevents terminal contention/freeze)
        paramiko_err = None
        try:
            self.log("Establishing dedicated Paramiko Transport socket...")
            sock = socket.create_connection((self.hostname, self.port), timeout=10)
            self.transport = paramiko.Transport(sock)
            configure_security_options(self.transport)

            if self.key_filename and os.path.exists(self.key_filename):
                try:
                    pkey = paramiko.RSAKey.from_private_key_file(self.key_filename)
                    self.transport.connect(username=self.username, pkey=pkey)
                except Exception:
                    self.transport.connect(username=self.username, password=self.password)
            else:
                self.transport.connect(username=self.username, password=self.password)

            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
            self.is_connected = True
            self.log("Dedicated Paramiko SFTP session established successfully.")
            return True
        except Exception as e:
            paramiko_err = str(e)
            self.log(f"Dedicated Paramiko SFTP Connection Error: {paramiko_err}")

        # 2. Fallback: If dedicated socket fails and active Paramiko transport exists, attempt reuse
        if self.ssh_engine and getattr(self.ssh_engine, "transport", None):
            try:
                active_trans = self.ssh_engine.transport
                if active_trans and active_trans.is_active():
                    self.log("Falling back to active Paramiko SSH Transport from terminal session...")
                    self.sftp = paramiko.SFTPClient.from_transport(active_trans)
                    self.is_connected = True
                    self.log("SFTP subsystem opened successfully over active transport.")
                    return True
            except Exception as e:
                self.log(f"Transport reuse SFTP notice: {str(e)}")

        # 3. Fallback to Native OpenSSH SFTP / SCP Engine
        self.log("Switching seamlessly to Native OpenSSH SFTP / SCP Fallback...")
        self.disconnect()
        try:
            self.native_sftp = self._get_native_sftp()
            connected = self.native_sftp.connect()
            self.is_connected = connected
            return connected
        except Exception as native_err:
            self.is_connected = False
            self.log(f"Native SFTP Fallback failed: {str(native_err)}")
            raise Exception(f"SFTP failed. Paramiko: {paramiko_err} | Native: {str(native_err)}")

    def get_current_dir(self) -> str:
        if self.sftp:
            try:
                return self.sftp.normalize(".")
            except Exception:
                return "/"
        elif self.shell_engine:
            return self.shell_engine.get_current_dir()
        elif self.native_sftp:
            return self.native_sftp.get_current_dir()
        return "/"

    def list_remote_dir(self, remote_path: str = ".") -> List[Dict[str, Any]]:
        """Lists files and folders in specified remote directory."""
        with self._lock:
            self.log(f"Requesting remote directory listing for: '{remote_path}'")
            if self.sftp:
                try:
                    attr_list = self.sftp.listdir_attr(remote_path)
                    items = []
                    for attr in attr_list:
                        is_dir = stat.S_ISDIR(attr.st_mode)
                        items.append({
                            "name": attr.filename,
                            "size": attr.st_size if not is_dir else 0,
                            "is_dir": is_dir,
                            "permissions": stat.filemode(attr.st_mode),
                            "mtime": attr.st_mtime
                        })
                    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
                    self.log(f"Paramiko SFTP listing successful: {len(items)} items found.")
                    return items
                except Exception as e:
                    self.log(f"Paramiko listdir_attr error: {str(e)}")
                    raise e
            elif self.shell_engine:
                return self.shell_engine.list_remote_dir(remote_path)
            elif self.native_sftp:
                return self.native_sftp.list_remote_dir(remote_path)
            else:
                self.log("SFTP Error: Not connected.")
                raise Exception("SFTP not connected")

    def upload_file(self, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        if self.sftp:
            self.log(f"Uploading '{local_path}' to '{remote_path}' via Paramiko SFTP...")
            self.sftp.put(local_path, remote_path, callback=progress_callback)
            self.log("Paramiko SFTP upload complete.")
        elif self.shell_engine:
            self.log("Shell engine active. Falling back to native scp for upload...")
            self._get_native_sftp().upload_file(local_path, remote_path, progress_callback)
        elif self.native_sftp:
            self.native_sftp.upload_file(local_path, remote_path, progress_callback)
        else:
            raise Exception("SFTP not connected")

    def download_file(self, remote_path: str, local_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        if self.sftp:
            self.log(f"Downloading '{remote_path}' to '{local_path}' via Paramiko SFTP...")
            self.sftp.get(remote_path, local_path, callback=progress_callback)
            self.log("Paramiko SFTP download complete.")
        elif self.shell_engine:
            self.log("Shell engine active. Falling back to native scp for download...")
            self._get_native_sftp().download_file(remote_path, local_path, progress_callback)
        elif self.native_sftp:
            self.native_sftp.download_file(remote_path, local_path, progress_callback)
        else:
            raise Exception("SFTP not connected")

    def upload_directory(self, local_path: str, remote_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        if self.sftp:
            self.log(f"Uploading directory '{local_path}' to '{remote_path}' via Paramiko SFTP...")
            self._paramiko_upload_dir(local_path, remote_path)
            self.log("Paramiko SFTP directory upload complete.")
        elif self.shell_engine:
            self.log("Shell engine active. Falling back to native scp for directory upload...")
            self._get_native_sftp().upload_directory(local_path, remote_path, progress_callback)
        elif self.native_sftp:
            self.native_sftp.upload_directory(local_path, remote_path, progress_callback)
        else:
            raise Exception("SFTP not connected")

    def _paramiko_upload_dir(self, local_dir, remote_dir):
        try:
            self.sftp.mkdir(remote_dir)
        except IOError:
            pass # Ignore if it exists
            
        for item in os.listdir(local_dir):
            local_path = os.path.join(local_dir, item)
            item_remote_path = f"{remote_dir}/{item}"
            if os.path.isfile(local_path):
                self.sftp.put(local_path, item_remote_path)
            elif os.path.isdir(local_path):
                self._paramiko_upload_dir(local_path, item_remote_path)

    def download_directory(self, remote_path: str, local_path: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        if self.sftp:
            self.log(f"Downloading directory '{remote_path}' to '{local_path}' via Paramiko SFTP...")
            self._paramiko_download_dir(remote_path, local_path)
            self.log("Paramiko SFTP directory download complete.")
        elif self.shell_engine:
            self.log("Shell engine active. Falling back to native scp for directory download...")
            self._get_native_sftp().download_directory(remote_path, local_path, progress_callback)
        elif self.native_sftp:
            self.native_sftp.download_directory(remote_path, local_path, progress_callback)
        else:
            raise Exception("SFTP not connected")

    def _paramiko_download_dir(self, remote_dir, local_dir):
        os.makedirs(local_dir, exist_ok=True)
        for attr in self.sftp.listdir_attr(remote_dir):
            item_remote_path = f"{remote_dir}/{attr.filename}"
            local_path = os.path.join(local_dir, attr.filename)
            if stat.S_ISDIR(attr.st_mode):
                self._paramiko_download_dir(item_remote_path, local_path)
            else:
                self.sftp.get(item_remote_path, local_path)

    def create_remote_dir(self, remote_path: str):
        with self._lock:
            if self.sftp:
                dirs = []
                dir_path = remote_path
                while dir_path and dir_path not in ("/", ".", ""):
                    dirs.append(dir_path)
                    dir_path = os.path.dirname(dir_path)
                for d in reversed(dirs):
                    try:
                        self.sftp.mkdir(d)
                    except Exception:
                        pass
            elif self.shell_engine:
                self.shell_engine.execute_command(f"mkdir -p \"{remote_path}\"")
            elif self.native_sftp:
                self.native_sftp.create_remote_dir(remote_path)
            else:
                raise Exception("SFTP not connected")

    def remove_remote_file(self, remote_path: str):
        if self.sftp:
            self.sftp.remove(remote_path)
        elif self.shell_engine:
            self.shell_engine.execute_command(f"rm -f \"{remote_path}\"")
        elif self.native_sftp:
            self.native_sftp.remove_remote_file(remote_path)
        else:
            raise Exception("SFTP not connected")

    def remove_remote_dir(self, remote_path: str):
        if self.sftp:
            self._paramiko_remove_dir(remote_path)
        elif self.shell_engine:
            self.shell_engine.execute_command(f"rm -rf \"{remote_path}\"")
        elif self.native_sftp:
            self.native_sftp.remove_remote_dir(remote_path)
        else:
            raise Exception("SFTP not connected")

    def _paramiko_remove_dir(self, remote_dir: str):
        for attr in self.sftp.listdir_attr(remote_dir):
            item_path = f"{remote_dir}/{attr.filename}"
            if stat.S_ISDIR(attr.st_mode):
                self._paramiko_remove_dir(item_path)
            else:
                self.sftp.remove(item_path)
        self.sftp.rmdir(remote_dir)

    def rename_remote(self, old_path: str, new_path: str):
        if self.sftp:
            self.sftp.rename(old_path, new_path)
        elif self.shell_engine:
            self.shell_engine.execute_command(f"mv \"{old_path}\" \"{new_path}\"")
        elif self.native_sftp:
            self.native_sftp.rename_remote(old_path, new_path)
        else:
            raise Exception("SFTP not connected")

    def remote_exists(self, remote_path: str) -> bool:
        if self.sftp:
            try:
                self.sftp.stat(remote_path)
                return True
            except Exception:
                return False
        elif self.shell_engine:
            res = self.shell_engine.execute_command(f"test -e \"{remote_path}\" && echo OK")
            return "OK" in res
        elif self.native_sftp:
            return self.native_sftp.remote_exists(remote_path)
        return False


    def disconnect(self):
        if self.sftp:
            try:
                self.sftp.close()
            except Exception:
                pass
            self.sftp = None

        if self.shell_engine:
            self.shell_engine.disconnect()
            self.shell_engine = None

        if self.transport:
            try:
                self.transport.close()
            except Exception:
                pass
            self.transport = None

        if self.native_sftp:
            self.native_sftp.disconnect()
            self.native_sftp = None

        self.is_connected = False
