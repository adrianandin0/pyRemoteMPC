import hashlib
import os
import pty
import select
import shutil
import socket
import subprocess
import threading
import time
from typing import Callable, Optional, Tuple
import paramiko
from paramiko.kex_group14 import KexGroup14SHA256
from paramiko.kex_gex import KexGexSHA256
from paramiko.rsakey import RSAKey
from pyremotempc.engine.ssh1_engine import PurePythonSSH1Engine
from pyremotempc.engine.base_engine import BaseProtocolEngine


# Custom SHA1 Key Exchange Classes for Legacy SSH Peer Compatibility
class KexGroup1SHA1(KexGroup14SHA256):
    P = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF
    G = 2
    name = "diffie-hellman-group1-sha1"
    hash_algo = hashlib.sha1

    def _generate_x(self):
        from paramiko import util
        q = (self.P - 1) // 2
        while True:
            x_bytes = os.urandom(16)
            x = util.inflate_long(x_bytes, 1)
            if 1 < x < q:
                break
        self.x = x


class KexGroup14SHA1(KexGroup14SHA256):
    name = "diffie-hellman-group14-sha1"
    hash_algo = hashlib.sha1


class KexGexSHA1(KexGexSHA256):
    name = "diffie-hellman-group-exchange-sha1"
    hash_algo = hashlib.sha1


LEGACY_KEX = (
    'curve25519-sha256',
    'curve25519-sha256@libssh.org',
    'ecdh-sha2-nistp256',
    'ecdh-sha2-nistp384',
    'ecdh-sha2-nistp521',
    'diffie-hellman-group14-sha256',
    'diffie-hellman-group-exchange-sha256',
    'diffie-hellman-group14-sha1',
    'diffie-hellman-group-exchange-sha1',
    'diffie-hellman-group1-sha1',
)

import logging

# Suppress paramiko internal transport thread traceback logging to CLI
logging.getLogger("paramiko.transport").setLevel(logging.CRITICAL)

# Preferred key algorithms order (supporting legacy ssh-rsa host key signatures)
LEGACY_KEYS = (
    'ssh-ed25519',
    'ecdsa-sha2-nistp256',
    'ecdsa-sha2-nistp384',
    'ecdsa-sha2-nistp521',
    'ssh-rsa',
    'rsa-sha2-512',
    'rsa-sha2-256',
)

LEGACY_CIPHERS = (
    'aes128-ctr',
    'aes192-ctr',
    'aes256-ctr',
    'aes128-gcm@openssh.com',
    'aes256-gcm@openssh.com',
    'aes128-cbc',
    'aes192-cbc',
    'aes256-cbc',
    '3des-cbc',
    'blowfish-cbc',
    'cast128-cbc',
)

LEGACY_MACS = (
    'hmac-sha2-256',
    'hmac-sha2-512',
    'hmac-sha1',
    'hmac-md5',
    'hmac-sha1-96',
    'hmac-md5-96',
)

# Register custom key exchange algorithms and ssh-rsa key handler
paramiko.Transport._kex_info["diffie-hellman-group1-sha1"] = KexGroup1SHA1
paramiko.Transport._kex_info["diffie-hellman-group14-sha1"] = KexGroup14SHA1
paramiko.Transport._kex_info["diffie-hellman-group-exchange-sha1"] = KexGexSHA1
paramiko.Transport._key_info["ssh-rsa"] = RSAKey

paramiko.Transport._preferred_kex = LEGACY_KEX
paramiko.Transport._preferred_keys = LEGACY_KEYS
paramiko.Transport._preferred_pubkeys = LEGACY_KEYS
paramiko.Transport._preferred_ciphers = LEGACY_CIPHERS
paramiko.Transport._preferred_macs = LEGACY_MACS


