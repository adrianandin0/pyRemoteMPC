from typing import Type
from pyremotempc.plugins.plugin_base import ProtocolPlugin
from pyremotempc.engine.base_engine import BaseProtocolEngine
from pyremotempc.engine.vnc_engine import VNCEngine


class VNCProtocolPlugin(ProtocolPlugin):
    """Protocol plugin for Virtual Network Computing (VNC / vinagre / xtigervncviewer)."""

    @property
    def protocol_name(self) -> str:
        return "VNC"

    @property
    def display_name(self) -> str:
        return "VNC Remote Display"

    @property
    def default_port(self) -> int:
        return 5900

    @property
    def icon_name(self) -> str:
        return "server"

    @property
    def engine_class(self) -> Type[BaseProtocolEngine]:
        return VNCEngine
