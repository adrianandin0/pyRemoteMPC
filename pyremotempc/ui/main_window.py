import os
import xml.etree.ElementTree as ET
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QFileDialog, QMessageBox, QToolBar,
    QStatusBar, QApplication, QSplitter, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QLabel, QInputDialog
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt, QSize, QPoint, QTimer, QByteArray

from pyremotempc.config.models import ConnectionNode
from pyremotempc.config.settings import SettingsManager
from pyremotempc.config.i18n import tr
from pyremotempc.config.xml_parser import mRemoteNGXmlParser
from pyremotempc.config.securecrt_parser import SecureCRTXmlParser
from pyremotempc.config.asbru_parser import AsbruYamlParser
from pyremotempc.config.rdcman_parser import RdcmanXmlParser
from pyremotempc.crypto.master_key_manager import MasterKeyManager
from pyremotempc.ui.tree_widget import ConnectionTreeWidget
from pyremotempc.ui.property_grid import PropertyGridWidget
from pyremotempc.ui.tab_widget import SessionTabWidget
from pyremotempc.ui.preferences_dialog import PreferencesDialog
from pyremotempc.ui.dialogs.master_password_dialog import MasterPasswordDialog
from pyremotempc.ui.dialogs.import_folder_dialog import ImportFolderDialog
from pyremotempc.ui.icon_manager import get_icon
from pyremotempc.plugins.plugin_manager import PluginManager
from pyremotempc.utils.serial_utils import get_available_serial_ports


def get_user_config_dir() -> str:
    """Returns ~/.config/pyremotempc directory, creating it if needed."""
    config_dir = os.path.expanduser("~/.config/pyremotempc")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_default_config_path() -> str:
    """Returns ~/.config/pyremotempc/confCons.xml."""
    return os.path.join(get_user_config_dir(), "confCons.xml")


