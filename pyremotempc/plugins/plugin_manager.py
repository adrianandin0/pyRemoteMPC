import os
import importlib
import pkgutil
from typing import Dict, Type, List, Optional
from pyremotempc.plugins.plugin_base import ProtocolPlugin
from pyremotempc.engine.base_engine import BaseProtocolEngine


class PluginManager:
    """
    Central Manager for discovering, registering, and instantiating pyRemoteMPC Protocol Plugins.
    Scans internal and external plugin paths using importlib.
    """

    _instance: Optional['PluginManager'] = None

    def __init__(self):
        self._plugins: Dict[str, ProtocolPlugin] = {}

    @classmethod
    def instance(cls) -> 'PluginManager':
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.discover_plugins()
        return cls._instance

    def register_plugin(self, plugin: ProtocolPlugin):
        """Registers a ProtocolPlugin instance."""
        proto_key = plugin.protocol_name.upper()
        self._plugins[proto_key] = plugin

    def get_plugin(self, protocol_name: str) -> Optional[ProtocolPlugin]:
        """Returns registered ProtocolPlugin for protocol name."""
        return self._plugins.get(protocol_name.upper())

    def get_engine_class(self, protocol_name: str) -> Optional[Type[BaseProtocolEngine]]:
        """Returns BaseProtocolEngine class for protocol name if registered."""
        plugin = self.get_plugin(protocol_name)
        return plugin.engine_class if plugin else None

    def list_protocols(self) -> List[str]:
        """Returns list of registered protocol names."""
        return list(self._plugins.keys())

    def discover_plugins(self):
        """Scans plugins package directory and registers all ProtocolPlugin subclasses."""
        plugins_dir = os.path.dirname(os.path.abspath(__file__))
        for _, module_name, is_pkg in pkgutil.iter_modules([plugins_dir]):
            if module_name in ("plugin_base", "plugin_manager"):
                continue
            try:
                mod = importlib.import_module(f"pyremotempc.plugins.{module_name}")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, ProtocolPlugin) and 
                        attr is not ProtocolPlugin):
                        plugin_inst = attr()
                        self.register_plugin(plugin_inst)
            except Exception as e:
                print(f"Failed to load plugin '{module_name}': {e}")
