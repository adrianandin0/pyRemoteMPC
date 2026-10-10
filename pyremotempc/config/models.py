from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import uuid


@dataclass
class ConnectionNode:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Connection"
    node_type: str = "Connection"  # "Container" or "Connection"
    is_expanded: bool = False

    # Connection parameters
    hostname: str = ""
    protocol: str = "SSH2"  # RDP, SSH2, SSH1, VNC, Telnet, HTTP, HTTPS, RAW
    port: int = 22
    username: str = ""
    password: str = ""
    domain: str = ""
    description: str = ""
    icon: str = "Server"
    auto_reconnect: bool = False

    # SSH Specific
    legacy_ssh: bool = False  # Allows old ciphers, kex, host keys for legacy switches/servers
    agent_forwarding: bool = False  # Enables SSH Agent Forwarding (-A)
    auth_method: str = "password"  # password, key, agent, interactive
    key_path: str = ""
    key_passphrase: str = ""
    ssh_version: str = "Auto"  # Auto, SSH2, SSH1
    private_key_file: str = ""  # Backward compatibility alias for key_path

    # RDP Specific
    resolution: str = "FitToWindow"  # FitToWindow, SmartSizing, 1920x1080, etc.
    colors: str = "Colors32Bit"
    rdp_security: str = "Auto"  # Auto, NLA, RDP, TLS
    rdp_cert_ignore: bool = True  # Ignore untrusted SSL/TLS certificates
    rdp_cert_path: str = ""  # Path to custom SSL Certificate / CA bundle
    redirect_sound: str = "BringToThisComputer"
    redirect_drives: bool = True
    redirect_printers: bool = False
    redirect_clipboard: bool = True
    rdp_shared_folder: str = ""  # Optional per-connection local folder path override

    # VNC Specific
    vnc_engine_type: str = "Auto"  # Auto, Native, System
    vnc_sec_type: str = "Auto"  # Auto, Standard (Type 2), UltraVNC MSLogon (Type 11), None (Type 1)

    # Serial Specific
    serial_port: str = "/dev/ttyUSB0"
    baudrate: int = 9600
    data_bits: int = 8
    parity: str = "N"  # N, E, O, M, S
    stop_bits: float = 1.0  # 1, 1.5, 2
    flow_control: str = "None"  # None, RTS/CTS, XON/XOFF


    # Folder / Inheritance
    parent_id: Optional[str] = None
    children: List["ConnectionNode"] = field(default_factory=list)
    inheritance: Dict[str, bool] = field(default_factory=dict)

    def is_container(self) -> bool:
        return self.node_type.lower() in ("container", "folder") or self.parent_id is None or (self.name and self.name.lower() in ("connections", "conexiones"))

    def get_effective_property(self, prop_name: str, parent_node: Optional["ConnectionNode"] = None) -> Any:
        """Resolves property with mRemoteNG inheritance rules."""
        val = getattr(self, prop_name, None)
        if (val is None or val == "") and parent_node:
            return parent_node.get_effective_property(prop_name, getattr(parent_node, "parent", None))
        return val

    def to_dict(self) -> Dict[str, Any]:
        """Serializes node to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type,
            "hostname": self.hostname,
            "protocol": self.protocol,
            "port": self.port,
            "username": self.username,
            "domain": self.domain,
            "description": self.description,
            "icon": self.icon,
            "auto_reconnect": self.auto_reconnect,
            "legacy_ssh": self.legacy_ssh,
            "agent_forwarding": self.agent_forwarding,
            "auth_method": self.auth_method,
            "key_path": self.key_path or self.private_key_file,
            "key_passphrase": self.key_passphrase,
            "ssh_version": self.ssh_version,
            "resolution": self.resolution,
            "rdp_security": self.rdp_security,
            "redirect_drives": self.redirect_drives,
            "serial_port": self.serial_port,
            "baudrate": self.baudrate,
            "data_bits": self.data_bits,
            "parity": self.parity,
            "stop_bits": self.stop_bits,
            "flow_control": self.flow_control,
            "children": [child.to_dict() for child in self.children],
        }
