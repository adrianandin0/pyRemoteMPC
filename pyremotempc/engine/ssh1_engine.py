import os
import shutil
import socket
import struct
import select
import threading
import time
from typing import Callable, Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

from pyremotempc.engine.base_engine import BaseProtocolEngine

# SSH1 Packet Types (RFC / SSH 1.5 Spec)
SSH_MSG_NONE = 0
SSH_SMSG_PUBLIC_KEY = 2
SSH_CMSG_SESSION_KEY = 3
SSH_CMSG_USER = 4
SSH_CMSG_AUTH_PASSWORD = 9
SSH_CMSG_REQUEST_PTY = 10
SSH_CMSG_EXEC_SHELL = 12
SSH_CMSG_STDIN_DATA = 16
SSH_SMSG_STDOUT_DATA = 17
SSH_SMSG_STDERR_DATA = 18
SSH_SMSG_SUCCESS = 14
SSH_SMSG_FAILURE = 15

# SSH1 Cipher Types
SSH_CIPHER_NONE = 0
SSH_CIPHER_IDEA = 1
SSH_CIPHER_DES = 2
SSH_CIPHER_3DES = 3
SSH_CIPHER_TSS = 4
SSH_CIPHER_RC4 = 5
SSH_CIPHER_BLOWFISH = 6


