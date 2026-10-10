import abc
from typing import Callable, Optional


class BaseProtocolEngine(abc.ABC):
    """
    Abstract Base Class for all pyRemoteMPC Protocol Engines (SSH, RDP, VNC, Telnet, Serial, etc.).
    Defines a unified lifecycle and interface across all connection protocols.
    """

    def __init__(self, hostname: str, port: int = 0, username: str = "", password: str = ""):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.is_connected = False
        self.output_callback: Optional[Callable[[str], None]] = None
        self.close_callback: Optional[Callable[[], None]] = None

    @abc.abstractmethod
    def connect(self, on_output: Optional[Callable[[str], None]] = None,
                on_close: Optional[Callable[[], None]] = None,
                term_type: str = "xterm", width: int = 80, height: int = 24) -> bool:
        """Establishes connection and starts session handling."""
        pass

    @abc.abstractmethod
    def disconnect(self):
        """Terminates session and cleans up resources."""
        pass

    @abc.abstractmethod
    def send_input(self, data: str):
        """Sends user input data to remote host or process."""
        pass

    def resize(self, width: int, height: int):
        """Resizes terminal or remote desktop viewport dimensions."""
        pass

    def get_status(self) -> str:
        """Returns string representation of current connection status."""
        return "Connected" if self.is_connected else "Disconnected"
