import os
from PySide6.QtGui import QIcon

ICON_DIR = os.path.join(os.path.dirname(__file__), "iconos")


def get_icon(name: str, fallback_theme: str = "") -> QIcon:
    """
    Returns QIcon from pyremotempc/ui/iconos/<name>.png if present,
    falling back to QIcon.fromTheme(fallback_theme) or empty QIcon.
    """
    path = os.path.join(ICON_DIR, f"{name}.png")
    if os.path.exists(path):
        return QIcon(path)
    
    if not name.endswith(".png"):
        path_png = os.path.join(ICON_DIR, f"{name}.png")
        if os.path.exists(path_png):
            return QIcon(path_png)

    if fallback_theme:
        icon = QIcon.fromTheme(fallback_theme)
        if not icon.isNull():
            return icon

    return QIcon()


def get_node_icon(node) -> QIcon:
    """
    Returns the appropriate QIcon for a ConnectionNode.
    - Quick Connect sessions (node.is_quick_connect == True): icon is determined strictly by protocol.
    - Saved Connections: icon is determined by node.icon set by the user in the 'Icon:' field.
    """
    if not node:
        return get_icon("server")

    is_quick_connect = getattr(node, "is_quick_connect", False)
    is_cont = getattr(node, "is_container", lambda: False)()
    proto = (getattr(node, "protocol", "") or "").upper()

    # 1. Defaults for container folders
    if is_cont:
        if (getattr(node, "parent_id", None) is None) or (getattr(node, "name", "").lower() in ("connections", "conexiones")):
            return get_icon("connections")
        icon_name = (getattr(node, "icon", "") or "").strip().lower()
        if icon_name and "folder" not in icon_name and icon_name not in ("default", ""):
            ic = get_icon(icon_name)
            if not ic.isNull():
                return ic
        return get_icon("folder")

    # 2. Quick Connect sessions: STRICTLY protocol-based icon
    if is_quick_connect:
        if proto == "RDP":
            return get_icon("windows")
        elif proto in ("SSH2", "SSH1", "SSH"):
            return get_icon("linux")
        elif proto == "TELNET":
            return get_icon("terminal")
        elif proto == "VNC":
            return get_icon("vnc")
        elif proto in ("SFTP", "FTP", "SCP"):
            return get_icon("ftp")
        elif proto in ("SERIAL", "COM1", "TTY"):
            return get_icon("serial")
        return get_icon("server")

    # 3. Saved Connections: User-defined icon in 'Icon:' field
    icon_name = (getattr(node, "icon", "") or "").strip().lower()
    if icon_name:
        if "connections" in icon_name:
            return get_icon("connections")
        if "linux" in icon_name:
            return get_icon("linux")
        if "windows" in icon_name:
            return get_icon("windows")
        if "terminal" in icon_name or "shell" in icon_name:
            return get_icon("terminal")
        if "vnc" in icon_name:
            return get_icon("vnc")
        if "serial" in icon_name or "tty" in icon_name or "com" in icon_name:
            return get_icon("serial")
        if "ftp" in icon_name or "sftp" in icon_name:
            return get_icon("ftp")
        if "router" in icon_name or "switch" in icon_name or "network" in icon_name:
            return get_icon("network")
        if "vm" in icon_name:
            return get_icon("vm")
        if "storage" in icon_name:
            return get_icon("storage")
        if "database" in icon_name:
            return get_icon("database")
        if "server" in icon_name:
            return get_icon("server")

        ic = get_icon(icon_name)
        if not ic.isNull():
            return ic

    # Fallback to protocol icon if icon_name is empty
    if proto == "RDP":
        return get_icon("windows")
    elif proto in ("SSH2", "SSH1", "SSH"):
        return get_icon("linux")
    elif proto == "TELNET":
        return get_icon("terminal")
    elif proto == "VNC":
        return get_icon("vnc")
    elif proto in ("SFTP", "FTP", "SCP"):
        return get_icon("ftp")
    elif proto in ("SERIAL", "COM1", "TTY"):
        return get_icon("serial")

    return get_icon("server")
