import xml.etree.ElementTree as ET
import os
import shutil
from typing import Tuple, List, Optional
from pyremotempc.config.models import ConnectionNode
from pyremotempc.crypto.aead_gcm import decrypt_aead_password, encrypt_aead_password
from pyremotempc.crypto.rijndael_legacy import decrypt_legacy_password, encrypt_legacy_password


def _clean_tag(tag: str) -> str:
    """Strips XML namespaces from tag strings."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _get_case_insensitive_attr(elem: ET.Element, candidate_names: List[str], default: str = "") -> str:
    """Retrieves attribute value by checking candidate names in a case-insensitive manner."""
    for key, val in elem.attrib.items():
        clean_key = _clean_tag(key).lower()
        for cand in candidate_names:
            if clean_key == cand.lower():
                return val
    return default


class mRemoteNGXmlParser:
    """
    Parser and Exporter for mRemoteNG XML connection trees (confCons.xml).
    Supports AEAD GCM (v2.6+) and Legacy Rijndael CBC encryption/decryption.
    """

    def __init__(self, master_password: str = "mR3m", skip_passwords: bool = False):
        self.master_password = master_password
        self.skip_passwords = skip_passwords

    def parse_file(self, file_path: str, is_import: bool = False) -> Tuple[ConnectionNode, str]:
        """Parses an mRemoteNG XML file and returns (root_node, version)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"XML file not found: {file_path}")

        tree = ET.parse(file_path)
        root_elem = tree.getroot()

        version = _get_case_insensitive_attr(root_elem, ["ConfVersion", "version"], "2.5")
        iter_str = _get_case_insensitive_attr(root_elem, ["KdfIterations"], "1000")
        iterations = int(iter_str) if iter_str.isdigit() else 1000

        root_tag = _clean_tag(root_elem.tag).lower()
        if root_tag in ("connections", "mremoteng"):
            root_node = self._parse_node(root_elem, version, iterations, is_import=is_import, is_root=True)
        else:
            root_node_elem = self._find_first_node(root_elem)
            root_node = self._parse_node(root_node_elem if root_node_elem is not None else root_elem, version, iterations, is_import=is_import, is_root=True)

        # Post-process inheritance down the tree
        self._apply_inheritance(root_node)

        return root_node, version

    def parse_string(self, xml_content: str, is_import: bool = False) -> Tuple[ConnectionNode, str]:
        """Parses XML string and returns (root_node, version)."""
        root_elem = ET.fromstring(xml_content)
        version = _get_case_insensitive_attr(root_elem, ["ConfVersion", "version"], "2.5")
        iter_str = _get_case_insensitive_attr(root_elem, ["KdfIterations"], "1000")
        iterations = int(iter_str) if iter_str.isdigit() else 1000

        root_tag = _clean_tag(root_elem.tag).lower()
        if root_tag in ("connections", "mremoteng"):
            root_node = self._parse_node(root_elem, version, iterations, is_import=is_import, is_root=True)
        else:
            root_node_elem = self._find_first_node(root_elem)
            root_node = self._parse_node(root_node_elem if root_node_elem is not None else root_elem, version, iterations, is_import=is_import, is_root=True)

        self._apply_inheritance(root_node)
        return root_node, version

    def _find_first_node(self, parent: ET.Element) -> Optional[ET.Element]:
        for child in parent:
            if _clean_tag(child.tag).lower() == "node":
                return child
        return None

    def _find_all_child_nodes(self, parent: ET.Element) -> List[ET.Element]:
        return [child for child in parent if _clean_tag(child.tag).lower() == "node"]

    def _decrypt_str(self, encrypted_val: str, version: str, iterations: int = 1000) -> str:
        if not encrypted_val:
            return ""

        # Try AEAD GCM decrypt first if version >= 2.6
        if float(version) >= 2.6 if version.replace('.', '', 1).isdigit() else False:
            decrypted = decrypt_aead_password(encrypted_val, self.master_password, iterations=iterations)
            if decrypted != encrypted_val and decrypted:
                return decrypted

        # Fallback to Legacy Rijndael
        decrypted = decrypt_legacy_password(encrypted_val, self.master_password)
        return decrypted

    def _parse_node(self, elem: ET.Element, version: str, iterations: int = 1000, is_import: bool = False, is_root: bool = False) -> ConnectionNode:
        name = _get_case_insensitive_attr(elem, ["Name"], "Unnamed")
        tag_clean = _clean_tag(elem.tag).lower()
        if tag_clean in ("connections", "mremoteng") or name.lower() in ("connections", "conexiones"):
            node_type = "Container"
        else:
            node_type = _get_case_insensitive_attr(elem, ["Type"], "Connection")
        hostname = _get_case_insensitive_attr(elem, ["Hostname", "Host", "IP", "IPAddress", "Server"])
        protocol = _get_case_insensitive_attr(elem, ["Protocol", "Proto"], "SSH2").upper()

        port_str = _get_case_insensitive_attr(elem, ["Port"])
        if port_str and port_str.isdigit():
            port = int(port_str)
        else:
            port = 22 if "SSH" in protocol else (3389 if protocol == "RDP" else 5900)

        username = _get_case_insensitive_attr(elem, ["Username", "User"])
        
        # If skip_passwords is True or importing from external mRemoteNG XML, passwords are left blank.
        # If loading pyRemoteMPC's own saved connections with valid password, passwords are decrypted and preserved.
        raw_password = _get_case_insensitive_attr(elem, ["Password", "Pass"])
        password = ""
        if raw_password and not self.skip_passwords:
            decrypted = self._decrypt_str(raw_password, version, iterations)
            if decrypted and decrypted != raw_password:
                password = decrypted
            elif not is_import:
                password = raw_password

        domain = _get_case_insensitive_attr(elem, ["Domain"])
        description = _get_case_insensitive_attr(elem, ["Descr", "Description"])
        icon = _get_case_insensitive_attr(elem, ["Icon"], "Server" if node_type == "Connection" else "Folder")

        node_id = _get_case_insensitive_attr(elem, ["Id", "UniqueIdentifier"])

        # Flags & Inheritance
        inherit_user = _get_case_insensitive_attr(elem, ["InheritUsername"], "False").lower() == "true"
        inherit_pass = _get_case_insensitive_attr(elem, ["InheritPassword"], "False").lower() == "true"
        inherit_domain = _get_case_insensitive_attr(elem, ["InheritDomain"], "False").lower() == "true"
        inherit_port = _get_case_insensitive_attr(elem, ["InheritPort"], "False").lower() == "true"
        inherit_proto = _get_case_insensitive_attr(elem, ["InheritProtocol"], "False").lower() == "true"

        inheritance = {
            "username": inherit_user,
            "password": inherit_pass,
            "domain": inherit_domain,
            "port": inherit_port,
            "protocol": inherit_proto,
        }

        node = ConnectionNode(
            name=name,
            node_type=node_type,
            hostname=hostname,
            protocol=protocol,
            port=port,
            username=username,
            password=password,
            domain=domain,
            description=description,
            icon=icon,
            inheritance=inheritance
        )
        if node_id:
            node.id = node_id
        elif is_root:
            node.id = f"ROOT_{name.strip()}"

        for child_elem in self._find_all_child_nodes(elem):
            child_node = self._parse_node(child_elem, version, iterations, is_import=is_import)
            child_node.parent_id = node.id
            node.children.append(child_node)

        return node

    def _apply_inheritance(self, parent_node: ConnectionNode):
        """Recursively applies parent folder properties to child nodes when explicitly inherited."""
        for child in parent_node.children:
            if child.inheritance.get("username") or not child.username:
                if parent_node.username:
                    child.username = parent_node.username

            if child.inheritance.get("password") or not child.password:
                if parent_node.password:
                    child.password = parent_node.password

            if child.inheritance.get("domain") or not child.domain:
                if parent_node.domain:
                    child.domain = parent_node.domain

            if child.inheritance.get("protocol") or not child.protocol:
                if parent_node.protocol:
                    child.protocol = parent_node.protocol

            if child.inheritance.get("port"):
                if parent_node.port:
                    child.port = parent_node.port

            if not child.hostname and parent_node.hostname:
                child.hostname = parent_node.hostname

            if child.is_container():
                self._apply_inheritance(child)

    def export_to_file(self, root_node: ConnectionNode, file_path: str, version: str = "2.5") -> None:
        """
        Exports a ConnectionNode tree to an mRemoteNG XML file atomically.
        Writes to a temporary file in the same directory, flushes and syncs to disk,
        creates a .bak backup of the existing file, and uses os.replace for atomic overwrite.
        """
        root_elem = ET.Element("Connections", {
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
            "Name": root_node.name if root_node.name else "Connections",
            "Export": "False",
            "ConfVersion": version
        })

        for child in root_node.children:
            root_elem.append(self._serialize_node(child, version))

        tree = ET.ElementTree(root_elem)
        ET.indent(tree, space="  ")

        dir_name = os.path.dirname(os.path.abspath(file_path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        tmp_path = f"{file_path}.tmp"
        bak_path = f"{file_path}.bak"

        # 1. Write completely to temporary file and sync to disk
        with open(tmp_path, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)
            f.flush()
            os.fsync(f.fileno())

        # 2. Backup existing file safely if it exists and has content
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            try:
                shutil.copy2(file_path, bak_path)
            except Exception:
                pass

        # 3. Atomic replacement on filesystem level
        os.replace(tmp_path, file_path)

    def _serialize_node(self, node: ConnectionNode, version: str) -> ET.Element:
        enc_pass = ""
        if node.password:
            if float(version) >= 2.6 if version.replace('.', '', 1).isdigit() else False:
                enc_pass = encrypt_aead_password(node.password, self.master_password)
            else:
                enc_pass = encrypt_legacy_password(node.password, self.master_password)

        attrs = {
            "Name": node.name,
            "Type": node.node_type,
            "Descr": node.description,
            "Icon": node.icon,
            "Id": node.id,
            "Hostname": node.hostname,
            "Protocol": node.protocol,
            "Port": str(node.port),
            "Username": node.username,
            "Password": enc_pass,
            "Domain": node.domain,
        }

        elem = ET.Element("Node", attrs)
        for child in node.children:
            elem.append(self._serialize_node(child, version))

        return elem
