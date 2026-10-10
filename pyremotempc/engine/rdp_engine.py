import os
import shutil
import subprocess
import threading
import time
from typing import List, Optional, Callable, Tuple
from pyremotempc.engine.base_engine import BaseProtocolEngine


class RDPEngine(BaseProtocolEngine):
    """
    Universal RDP Engine using FreeRDP (xfreerdp / freerdp / rdesktop / remmina).
    Captures process output in real-time and provides clear diagnostic logging.
    Inherits from BaseProtocolEngine and enforces secure credential passing via anonymous kernel pipes (/args-from:fd).
    Includes automated OpenSSL legacy configuration and security fallback for Windows Server 2008 R2, 2012, and modern systems.
    """

    _supports_args_from_cache: Optional[bool] = None

    @classmethod
    def get_rdp_openssl_conf(cls) -> Optional[str]:
        """
        Creates/returns the path to an openssl.cnf that enables legacy ciphers,
        TLS 1.0+, and SHA-1 signatures for RDP server compatibility on modern Linux distros (Fedora 40+, Ubuntu 24+).
        """
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        candidate_dirs = []
        if runtime_dir and os.path.isdir(runtime_dir):
            candidate_dirs.append(os.path.join(runtime_dir, "pyremotempc"))
        candidate_dirs.append(os.path.expanduser("~/.config/pyremotempc"))

        content = """# pyRemoteMPC FreeRDP compatibility OpenSSL configuration
openssl_conf = openssl_init

[openssl_init]
providers = provider_sect
ssl_conf = ssl_sect
alg_section = evp_properties

[provider_sect]
default = default_sect
legacy = legacy_sect

[default_sect]
activate = 1

[legacy_sect]
activate = 1

[evp_properties]
rh-allow-sha1-signatures = yes

[ssl_sect]
system_default = system_default_sect

[system_default_sect]
MinProtocol = TLSv1.0
CipherString = ALL:@SECLEVEL=0
"""
        for config_dir in candidate_dirs:
            try:
                os.makedirs(config_dir, mode=0o700, exist_ok=True)
                cnf_path = os.path.join(config_dir, "openssl_rdp.cnf")
                if not os.path.exists(cnf_path):
                    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                    fd = os.open(cnf_path, flags, 0o600)
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(content)
                return cnf_path
            except Exception:
                continue
        return None

    @classmethod
    def supports_args_from(cls, exe_path: str) -> bool:
        if cls._supports_args_from_cache is None:
            try:
                res = subprocess.run([exe_path, "/help"], capture_output=True, text=True, timeout=2)
                cls._supports_args_from_cache = "/args-from" in res.stdout or "/args-from" in res.stderr
            except Exception:
                cls._supports_args_from_cache = False
        return cls._supports_args_from_cache

    @staticmethod
    def get_rdp_client_info() -> Tuple[str, str]:
        """Finds available RDP client binary and type."""
        for binary in ["xfreerdp3", "xfreerdp", "freerdp", "wlfreerdp", "sdl-freerdp"]:
            path = shutil.which(binary)
            if path:
                return path, "freerdp"
        if shutil.which("rdesktop"):
            return shutil.which("rdesktop"), "rdesktop"
        if shutil.which("remmina"):
            return shutil.which("remmina"), "remmina"
        return "", "none"

    def __init__(self, hostname: str, port: int = 3389, username: str = "", password: str = "",
                 domain: str = "", rdp_security: str = "Auto", rdp_cert_ignore: bool = True,
                 rdp_cert_path: str = "", redirect_drives: bool = True,
                 redirect_clipboard: bool = True, redirect_sound: bool = True,
                 shared_folder: str = "", colors: str = ""):
        super().__init__(hostname, port, username, password)
        self.domain = domain
        self.rdp_security = rdp_security
        self.rdp_cert_ignore = rdp_cert_ignore
        self.rdp_cert_path = rdp_cert_path
        self.redirect_drives = redirect_drives
        self.redirect_clipboard = redirect_clipboard
        self.redirect_sound = redirect_sound
        self.shared_folder = shared_folder
        self.colors = colors

        self.process: Optional[subprocess.Popen] = None
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.width = 1280
        self.height = 720
        self._current_win_id: Optional[int] = None
        self._has_retried_sec = False
        self._should_fallback_to: Optional[str] = None
        self._effective_sec: str = "auto"

    def build_args(self, win_id: Optional[int] = None, width: int = 1280, height: int = 720,
                   force_sec: Optional[str] = None,
                   force_tls_enforce: Optional[str] = None) -> Tuple[str, str, List[str]]:
        """
        Builds RDP command arguments.
        Returns: (exe_path, client_type, full_args_list)
        """
        exe_path, client_type = self.get_rdp_client_info()
        if not exe_path:
            raise FileNotFoundError("No RDP client found. Please install xfreerdp, freerdp, or rdesktop.")

        if client_type == "freerdp":
            args = [
                f"/v:{self.hostname}:{self.port}",
                "/client-hostname:pyRemoteMPC"
            ]
            if self.username:
                args.append(f"/u:{self.username}")
            if self.password:
                args.append(f"/p:{self.password}")
            if self.domain:
                args.append(f"/d:{self.domain}")

            if win_id is not None:
                # /parent-window is X11-only in FreeRDP
                args.append(f"/parent-window:{win_id}")
                args.append(f"/size:{width}x{height}")
            else:
                args.append(f"/size:{width}x{height}")
                args.append("/workarea")
                args.append("+dynamic-resolution")

            if self.colors:
                bpp = None
                if "16" in str(self.colors):
                    bpp = "16"
                elif "24" in str(self.colors):
                    bpp = "24"
                elif "32" in str(self.colors):
                    bpp = "32"
                elif "8" in str(self.colors):
                    bpp = "8"
                if bpp:
                    args.append(f"/bpp:{bpp}")

            sec = (force_sec or self.rdp_security).lower()
            if sec in ("nla", "rdp", "tls"):
                args.append(f"/sec:{sec}")

            if self.redirect_clipboard:
                args.append("+clipboard")
            else:
                args.append("-clipboard")

            if self.redirect_sound:
                args.append("/sound")
            else:
                args.append("-sound")

            if self.redirect_drives:
                folder_to_share = self.shared_folder
                if not folder_to_share or not os.path.exists(folder_to_share):
                    folder_to_share = os.path.expanduser("~/RDP_Shared")
                try:
                    os.makedirs(folder_to_share, exist_ok=True)
                except Exception:
                    pass
                args.append(f"/drive:Shared,{folder_to_share}")

            if self.rdp_cert_path and os.path.exists(self.rdp_cert_path):
                args.append(f"/cert:file:{self.rdp_cert_path}")
            elif self.rdp_cert_ignore:
                args.append("/cert:ignore")

            # Lower TLS security level for older servers when TLS/NLA is active
            if sec != "rdp":
                args.append("/tls:seclevel:0")

            if force_tls_enforce:
                args.append(f"/tls:enforce:{force_tls_enforce}")

            return exe_path, client_type, args

        elif client_type == "rdesktop":
            args = [f"{self.hostname}:{self.port}", "-g", f"{width}x{height}"]
            if self.username:
                args.extend(["-u", self.username])
            if self.password:
                args.extend(["-p", self.password])
            if self.domain:
                args.extend(["-d", self.domain])
            return exe_path, client_type, args

        else:
            return exe_path or "remmina", client_type, ["-c", f"rdp://{self.hostname}:{self.port}"]

    def build_cmd(self, win_id: Optional[int] = None, width: int = 1280, height: int = 720) -> List[str]:
        """Backward-compatible command builder."""
        exe_path, client_type, args = self.build_args(win_id=win_id, width=width, height=height)
        return [exe_path] + args

    def connect(self, on_output: Optional[Callable[[str], None]] = None,
                term_type: str = "xterm", width: int = 1280, height: int = 720,
                win_id: Optional[int] = None) -> bool:
        """BaseProtocolEngine interface implementation."""
        return self.start_session(on_output=on_output, win_id=win_id, width=width, height=height)

    def disconnect(self):
        """BaseProtocolEngine interface implementation."""
        self.stop_session()

    def send_input(self, data: str):
        """BaseProtocolEngine interface implementation."""
        pass

    def start_session(self, on_output: Optional[Callable[[str], None]] = None,
                      win_id: Optional[int] = None, width: int = 1280, height: int = 720,
                      force_sec: Optional[str] = None,
                      force_tls_enforce: Optional[str] = None) -> bool:
        """Launches RDP client process securely and streams stdout/stderr to callback."""
        self.output_callback = on_output
        self.width = width
        self.height = height
        self._current_win_id = win_id
        self._effective_sec = (force_sec or self.rdp_security).lower()
        if force_sec is None and force_tls_enforce is None:
            self._has_retried_sec = False
        self._should_fallback_to = None

        try:
            exe_path, client_type, full_args = self.build_args(
                win_id=win_id, width=width, height=height,
                force_sec=force_sec, force_tls_enforce=force_tls_enforce
            )

            # Display safe command in log (credentials masked)
            if self.output_callback:
                safe_cmd = [exe_path]
                skip_next = False
                for token in full_args:
                    if skip_next:
                        skip_next = False
                        continue
                    if token.startswith("/p:"):
                        safe_cmd.append("/p:********")
                    elif token in ("-p", "/p"):
                        safe_cmd.append(token)
                        safe_cmd.append("********")
                        skip_next = True
                    elif token.startswith("-p"):
                        safe_cmd.append("-p********")
                    else:
                        safe_cmd.append(token)
                self.output_callback(f"[RDP Command]: {' '.join(safe_cmd)}\nLaunching RDP session...\n")

            env = os.environ.copy()
            # Force xfreerdp to use X11 so XEmbed works
            if "WAYLAND_DISPLAY" in env:
                del env["WAYLAND_DISPLAY"]

            # Enable legacy ciphers, TLS 1.0+, and SHA-1 signatures for RDP server compatibility
            cnf_path = self.get_rdp_openssl_conf()
            if cnf_path and os.path.exists(cnf_path):
                env["OPENSSL_CONF"] = cnf_path
            env["OPENSSL_ENABLE_SHA1_SIGNATURES"] = "1"

            if client_type == "freerdp" and self.supports_args_from(exe_path):
                # Securely pass credentials and all arguments through an anonymous kernel pipe
                # FreeRDP reads the arguments directly from the file descriptor (/args-from:fd:<n>)
                # Neither the password nor any connection args appear in ps aux / /proc cmdline.
                r_fd, w_fd = os.pipe()
                try:
                    payload = "\n".join(full_args).encode("utf-8")
                    os.write(w_fd, payload)
                finally:
                    os.close(w_fd)

                try:
                    cmd = [exe_path, f"/args-from:fd:{r_fd}"]
                    self.process = subprocess.Popen(
                        cmd,
                        pass_fds=(r_fd,),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        env=env
                    )
                finally:
                    os.close(r_fd)
            else:
                cmd = [exe_path] + full_args
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env
                )

            self.is_connected = True
            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True
        except Exception as e:
            if self.output_callback:
                self.output_callback(f"[RDP Launch Error]: {str(e)}\n")
            self.is_connected = False
            return False

    def _read_loop(self):
        if not self.process or not self.process.stdout:
            return

        while not self._stop_event.is_set() and self.process.poll() is None:
            line = self.process.stdout.readline()
            if line:
                if self.output_callback:
                    self.output_callback(line)

                # Automatic error detection and smart fallback handling:
                # 1. Server explicitly demands NLA (HYBRID):
                if ("ERRCONNECT_HYBRID_REQUIRED_BY_SERVER" in line or
                    "HYBRID_REQUIRED_BY_SERVER" in line):
                    if self._effective_sec != "nla" and not self._has_retried_sec:
                        self._should_fallback_to = "nla"

                # 2. Connection reset when plain RDP encryption was attempted on a server enforcing NLA:
                elif ("ERRCONNECT_CONNECT_TRANSPORT_FAILED" in line or
                      "conexión reinicializada" in line.lower() or
                      "connection reset" in line.lower() or
                      "transport failed" in line.lower()) and self._effective_sec == "rdp":
                    if not self._has_retried_sec:
                        self._should_fallback_to = "nla"

                # 3. Server failed TLS handshake (e.g. NLA/TLS disabled on server, requires plain RDP):
                elif ("ERRCONNECT_TLS_CONNECT_FAILED" in line or
                      "freerdp_tls_handshake]: BIO_do_handshake failed" in line):
                    if self._effective_sec != "rdp" and not self._has_retried_sec:
                        self._should_fallback_to = "rdp"
            else:
                time.sleep(0.05)

        ret = self.process.poll() if self.process else None
        if self.output_callback and not self._should_fallback_to:
            self.output_callback(f"\n[RDP Process Exited with Return Code: {ret}]\n")

        # Execute automatic fallback if server rejected negotiation
        if self._should_fallback_to and not self._stop_event.is_set():
            target_sec = self._should_fallback_to
            self._should_fallback_to = None
            self._has_retried_sec = True
            if self.output_callback:
                self.output_callback(f"\n[RDP Fallback]: Server required security adjustment. Retrying with /sec:{target_sec}...\n")
            threading.Thread(
                target=self.start_session,
                kwargs={
                    "on_output": self.output_callback,
                    "win_id": self._current_win_id,
                    "width": self.width,
                    "height": self.height,
                    "force_sec": target_sec
                },
                daemon=True
            ).start()

    def stop_session(self):
        self._stop_event.set()
        self._should_fallback_to = None
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None

    def stop(self):
        """Alias for stop_session for engine interface consistency."""
        self.stop_session()
