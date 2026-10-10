from typing import Type
from pyremotempc.plugins.plugin_base import ProtocolPlugin
from pyremotempc.engine.base_engine import BaseProtocolEngine
from pyremotempc.engine.ssh_engine import SSHEngine


class SSHProtocolPlugin(ProtocolPlugin):
    """Protocol plugin for Secure Shell (SSH2 / Native OpenSSH PTY)."""

    @property
    def protocol_name(self) -> str:
        return "SSH"

    @property
    def display_name(self) -> str:
        return "Secure Shell (SSH2)"

    @property
    def default_port(self) -> int:
        return 22

    @property
    def icon_name(self) -> str:
        return "linux"

    @property
    def engine_class(self) -> Type[BaseProtocolEngine]:
        return SSHEngine
