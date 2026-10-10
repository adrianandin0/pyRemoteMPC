from typing import Type
from pyremotempc.plugins.plugin_base import ProtocolPlugin
from pyremotempc.engine.base_engine import BaseProtocolEngine
from pyremotempc.engine.serial_engine import SerialEngine


class SerialProtocolPlugin(ProtocolPlugin):
    """Protocol plugin for Serial Port Communication (COM / ttyUSB / ttyS)."""

    @property
    def protocol_name(self) -> str:
        return "SERIAL"

    @property
    def display_name(self) -> str:
        return "Serial Port (COM/ttyUSB)"

    @property
    def default_port(self) -> int:
        return 0

    @property
    def icon_name(self) -> str:
        return "terminal"

    @property
    def engine_class(self) -> Type[BaseProtocolEngine]:
        return SerialEngine
