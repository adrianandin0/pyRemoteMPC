from typing import Type
from pyremotempc.plugins.plugin_base import ProtocolPlugin
from pyremotempc.engine.base_engine import BaseProtocolEngine
from pyremotempc.engine.ftp_engine import FTPEngine


class FTPProtocolPlugin(ProtocolPlugin):
    """Protocol plugin for FTP (File Transfer Protocol)."""

    @property
    def protocol_name(self) -> str:
        return "FTP"

    @property
    def display_name(self) -> str:
        return "File Transfer Protocol (FTP)"

    @property
    def default_port(self) -> int:
        return 21

    @property
    def icon_name(self) -> str:
        return "ftp"

    @property
    def engine_class(self) -> Type[BaseProtocolEngine]:
        return FTPEngine
