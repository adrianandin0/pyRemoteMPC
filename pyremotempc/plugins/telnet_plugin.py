from typing import Type
from pyremotempc.plugins.plugin_base import ProtocolPlugin
from pyremotempc.engine.base_engine import BaseProtocolEngine
from pyremotempc.engine.telnet_engine import TelnetEngine


class TelnetProtocolPlugin(ProtocolPlugin):
    """Protocol plugin for Telnet Terminal Protocol."""

    @property
    def protocol_name(self) -> str:
        return "TELNET"

    @property
    def display_name(self) -> str:
        return "Telnet Terminal"

    @property
    def default_port(self) -> int:
        return 23

    @property
    def icon_name(self) -> str:
        return "server"

    @property
    def engine_class(self) -> Type[BaseProtocolEngine]:
        return TelnetEngine