def configure_security_options(transport: paramiko.Transport):
    """Configures Paramiko Transport SecurityOptions using instance API."""
    try:
        opts = transport.get_security_options()

        valid_kex = [k for k in opts.kex if k in paramiko.Transport._kex_info]
        for k in LEGACY_KEX:
            if k in paramiko.Transport._kex_info and k not in valid_kex:
                valid_kex.append(k)
        opts.kex = tuple(valid_kex)

        valid_keys = [k for k in opts.key_types if k in paramiko.Transport._key_info]
        for k in LEGACY_KEYS:
            if k in paramiko.Transport._key_info and k not in valid_keys:
                valid_keys.append(k)
        opts.key_types = tuple(valid_keys)

        valid_ciphers = [c for c in opts.ciphers if c in paramiko.Transport._cipher_info]
        for c in LEGACY_CIPHERS:
            if c in paramiko.Transport._cipher_info and c not in valid_ciphers:
                valid_ciphers.append(c)
        opts.ciphers = tuple(valid_ciphers)

        valid_macs = [m for m in opts.digests if m in paramiko.Transport._mac_info]
        for m in LEGACY_MACS:
            if m in paramiko.Transport._mac_info and m not in valid_macs:
                valid_macs.append(m)
        opts.digests = tuple(valid_macs)
    except Exception as e:
        print(f"configure_security_options notice: {e}")


def load_encrypted_private_key(key_filename: str, passphrase: Optional[str] = None) -> Optional[paramiko.PKey]:
    """
    Attempts to load an SSH private key file (Ed25519, RSA, ECDSA, DSA, PuTTY .ppk) using Paramiko.
    Handles passphrase-protected keys cleanly.
    """
    if not key_filename or not os.path.exists(key_filename):
        return None

    # Check for PuTTY .ppk file format header
    try:
        with open(key_filename, 'r', encoding='latin-1', errors='ignore') as f:
            header = f.read(100)
            if "PuTTY-User-Key-File-" in header:
                return paramiko.PKey.from_private_key_file(key_filename, password=passphrase)
    except paramiko.PasswordRequiredException:
        raise
    except Exception:
        pass

    key_classes = [
        paramiko.Ed25519Key,
        paramiko.RSAKey,
        paramiko.ECDSAKey,
        paramiko.DSSKey
    ]

    last_error = None
    for k_cls in key_classes:
        try:
            return k_cls.from_private_key_file(key_filename, password=passphrase)
        except paramiko.PasswordRequiredException:
            raise
        except Exception as e:
            last_error = e

    if last_error:
        raise last_error
    return None


