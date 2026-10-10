import xml.etree.ElementTree as ET
import os
from typing import Optional
from pyremotempc.config.models import ConnectionNode


class RdcmanXmlParser:
    """
    Parser for Microsoft Remote Desktop Connection Manager (RDCMan) .rdg XML export files.
    Extracts group hierarchy and RDP server connections.
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
        if root_elem.tag != "RDCMan":
            raise ValueError("Invalid RDCMan XML: root tag must be <RDCMan>")

        file_elem = root_elem.find("file")
        if file_elem is None:
            file_elem = root_elem

        root_node = ConnectionNode(name="Connections", node_type="Container", icon="Folder")

        for child in file_elem:
            tag = child.tag.lower()
            if tag == "group":
                folder_node = self._parse_group(child)
                if folder_node:
                    folder_node.parent_id = root_node.id
                    root_node.children.append(folder_node)
            elif tag == "server":
                server_node = self._parse_server(child)
                if server_node:
                    server_node.parent_id = root_node.id
                    root_node.children.append(server_node)

        return root_node

    def _parse_group(self, group_elem: ET.Element) -> ConnectionNode:
        props_elem = group_elem.find("properties")
        group_name = "Folder"
        if props_elem is not None:
            name_elem = props_elem.find("name")
            if name_elem is not None and name_elem.text:
                group_name = name_elem.text.strip()

        folder_node = ConnectionNode(name=group_name, node_type="Container", icon="Folder")

        for child in group_elem:
            tag = child.tag.lower()
            if tag == "group":
                child_folder = self._parse_group(child)
                if child_folder:
                    child_folder.parent_id = folder_node.id
                    folder_node.children.append(child_folder)
            elif tag == "server":
                child_server = self._parse_server(child)
                if child_server:
                    child_server.parent_id = folder_node.id
                    folder_node.children.append(child_server)

        return folder_node

    def _parse_server(self, server_elem: ET.Element) -> ConnectionNode:
        props_elem = server_elem.find("properties")
        server_name = ""
        display_name = ""
        comment = ""
        port = 3389

        if props_elem is not None:
            name_el = props_elem.find("name")
            if name_el is not None and name_el.text:
                server_name = name_el.text.strip()

            disp_el = props_elem.find("displayName")
            if disp_el is not None and disp_el.text:
                display_name = disp_el.text.strip()

            comm_el = props_elem.find("comment")
            if comm_el is not None and comm_el.text:
                comment = comm_el.text.strip()

            port_el = props_elem.find("port")
            if port_el is not None and port_el.text and port_el.text.isdigit():
                port = int(port_el.text.strip())

        node_name = display_name if display_name else (server_name if server_name else "RDP Server")
        hostname = server_name if server_name else display_name

        username = ""
        domain = ""
        creds_elem = server_elem.find("logonCredentials")
        if creds_elem is not None:
            user_el = creds_elem.find("userName")
            if user_el is not None and user_el.text:
                username = user_el.text.strip()

            dom_el = creds_elem.find("domain")
            if dom_el is not None and dom_el.text:
                domain = dom_el.text.strip()

        node = ConnectionNode(
            name=node_name,
            node_type="Connection",
            hostname=hostname,
            protocol="RDP",
            port=port,
            username=username,
            domain=domain,
            password="",  # DPAPI encrypted in RDCMan, left empty for security
            description=comment,
            icon="Windows"
        )

        return node
