from typing import Type
from pyremotempc.plugins.plugin_base import ProtocolPlugin
from pyremotempc.engine.base_engine import BaseProtocolEngine
from pyremotempc.engine.sftp_engine import SFTPEngine


class SFTPProtocolPlugin(ProtocolPlugin):
    """Protocol plugin for SFTP (SSH File Transfer Protocol)."""

    @property
    def protocol_name(self) -> str:
        return "SFTP"

    @property
    def display_name(self) -> str:
        return "SSH File Transfer Protocol (SFTP)"

    @property
    def default_port(self) -> int:
        return 22

    @property
    def icon_name(self) -> str:
        return "ftp"

    @property
    def engine_class(self) -> Type[BaseProtocolEngine]:
        return SFTPEngine