class NativePTYSSHEngine(BaseProtocolEngine):
    """
    Fallback SSH Engine using Linux native PTY process (ssh / sshpass).
    Supports SSH1, SSH2, and legacy devices with valid OpenSSH legacy flags.
    """

    def __init__(self, hostname: str, port: int = 22, username: str = "", password: str = "",
                 key_filename: Optional[str] = None, key_passphrase: Optional[str] = None, protocol: str = "SSH2",
                 agent_forwarding: bool = False, auto_reconnect: bool = False):
        super().__init__(hostname, port, username, password)
        self.key_filename = key_filename
        self.key_passphrase = key_passphrase
        self.protocol = protocol.upper()
        self.agent_forwarding = agent_forwarding
        self.auto_reconnect = auto_reconnect

        self.master_fd = None
        self.slave_fd = None
        self.process: Optional[subprocess.Popen] = None
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def connect(self, on_output: Callable[[str], None], on_close: Optional[Callable[[], None]] = None, term_type: str = "xterm", width: int = 80, height: int = 24) -> bool:
        self.output_callback = on_output
        self.close_callback = on_close

        sshpass = shutil.which("sshpass")
        cmd = []
        env = os.environ.copy()
        env["TERM"] = term_type
        if sshpass and self.password:
            cmd.extend([sshpass, "-e"])
            env["SSHPASS"] = self.password

        known_hosts_file = os.path.expanduser("~/.ssh/known_hosts")
        try:
            os.makedirs(os.path.dirname(known_hosts_file), mode=0o700, exist_ok=True)
        except Exception:
            pass

        cmd.append("ssh")
        cmd.extend([
            "-tt",
            "-F", "/dev/null",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", f"UserKnownHostsFile={known_hosts_file}",
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=3",
            "-o", "Ciphers=aes128-cbc,3des-cbc,aes192-cbc,aes256-cbc,aes128-ctr,aes192-ctr,aes256-ctr",
            "-o", "KexAlgorithms=+diffie-hellman-group1-sha1,diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha1",
            "-o", "HostKeyAlgorithms=+ssh-rsa,rsa-sha2-256,rsa-sha2-512,ssh-ed25519",
            "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa,rsa-sha2-256,rsa-sha2-512",
            "-p", str(self.port)
        ])

        if self.agent_forwarding:
            cmd.append("-A")

        if self.key_filename and os.path.exists(self.key_filename):
            cmd.extend(["-i", self.key_filename])

        if self.username:
            cmd.append(f"{self.username}@{self.hostname}")
        else:
            cmd.append(self.hostname)

        try:
            self.master_fd, self.slave_fd = pty.openpty()
            import fcntl, termios, struct

            try:
                winsz = struct.pack("HHHH", height, width, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsz)
            except Exception:
                pass

            slave = self.slave_fd
            def _child_setup():
                try:
                    os.login_tty(slave)
                except Exception:
                    pass

            self.process = subprocess.Popen(
                cmd,
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                close_fds=True,
                preexec_fn=_child_setup,
                env=env
            )
            self.is_connected = True

            # Close slave in parent process after spawn so parent only manages master_fd
            try:
                os.close(self.slave_fd)
            except Exception:
                pass
            self.slave_fd = None

            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True
        except Exception as e:
            if self.output_callback:
                self.output_callback(f"\r\n[Native SSH Error]: {str(e)}\r\n")
            self.disconnect()
            return False

    def send_input(self, data: str):
        if self.master_fd is not None and self.is_connected:
            try:
                os.write(self.master_fd, data.encode("utf-8"))
            except Exception:
                pass

    def resize(self, width: int, height: int):
        self.resize_pty(width, height)

    def resize_pty(self, width: int, height: int):
        if self.master_fd is not None and self.is_connected:
            try:
                import fcntl, termios, struct
                winsz = struct.pack("HHHH", height, width, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsz)
            except Exception:
                pass

    def _read_loop(self):
        password_sent = False
        warning_shown = False
        auth_phase = True                    # Solo durante esta fase se permite auto-envío
        start_time = time.time()
        AUTH_TIMEOUT = 12.0                  # segundos máximos de fase de autenticación

        if self.protocol == "SSH1" and self.output_callback and not warning_shown:
            self.output_callback(
                "\r\n\033[33m[SSH Security Warning]: Session connected using legacy SSH 1.5 protocol. "
                "Recommend updating remote server configuration.\033[0m\r\n"
            )
            warning_shown = True

        while not self._stop_event.is_set() and self.master_fd is not None:
            try:
                # Salir de la fase de autenticación por timeout
                if auth_phase and (time.time() - start_time) > AUTH_TIMEOUT:
                    auth_phase = False

                r, _, _ = select.select([self.master_fd], [], [], 0.005)
                if self.master_fd in r:
                    data = os.read(self.master_fd, 8192)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        if self.output_callback:
                            self.output_callback(text)

                        lower_text = text.lower()

                        # Solo intentar auto-enviar durante la fase de autenticación
                        if auth_phase and not password_sent:
                            # Passphrase de clave privada
                            if self.key_passphrase and (
                                "enter passphrase for key" in lower_text
                                or "passphrase for key" in lower_text
                            ):
                                time.sleep(0.04)
                                os.write(self.master_fd, (self.key_passphrase + "\n").encode("utf-8"))
                                # No marcamos password_sent todavía (puede pedir password después)

                            # Password normal de usuario
                            elif self.password and (
                                "password:" in lower_text
                                or "password :" in lower_text
                            ):
                                time.sleep(0.04)
                                os.write(self.master_fd, (self.password + "\n").encode("utf-8"))
                                password_sent = True
                                auth_phase = False          # Una vez enviada, salimos de fase auth

                        # Detección de prompt de shell → salir de fase de autenticación
                        if auth_phase and (
                            lower_text.strip().endswith("$")
                            or lower_text.strip().endswith("#")
                            or lower_text.strip().endswith("%")
                            or "last login" in lower_text
                            or "welcome to" in lower_text
                        ):
                            auth_phase = False

                    else:
                        break
            except Exception:
                break

        self.is_connected = False
        if self.output_callback:
            self.output_callback("\r\n[SSH Session Closed]\r\n")
        if getattr(self, "close_callback", None):
            try:
                self.close_callback()
            except Exception:
                pass



    def disconnect(self):
        self._stop_event.set()
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except Exception:
                pass
            self.master_fd = None

        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except Exception:
                pass
            self.slave_fd = None

        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        self.process = None
        self.is_connected = False


