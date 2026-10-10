from typing import Type
from pyremotempc.plugins.plugin_base import ProtocolPlugin
from pyremotempc.engine.base_engine import BaseProtocolEngine
from pyremotempc.engine.rdp_engine import RDPEngine


class RDPProtocolPlugin(ProtocolPlugin):
    """Protocol plugin for Remote Desktop Protocol (FreeRDP xfreerdp)."""

    @property
    def protocol_name(self) -> str:
        return "RDP"

    @property
    def display_name(self) -> str:
        return "Remote Desktop (RDP)"

    @property
    def default_port(self) -> int:
        return 3389

    @property
    def icon_name(self) -> str:
        return "windows"

    @property
    def engine_class(self) -> Type[BaseProtocolEngine]:
        return RDPEngine
