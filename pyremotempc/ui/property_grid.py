from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QScrollArea, QLabel
)
import os
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSize
from pyremotempc.config.models import ConnectionNode
from pyremotempc.ui.icon_manager import get_icon
from pyremotempc.plugins.plugin_manager import PluginManager
from pyremotempc.utils.serial_utils import get_available_serial_ports


class PropertyGridScrollContent(QWidget):
    """Container widget for QScrollArea that returns a 0 width sizeHint & minimumSizeHint so QScrollArea never overflows horizontally."""
    def sizeHint(self):
        s = super().sizeHint()
        return QSize(0, s.height())

    def minimumSizeHint(self):
        s = super().minimumSizeHint()
        return QSize(0, s.height())


class PropertyGridWidget(QWidget):
    """
    Property Grid Inspector Panel for selected connection/folder.
    Updates dynamically whenever a node is selected in the tree.
    All input fields expand fluidly to fill the sidebar width.
    """
    property_changed = Signal(ConnectionNode)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_node: ConnectionNode = None
        self.loading: bool = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = PropertyGridScrollContent()
        
        self.form_layout = QFormLayout(scroll_content)
        self.form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form_layout.setContentsMargins(6, 6, 10, 6)
        self.form_layout.setSpacing(6)

        # General Group
        self.lbl_name = QLabel("Name:")
        self.txt_name = QLineEdit()
        self.txt_name.setMinimumWidth(30)
        self.txt_name.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_name, self.txt_name)

        self.lbl_description = QLabel("Description:")
        self.txt_description = QLineEdit()
        self.txt_description.setMinimumWidth(30)
        self.txt_description.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_description, self.txt_description)

        self.lbl_icon = QLabel("Icon:")
        self.cmb_icon = QComboBox()
        self.cmb_icon.setMinimumWidth(30)
        self.cmb_icon.addItem(get_icon("connections"), "Connections")
        self.cmb_icon.addItem(get_icon("folder"), "Folder")
        self.cmb_icon.addItem(get_icon("server"), "Server")
        self.cmb_icon.addItem(get_icon("linux"), "Linux")
        self.cmb_icon.addItem(get_icon("windows"), "Windows")
        self.cmb_icon.addItem(get_icon("terminal"), "Terminal")
        self.cmb_icon.addItem(get_icon("vnc"), "VNC")
        self.cmb_icon.addItem(get_icon("ftp"), "SFTP / FTP / SCP")
        self.cmb_icon.addItem(get_icon("network"), "Router")
        self.cmb_icon.addItem(get_icon("network"), "Switch")
        self.cmb_icon.addItem(get_icon("vm"), "VM")
        self.cmb_icon.addItem(get_icon("storage"), "Storage")
        self.cmb_icon.addItem(get_icon("database"), "Database")
        self.cmb_icon.addItem(get_icon("serial"), "Serial")
        self.cmb_icon.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_icon, self.cmb_icon)

        # Connection Group
        self.lbl_hostname = QLabel("Hostname / IP:")
        self.txt_hostname = QLineEdit()
        self.txt_hostname.setMinimumWidth(30)
        self.txt_hostname.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_hostname, self.txt_hostname)

        self.lbl_protocol = QLabel("Protocol:")
        self.cmb_protocol = QComboBox()
        self.cmb_protocol.setMinimumWidth(30)
        protocols = PluginManager.instance().list_protocols()
        if protocols:
            self.cmb_protocol.addItems(protocols)
        else:
            self.cmb_protocol.addItems(["SSH", "SSH1", "RDP", "VNC", "TELNET"])
        self.cmb_protocol.currentTextChanged.connect(self._on_protocol_changed)
        self.form_layout.addRow(self.lbl_protocol, self.cmb_protocol)

        self.lbl_port = QLabel("Port:")
        self.spn_port = QSpinBox()
        self.spn_port.setMinimumWidth(30)
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(22)
        self.spn_port.valueChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_port, self.spn_port)

        # Credentials Group
        self.lbl_domain = QLabel("Domain:")
        self.txt_domain = QLineEdit()
        self.txt_domain.setMinimumWidth(30)
        self.txt_domain.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_domain, self.txt_domain)

        self.lbl_username = QLabel("Username:")
        self.txt_username = QLineEdit()
        self.txt_username.setMinimumWidth(30)
        self.txt_username.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_username, self.txt_username)

        self.lbl_password = QLabel("Password:")
        self.txt_password = QLineEdit()
        self.txt_password.setMinimumWidth(30)
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_password, self.txt_password)

        # Private Key File Layout
        self.lbl_private_key = QLabel("Private Key File:")
        self.txt_private_key = QLineEdit()
        self.txt_private_key.setMinimumWidth(30)
        self.txt_private_key.textChanged.connect(self._on_field_edited)
        self.btn_browse_key = QPushButton("...")
        self.btn_browse_key.setFixedWidth(26)
        self.btn_browse_key.clicked.connect(self._on_browse_key)
        
        self.key_container = QWidget()
        key_layout = QHBoxLayout(self.key_container)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(2)
        key_layout.addWidget(self.txt_private_key)
        key_layout.addWidget(self.btn_browse_key)
        self.form_layout.addRow(self.lbl_private_key, self.key_container)

        # Protocol Specific Settings
        self.lbl_auto_reconnect = QLabel("Auto Reconnect:")
        self.chk_auto_reconnect = QCheckBox("Enable Auto Reconnect on Drop")
        self.chk_auto_reconnect.toggled.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_auto_reconnect, self.chk_auto_reconnect)

        self.lbl_ssh_options = QLabel("SSH Options:")
        self.chk_legacy_ssh = QCheckBox("Enable Legacy Security")
        self.chk_legacy_ssh.setChecked(True)
        self.chk_legacy_ssh.toggled.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_ssh_options, self.chk_legacy_ssh)

        self.lbl_agent_forwarding = QLabel("SSH Agent:")
        self.chk_agent_forwarding = QCheckBox("Enable Agent Forwarding (-A)")
        self.chk_agent_forwarding.toggled.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_agent_forwarding, self.chk_agent_forwarding)

        self.lbl_rdp_sec = QLabel("RDP Security:")
        self.cmb_rdp_sec = QComboBox()
        self.cmb_rdp_sec.setMinimumWidth(30)
        self.cmb_rdp_sec.addItems(["Auto", "NLA", "RDP", "TLS"])
        self.cmb_rdp_sec.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_rdp_sec, self.cmb_rdp_sec)

        # RDP SSL Certificate Options
        self.lbl_rdp_cert_ignore = QLabel("RDP SSL Cert:")
        self.chk_rdp_cert_ignore = QCheckBox("Ignore Untrusted SSL Certs")
        self.chk_rdp_cert_ignore.setChecked(True)
        self.chk_rdp_cert_ignore.toggled.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_rdp_cert_ignore, self.chk_rdp_cert_ignore)

        self.lbl_rdp_cert_path = QLabel("Custom CA File:")
        self.txt_rdp_cert_path = QLineEdit()
        self.txt_rdp_cert_path.setMinimumWidth(30)
        self.txt_rdp_cert_path.setPlaceholderText("Path to custom CA / cert.crt")
        self.txt_rdp_cert_path.textChanged.connect(self._on_field_edited)
        self.btn_browse_cert = QPushButton("...")
        self.btn_browse_cert.setFixedWidth(26)
        self.btn_browse_cert.clicked.connect(self._on_browse_cert)

        self.cert_container = QWidget()
        cert_layout = QHBoxLayout(self.cert_container)
        cert_layout.setContentsMargins(0, 0, 0, 0)
        cert_layout.setSpacing(2)
        cert_layout.addWidget(self.txt_rdp_cert_path)
        cert_layout.addWidget(self.btn_browse_cert)
        self.form_layout.addRow(self.lbl_rdp_cert_path, self.cert_container)

        self.lbl_redirect_clipboard = QLabel("RDP Clipboard:")
        self.chk_redirect_clipboard = QCheckBox("Redirect Clipboard (+clipboard)")
        self.chk_redirect_clipboard.setChecked(True)
        self.chk_redirect_clipboard.toggled.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_redirect_clipboard, self.chk_redirect_clipboard)

        self.lbl_redirect_drives = QLabel("RDP Drive:")
        self.chk_redirect_drives = QCheckBox("Redirect Network Drive")
        self.chk_redirect_drives.setChecked(True)
        self.chk_redirect_drives.toggled.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_redirect_drives, self.chk_redirect_drives)

        self.lbl_rdp_shared_folder = QLabel("RDP Shared Folder:")
        self.txt_rdp_shared_folder = QLineEdit()
        self.txt_rdp_shared_folder.setMinimumWidth(30)
        self.txt_rdp_shared_folder.setPlaceholderText("Global default (~/RDP_Shared)")
        self.txt_rdp_shared_folder.textChanged.connect(self._on_field_edited)
        self.btn_browse_rdp_folder = QPushButton("...")
        self.btn_browse_rdp_folder.setFixedWidth(26)
        self.btn_browse_rdp_folder.clicked.connect(self._on_browse_rdp_folder)

        self.folder_container = QWidget()
        folder_layout = QHBoxLayout(self.folder_container)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(2)
        folder_layout.addWidget(self.txt_rdp_shared_folder)
        folder_layout.addWidget(self.btn_browse_rdp_folder)
        self.form_layout.addRow(self.lbl_rdp_shared_folder, self.folder_container)

        # VNC Specific Settings
        self.lbl_vnc_engine = QLabel("VNC Engine:")
        self.cmb_vnc_engine = QComboBox()
        self.cmb_vnc_engine.setMinimumWidth(30)
        self.cmb_vnc_engine.addItems(["Auto", "Native", "System (TigerVNC / Remmina)"])
        self.cmb_vnc_engine.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_vnc_engine, self.cmb_vnc_engine)

        self.lbl_vnc_sec = QLabel("VNC Security:")
        self.cmb_vnc_sec = QComboBox()
        self.cmb_vnc_sec.setMinimumWidth(30)
        self.cmb_vnc_sec.addItems(["Auto", "Standard VNC Auth (Type 2)", "UltraVNC MSLogon (Type 11)"])
        self.cmb_vnc_sec.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_vnc_sec, self.cmb_vnc_sec)

        # Serial Specific Settings
        self.lbl_serial_port = QLabel("Serial Port:")
        self.cmb_serial_port = QComboBox()
        self.cmb_serial_port.setMinimumWidth(30)
        self.cmb_serial_port.setEditable(True)

        self.btn_refresh_serial = QPushButton()
        self.btn_refresh_serial.setIcon(get_icon("refresh"))
        self.btn_refresh_serial.setIconSize(QSize(16, 16))
        self.btn_refresh_serial.setFixedSize(22, 22)
        self.btn_refresh_serial.setToolTip("Rescan / Refresh available serial ports")
        self.btn_refresh_serial.setStyleSheet(
            "QPushButton { border: none; background: transparent; padding: 2px; } "
            "QPushButton:hover { background-color: rgba(255, 255, 255, 30); border-radius: 3px; } "
            "QPushButton:pressed { background-color: rgba(255, 255, 255, 50); border-radius: 3px; }"
        )
        self.btn_refresh_serial.clicked.connect(self.refresh_serial_ports)

        self.serial_port_container = QWidget()
        serial_layout = QHBoxLayout(self.serial_port_container)
        serial_layout.setContentsMargins(0, 0, 0, 0)
        serial_layout.setSpacing(2)
        serial_layout.addWidget(self.cmb_serial_port)
        serial_layout.addWidget(self.btn_refresh_serial)

        self.refresh_serial_ports()
        self.cmb_serial_port.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_serial_port, self.serial_port_container)

        self.lbl_baudrate = QLabel("Baud Rate:")
        self.cmb_baudrate = QComboBox()
        self.cmb_baudrate.setMinimumWidth(30)
        self.cmb_baudrate.addItems(["9600", "115200", "57600", "38400", "19200", "14400", "4800", "2400", "1200", "600", "300", "110"])
        self.cmb_baudrate.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_baudrate, self.cmb_baudrate)

        self.lbl_data_bits = QLabel("Data Bits:")
        self.cmb_data_bits = QComboBox()
        self.cmb_data_bits.setMinimumWidth(30)
        self.cmb_data_bits.addItems(["8", "7", "6", "5"])
        self.cmb_data_bits.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_data_bits, self.cmb_data_bits)

        self.lbl_parity = QLabel("Parity:")
        self.cmb_parity = QComboBox()
        self.cmb_parity.setMinimumWidth(30)
        self.cmb_parity.addItems(["N (None)", "E (Even)", "O (Odd)", "M (Mark)", "S (Space)"])
        self.cmb_parity.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_parity, self.cmb_parity)

        self.lbl_stop_bits = QLabel("Stop Bits:")
        self.cmb_stop_bits = QComboBox()
        self.cmb_stop_bits.setMinimumWidth(30)
        self.cmb_stop_bits.addItems(["1", "1.5", "2"])
        self.cmb_stop_bits.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_stop_bits, self.cmb_stop_bits)

        self.lbl_flow_control = QLabel("Flow Control:")
        self.cmb_flow_control = QComboBox()
        self.cmb_flow_control.setMinimumWidth(30)
        self.cmb_flow_control.addItems(["None", "RTS/CTS", "XON/XOFF"])
        self.cmb_flow_control.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow(self.lbl_flow_control, self.cmb_flow_control)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def refresh_serial_ports(self):
        """Scans and updates available serial ports in combo box."""
        current = self.cmb_serial_port.currentText()
        self.cmb_serial_port.clear()
        ports = get_available_serial_ports()
        for dev, label in ports:
            self.cmb_serial_port.addItem(label, dev)
        if current and self.cmb_serial_port.findText(current) != -1:
            self.cmb_serial_port.setCurrentText(current)
        elif current and not current.startswith("No ports"):
            self.cmb_serial_port.setCurrentText(current)

    def _set_row_visible(self, label, field, visible: bool):
        label.setVisible(visible)
        field.setVisible(visible)

    def _update_field_visibilities(self):
        if not self.current_node:
            return

        is_container = self.current_node.is_container()

        # Name and Description are ALWAYS visible
        self._set_row_visible(self.lbl_name, self.txt_name, True)
        self._set_row_visible(self.lbl_description, self.txt_description, True)

        if is_container:
            # Container Nodes (Root "Connections" & Folders): ONLY Name, Description & Icon are visible
            self._set_row_visible(self.lbl_icon, self.cmb_icon, True)
            self._set_row_visible(self.lbl_hostname, self.txt_hostname, False)
            self._set_row_visible(self.lbl_protocol, self.cmb_protocol, False)
            self._set_row_visible(self.lbl_port, self.spn_port, False)
            self._set_row_visible(self.lbl_domain, self.txt_domain, False)
            self._set_row_visible(self.lbl_username, self.txt_username, False)
            self._set_row_visible(self.lbl_password, self.txt_password, False)
            self._set_row_visible(self.lbl_auto_reconnect, self.chk_auto_reconnect, False)

            # SSH
            self._set_row_visible(self.lbl_private_key, self.key_container, False)
            self._set_row_visible(self.lbl_ssh_options, self.chk_legacy_ssh, False)
            self._set_row_visible(self.lbl_agent_forwarding, self.chk_agent_forwarding, False)

            # RDP
            self._set_row_visible(self.lbl_rdp_sec, self.cmb_rdp_sec, False)
            self._set_row_visible(self.lbl_rdp_cert_ignore, self.chk_rdp_cert_ignore, False)
            self._set_row_visible(self.lbl_rdp_cert_path, self.cert_container, False)
            self._set_row_visible(self.lbl_redirect_clipboard, self.chk_redirect_clipboard, False)
            self._set_row_visible(self.lbl_redirect_drives, self.chk_redirect_drives, False)
            self._set_row_visible(self.lbl_rdp_shared_folder, self.folder_container, False)

            # VNC
            self._set_row_visible(self.lbl_vnc_engine, self.cmb_vnc_engine, False)
            self._set_row_visible(self.lbl_vnc_sec, self.cmb_vnc_sec, False)

            # Serial
            self._set_row_visible(self.lbl_serial_port, self.serial_port_container, False)
            self._set_row_visible(self.lbl_baudrate, self.cmb_baudrate, False)
            self._set_row_visible(self.lbl_data_bits, self.cmb_data_bits, False)
            self._set_row_visible(self.lbl_parity, self.cmb_parity, False)
            self._set_row_visible(self.lbl_stop_bits, self.cmb_stop_bits, False)
            self._set_row_visible(self.lbl_flow_control, self.cmb_flow_control, False)
        else:
            proto = self.cmb_protocol.currentText().upper()
            is_serial = (proto == "SERIAL")
            is_ssh = proto in ("SSH", "SSH2", "SSH1")
            is_sftp = proto in ("SFTP", "SCP")
            is_rdp = (proto == "RDP")
            is_vnc = (proto == "VNC")

            # Connection Nodes:
            self._set_row_visible(self.lbl_icon, self.cmb_icon, True)
            self._set_row_visible(self.lbl_protocol, self.cmb_protocol, True)

            # Hide standard network credentials for Serial
            self._set_row_visible(self.lbl_hostname, self.txt_hostname, not is_serial)
            self._set_row_visible(self.lbl_port, self.spn_port, not is_serial)
            self._set_row_visible(self.lbl_domain, self.txt_domain, not is_serial)
            self._set_row_visible(self.lbl_username, self.txt_username, not is_serial)
            self._set_row_visible(self.lbl_password, self.txt_password, not is_serial)
            self._set_row_visible(self.lbl_auto_reconnect, self.chk_auto_reconnect, not is_serial)

            # Serial Options
            self._set_row_visible(self.lbl_serial_port, self.serial_port_container, is_serial)
            self._set_row_visible(self.lbl_baudrate, self.cmb_baudrate, is_serial)
            self._set_row_visible(self.lbl_data_bits, self.cmb_data_bits, is_serial)
            self._set_row_visible(self.lbl_parity, self.cmb_parity, is_serial)
            self._set_row_visible(self.lbl_stop_bits, self.cmb_stop_bits, is_serial)
            self._set_row_visible(self.lbl_flow_control, self.cmb_flow_control, is_serial)

            # SSH / SFTP Options
            self._set_row_visible(self.lbl_private_key, self.key_container, is_ssh or is_sftp)
            self._set_row_visible(self.lbl_ssh_options, self.chk_legacy_ssh, is_ssh)
            self._set_row_visible(self.lbl_agent_forwarding, self.chk_agent_forwarding, is_ssh)

            # RDP Options
            self._set_row_visible(self.lbl_rdp_sec, self.cmb_rdp_sec, is_rdp)
            self._set_row_visible(self.lbl_rdp_cert_ignore, self.chk_rdp_cert_ignore, is_rdp)
            self._set_row_visible(self.lbl_rdp_cert_path, self.cert_container, is_rdp)
            self._set_row_visible(self.lbl_redirect_clipboard, self.chk_redirect_clipboard, is_rdp)
            self._set_row_visible(self.lbl_redirect_drives, self.chk_redirect_drives, is_rdp)
            self._set_row_visible(self.lbl_rdp_shared_folder, self.folder_container, is_rdp)

            # VNC Options
            self._set_row_visible(self.lbl_vnc_engine, self.cmb_vnc_engine, is_vnc)
            self._set_row_visible(self.lbl_vnc_sec, self.cmb_vnc_sec, is_vnc)

    def load_node(self, node: ConnectionNode):
        """Populates the property fields with data from node cleanly."""
        if not node:
            return

        self.loading = True
        self.current_node = node

        self.txt_name.setText(node.name or "")
        self.txt_description.setText(node.description or "")
        
        target_icon = (node.icon or "").strip()
        if not target_icon:
            target_icon = "Connections" if (node.is_container() and node.parent_id is None) else ("Folder" if node.is_container() else "Server")

        idx = self.cmb_icon.findText(target_icon, Qt.MatchFlag.MatchExactly)
        if idx < 0:
            for i in range(self.cmb_icon.count()):
                if self.cmb_icon.itemText(i).lower() == target_icon.lower():
                    idx = i
                    break
        if idx >= 0:
            self.cmb_icon.setCurrentIndex(idx)
        else:
            self.cmb_icon.setCurrentText(target_icon)

        self.txt_hostname.setText(node.hostname or "")
        proto_val = node.protocol or "SSH"
        if proto_val in ("SSH2", "SSH1") and self.cmb_protocol.findText("SSH") >= 0:
            proto_val = "SSH"
        self.cmb_protocol.setCurrentText(proto_val)
        self.spn_port.setValue(node.port if node.port else 22)
        self.txt_username.setText(node.username or "")
        self.txt_password.setText(node.password or "")
        self.txt_domain.setText(node.domain or "")
        self.chk_auto_reconnect.setChecked(getattr(node, "auto_reconnect", False))
        self.txt_private_key.setText(getattr(node, "private_key_file", ""))
        self.chk_legacy_ssh.setChecked(getattr(node, "legacy_ssh", True))
        self.chk_agent_forwarding.setChecked(getattr(node, "agent_forwarding", False))
        self.cmb_rdp_sec.setCurrentText(getattr(node, "rdp_security", "Auto"))
        self.chk_rdp_cert_ignore.setChecked(getattr(node, "rdp_cert_ignore", True))
        self.txt_rdp_cert_path.setText(getattr(node, "rdp_cert_path", ""))
        self.chk_redirect_clipboard.setChecked(getattr(node, "redirect_clipboard", True))
        self.chk_redirect_drives.setChecked(getattr(node, "redirect_drives", True))
        self.txt_rdp_shared_folder.setText(getattr(node, "rdp_shared_folder", ""))
        self.cmb_vnc_engine.setCurrentText(getattr(node, "vnc_engine_type", "Auto"))
        self.cmb_vnc_sec.setCurrentText(getattr(node, "vnc_sec_type", "Auto"))

        self.refresh_serial_ports()
        self.cmb_serial_port.setCurrentText(getattr(node, "serial_port", "/dev/ttyUSB0"))
        self.cmb_baudrate.setCurrentText(str(getattr(node, "baudrate", 9600)))
        self.cmb_data_bits.setCurrentText(str(getattr(node, "data_bits", 8)))
        parity_val = getattr(node, "parity", "N").upper()
        parity_map = {"N": "N (None)", "E": "E (Even)", "O": "O (Odd)", "M": "M (Mark)", "S": "S (Space)"}
        self.cmb_parity.setCurrentText(parity_map.get(parity_val, "N (None)"))
        self.cmb_stop_bits.setCurrentText(str(getattr(node, "stop_bits", 1)))
        self.cmb_flow_control.setCurrentText(getattr(node, "flow_control", "None"))

        is_conn = not node.is_container()
        self.txt_hostname.setEnabled(is_conn)
        self.cmb_protocol.setEnabled(is_conn)
        self.spn_port.setEnabled(is_conn)

        self._update_field_visibilities()

        self.loading = False

    def _on_protocol_changed(self, protocol_str: str):
        if self.loading or not self.current_node:
            return

        self.current_node.protocol = protocol_str
        plugin = PluginManager.instance().get_plugin(protocol_str)
        if plugin and plugin.default_port > 0:
            self.spn_port.setValue(plugin.default_port)

        self._update_field_visibilities()
        self._on_field_edited()

    def _on_browse_key(self):
        if self.loading or not self.current_node:
            return
        
        from pyremotempc.ui.dialogs.key_selector_dialog import KeySelectorDialog
        dlg = KeySelectorDialog(
            parent=self,
            current_key_path=getattr(self.current_node, "key_path", "") or getattr(self.current_node, "private_key_file", ""),
            current_auth_method=getattr(self.current_node, "auth_method", "key")
        )
        if dlg.exec():
            self.current_node.auth_method = dlg.selected_auth_method
            self.current_node.key_path = dlg.selected_key_path
            self.current_node.private_key_file = dlg.selected_key_path
            if dlg.passphrase:
                self.current_node.key_passphrase = dlg.passphrase
            
            if dlg.selected_auth_method == "agent":
                self.txt_private_key.setText("[SSH Agent Identity]")
            else:
                self.txt_private_key.setText(dlg.selected_key_path)
            self._on_field_edited()

    def _on_browse_cert(self):
        if self.loading or not self.current_node:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select SSL Certificate / CA File", os.path.expanduser("~"), "Certificates (*.crt *.pem *.cer *.key);;All Files (*)"
        )
        if file_path:
            self.txt_rdp_cert_path.setText(file_path)
            self._on_field_edited()

    def _on_browse_rdp_folder(self):
        if self.loading or not self.current_node:
            return
        directory = QFileDialog.getExistingDirectory(
            self, "Select RDP Shared Directory", os.path.expanduser(self.txt_rdp_shared_folder.text() or "~")
        )
        if directory:
            self.txt_rdp_shared_folder.setText(directory)
            self._on_field_edited()

    def _on_field_edited(self):
        if self.loading or not self.current_node:
            return

        self.current_node.name = self.txt_name.text()
        self.current_node.description = self.txt_description.text()
        self.current_node.icon = self.cmb_icon.currentText()
        self.current_node.hostname = self.txt_hostname.text()
        self.current_node.protocol = self.cmb_protocol.currentText()
        self.current_node.port = self.spn_port.value()
        self.current_node.username = self.txt_username.text()
        self.current_node.password = self.txt_password.text()
        self.current_node.domain = self.txt_domain.text()
        self.current_node.auto_reconnect = self.chk_auto_reconnect.isChecked()
        self.current_node.private_key_file = self.txt_private_key.text()
        self.current_node.legacy_ssh = self.chk_legacy_ssh.isChecked()
        self.current_node.agent_forwarding = self.chk_agent_forwarding.isChecked()
        self.current_node.rdp_security = self.cmb_rdp_sec.currentText()
        self.current_node.rdp_cert_ignore = self.chk_rdp_cert_ignore.isChecked()
        self.current_node.rdp_cert_path = self.txt_rdp_cert_path.text()
        self.current_node.redirect_clipboard = self.chk_redirect_clipboard.isChecked()
        self.current_node.redirect_drives = self.chk_redirect_drives.isChecked()
        self.current_node.rdp_shared_folder = self.txt_rdp_shared_folder.text()
        self.current_node.vnc_engine_type = self.cmb_vnc_engine.currentText()
        self.current_node.vnc_sec_type = self.cmb_vnc_sec.currentText()

        port_text = self.cmb_serial_port.currentText()
        port_data = self.cmb_serial_port.currentData()
        self.current_node.serial_port = port_data if port_data else port_text

        try:
            self.current_node.baudrate = int(self.cmb_baudrate.currentText())
        except Exception:
            self.current_node.baudrate = 9600
        try:
            self.current_node.data_bits = int(self.cmb_data_bits.currentText())
        except Exception:
            self.current_node.data_bits = 8
        self.current_node.parity = self.cmb_parity.currentText()[0]
        try:
            self.current_node.stop_bits = float(self.cmb_stop_bits.currentText())
        except Exception:
            self.current_node.stop_bits = 1.0
        self.current_node.flow_control = self.cmb_flow_control.currentText()
        self.property_changed.emit(self.current_node)
