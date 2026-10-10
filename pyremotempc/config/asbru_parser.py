import os
import re
from typing import Optional, Dict, Any, List
from pyremotempc.config.models import ConnectionNode

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def _parse_yaml_fallback(yaml_content: str) -> dict:
    """Fallback indent-based parser for Asbrú YAML files if PyYAML is not installed."""
    data = {}
    dict_stack = [data]
    indent_stack = [-1]

    for line in yaml_content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue

        indent = len(line) - len(line.lstrip(" "))
        
        while len(indent_stack) > 1 and indent <= indent_stack[-1]:
            indent_stack.pop()
            dict_stack.pop()

        target_dict = dict_stack[-1]

        if ":" in stripped:
            k, v = stripped.split(":", 1)
            k = k.strip().strip("'\"")
            v = v.strip()

            if v == "" or v == "~":
                new_dict = {}
                target_dict[k] = new_dict
                dict_stack.append(new_dict)
                indent_stack.append(indent)
            elif v.startswith("[") and v.endswith("]"):
                target_dict[k] = []
            elif v.startswith("{") and v.endswith("}"):
                target_dict[k] = {}
            else:
                if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
                    val = v[1:-1]
                elif v.isdigit():
                    val = int(v)
                else:
                    val = v
                target_dict[k] = val
    return data


class AsbruYamlParser:
    """
    Parser for Asbrú Connection Manager YAML export files (.yml / .yaml / .txt).
    Extracts group hierarchy and SSH/Telnet/RDP/VNC sessions,
    cleaning exported '- copy' suffixes added by Asbrú export function.
    """

    def parse_file(self, file_path: str) -> ConnectionNode:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return self.parse_string(content)

    def parse_string(self, yaml_content: str) -> ConnectionNode:
        if HAS_YAML:
            data = yaml.safe_load(yaml_content)
        else:
            data = _parse_yaml_fallback(yaml_content)

        if not isinstance(data, dict):
            raise ValueError("Invalid Asbrú YAML: top-level element is not a mapping")
        return self.parse_dict(data)

    def parse_dict(self, data: Dict[str, Any]) -> ConnectionNode:
        root_node = ConnectionNode(name="Connections", node_type="Container", icon="Folder")

        top_ids: List[str] = []

        exported = data.get("__PAC__EXPORTED__")
        root_pac = data.get("__PAC__ROOT__")

        if isinstance(exported, dict) and "children" in exported:
            children = exported["children"]
            if isinstance(children, dict):
                top_ids = list(children.keys())
            elif isinstance(children, list):
                top_ids = children

        if not top_ids and isinstance(root_pac, dict) and "children" in root_pac:
            children = root_pac["children"]
            if isinstance(children, dict):
                top_ids = list(children.keys())
            elif isinstance(children, list):
                top_ids = children

        if not top_ids:
            for k, v in data.items():
                if k.startswith("__PAC__") or not isinstance(v, dict):
                    continue
                parent = v.get("parent", "")
                if parent in ("__PAC__EXPORTED__", "__PAC__ROOT__", "") or parent not in data:
                    top_ids.append(k)

        visited = set()
        for node_id in top_ids:
            node = self._parse_node(data, node_id, visited)
            if node:
                node.parent_id = root_node.id
                root_node.children.append(node)

        return root_node

    def _parse_node(self, data: Dict[str, Any], node_id: str, visited: set) -> Optional[ConnectionNode]:
        if node_id in visited or node_id not in data:
            return None
        visited.add(node_id)

        node_dict = data[node_id]
        if not isinstance(node_dict, dict):
            return None

        is_group = node_dict.get("_is_group", 0) == 1
        raw_name = str(node_dict.get("name", "Unnamed")).strip()
        description = str(node_dict.get("description", "")).strip()
        title = str(node_dict.get("title", "")).strip()

        # Clean name resolution logic for Asbrú exports:
        # Asbrú appends '- copy' to the 'name' attribute during file export.
        if is_group:
            m = re.search(r"Connection group ['\"](.*?)['\"]", description)
            if m and m.group(1):
                clean_name = m.group(1).strip()
            elif raw_name.endswith(" - copy"):
                clean_name = raw_name[:-7].strip()
            else:
                clean_name = raw_name
        else:
            if title and raw_name.endswith(" - copy - copy"):
                clean_name = f"{title} - copy"
            elif title and raw_name.endswith(" - copy"):
                clean_name = title
            elif raw_name.endswith(" - copy"):
                clean_name = raw_name[:-7].strip()
            else:
                clean_name = title if title else raw_name

        if is_group:
            folder_node = ConnectionNode(
                name=clean_name,
                node_type="Container",
                icon="Folder"
            )
            children = node_dict.get("children", {})
            child_ids = []
            if isinstance(children, dict):
                child_ids = list(children.keys())
            elif isinstance(children, list):
                child_ids = children

            for child_id in child_ids:
                child_node = self._parse_node(data, child_id, visited)
                if child_node:
                    child_node.parent_id = folder_node.id
                    folder_node.children.append(child_node)

            return folder_node
        else:
            hostname = str(node_dict.get("ip", title if title else raw_name))
            method_raw = str(node_dict.get("method", "SSH")).upper()

            if "SSH" in method_raw:
                protocol = "SSH2"
            elif "TELNET" in method_raw:
                protocol = "Telnet"
            elif "RDP" in method_raw:
                protocol = "RDP"
            elif "VNC" in method_raw:
                protocol = "VNC"
            elif "SERIAL" in method_raw:
                protocol = "Serial"
            elif "RAW" in method_raw:
                protocol = "RAW"
            else:
                protocol = method_raw if method_raw else "SSH2"

            port = 22
            port_val = node_dict.get("port")
            if port_val is not None:
                try:
                    port = int(port_val)
                except ValueError:
                    pass

            username = str(node_dict.get("user", ""))
            password = str(node_dict.get("pass", ""))
            key_path = str(node_dict.get("public key", ""))

            node = ConnectionNode(
                name=clean_name,
                node_type="Connection",
                hostname=hostname,
                protocol=protocol,
                port=port,
                username=username,
                password=password,
                key_path=key_path,
                description=description,
                icon="Server"
            )
            if key_path:
                node.auth_method = "key"

            return node