class PlinkSSHEngine(BaseProtocolEngine):
    """
    Official PuTTY (plink) Engine for legacy SSH1, SSH2, and network hardware compatibility.
    Uses /usr/bin/plink (PuTTY Command-Line Utility) for 100% native PuTTY connection handling.
    """

    def __init__(self, hostname: str, port: int = 22, username: str = "", password: str = "", protocol: str = "SSH2"):
        super().__init__(hostname, port, username, password)
        self.protocol = protocol.upper()

        self.master_fd = None
        self.slave_fd = None
        self.process: Optional[subprocess.Popen] = None
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def connect(self, on_output: Callable[[str], None], on_close: Optional[Callable[[], None]] = None, term_type: str = "xterm", width: int = 80, height: int = 24) -> bool:
        self.output_callback = on_output
        self.close_callback = on_close

        plink = shutil.which("plink") or "/usr/bin/plink"
        cmd = [plink, "-ssh", "-t", "-no-antispoof"]

        if self.protocol == "SSH1":
            cmd.append("-1")
        elif self.protocol == "SSH2":
            cmd.append("-2")

        if self.port:
            cmd.extend(["-P", str(self.port)])

        if self.password:
            cmd.extend(["-pw", self.password])

        if self.username:
            cmd.extend(["-l", self.username])

        cmd.append(self.hostname)

        try:
            self.master_fd, self.slave_fd = pty.openpty()
            import fcntl, termios, struct

            try:
                winsz = struct.pack("HHHH", height, width, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsz)
            except Exception:
                pass

            env = os.environ.copy()
            env["TERM"] = term_type

            slave = self.slave_fd
            def _child_setup():
                try:
                    os.login_tty(slave)
                except Exception:
                    pass

            self.process = subprocess.Popen(
                cmd,
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                close_fds=True,
                preexec_fn=_child_setup,
                env=env
            )
            self.is_connected = True

            try:
                os.close(self.slave_fd)
            except Exception:
                pass
            self.slave_fd = None

            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True
        except Exception as e:
            if self.output_callback:
                self.output_callback(f"\r\n[PuTTY/Plink Engine Error]: {str(e)}\r\n")
            self.disconnect()
            return False

    def send_input(self, data: str):
        if self.master_fd is not None and self.is_connected:
            try:
                os.write(self.master_fd, data.encode("utf-8"))
            except Exception:
                pass

    def resize_pty(self, width: int, height: int):
        if self.master_fd is not None and self.is_connected:
            try:
                import fcntl, termios, struct
                winsz = struct.pack("HHHH", height, width, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsz)
            except Exception:
                pass

    def _read_loop(self):
        y_sent = False
        while not self._stop_event.is_set() and self.master_fd is not None:
            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.005)
                if self.master_fd in r:
                    data = os.read(self.master_fd, 8192)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        if self.output_callback:
                            self.output_callback(text)

                        if not y_sent and ("Store key in cache?" in text or "Update cached key?" in text or "(y/n)" in text.lower()):
                            time.sleep(0.05)
                            os.write(self.master_fd, b"y\n")
                            y_sent = True
                    else:
                        break
            except Exception:
                break

        self.is_connected = False
        if self.output_callback:
            self.output_callback("\r\n[SSH Session Closed]\r\n")
        if getattr(self, "close_callback", None):
            try:
                self.close_callback()
            except Exception:
                pass

    def disconnect(self):
        self._stop_event.set()
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except Exception:
                pass
            self.master_fd = None

        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        self.process = None
        self.is_connected = False