class MainWindow(QMainWindow):
    """
    Main Application Window for pyRemoteMPC.
    Compatible with KDE Plasma, GNOME, XFCE and all Linux desktop environments.
    Supports Spanish and English interface languages.
    """

    def __init__(self):
        super().__init__()
        # Settings & Master Security Manager
        self.settings = SettingsManager()
        self.master_key_mgr = MasterKeyManager(self.settings)

        self.setObjectName("MainWindow")
        self.setWindowTitle(tr("app_title", self.settings.language))
        self.setWindowIcon(get_icon("pyremotempc"))
        self.resize(1318, 768)
        self._restore_window_settings()

        self.master_password = "mR3m"
        self.read_only_passwords_mode = False
        self.current_file_path = get_default_config_path()

        # Core central tabs container with single ultra-narrow sidebar toggle button on outer boundary
        central_container = QWidget(self)
        central_layout = QHBoxLayout(central_container)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # Single ultra-narrow toggle button (10px wide) placed on outer boundary
        self.btn_toggle_sidebar = QPushButton("◀", central_container)
        self.btn_toggle_sidebar.setFixedSize(10, 48)
        self.btn_toggle_sidebar.setToolTip("Toggle Connections Sidebar")
        self.btn_toggle_sidebar.setStyleSheet(
            "QPushButton { border-left: none; border-top-right-radius: 3px; border-bottom-right-radius: 3px; font-size: 8px; font-weight: bold; padding: 0px; }"
        )
        self.btn_toggle_sidebar.clicked.connect(self._toggle_sidebar)

        # Wrapper to align toggle button vertically near middle of Connections tree area
        toggle_wrapper = QWidget(central_container)
        self.toggle_layout = QVBoxLayout(toggle_wrapper)
        self.toggle_layout.setContentsMargins(0, 0, 0, 0)
        self.toggle_layout.setSpacing(0)
        self.toggle_layout.addWidget(self.btn_toggle_sidebar, 0, Qt.AlignmentFlag.AlignTop)

        central_layout.addWidget(toggle_wrapper, 0)

        self.session_tabs = SessionTabWidget(settings_manager=self.settings, parent=central_container)
        central_layout.addWidget(self.session_tabs, 1)
        self.setCentralWidget(central_container)

        # Left Dock: Combined Tree (67%) and Properties (33%) stacked vertically
        self.sidebar_dock = QDockWidget(tr("connections_and_properties", self.settings.language), self)
        self.sidebar_dock.setObjectName("SidebarDock")
        sidebar_container = QWidget(self.sidebar_dock)
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar_splitter = QSplitter(Qt.Orientation.Vertical, sidebar_container)

        # Top Connections Container (Title + Real-time Search Box)
        # Top Connections Container (connections.png Icon + Real-time Search Box)
        conn_container = QWidget(self.sidebar_splitter)
        conn_vbox = QVBoxLayout(conn_container)
        conn_vbox.setContentsMargins(0, 0, 0, 0)
        conn_vbox.setSpacing(0)

        conn_header_widget = QWidget(conn_container)
        conn_header_widget.setFixedHeight(32)
        conn_header_widget.setStyleSheet("border: none;")
        conn_header_layout = QHBoxLayout(conn_header_widget)
        conn_header_layout.setContentsMargins(4, 0, 1, 0)
        conn_header_layout.setSpacing(4)

        lbl_conn_icon = QLabel(conn_header_widget)
        lbl_conn_icon.setPixmap(get_icon("connections").pixmap(18, 18))
        lbl_conn_icon.setToolTip(tr("connections", self.settings.language))
        conn_header_layout.addWidget(lbl_conn_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        conn_header_layout.addStretch(1)

        self.edit_tree_search = QLineEdit(conn_header_widget)
        self.edit_tree_search.setPlaceholderText("Search...")
        self.edit_tree_search.setClearButtonEnabled(True)
        self.edit_tree_search.setFixedWidth(110)
        self.edit_tree_search.addAction(get_icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.edit_tree_search.setStyleSheet("QLineEdit { border-radius: 3px; padding: 2px 4px; font-size: 11px; }")

        conn_header_layout.addWidget(self.edit_tree_search, 0, Qt.AlignmentFlag.AlignVCenter)
        conn_vbox.addWidget(conn_header_widget)

        self.tree_widget = ConnectionTreeWidget(conn_container, settings=self.settings)
        self.tree_widget.setHeaderHidden(True)
        self.edit_tree_search.textChanged.connect(self.tree_widget.filter_nodes)
        conn_vbox.addWidget(self.tree_widget)

        # Bottom Properties Container (settings.png Icon Header + Property Grid)
        prop_container = QWidget(self.sidebar_splitter)
        prop_vbox = QVBoxLayout(prop_container)
        prop_vbox.setContentsMargins(0, 0, 0, 0)
        prop_vbox.setSpacing(0)

        prop_header_widget = QWidget(prop_container)
        prop_header_widget.setFixedHeight(32)
        prop_header_widget.setStyleSheet("border: none;")
        prop_header_layout = QHBoxLayout(prop_header_widget)
        prop_header_layout.setContentsMargins(6, 0, 6, 0)
        prop_header_layout.setSpacing(4)

        lbl_prop_icon = QLabel(prop_header_widget)
        lbl_prop_icon.setPixmap(get_icon("options").pixmap(18, 18))
        lbl_prop_icon.setToolTip(tr("properties", self.settings.language))
        prop_header_layout.addWidget(lbl_prop_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        prop_header_layout.addStretch()

        self.btn_toggle_prop = QPushButton("▼", prop_header_widget)
        self.btn_toggle_prop.setFixedSize(20, 20)
        self.btn_toggle_prop.setToolTip(tr("properties", self.settings.language))
        self.btn_toggle_prop.setStyleSheet("QPushButton { border: none; font-size: 11px; font-weight: bold; padding: 0px; }")
        self.btn_toggle_prop.clicked.connect(self._toggle_properties_panel)
        prop_header_layout.addWidget(self.btn_toggle_prop, 0, Qt.AlignmentFlag.AlignVCenter)

        prop_vbox.addWidget(prop_header_widget)

        self.prop_grid = PropertyGridWidget(prop_container)
        prop_vbox.addWidget(self.prop_grid)

        self.sidebar_splitter.addWidget(conn_container)
        self.sidebar_splitter.addWidget(prop_container)

        # Restore saved vertical splitter sizes or default to [670, 330]
        saved_splitter = self.settings.get("sidebar_splitter_sizes", [670, 330])
        self.sidebar_splitter.setSizes(saved_splitter)
        self.sidebar_splitter.setStretchFactor(0, 67)
        self.sidebar_splitter.setStretchFactor(1, 33)
        self.sidebar_splitter.splitterMoved.connect(self._on_sidebar_splitter_moved)

        sidebar_layout.addWidget(self.sidebar_splitter)
        self.sidebar_dock.setWidget(sidebar_container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar_dock)

        # Allow sidebar dock width adjustment up to 450px and restore saved width
        self.sidebar_dock.setMaximumWidth(450)
        saved_width = self.settings.get("sidebar_width", 260)
        self.resizeDocks([self.sidebar_dock], [saved_width], Qt.Orientation.Horizontal)
        self.sidebar_dock.visibilityChanged.connect(self._on_dock_visibility_changed)

        # Connect signals for property grid sync and tree updates
        self.tree_widget.node_selected.connect(self.prop_grid.load_node)
        self.tree_widget.node_activated.connect(self.session_tabs.open_session)
        self.prop_grid.property_changed.connect(self._on_property_changed)

        # Setup menus, toolbars and statusbar
        self._create_menus()
        self._create_toolbar()
        self._create_quick_connect_bar()

        self.statusBar().showMessage("Ready")


        # Auto-load existing connections or default tree
        self._auto_load_connections()

    def _auto_load_connections(self):
        """Loads connections from user config file (~/.config/pyremotempc/confCons.xml) if present."""
        default_path = get_default_config_path()
        if os.path.exists(default_path):
            skip_passwords = False
            require_startup = self.settings.get("require_master_password_on_startup", False)
            if require_startup and self.master_key_mgr.is_master_key_set():
                attempts = 0
                while attempts < 3:
                    dialog = MasterPasswordDialog(self, is_default=False, show_skip_passwords=True)
                    res = dialog.exec()
                    if dialog.is_skip_passwords():
                        skip_passwords = True
                        break
                    elif res == MasterPasswordDialog.DialogCode.Accepted:
                        entered_pass = dialog.get_password()
                        if self.master_key_mgr.verify_master_key(entered_pass):
                            self.master_password = entered_pass
                            break
                        else:
                            QMessageBox.warning(self, "Access Denied", "Incorrect Master Password. Please try again.")
                            attempts += 1
                    else:
                        skip_passwords = True
                        break

            self.read_only_passwords_mode = skip_passwords

            try:
                parser = mRemoteNGXmlParser(master_password=self.master_password, skip_passwords=skip_passwords)
                root_node, ver = parser.parse_file(default_path)
                self.tree_widget.load_tree(root_node)
                if skip_passwords:
                    self.statusBar().showMessage("Connections loaded in Read-Only mode (original encrypted passwords preserved on disk).")
            except Exception as e:
                print(f"Failed to auto-load connections from primary file: {e}")
                bak_path = f"{default_path}.bak"
                if os.path.exists(bak_path) and os.path.getsize(bak_path) > 0:
                    try:
                        parser = mRemoteNGXmlParser(master_password=self.master_password, skip_passwords=skip_passwords)
                        root_node, ver = parser.parse_file(bak_path)
                        self.tree_widget.load_tree(root_node)
                        self.statusBar().showMessage(tr("connections", self.settings.language) + " recovered from backup (.bak).")
                        return
                    except Exception as be:
                        print(f"Failed to recover from backup file: {be}")

    def _load_default_tree(self):
        root = ConnectionNode(name=tr("connections", self.settings.language), node_type="Container", icon="Connections")

        folder_linux = ConnectionNode(name="Linux Servers", node_type="Container", icon="Folder")
        node_local = ConnectionNode(
            name="Local SSH Server",
            node_type="Connection",
            hostname="127.0.0.1",
            protocol="SSH2",
            port=22,
            username=os.environ.get("USER", "root"),
            icon="Server"
        )
        folder_linux.children.append(node_local)
        root.children.append(folder_linux)

        self.tree_widget.load_tree(root)

    def _auto_save_connections(self):
        """Auto-saves current connection tree to ~/.config/pyremotempc/confCons.xml."""
        if getattr(self, "read_only_passwords_mode", False):
            # Protect original encrypted passwords file on disk when opened in Read-Only (no-passwords) mode
            return
        default_path = get_default_config_path()
        try:
            parser = mRemoteNGXmlParser(master_password=self.master_password)
            parser.export_to_file(self.tree_widget.root_node, default_path, version="2.5")
        except Exception as e:
            print(f"Auto-save connections failed: {e}")

    def _on_property_changed(self, node: ConnectionNode):
        self.tree_widget.update_node_display(node)
        if hasattr(self, "session_tabs"):
            self.session_tabs.update_node_tabs(node)
        self._auto_save_connections()

    def _create_menus(self):
        menubar = self.menuBar()
        lang = self.settings.language

        # File Menu
        menu_file = menubar.addMenu(tr("file", lang))

        act_new_conn = QAction(get_icon("add"), tr("new_connection", lang), self)
        # No shortcut: Ctrl+N conflicts with terminal apps
        act_new_conn.triggered.connect(lambda: self.tree_widget.add_new_connection())
        menu_file.addAction(act_new_conn)

        act_new_folder = QAction(get_icon("folder"), tr("new_folder", lang), self)
        # No shortcut: Ctrl+Shift+N is reserved for terminal use
        act_new_folder.triggered.connect(lambda: self.tree_widget.add_new_folder())
        menu_file.addAction(act_new_folder)

        menu_file.addSeparator()

        act_open = QAction(get_icon("upload"), tr("import_xml", lang), self)
        # No shortcut: Ctrl+O conflicts with nano (Write Out) and other terminal apps
        act_open.triggered.connect(self.import_xml)
        menu_file.addAction(act_open)

        act_save = QAction(get_icon("download"), tr("export_xml", lang), self)
        # No shortcut: Ctrl+S conflicts with terminal flow control (XOFF) and nano
        act_save.triggered.connect(self.export_xml)
        menu_file.addAction(act_save)

        menu_file.addSeparator()

        act_exit = QAction(get_icon("close"), tr("exit", lang), self)
        # No shortcut: Ctrl+Q conflicts with terminal apps
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # Settings Menu
        menu_settings = menubar.addMenu(tr("settings", lang))
        act_prefs = QAction(get_icon("settings"), tr("preferences", lang), self)
        act_prefs.triggered.connect(self._open_preferences)
        menu_settings.addAction(act_prefs)

        act_master_pass = QAction(get_icon("password"), tr("set_master_pass", lang), self)
        act_master_pass.triggered.connect(self._change_master_password)
        menu_settings.addAction(act_master_pass)

        # Help Menu
        menu_help = menubar.addMenu(tr("help", lang))
        act_about = QAction(get_icon("settings"), tr("about", lang), self)
        act_about.triggered.connect(self._show_about)
        menu_help.addAction(act_about)

    def _open_preferences(self, initial_tab: int = 0):
        """Opens the Preferences and Options dialog."""
        dialog = PreferencesDialog(self.settings, initial_tab=initial_tab, parent=self)
        if dialog.exec() == PreferencesDialog.DialogCode.Accepted:
            # Refresh language & window title
            lang = self.settings.language
            self.setWindowTitle(tr("app_title", lang))

            # Apply updated settings across active terminal tabs
            for i in range(self.session_tabs.count()):
                widget = self.session_tabs.widget(i)
                if hasattr(widget, "term"):
                    widget.term.apply_settings()

            self.statusBar().showMessage("Preferences updated successfully.")

    def _create_toolbar(self):
        lang = self.settings.language
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setObjectName("MainToolbar")
        toolbar.setIconSize(QSize(22, 22))
        self.addToolBar(toolbar)

        act_new_conn = QAction(get_icon("add"), tr("new_connection", lang), self)
        act_new_conn.triggered.connect(lambda: self.tree_widget.add_new_connection())
        toolbar.addAction(act_new_conn)

        act_new_folder = QAction(get_icon("folder"), tr("new_folder", lang), self)
        act_new_folder.triggered.connect(lambda: self.tree_widget.add_new_folder())
        toolbar.addAction(act_new_folder)

    def _create_quick_connect_bar(self):
        """Creates top Quick Connect bar for manual IP/host input, protocol selection and Save option."""
        lang = self.settings.language
        qc_toolbar = QToolBar("Quick Connect Bar", self)
        qc_toolbar.setObjectName("QuickConnectBar")
        qc_toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, qc_toolbar)

        self.lbl_qc_host = QLabel(f" {tr('quick_connect', lang)}: ")
        self.act_qc_host_lbl = qc_toolbar.addWidget(self.lbl_qc_host)

        self.qc_host = QLineEdit()
        self.qc_host.setPlaceholderText("Hostname / IP")
        self.qc_host.setMinimumWidth(180)
        self.qc_host.setMaximumWidth(260)
        self.qc_host.returnPressed.connect(self._exec_quick_connect)
        self.act_qc_host = qc_toolbar.addWidget(self.qc_host)

        # Serial Port Selector (hidden by default)
        self.lbl_qc_serial_port = QLabel(" Serial Port: ")
        self.act_qc_serial_port_lbl = qc_toolbar.addWidget(self.lbl_qc_serial_port)
        self.act_qc_serial_port_lbl.setVisible(False)

        self.qc_serial_port = QComboBox()
        self.qc_serial_port.setEditable(True)
        self.qc_serial_port.setMinimumWidth(180)
        self.act_qc_serial_port = qc_toolbar.addWidget(self.qc_serial_port)
        self.act_qc_serial_port.setVisible(False)

        self.act_qc_refresh_serial = QAction(get_icon("refresh"), "", self)
        self.act_qc_refresh_serial.setToolTip("Rescan / Refresh available serial ports")
        self.act_qc_refresh_serial.triggered.connect(self._refresh_qc_serial_ports)
        qc_toolbar.addAction(self.act_qc_refresh_serial)
        self.act_qc_refresh_serial.setVisible(False)

        self._refresh_qc_serial_ports()

        qc_toolbar.addWidget(QLabel(f" {tr('proto', lang)}: "))
        self.qc_proto = QComboBox()
        protocols = PluginManager.instance().list_protocols()
        if protocols:
            self.qc_proto.addItems(protocols)
        else:
            self.qc_proto.addItems(["SSH", "SSH1", "RDP", "VNC", "TELNET", "SERIAL"])
        self.qc_proto.currentTextChanged.connect(self._on_qc_proto_changed)
        qc_toolbar.addWidget(self.qc_proto)

        # Serial Baud Rate (hidden by default)
        self.lbl_qc_baud = QLabel(" Baud: ")
        self.qc_baud = QComboBox()
        self.qc_baud.addItems(["9600", "115200", "57600", "38400", "19200", "14400", "4800", "2400", "1200", "600", "300", "110"])
        self.act_qc_baud_lbl = qc_toolbar.addWidget(self.lbl_qc_baud)
        self.act_qc_baud = qc_toolbar.addWidget(self.qc_baud)
        self.act_qc_baud_lbl.setVisible(False)
        self.act_qc_baud.setVisible(False)

        # Network TCP Port
        self.lbl_qc_port = QLabel(f" {tr('port', lang)}: ")
        self.qc_port = QSpinBox()
        self.qc_port.setRange(1, 65535)
        self.qc_port.setValue(22)
        self.act_qc_port_lbl = qc_toolbar.addWidget(self.lbl_qc_port)
        self.act_qc_port = qc_toolbar.addWidget(self.qc_port)

        # Domain
        self.lbl_qc_domain = QLabel(f" {tr('domain', lang)}: ")
        self.qc_domain = QLineEdit()
        self.qc_domain.setPlaceholderText(tr("domain", lang))
        self.qc_domain.setMaximumWidth(120)
        self.qc_domain.returnPressed.connect(self._exec_quick_connect)
        self.act_qc_domain_lbl = qc_toolbar.addWidget(self.lbl_qc_domain)
        self.act_qc_domain = qc_toolbar.addWidget(self.qc_domain)

        # User
        self.lbl_qc_user = QLabel(f" {tr('user', lang)}: ")
        self.qc_user = QLineEdit()
        self.qc_user.setPlaceholderText(tr("user", lang))
        self.qc_user.setMaximumWidth(120)
        self.qc_user.returnPressed.connect(self._exec_quick_connect)
        self.act_qc_user_lbl = qc_toolbar.addWidget(self.lbl_qc_user)
        self.act_qc_user = qc_toolbar.addWidget(self.qc_user)

        # Password
        self.lbl_qc_pass = QLabel(f" {tr('pass', lang)}: ")
        self.qc_pass = QLineEdit()
        self.qc_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.qc_pass.setPlaceholderText(tr("pass", lang))
        self.qc_pass.setMaximumWidth(120)
        self.qc_pass.returnPressed.connect(self._exec_quick_connect)
        self.act_qc_pass_lbl = qc_toolbar.addWidget(self.lbl_qc_pass)
        self.act_qc_pass = qc_toolbar.addWidget(self.qc_pass)

        qc_toolbar.addSeparator()

        # Quick Connect Action Button
        act_qc_connect = QAction(get_icon("connect"), f" {tr('connect', lang)}", self)
        act_qc_connect.setToolTip("Connect directly to Hostname / IP or Serial Port")
        act_qc_connect.triggered.connect(self._exec_quick_connect)
        qc_toolbar.addAction(act_qc_connect)

        # Save Connection Action Button
        act_qc_save = QAction(get_icon("save"), f" {tr('save_conn', lang)}", self)
        act_qc_save.setToolTip("Save this Quick Connect entry into the left connections tree")
        act_qc_save.triggered.connect(self._exec_quick_save)
        qc_toolbar.addAction(act_qc_save)

    def _refresh_qc_serial_ports(self):
        """Refreshes active serial ports in Quick Connect combo box."""
        current = self.qc_serial_port.currentText()
        self.qc_serial_port.clear()
        for dev, label in get_available_serial_ports():
            self.qc_serial_port.addItem(label, dev)
        if current and self.qc_serial_port.findText(current) != -1:
            self.qc_serial_port.setCurrentText(current)
        elif current and not current.startswith("No ports"):
            self.qc_serial_port.setCurrentText(current)

    def _on_qc_proto_changed(self, proto: str):
        is_serial = (proto.upper() == "SERIAL")
        if is_serial:
            self.act_qc_host_lbl.setVisible(False)
            self.act_qc_host.setVisible(False)

            self.act_qc_serial_port_lbl.setVisible(True)
            self.act_qc_serial_port.setVisible(True)
            self.act_qc_refresh_serial.setVisible(True)

            self.act_qc_baud_lbl.setVisible(True)
            self.act_qc_baud.setVisible(True)

            self.act_qc_port_lbl.setVisible(False)
            self.act_qc_port.setVisible(False)

            self.act_qc_domain_lbl.setVisible(False)
            self.act_qc_domain.setVisible(False)

            self.act_qc_user_lbl.setVisible(False)
            self.act_qc_user.setVisible(False)

            self.act_qc_pass_lbl.setVisible(False)
            self.act_qc_pass.setVisible(False)
        else:
            self.act_qc_host_lbl.setVisible(True)
            self.act_qc_host.setVisible(True)
            self.qc_host.setPlaceholderText("Hostname / IP")

            self.act_qc_serial_port_lbl.setVisible(False)
            self.act_qc_serial_port.setVisible(False)
            self.act_qc_refresh_serial.setVisible(False)

            self.act_qc_baud_lbl.setVisible(False)
            self.act_qc_baud.setVisible(False)

            self.act_qc_port_lbl.setVisible(True)
            self.act_qc_port.setVisible(True)

            self.act_qc_domain_lbl.setVisible(True)
            self.act_qc_domain.setVisible(True)

            self.act_qc_user_lbl.setVisible(True)
            self.act_qc_user.setVisible(True)

            self.act_qc_pass_lbl.setVisible(True)
            self.act_qc_pass.setVisible(True)

            plugin = PluginManager.instance().get_plugin(proto)
            if plugin and plugin.default_port > 0:
                self.qc_port.setValue(plugin.default_port)

    def _exec_quick_connect(self):
        proto = self.qc_proto.currentText().upper()

        if proto == "SERIAL":
            port_text = self.qc_serial_port.currentText().strip()
            port_data = self.qc_serial_port.currentData()
            serial_port = port_data if port_data else port_text

            if not serial_port or serial_port.startswith("No ports"):
                err_title = tr("quick_connect", self.settings.language)
                QMessageBox.warning(self, err_title, "Please select or enter a valid Serial Port (e.g. /dev/ttyUSB0 or COM1).")
                return

            try:
                baud = int(self.qc_baud.currentText())
            except Exception:
                baud = 9600

            quick_node = ConnectionNode(
                name=f"Serial ({serial_port})",
                node_type="Connection",
                protocol="SERIAL",
                serial_port=serial_port,
                baudrate=baud,
                hostname=""
            )
        else:
            host = self.qc_host.text().strip()
            if not host:
                err_title = tr("quick_connect", self.settings.language)
                QMessageBox.warning(self, err_title, "Please enter a valid Hostname or IP address.")
                return

            quick_node = ConnectionNode(
                name=host,
                node_type="Connection",
                hostname=host,
                protocol=self.qc_proto.currentText(),
                port=self.qc_port.value(),
                username=self.qc_user.text().strip(),
                password=self.qc_pass.text(),
                domain=self.qc_domain.text().strip(),
                legacy_ssh=True
            )

        quick_node.is_quick_connect = True

        # Clear focus from quick connect input fields so Enter key goes to terminal
        self.qc_host.clearFocus()
        self.qc_domain.clearFocus()
        self.qc_user.clearFocus()
        self.qc_pass.clearFocus()

        self.session_tabs.open_session(quick_node)

    def _exec_quick_save(self):
        proto = self.qc_proto.currentText().upper()

        if proto == "SERIAL":
            port_text = self.qc_serial_port.currentText().strip()
            port_data = self.qc_serial_port.currentData()
            serial_port = port_data if port_data else port_text

            if not serial_port or serial_port.startswith("No ports"):
                err_title = tr("save_conn", self.settings.language)
                QMessageBox.warning(self, err_title, "Please select or enter a valid Serial Port to save.")
                return

            try:
                baud = int(self.qc_baud.currentText())
            except Exception:
                baud = 9600

            default_name = f"Serial ({serial_port})"
            conn_name, ok = QInputDialog.getText(
                self, tr("save_conn", self.settings.language), "Enter a name for this serial connection:", QLineEdit.EchoMode.Normal, default_name
            )
            if not ok or not conn_name.strip():
                conn_name = default_name

            new_node = ConnectionNode(
                name=conn_name.strip(),
                node_type="Connection",
                protocol="SERIAL",
                serial_port=serial_port,
                baudrate=baud,
                hostname=""
            )
        else:
            host = self.qc_host.text().strip()
            if not host:
                err_title = tr("save_conn", self.settings.language)
                QMessageBox.warning(self, err_title, "Please enter a valid Hostname or IP address to save.")
                return

            conn_name, ok = QInputDialog.getText(
                self, tr("save_conn", self.settings.language), "Enter a name for this connection:", QLineEdit.EchoMode.Normal, host
            )
            if not ok or not conn_name.strip():
                conn_name = host

            new_node = ConnectionNode(
                name=conn_name.strip(),
                node_type="Connection",
                hostname=host,
                protocol=self.qc_proto.currentText(),
                port=self.qc_port.value(),
                username=self.qc_user.text().strip(),
                password=self.qc_pass.text(),
                domain=self.qc_domain.text().strip(),
                legacy_ssh=True
            )

        parent_node = self.tree_widget.get_selected_node() or self.tree_widget.root_node
        self.tree_widget.add_new_connection(parent_node=parent_node, new_node=new_node)
        self._auto_save_connections()
        self.statusBar().showMessage(f"Saved connection '{conn_name}' to tree.")

    def _connect_selected(self):
        node = self.tree_widget.get_selected_node()
        if node and not node.is_container():
            self.session_tabs.open_session(node)

    def _prompt_and_import_nodes(self, imported_root: ConnectionNode, format_name: str, file_path: str):
        """Prompts user for root folder name & icon before effectively appending imported nodes."""
        suggested_name = self.tree_widget.get_suggested_import_folder_name(base_name="Imported from File")
        dialog = ImportFolderDialog(self, default_name=suggested_name, default_icon="Folder")
        if dialog.exec() == ImportFolderDialog.DialogCode.Accepted:
            folder_name = dialog.get_folder_name()
            folder_icon = dialog.get_folder_icon()
            import_folder = self.tree_widget.import_nodes_into_new_folder(
                imported_root, folder_name=folder_name, folder_icon=folder_icon
            )
            self.current_file_path = file_path
            self._auto_save_connections()
            self.statusBar().showMessage(
                f"Imported {format_name} connections into '{import_folder.name}' from {os.path.basename(file_path)}"
            )

    def import_xml(self):
        """Opens dialog to import connection files."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("import_xml", self.settings.language),
            "",
            "All Supported Connection Files (*.xml *.rdg *.yml *.yaml *.txt);;XML Connections (*.xml);;RDCMan RDG (*.rdg *.xml);;Asbrú Connection Manager (*.yml *.yaml *.txt);;All Files (*)"
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()

        # Check if file is Asbrú YAML (.yml, .yaml, or contains Asbrú markers)
        is_asbru = ext in (".yml", ".yaml")
        if not is_asbru:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    sample = f.read(2048)
                    if "__PAC__" in sample or "_is_group" in sample:
                        is_asbru = True
            except Exception:
                pass

        if is_asbru:
            try:
                parser = AsbruYamlParser()
                root_node = parser.parse_file(file_path)
                self._prompt_and_import_nodes(root_node, "Asbrú", file_path)
                return
            except Exception as e:
                if not ext.endswith((".xml", ".rdg")):
                    QMessageBox.critical(self, "Import Error", f"Failed to parse Asbrú YAML file:\n{str(e)}")
                    return

        # Handle XML Formats (RDCMan / SecureCRT / Generic XML)
        try:
            tree = ET.parse(file_path)
            root_elem = tree.getroot()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to read connection file:\n{str(e)}")
            return

        if root_elem.tag == "RDCMan":
            # Microsoft RDCMan RDG/XML
            try:
                parser = RdcmanXmlParser()
                root_node = parser.parse_file(file_path)
                self._prompt_and_import_nodes(root_node, "RDCMan", file_path)
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to parse RDCMan XML:\n{str(e)}")
        elif root_elem.tag == "VanDyke":
            # SecureCRT XML Export
            try:
                parser = SecureCRTXmlParser()
                root_node = parser.parse_file(file_path)
                self._prompt_and_import_nodes(root_node, "SecureCRT", file_path)
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to parse SecureCRT XML:\n{str(e)}")
        else:
            # Generic / Encrypted XML Connections
            dialog = MasterPasswordDialog(self, is_default=(self.master_password == "mR3m"), show_skip_passwords=True)
            res = dialog.exec()
            if dialog.is_skip_passwords():
                try:
                    parser = mRemoteNGXmlParser(master_password="", skip_passwords=True)
                    root_node, ver = parser.parse_file(file_path, is_import=True)
                    self._prompt_and_import_nodes(root_node, "XML", file_path)
                except Exception as e:
                    QMessageBox.critical(self, "Import Error", f"Failed to parse XML connection file:\n{str(e)}")
            elif res == MasterPasswordDialog.DialogCode.Accepted:
                self.master_password = dialog.get_password()
                try:
                    parser = mRemoteNGXmlParser(master_password=self.master_password)
                    root_node, ver = parser.parse_file(file_path, is_import=True)
                    self._prompt_and_import_nodes(root_node, "XML", file_path)
                except Exception as e:
                    QMessageBox.critical(self, "Import Error", f"Failed to parse XML connection file:\n{str(e)}")

    def export_xml(self):
        """Exports connection tree to XML format."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, tr("export_xml", self.settings.language), "connections.xml", "Connections XML (*.xml);;All Files (*)"
        )
        if not file_path:
            return

        try:
            parser = mRemoteNGXmlParser(master_password=self.master_password)
            parser.export_to_file(self.tree_widget.root_node, file_path, version="2.5")
            self.statusBar().showMessage(f"Exported connections to {file_path}")
            QMessageBox.information(self, "Export Successful", f"Successfully exported connections to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export XML:\n{str(e)}")

    def _change_master_password(self):
        self._open_preferences(initial_tab=3)

    def _show_about(self):
        from pyremotempc.ui.dialogs.about_dialog import AboutDialog
        dlg = AboutDialog(self, theme=self.settings.theme)
        dlg.exec()

    def _toggle_sidebar(self):
        is_vis = self.sidebar_dock.isVisible()
        self.sidebar_dock.setVisible(not is_vis)
        self.btn_toggle_sidebar.setText("▶" if is_vis else "◀")
        self._sync_toggle_button_position()

    def _toggle_properties_panel(self):
        if not hasattr(self, "prop_grid") or not hasattr(self, "sidebar_splitter"):
            return

        if self.prop_grid.isVisible():
            sizes = self.sidebar_splitter.sizes()
            if len(sizes) == 2 and sizes[1] > 40:
                self._saved_prop_splitter_sizes = sizes
            self.prop_grid.setVisible(False)
            total = sum(self.sidebar_splitter.sizes())
            self.sidebar_splitter.setSizes([total - 32, 32])
            self.btn_toggle_prop.setText("▲")
        else:
            self.prop_grid.setVisible(True)
            saved = getattr(self, "_saved_prop_splitter_sizes", None)
            if not saved or len(saved) != 2 or saved[1] <= 40:
                saved = self.settings.get("sidebar_splitter_sizes", [670, 330])
            self.sidebar_splitter.setSizes(saved)
            self.btn_toggle_prop.setText("▼")

        self._sync_toggle_button_position()
        QTimer.singleShot(20, self._sync_toggle_button_position)
        self._save_sidebar_settings()

    def _on_dock_visibility_changed(self, visible: bool):
        self.btn_toggle_sidebar.setText("◀" if visible else "▶")
        self._sync_toggle_button_position()

    def _sync_toggle_button_position(self):
        if not hasattr(self, "tree_widget") or not hasattr(self, "btn_toggle_sidebar") or not hasattr(self, "toggle_layout"):
            return
        try:
            tree_pos_y = self.tree_widget.mapTo(self, QPoint(0, 0)).y()
            tree_center_y = tree_pos_y + (self.tree_widget.height() // 2)

            central_pos_y = self.centralWidget().mapTo(self, QPoint(0, 0)).y()
            target_margin_top = max(0, tree_center_y - central_pos_y - (self.btn_toggle_sidebar.height() // 2))

            self.toggle_layout.setContentsMargins(0, target_margin_top, 0, 0)
        except Exception:
            pass

    def _on_sidebar_splitter_moved(self, *args):
        self._sync_toggle_button_position()
        self._save_sidebar_settings()

    def _save_window_settings(self):
        try:
            geom = bytes(self.saveGeometry().toHex()).decode("ascii")
            state = bytes(self.saveState().toHex()).decode("ascii")
            self.settings.set("window_geometry", geom)
            self.settings.set("window_state", state)
        except Exception:
            pass

    def _restore_window_settings(self):
        geom_str = self.settings.get("window_geometry", "")
        if geom_str:
            try:
                self.restoreGeometry(QByteArray.fromHex(geom_str.encode("ascii")))
            except Exception:
                pass
        state_str = self.settings.get("window_state", "")
        if state_str:
            try:
                self.restoreState(QByteArray.fromHex(state_str.encode("ascii")))
            except Exception:
                pass

    def _save_sidebar_settings(self):
        if not getattr(self, "_initialized", False):
            return
        try:
            if hasattr(self, "sidebar_dock") and self.sidebar_dock.isVisible():
                w = self.sidebar_dock.width()
                if w > 100:
                    self.settings.set("sidebar_width", w)
            if hasattr(self, "sidebar_splitter"):
                sizes = self.sidebar_splitter.sizes()
                if len(sizes) == 2 and sum(sizes) > 100:
                    self.settings.set("sidebar_splitter_sizes", sizes)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        saved_width = self.settings.get("sidebar_width", 260)
        saved_splitter = self.settings.get("sidebar_splitter_sizes", [670, 330])
        self.resizeDocks([self.sidebar_dock], [saved_width], Qt.Orientation.Horizontal)
        self.sidebar_splitter.setSizes(saved_splitter)
        self._initialized = True
        QTimer.singleShot(50, self._sync_toggle_button_position)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sidebar_dock.setMaximumWidth(450)
        self._sync_toggle_button_position()
        self._save_sidebar_settings()

    def closeEvent(self, event):
        if hasattr(self, "session_tabs"):
            active_count = self.session_tabs.get_active_sessions_count()
            if active_count > 0:
                lang = self.settings.language
                msg = tr("confirm_exit_app_msg", lang).format(count=active_count)
                title = tr("confirm_exit_app_title", lang)

                reply = QMessageBox.question(
                    self,
                    title,
                    msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return

            self.session_tabs.close_all_tabs(confirm=False)

        self._save_window_settings()
        self._save_sidebar_settings()
        self._auto_save_connections()
        event.accept()
        super().closeEvent(event)

