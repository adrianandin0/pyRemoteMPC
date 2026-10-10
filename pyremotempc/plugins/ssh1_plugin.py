from typing import Type
from pyremotempc.plugins.plugin_base import ProtocolPlugin
from pyremotempc.engine.base_engine import BaseProtocolEngine
from pyremotempc.engine.ssh1_engine import SSH1Engine


class SSH1ProtocolPlugin(ProtocolPlugin):
    """Protocol plugin for Legacy SSH Version 1."""

    @property
    def protocol_name(self) -> str:
        return "SSH1"

    @property
    def display_name(self) -> str:
        return "Legacy SSH Version 1"

    @property
    def default_port(self) -> int:
        return 22

    @property
    def icon_name(self) -> str:
        return "linux"

    @property
    def engine_class(self) -> Type[BaseProtocolEngine]:
        return SSH1Engine