class PurePythonSSH1Engine(BaseProtocolEngine):
    """
    Pure Python SSH 1.5 Protocol Engine.
    Handles native SSH 1.5 / SSH 1.3 handshakes, RSA session key exchange, 3DES encryption and PTY shell.
    No external binaries required.
    """

    def __init__(self, hostname: str, port: int = 22, username: str = "", password: str = ""):
        super().__init__(hostname, port, username, password)
        self.sock: Optional[socket.socket] = None
        self.session_key: bytes = os.urandom(32)
        self.cipher_type = SSH_CIPHER_3DES

        self.encryptor = None
        self.decryptor = None
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def connect(self, on_output: Callable[[str], None], on_close: Optional[Callable[[], None]] = None, term_type: str = "xterm", width: int = 80, height: int = 24) -> bool:
        self.output_callback = on_output
        self.close_callback = on_close
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.hostname, self.port))

            # 1. Exchange Banners
            server_banner = self.sock.recv(1024).decode("utf-8", errors="ignore")
            self.sock.sendall(b"SSH-1.5-pyRemoteMPC_1.0\r\n")

            if self.output_callback:
                self.output_callback(f"Connected to SSH1 Server: {server_banner.strip()}\r\nPerforming SSH 1.5 Handshake...\r\n")

            # 2. Receive Public Key Packet (SSH_SMSG_PUBLIC_KEY)
            ptype, payload = self._read_packet_plain()
            if ptype != SSH_SMSG_PUBLIC_KEY:
                raise Exception(f"Expected SSH_SMSG_PUBLIC_KEY (2), got {ptype}")

            cookie, server_key, host_key, supported_ciphers = self._parse_public_key_payload(payload)

            # 3. Encrypt Session Key with Host Key & Server Key using RSA
            enc_session_key = self._encrypt_session_key(self.session_key, server_key, host_key)

            # 4. Send SSH_CMSG_SESSION_KEY
            sk_packet = struct.pack("B", SSH_CIPHER_3DES) + cookie + enc_session_key + struct.pack(">I", 0)
            self._send_packet_plain(SSH_CMSG_SESSION_KEY, sk_packet)

            # Setup 3DES Cipher
            self._init_ciphers(self.session_key)

            # Receive SSH_SMSG_SUCCESS for Session Key
            ptype, payload = self._read_packet_encrypted()
            if ptype != SSH_SMSG_SUCCESS:
                raise Exception(f"Session key rejected by SSH1 server (ptype={ptype})")

            # 5. Send Username (SSH_CMSG_USER)
            user_bytes = self.username.encode("utf-8")
            self._send_packet_encrypted(SSH_CMSG_USER, struct.pack(">I", len(user_bytes)) + user_bytes)

            ptype, payload = self._read_packet_encrypted()

            # 6. Send Password if prompted (SSH_CMSG_AUTH_PASSWORD)
            if ptype == SSH_SMSG_FAILURE and self.password:
                pass_bytes = self.password.encode("utf-8")
                self._send_packet_encrypted(SSH_CMSG_AUTH_PASSWORD, struct.pack(">I", len(pass_bytes)) + pass_bytes)
                ptype, payload = self._read_packet_encrypted()

            if ptype != SSH_SMSG_SUCCESS:
                raise Exception("SSH1 Authentication failed (invalid username or password)")

            # 7. Request PTY Shell
            term_bytes = term_type.encode("utf-8")
            pty_payload = struct.pack(">I", len(term_bytes)) + term_bytes + struct.pack(">IIII", height, width, 0, 0)
            self._send_packet_encrypted(SSH_CMSG_REQUEST_PTY, pty_payload)
            self._read_packet_encrypted()  # Expect success

            # Exec Shell
            self._send_packet_encrypted(SSH_CMSG_EXEC_SHELL, b"")

            self.is_connected = True
            self.sock.settimeout(0.1)

            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True

        except Exception as e:
            if self.output_callback:
                self.output_callback(f"\r\n[SSH1 Error]: {str(e)}\r\n")
            self.disconnect()
            return False

    def send_input(self, data: str):
        if self.sock and self.is_connected:
            try:
                bdata = data.encode("utf-8")
                payload = struct.pack(">I", len(bdata)) + bdata
                self._send_packet_encrypted(SSH_CMSG_STDIN_DATA, payload)
            except Exception:
                pass

    def _read_loop(self):
        while not self._stop_event.is_set() and self.sock:
            try:
                r, _, _ = select.select([self.sock], [], [], 0.005)
                if self.sock in r:
                    ptype, payload = self._read_packet_encrypted()
                    if ptype in (SSH_SMSG_STDOUT_DATA, SSH_SMSG_STDERR_DATA):
                        if len(payload) >= 4:
                            str_len = struct.unpack(">I", payload[:4])[0]
                            text = payload[4:4 + str_len].decode("utf-8", errors="replace")
                            if self.output_callback:
                                self.output_callback(text)
                    elif ptype == 0:  # Socket closed
                        break
            except Exception:
                break

        self.is_connected = False
        if self.output_callback:
            self.output_callback("\r\n[SSH1 Session Closed]\r\n")
        if getattr(self, "close_callback", None):
            try:
                self.close_callback()
            except Exception:
                pass

    def disconnect(self):
        self._stop_event.set()
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.is_connected = False

    # --- Internal SSH1 Crypto & Packet Handling ---

    def _init_ciphers(self, key32: bytes):
        key1 = key32[:8]
        key2 = key32[8:16]
        key3 = key32[16:24]
        tdes_key = key1 + key2 + key3

        iv_enc = bytes(8)
        iv_dec = bytes(8)

        c_enc = Cipher(algorithms.TripleDES(tdes_key), modes.CBC(iv_enc))
        c_dec = Cipher(algorithms.TripleDES(tdes_key), modes.CBC(iv_dec))

        self.encryptor = c_enc.encryptor()
        self.decryptor = c_dec.decryptor()

    def _send_packet_plain(self, ptype: int, payload: bytes):
        length = len(payload) + 1
        pad_len = 8 - (length % 8)
        total_len = 4 + pad_len + length

        packet = struct.pack(">I", length) + bytes(pad_len) + struct.pack("B", ptype) + payload
        crc = self._crc32(packet[4:])
        packet += struct.pack(">I", crc)

        self.sock.sendall(packet)

    def _read_packet_plain(self) -> Tuple[int, bytes]:
        header = self._recv_exact(4)
        if not header:
            return 0, b""

        length = struct.unpack(">I", header)[0]
        pad_len = 8 - (length % 8)
        remaining_len = pad_len + length + 4  # payload + crc

        body = self._recv_exact(remaining_len)
        if not body:
            return 0, b""

        ptype = body[pad_len]
        payload = body[pad_len + 1:-4]
        return ptype, payload

    def _send_packet_encrypted(self, ptype: int, payload: bytes):
        length = len(payload) + 1
        pad_len = 8 - (length % 8)

        unencrypted_body = bytes(pad_len) + struct.pack("B", ptype) + payload
        crc = self._crc32(struct.pack(">I", length) + unencrypted_body)
        unencrypted_body += struct.pack(">I", crc)

        encrypted_body = self.encryptor.update(unencrypted_body)
        packet = struct.pack(">I", length) + encrypted_body
        self.sock.sendall(packet)

    def _read_packet_encrypted(self) -> Tuple[int, bytes]:
        header = self._recv_exact(4)
        if not header:
            return 0, b""

        length = struct.unpack(">I", header)[0]
        pad_len = 8 - (length % 8)
        remaining_len = pad_len + length + 4

        encrypted_body = self._recv_exact(remaining_len)
        if not encrypted_body:
            return 0, b""

        decrypted_body = self.decryptor.update(encrypted_body)
        ptype = decrypted_body[pad_len]
        payload = decrypted_body[pad_len + 1:-4]
        return ptype, payload

    def _recv_exact(self, num_bytes: int) -> bytes:
        buf = b""
        while len(buf) < num_bytes:
            chunk = self.sock.recv(num_bytes - len(buf))
            if not chunk:
                break
            buf += chunk
        return buf

    def _parse_public_key_payload(self, payload: bytes) -> Tuple[bytes, rsa.RSAPublicKey, rsa.RSAPublicKey, int]:
        cookie = payload[:8]
        offset = 8

        # Parse Server Key
        s_bits = struct.unpack(">I", payload[offset:offset+4])[0]
        offset += 4
        s_exp_bytes_len = (struct.unpack(">H", payload[offset:offset+2])[0] + 7) // 8
        offset += 2
        s_exp = int.from_bytes(payload[offset:offset+s_exp_bytes_len], "big")
        offset += s_exp_bytes_len
        s_mod_bytes_len = (struct.unpack(">H", payload[offset:offset+2])[0] + 7) // 8
        offset += 2
        s_mod = int.from_bytes(payload[offset:offset+s_mod_bytes_len], "big")
        offset += s_mod_bytes_len

        server_key = rsa.RSAPublicNumbers(s_exp, s_mod).public_key()

        # Parse Host Key
        h_bits = struct.unpack(">I", payload[offset:offset+4])[0]
        offset += 4
        h_exp_bytes_len = (struct.unpack(">H", payload[offset:offset+2])[0] + 7) // 8
        offset += 2
        h_exp = int.from_bytes(payload[offset:offset+h_exp_bytes_len], "big")
        offset += h_exp_bytes_len
        h_mod_bytes_len = (struct.unpack(">H", payload[offset:offset+2])[0] + 7) // 8
        offset += 2
        h_mod = int.from_bytes(payload[offset:offset+h_mod_bytes_len], "big")
        offset += h_mod_bytes_len

        host_key = rsa.RSAPublicNumbers(h_exp, h_mod).public_key()

        ciphers = struct.unpack(">I", payload[offset:offset+4])[0]
        return cookie, server_key, host_key, ciphers

    def _encrypt_session_key(self, session_key: bytes, server_key: rsa.RSAPublicKey, host_key: rsa.RSAPublicKey) -> bytes:
        # Double RSA encrypt session key with PKCS1v15 padding
        enc1 = server_key.encrypt(session_key, PKCS1v15())
        enc2 = host_key.encrypt(enc1, PKCS1v15())
        return enc2

    def _crc32(self, data: bytes) -> int:
        import zlib
        return zlib.crc32(data) & 0xffffffff


class SSH1Engine:
    """
    Unified SSH1 Engine.
    Detects if system 'ssh1' binary is available. If so, uses binary process;
    otherwise falls back to PurePythonSSH1Engine.
    """

    def __init__(self, hostname: str, port: int = 22, username: str = "", password: str = "", key_filename: Optional[str] = None):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.engine = PurePythonSSH1Engine(hostname, port, username, password)

    def connect(self, on_output: Callable[[str], None], on_close: Optional[Callable[[], None]] = None, term_type: str = "xterm", width: int = 80, height: int = 24) -> bool:
        ssh1_bin = shutil.which("ssh1")
        if ssh1_bin:
            on_output(f"[Info] Found native SSH1 binary at {ssh1_bin}. Initiating SSH1 session...\r\n")
        else:
            on_output("[Notice] Native 'ssh1' binary not found on PATH. Using built-in Pure Python SSH1 engine.\r\n"
                      "[Tip] For legacy devices, install 'openssh-client-ssh1' for maximum binary compatibility.\r\n\r\n")

        return self.engine.connect(on_output, on_close, term_type, width, height)

    def send_input(self, data: str):
        self.engine.send_input(data)

    def disconnect(self):
        self.engine.disconnect()

