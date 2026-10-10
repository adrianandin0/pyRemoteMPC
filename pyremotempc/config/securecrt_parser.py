import xml.etree.ElementTree as ET
import os
from typing import Tuple, List, Optional, Dict
from pyremotempc.config.models import ConnectionNode


class SecureCRTXmlParser:
    """
    Parser for SecureCRT / VanDyke XML connection export files.
    Extracts folder hierarchy and connection sessions (SSH2, SSH1, Telnet, RDP, VNC, Serial, RAW),
    ignoring application-specific UI/printing/cipher settings.
    """

    def parse_file(self, file_path: str) -> ConnectionNode:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        tree = ET.parse(file_path)
        root_elem = tree.getroot()
        return self.parse_element(root_elem)

    def parse_string(self, xml_content: str) -> ConnectionNode:
        root_elem = ET.fromstring(xml_content)
        return self.parse_element(root_elem)

    def parse_element(self, root_elem: ET.Element) -> ConnectionNode:
        if root_elem.tag != "VanDyke":
            raise ValueError("Invalid SecureCRT XML: root tag must be <VanDyke>")

        # Find <key name="Sessions">
        sessions_key = None
        for key in root_elem.findall("key"):
            if key.attrib.get("name") == "Sessions":
                sessions_key = key
                break

        if sessions_key is None:
            sessions_key = root_elem

        root_node = ConnectionNode(name="Connections", node_type="Container", icon="Folder")

        for child_key in sessions_key.findall("key"):
            key_name = child_key.attrib.get("name", "")
            if key_name == "Default":
                # Skip template Default session
                continue
            
            node = self._parse_key(child_key)
            if node:
                node.parent_id = root_node.id
                root_node.children.append(node)

        return root_node

    def _parse_key(self, key_elem: ET.Element) -> Optional[ConnectionNode]:
        key_name = key_elem.attrib.get("name", "Unnamed")

        # Collect child keys and properties
        child_keys = key_elem.findall("key")
        
        strings: Dict[str, str] = {}
        dwords: Dict[str, str] = {}
        arrays: Dict[str, List[str]] = {}

        for s in key_elem.findall("string"):
            name = s.attrib.get("name")
            if name:
                strings[name] = s.text or ""

        for d in key_elem.findall("dword"):
            name = d.attrib.get("name")
            if name:
                dwords[name] = d.text or ""

        for a in key_elem.findall("array"):
            name = a.attrib.get("name")
            if name:
                items = [str_item.text or "" for str_item in a.findall("string")]
                arrays[name] = items

        is_session_val = dwords.get("Is Session", "0")
        is_session = is_session_val == "1"

        if is_session:
            # It's a Connection
            hostname = strings.get("Hostname", "")
            protocol_raw = strings.get("Protocol Name", "SSH2").upper()
            
            # Map protocol
            if "SSH2" in protocol_raw:
                protocol = "SSH2"
            elif "SSH1" in protocol_raw:
                protocol = "SSH1"
            elif "TELNET" in protocol_raw:
                protocol = "Telnet"
            elif "RDP" in protocol_raw:
                protocol = "RDP"
            elif "VNC" in protocol_raw:
                protocol = "VNC"
            elif "SERIAL" in protocol_raw:
                protocol = "Serial"
            elif "RAW" in protocol_raw:
                protocol = "RAW"
            else:
                protocol = protocol_raw if protocol_raw else "SSH2"

            # Port resolution
            port = 22
            port_found = False
            for dw_name, dw_val in dwords.items():
                if "port" in dw_name.lower() and dw_val:
                    try:
                        port = int(dw_val, 0)
                        port_found = True
                        break
                    except ValueError:
                        pass
            
            if not port_found:
                port_str = strings.get("Port", "")
                if port_str.isdigit():
                    port = int(port_str)
                else:
                    port = 22 if "SSH" in protocol else (23 if protocol == "Telnet" else (3389 if protocol == "RDP" else 5900))

            username = strings.get("Username", "")
            
            # Description
            descr_list = arrays.get("Description", [])
            description = "\n".join(descr_list) if descr_list else ""

            node = ConnectionNode(
                name=key_name,
                node_type="Connection",
                hostname=hostname,
                protocol=protocol,
                port=port,
                username=username,
                password="",  # Left blank for security
                description=description,
                icon="Server"
            )

            # Extra protocol-specific mapping if needed
            if protocol == "Serial":
                node.serial_port = strings.get("Com Port", "/dev/ttyUSB0")
                baud_str = dwords.get("Printer Baud Rate", dwords.get("Baud Rate", "9600"))
                if baud_str.isdigit():
                    node.baudrate = int(baud_str)

            return node
        else:
            # It's a Container (Folder)
            folder_node = ConnectionNode(
                name=key_name,
                node_type="Container",
                icon="Folder"
            )
            for child_key in child_keys:
                child_node = self._parse_key(child_key)
                if child_node:
                    child_node.parent_id = folder_node.id
                    folder_node.children.append(child_node)
            return folder_node
