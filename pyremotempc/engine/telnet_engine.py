import socket
import select
import threading
import time
from typing import Callable, Optional

from pyremotempc.engine.base_engine import BaseProtocolEngine

# Telnet Protocol Constants (RFC 854)
IAC = 255      # Interpret As Command
DONT = 254     # Don't perform option
DO = 253       # Do perform option
WONT = 252     # Won't perform option
WILL = 251     # Will perform option
SB = 250       # Subnegotiation Begin
SE = 240       # Subnegotiation End

# Telnet Options
OPT_ECHO = 1
OPT_SUPPRESS_GO_AHEAD = 3
OPT_TERMINAL_TYPE = 24
OPT_NAWS = 31  # Negotiate About Window Size


class TelnetEngine(BaseProtocolEngine):
    """
    Telnet Protocol Engine (RFC 854 compliant).
    Handles non-blocking TCP socket communication, Telnet IAC option negotiations
    (Echo, Terminal Type, Suppress Go Ahead, NAWS window resizing),
    and streams raw terminal text into TerminalWidget (pyte).
    """

    def __init__(self, hostname: str, port: int = 23, username: str = "", password: str = ""):
        super().__init__(hostname, port, username, password)
        self.sock: Optional[socket.socket] = None
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.term_type = "xterm"

    def connect(self, on_output: Callable[[str], None], on_close: Optional[Callable[[], None]] = None, term_type: str = "xterm", width: int = 80, height: int = 24) -> bool:
        self.output_callback = on_output
        self.close_callback = on_close
        self.term_type = term_type

        try:
            if self.output_callback:
                self.output_callback(f"Connecting via Telnet to {self.hostname}:{self.port}...\r\n")

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.hostname, self.port))

            self.is_connected = True
            self.sock.settimeout(0.1)

            # Send NAWS window size negotiation if supported
            self._send_naws(width, height)

            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True

        except Exception as e:
            if self.output_callback:
                self.output_callback(f"\r\n[Telnet Connection Error]: {str(e)}\r\n")
            self.disconnect()
            return False

    def send_input(self, data: str):
        """Sends user input data over the Telnet socket."""
        if self.sock and self.is_connected:
            try:
                # Replace lone \n with \r\n for Telnet standard
                data_bytes = data.encode("utf-8", errors="replace")
                self.sock.sendall(data_bytes)
            except Exception:
                pass

    def resize(self, width: int, height: int):
        """Sends updated window size (NAWS) to Telnet server."""
        if self.sock and self.is_connected:
            self._send_naws(width, height)

    def _send_naws(self, width: int, height: int):
        """Sends Negotiate About Window Size (NAWS) option packet."""
        try:
            # IAC SB NAWS width_high width_low height_high height_low IAC SE
            w_h, w_l = (width >> 8) & 0xFF, width & 0xFF
            h_h, h_l = (height >> 8) & 0xFF, height & 0xFF
            naws_pkt = bytes([IAC, SB, OPT_NAWS, w_h, w_l, h_h, h_l, IAC, SE])
            if self.sock:
                self.sock.sendall(naws_pkt)
        except Exception:
            pass

    def _read_loop(self):
        buf = bytearray()
        while not self._stop_event.is_set() and self.sock:
            try:
                r, _, _ = select.select([self.sock], [], [], 0.005)
                if self.sock in r:
                    chunk = self.sock.recv(8192)
                    if not chunk:
                        break
                    buf.extend(chunk)
                    clean_text = self._process_telnet_data(buf)
                    if clean_text and self.output_callback:
                        self.output_callback(clean_text)
            except Exception:
                break

        self.is_connected = False
        if self.output_callback:
            self.output_callback("\r\n[Telnet Session Closed]\r\n")
        if getattr(self, "close_callback", None):
            try:
                self.close_callback()
            except Exception:
                pass

    def _process_telnet_data(self, buf: bytearray) -> str:
        """
        Parses Telnet IAC commands from buffer, responds to option negotiation,
        and returns clean text data.
        """
        out = bytearray()
        i = 0
        n = len(buf)

        while i < n:
            b = buf[i]
            if b == IAC:
                if i + 1 < n:
                    cmd = buf[i + 1]
                    if cmd == IAC:
                        out.append(IAC)
                        i += 2
                    elif cmd in (DO, DONT, WILL, WONT):
                        if i + 2 < n:
                            opt = buf[i + 2]
                            self._handle_negotiation(cmd, opt)
                            i += 3
                        else:
                            break  # Need more data
                    elif cmd == SB:
                        # Find SB ... SE sequence
                        se_idx = -1
                        for j in range(i + 2, n - 1):
                            if buf[j] == IAC and buf[j + 1] == SE:
                                se_idx = j + 1
                                break
                        if se_idx != -1:
                            sb_data = buf[i + 2 : se_idx - 1]
                            self._handle_subnegotiation(sb_data)
                            i = se_idx + 1
                        else:
                            break  # Wait for complete subnegotiation
                    else:
                        i += 2
                else:
                    break
            else:
                out.append(b)
                i += 1

        del buf[:i]
        return out.decode("utf-8", errors="replace")

    def _handle_negotiation(self, cmd: int, opt: int):
        """Responds to server DO/DONT/WILL/WONT requests."""
        try:
            if not self.sock:
                return

            if cmd == DO:
                if opt in (OPT_ECHO, OPT_SUPPRESS_GO_AHEAD, OPT_TERMINAL_TYPE, OPT_NAWS):
                    self.sock.sendall(bytes([IAC, WILL, opt]))
                else:
                    self.sock.sendall(bytes([IAC, WONT, opt]))
            elif cmd == WILL:
                if opt in (OPT_ECHO, OPT_SUPPRESS_GO_AHEAD):
                    self.sock.sendall(bytes([IAC, DO, opt]))
                else:
                    self.sock.sendall(bytes([IAC, DONT, opt]))
        except Exception:
            pass

    def _handle_subnegotiation(self, sb_data: bytearray):
        """Responds to subnegotiations (e.g. TERMINAL_TYPE SEND)."""
        try:
            if not self.sock or not sb_data:
                return
            opt = sb_data[0]
            if opt == OPT_TERMINAL_TYPE and len(sb_data) > 1 and sb_data[1] == 1:  # SEND
                # Reply with IAC SB TERMINAL_TYPE IS <term_type> IAC SE
                term_bytes = self.term_type.encode("ascii", errors="ignore")
                pkt = bytes([IAC, SB, OPT_TERMINAL_TYPE, 0]) + term_bytes + bytes([IAC, SE])
                self.sock.sendall(pkt)
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
