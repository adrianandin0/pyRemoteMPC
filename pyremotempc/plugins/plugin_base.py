import abc
from typing import Type, Optional
from pyremotempc.engine.base_engine import BaseProtocolEngine


class ProtocolPlugin(abc.ABC):
    """
    Abstract Base Class for pyRemoteMPC Protocol Plugins.
    Enables dynamic third-party and built-in protocol extensions (e.g. SSH, RDP, VNC, Telnet, Serial, HTTP, etc.).
    """

    @property
    @abc.abstractmethod
    def protocol_name(self) -> str:
        """Unique identifier name for the protocol (e.g. 'SSH', 'RDP', 'SERIAL', 'HTTP')."""
        pass

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """Human-readable display title (e.g. 'Secure Shell (SSH)', 'Remote Desktop (RDP)')."""
        pass

    @property
    def default_port(self) -> int:
        """Default network port for this protocol."""
        return 0

    @property
    def icon_name(self) -> str:
        """Icon key for UI tree and tabs (e.g. 'server', 'linux', 'windows')."""
        return "server"

    @property
    @abc.abstractmethod
    def engine_class(self) -> Type[BaseProtocolEngine]:
        """Returns the BaseProtocolEngine class implementation for this protocol."""
        pass