class SSHEngine(BaseProtocolEngine):
    """
    Unified Universal SSH Engine.
    Features Automatic Server Version Detection (SSH 1.x vs SSH 2.0) and Direct Transport Algorithm Injection.
    Guarantees 100% compatibility with legacy OpenSSH 4.x, SSH1, Cisco, and modern Linux boxes.
    """

    def __init__(self, hostname: str, port: int = 22, username: str = "", password: str = "",
                 key_filename: Optional[str] = None, key_passphrase: Optional[str] = None,
                 legacy_mode: bool = True, protocol: str = "SSH2",
                 agent_forwarding: bool = False, auto_reconnect: bool = False):
        super().__init__(hostname, port, username, password)
        self.key_filename = key_filename
        self.key_passphrase = key_passphrase
        self.legacy_mode = legacy_mode
        self.protocol = protocol.upper()
        self.agent_forwarding = agent_forwarding
        self.auto_reconnect = auto_reconnect

        self.transport: Optional[paramiko.Transport] = None
        self.channel = None
        self.plink_engine: Optional[PlinkSSHEngine] = None
        self.ssh1_engine: Optional[PurePythonSSH1Engine] = None
        self.native_engine: Optional[NativePTYSSHEngine] = None
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def connect(self, on_output: Callable[[str], None], on_close: Optional[Callable[[], None]] = None, term_type: str = "xterm", width: int = 80, height: int = 24) -> bool:
        self.output_callback = on_output
        self.close_callback = on_close

        # 1. Detect actual SSH protocol version by connecting socket & inspecting server banner
        detected_version, banner = self._peek_server_banner()

        # 2. If Server speaks SSH1 (SSH-1.x), use Pure Python SSH1 Engine or Plink
        if detected_version == "SSH1":
            if self.output_callback:
                self.output_callback(f"Connecting to {self.hostname}:{self.port} (SSH 1.5 Protocol)...\r\nServer Banner: {banner.strip()}\r\n")
            if shutil.which("plink"):
                self.plink_engine = PlinkSSHEngine(
                    hostname=self.hostname, port=self.port, username=self.username, password=self.password, protocol="SSH1"
                )
                return self.plink_engine.connect(on_output=on_output, on_close=on_close, term_type=term_type, width=width, height=height)
            else:
                self.ssh1_engine = PurePythonSSH1Engine(
                    hostname=self.hostname, port=self.port, username=self.username, password=self.password
                )
                return self.ssh1_engine.connect(on_output=on_output, on_close=on_close, term_type=term_type, width=width, height=height)

        # 3. Server speaks SSH2 -> Use Native Linux SSH Engine first if available
        if shutil.which("ssh"):
            if self.output_callback:
                self.output_callback(f"Connecting to {self.hostname}:{self.port}...\r\nServer Banner: {banner.strip()}\r\n")

            self.native_engine = NativePTYSSHEngine(
                hostname=self.hostname, port=self.port, username=self.username, password=self.password,
                key_filename=self.key_filename, key_passphrase=self.key_passphrase, protocol=self.protocol,
                agent_forwarding=self.agent_forwarding, auto_reconnect=self.auto_reconnect
            )
            return self.native_engine.connect(on_output=on_output, on_close=on_close, term_type=term_type, width=width, height=height)

        # Fallback to Paramiko Direct Transport if native ssh is not present
        if self.output_callback:
            self.output_callback(f"Connecting to {self.hostname}:{self.port} via Paramiko Transport...\r\nServer Banner: {banner.strip()}\r\n")

        try:
            sock = socket.create_connection((self.hostname, self.port), timeout=10)
            # Enable TCP Keepalive on socket
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "IPPROTO_TCP"):
                if hasattr(socket, "TCP_KEEPIDLE"):
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 15)
                if hasattr(socket, "TCP_KEEPINTVL"):
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
                if hasattr(socket, "TCP_KEEPCNT"):
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)

            self.transport = paramiko.Transport(sock)
            configure_security_options(self.transport)

            if self.key_filename and os.path.exists(self.key_filename):
                try:
                    pkey = load_encrypted_private_key(self.key_filename, passphrase=self.key_passphrase)
                    if pkey:
                        self.transport.connect(username=self.username, pkey=pkey)
                except paramiko.PasswordRequiredException:
                    if self.output_callback:
                        self.output_callback("\r\n[SSH Notice]: Private key is encrypted with a passphrase. Attempting passphrase authentication...\r\n")
                    if self.key_passphrase:
                        try:
                            pkey = load_encrypted_private_key(self.key_filename, passphrase=self.key_passphrase)
                            if pkey:
                                self.transport.connect(username=self.username, pkey=pkey)
                        except Exception:
                            self.transport.connect(username=self.username, password=self.password)
                    else:
                        self.transport.connect(username=self.username, password=self.password)
                except Exception:
                    self.transport.connect(username=self.username, password=self.password)
            else:
                self.transport.connect(username=self.username, password=self.password)

            # Check host key against ~/.ssh/known_hosts to alert user of MITM
            try:
                remote_key = self.transport.get_remote_server_key()
                if remote_key:
                    known_hosts_path = os.path.expanduser("~/.ssh/known_hosts")
                    if os.path.exists(known_hosts_path):
                        host_keys = paramiko.util.load_host_keys(known_hosts_path)
                        if self.hostname in host_keys:
                            key_type = remote_key.get_name()
                            expected_key = host_keys[self.hostname].get(key_type)
                            if expected_key and expected_key != remote_key:
                                if self.output_callback:
                                    self.output_callback(
                                        f"\r\n\033[31m[SSH Security Alert]: Host key for {self.hostname} differs from known_hosts! Possible Man-in-the-Middle.\033[0m\r\n"
                                    )
            except Exception:
                pass

            # Open interactive PTY shell channel
            self.channel = self.transport.open_session()
            if self.agent_forwarding:
                try:
                    paramiko.agent.AgentRequestHandler(self.channel)
                except Exception:
                    pass
            self.channel.get_pty(term=term_type, width=width, height=height)
            self.channel.invoke_shell()

            self.is_connected = True
            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True

        except Exception as e:
            if shutil.which("plink"):
                if self.output_callback:
                    self.output_callback(f"\r\n[SSH2 Transport Notice]: {str(e)}. Switching to PuTTY (plink) Engine...\r\n")

                self.disconnect()
                self.plink_engine = PlinkSSHEngine(
                    hostname=self.hostname, port=self.port, username=self.username, password=self.password, protocol=self.protocol
                )
                return self.plink_engine.connect(on_output=on_output, on_close=on_close, term_type=term_type, width=width, height=height)
            else:
                if self.output_callback:
                    self.output_callback(f"\r\n[SSH2 Error]: {str(e)}\r\n")
                return False

    def send_input(self, data: str):
        if self.plink_engine:
            self.plink_engine.send_input(data)
        elif self.ssh1_engine:
            self.ssh1_engine.send_input(data)
        elif self.native_engine:
            self.native_engine.send_input(data)
        elif self.channel and self.is_connected:
            try:
                self.channel.send(data.encode("utf-8"))
            except Exception:
                pass

    def resize_pty(self, width: int, height: int):
        if self.plink_engine:
            self.plink_engine.resize_pty(width, height)
        elif self.native_engine:
            self.native_engine.resize_pty(width, height)
        elif self.channel and self.is_connected:
            try:
                self.channel.resize_pty(width=width, height=height)
            except Exception:
                pass

    def _peek_server_banner(self) -> Tuple[str, str]:
        """Peeks at server banner to auto-detect whether server is SSH 1.x or SSH 2.0."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((self.hostname, self.port))
            banner = s.recv(1024).decode("utf-8", errors="ignore")
            s.close()
            if "SSH-1." in banner:
                return "SSH1", banner
            return "SSH2", banner
        except Exception as e:
            return "SSH2", f"SSH-2.0-Generic ({str(e)})"

    def _read_loop(self):
        while not self._stop_event.is_set() and self.channel:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(8192)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        if self.output_callback:
                            self.output_callback(text)
                        continue
                    else:
                        break
                time.sleep(0.005)
            except Exception:
                break

        self.is_connected = False
        if self.output_callback:
            self.output_callback("\r\n[SSH Session Closed]\r\n")
        if getattr(self, "close_callback", None):
            try:
                self.close_callback()
            except Exception:
                pass

    def disconnect(self):
        self._stop_event.set()
        if self.plink_engine:
            self.plink_engine.disconnect()
            self.plink_engine = None

        if self.ssh1_engine:
            self.ssh1_engine.disconnect()
            self.ssh1_engine = None

        if self.native_engine:
            self.native_engine.disconnect()
            self.native_engine = None

        if self.channel:
            try:
                self.channel.close()
            except Exception:
                pass
            self.channel = None

        if self.transport:
            try:
                self.transport.close()
            except Exception:
                pass
            self.transport = None

        self.is_connected = False
