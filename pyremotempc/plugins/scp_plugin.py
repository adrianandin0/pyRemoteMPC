from typing import Type
from pyremotempc.plugins.plugin_base import ProtocolPlugin
from pyremotempc.engine.base_engine import BaseProtocolEngine
from pyremotempc.engine.sftp_engine import NativePTYSFTPEngine


class SCPProtocolPlugin(ProtocolPlugin):
    """Protocol plugin for SCP (Secure Copy Protocol)."""

    @property
    def protocol_name(self) -> str:
        return "SCP"

    @property
    def display_name(self) -> str:
        return "Secure Copy Protocol (SCP)"

    @property
    def default_port(self) -> int:
        return 22

    @property
    def icon_name(self) -> str:
        return "ftp"

    @property
    def engine_class(self) -> Type[BaseProtocolEngine]:
        return NativePTYSFTPEngine
