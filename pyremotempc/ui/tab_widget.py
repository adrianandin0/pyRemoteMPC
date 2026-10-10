from PySide6.QtWidgets import (
    QTabWidget, QTabBar, QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QHBoxLayout, QSplitter, QPlainTextEdit, QGroupBox,
    QMenu, QInputDialog, QLineEdit, QMessageBox
)
from PySide6.QtGui import QIcon, QTextCursor, QAction
from PySide6.QtCore import Qt, QObject, Signal, QTimer
from typing import Optional
from pyremotempc.config.models import ConnectionNode
from pyremotempc.config.settings import SettingsManager
from pyremotempc.config.i18n import tr
from pyremotempc.ui.icon_manager import get_icon, get_node_icon
from pyremotempc.ui.terminal_widget import TerminalWidget
from pyremotempc.ui.sftp_widget import SFTPWidget
from pyremotempc.engine.rdp_engine import RDPEngine
from pyremotempc.engine.vnc_engine import VNCEngine
from pyremotempc.ui.vnc_widget import VNCWidget
from pyremotempc.plugins.plugin_manager import PluginManager


import subprocess

class OutputBridge(QObject):
    """Bridge QObject to thread-safely emit signals from background thread to Qt GUI thread."""
    output_received = Signal(str)


def set_process_audio_muted(pid: Optional[int], mute: bool):
    """
    Mutes or unmutes the local audio playback of a process by PID using pactl/PipeWire.
    Does NOT restart the session or touch the remote server.
    """
    if not pid:
        return

    try:
        output = subprocess.check_output(["pactl", "list", "sink-inputs"], text=True, stderr=subprocess.DEVNULL)
        current_index = None
        for line in output.splitlines():
            line_str = line.strip()
            if line_str.startswith("Sink Input #") or line_str.startswith("Entrada del destino #"):
                current_index = line_str.split("#")[-1].strip()
            elif "application.process.id" in line_str:
                val = line_str.split("=")[-1].strip().strip('"')
                if val.isdigit() and int(val) == pid and current_index is not None:
                    mute_val = "1" if mute else "0"
                    subprocess.run(["pactl", "set-sink-input-mute", current_index, mute_val], check=False, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def format_tab_title(node: ConnectionNode) -> str:
    """
    Unified format for session tab titles:
    a) Saved connection: PROTOCOL: saved_name (e.g. RDP: VMW7-AANDINO or SSH: carlitos)
    b) New connection: PROTOCOL: ip/hostname (e.g. SSH: 172.20.70.43 or RDP: 10.4.13.100)
    """
    if not node:
        return "Session"

    proto = (getattr(node, "protocol", "") or "").upper()
    if proto in ("SSH2", "SSH1"):
        proto_str = "SSH"
    else:
        proto_str = proto or "CONN"

    name = (getattr(node, "name", "") or "").strip()
    host = (getattr(node, "hostname", "") or "").strip()

    if name and name != host:
        display_name = name
    else:
        display_name = host or name or "Unnamed"

    return f"{proto_str}: {display_name}"


def format_action_bar_info(node: ConnectionNode) -> str:
    """
    Formats sub-header text for session tab action bar:
    Shows ONLY hostname/ip:port or serial_port:baudrate without protocol prefix or outer parentheses.
    """
    if not node:
        return ""

    proto = (getattr(node, "protocol", "") or "").upper()
    if proto == "SERIAL":
        port = str(getattr(node, "serial_port", "") or getattr(node, "hostname", "") or "/dev/ttyUSB0").strip()
        baud = str(getattr(node, "baudrate", 9600)).strip()
        return f"{port}:{baud}"

    host = (getattr(node, "hostname", "") or "").strip()
    port = getattr(node, "port", None)

    if port:
        return f"{host}:{port}"
    return host


class X11EmbedWidget(QWidget):
    """A QWidget container for embedded X11 protocol client windows."""
    
    # Signal emitted when the widget size settles (after a resize debounce)
    size_settled = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_settled)

    def _on_resize_settled(self):
        self.size_settled.emit(self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start(500)  # 500ms debounce


class SessionTabWidget(QTabWidget):
    """
    Tab Bar Container for Active Sessions (SSH, RDP, VNC, etc.).
    Supports per-session SFTP File Transfer drawers, RDP session containers, TXT export,
    and right-click context menu (Rename, Duplicate, Save Connection, Close Tab).
    """

    def __init__(self, settings_manager: Optional[SettingsManager] = None, parent=None):
        super().__init__(parent)
        self.settings = settings_manager or SettingsManager()
        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self.close_tab)

        # Enable right-click context menu on tab bar
        self.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._show_tab_context_menu)

        # Enable middle-click (mouse wheel) tab closing
        self.tabBar().mousePressEvent = self._on_tabbar_mouse_press

        self._show_welcome_tab()

    def _on_tabbar_mouse_press(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            idx = self.tabBar().tabAt(event.position().toPoint())
            if idx >= 0:
                self.close_tab(idx)
                return
        QTabBar.mousePressEvent(self.tabBar(), event)

    def _show_welcome_tab(self):
        lang = self.settings.language
        welcome_widget = QFrame()
        layout = QVBoxLayout(welcome_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_title = QLabel(tr("welcome_title", lang))
        lbl_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        lbl_sub = QLabel(tr("welcome_sub", lang))
        lbl_sub.setStyleSheet("font-size: 11px; font-weight: normal;")


        layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub, alignment=Qt.AlignmentFlag.AlignCenter)

        idx = self.addTab(welcome_widget, get_icon("server"), "Welcome")
        self.tabBar().setTabButton(idx, self.tabBar().ButtonPosition.RightSide, None)

    def open_session(self, node: ConnectionNode):
        """Opens a new session tab for the specified ConnectionNode using PluginManager dynamic lookup."""
        if self.count() == 1 and self.tabText(0) in ("Welcome", "Bienvenido"):
            self.removeTab(0)

        proto = node.protocol.upper()
        if proto in ("SFTP", "FTP", "SCP"):
            self._open_standalone_sftp_session(node)
            return

        engine_cls = PluginManager.instance().get_engine_class(proto)

        if engine_cls is RDPEngine:
            self._open_rdp_session(node)
        elif engine_cls is VNCEngine:
            self._open_vnc_session(node)
        else:
            self._open_ssh_session(node)

    def _open_standalone_sftp_session(self, node: ConnectionNode):
        """Opens a standalone full-tab SFTP/FTP File Manager session."""
        lang = self.settings.language
        sftp_container = QWidget(self)
        vbox = QVBoxLayout(sftp_container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Action Bar
        action_bar = QWidget(sftp_container)
        action_bar.setObjectName("tab_action_bar")
        act_layout = QHBoxLayout(action_bar)
        act_layout.setContentsMargins(6, 2, 6, 2)

        lbl_info = QLabel(format_action_bar_info(node), action_bar)
        lbl_info.setStyleSheet("font-size: 11px; font-weight: normal;")
        act_layout.addWidget(lbl_info)
        act_layout.addStretch()

        btn_reconnect = QPushButton(tr("connect_sftp", lang), action_bar)
        btn_reconnect.setIcon(get_icon("connect"))
        act_layout.addWidget(btn_reconnect)

        vbox.addWidget(action_bar)

        sftp_panel = SFTPWidget(node, ssh_engine=None, settings_manager=self.settings, parent=sftp_container)
        vbox.addWidget(sftp_panel)

        btn_reconnect.clicked.connect(sftp_panel.connect_sftp)

        sftp_container.sftp_panel = sftp_panel
        sftp_container.node = node
        sftp_container.lbl_info = lbl_info

        idx = self.addTab(sftp_container, get_node_icon(node), format_tab_title(node))
        self.setCurrentIndex(idx)
        QTimer.singleShot(100, sftp_panel.connect_sftp)

    def _open_ssh_session(self, node: ConnectionNode):
        lang = self.settings.language
        session_container = QWidget(self)
        vbox = QVBoxLayout(session_container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Per-tab action bar
        action_bar = QWidget(session_container)
        action_bar.setObjectName("tab_action_bar")
        act_layout = QHBoxLayout(action_bar)
        act_layout.setContentsMargins(6, 2, 6, 2)

        lbl_info = QLabel(format_action_bar_info(node), action_bar)
        lbl_info.setStyleSheet("font-size: 11px; font-weight: normal;")
        act_layout.addWidget(lbl_info)

        act_layout.addStretch()

        btn_sftp = QPushButton(tr("sftp_manager", lang), action_bar)
        btn_sftp.setIcon(get_icon("ftp"))
        btn_sftp.setToolTip("Toggle integrated SFTP file manager for this active tab")
        act_layout.addWidget(btn_sftp)

        btn_export = QPushButton(tr("export_txt", lang), action_bar)
        btn_export.setIcon(get_icon("save-file"))
        btn_export.setToolTip("Export terminal output to TXT file")
        act_layout.addWidget(btn_export)

        vbox.addWidget(action_bar)

        # Vertical Splitter: Terminal on Top, SFTP File Manager on Bottom
        splitter = QSplitter(Qt.Orientation.Vertical, session_container)

        term = TerminalWidget(node, self.settings, splitter)
        splitter.addWidget(term)

        # Pass term.engine & settings_manager to SFTPWidget
        sftp_panel = SFTPWidget(node, ssh_engine=term.engine, settings_manager=self.settings, parent=splitter)
        sftp_panel.setVisible(False)
        splitter.addWidget(sftp_panel)

        vbox.addWidget(splitter)

        # Wire Action Bar Buttons
        btn_export.clicked.connect(term.export_to_txt)
        btn_sftp.clicked.connect(lambda: self._toggle_sftp(sftp_panel))

        # Store handles on container widget for closing & context actions
        session_container.term = term
        session_container.sftp_panel = sftp_panel
        session_container.node = node
        session_container.lbl_info = lbl_info

        # Connect session_closed to Smart Tab Close Handler
        term.session_closed.connect(
            lambda clean_exit, container=session_container: self._on_terminal_session_closed(container, clean_exit)
        )

        idx = self.addTab(session_container, get_node_icon(node), format_tab_title(node))
        self.setCurrentIndex(idx)
        QTimer.singleShot(50, term.start_session)
        QTimer.singleShot(100, lambda: term.text_edit.setFocus())

    def _on_terminal_session_closed(self, container_widget, clean_exit: bool = False):
        """Smart Session Close Handler: Closes tab automatically on clean exit (e.g. 'exit' shell command), keeps tab open on connection error."""
        if clean_exit:
            idx = self.indexOf(container_widget)
            if idx != -1:
                self.removeTab(idx)
                container_widget.deleteLater()

    def _toggle_sftp(self, sftp_panel: SFTPWidget):
        is_visible = sftp_panel.isVisible()
        sftp_panel.setVisible(not is_visible)
        if not is_visible and not sftp_panel.sftp_engine.is_connected:
            sftp_panel.connect_sftp()

    def _open_rdp_session(self, node: ConnectionNode):
        lang = self.settings.language
        rdp_container = QWidget(self)
        vbox = QVBoxLayout(rdp_container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Top Control Bar
        action_bar = QWidget(rdp_container)
        action_bar.setObjectName("tab_action_bar")
        act_layout = QHBoxLayout(action_bar)
        act_layout.setContentsMargins(6, 2, 6, 2)

        lbl_info = QLabel(format_action_bar_info(node), action_bar)
        lbl_info.setStyleSheet("font-size: 11px; font-weight: normal;")
        act_layout.addWidget(lbl_info)
        act_layout.addStretch()

        btn_mute = QPushButton(action_bar)
        btn_mute.setIcon(get_icon("unmute"))
        btn_mute.setCheckable(True)
        btn_mute.setChecked(False)
        btn_mute.setToolTip("Mute Audio")
        act_layout.addWidget(btn_mute)

        btn_toggle_log = QPushButton(tr("sftp_log_btn", lang).replace("📜 ", ""), action_bar)
        btn_toggle_log.setIcon(get_icon("log"))
        btn_toggle_log.setCheckable(True)
        btn_toggle_log.setChecked(False)
        act_layout.addWidget(btn_toggle_log)

        btn_reconnect = QPushButton(action_bar)
        btn_reconnect.setIcon(get_icon("refresh"))
        btn_reconnect.setToolTip(tr("reconnect_rdp", lang))
        act_layout.addWidget(btn_reconnect)

        vbox.addWidget(action_bar)

        # Splitter: Embedded Window Area on Top, Live Diagnostic Log on Bottom
        splitter = QSplitter(Qt.Orientation.Vertical, rdp_container)

        embed_widget = X11EmbedWidget(splitter)
        embed_layout = QVBoxLayout(embed_widget)
        lbl_status = QLabel(f"Launching RDP to {node.hostname}:{node.port}...", embed_widget)
        lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_status.setStyleSheet("font-size: 11px; font-weight: normal;")

        embed_layout.addWidget(lbl_status)
        splitter.addWidget(embed_widget)

        # RDP Log Console (hidden by default)
        group_log = QGroupBox(tr("rdp_log_title", lang), splitter)
        group_log.setVisible(False)
        log_vbox = QVBoxLayout(group_log)
        log_vbox.setContentsMargins(2, 2, 2, 2)

        txt_rdp_log = QPlainTextEdit(group_log)
        txt_rdp_log.setReadOnly(True)
        txt_rdp_log.setObjectName("log_console")
        txt_rdp_log.setStyleSheet("QPlainTextEdit#log_console { font-family: Monospace; font-size: 11px; }")
        log_vbox.addWidget(txt_rdp_log)
        splitter.addWidget(group_log)
        
        btn_toggle_log.toggled.connect(group_log.setVisible)

        splitter.setSizes([500, 200])
        vbox.addWidget(splitter)

        def append_rdp_log_safe(text: str):
            cursor = txt_rdp_log.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(text)
            txt_rdp_log.setTextCursor(cursor)
            txt_rdp_log.ensureCursorVisible()

        rdp_bridge = OutputBridge(rdp_container)
        rdp_bridge.output_received.connect(append_rdp_log_safe)

        shared_folder = getattr(node, "rdp_shared_folder", "") or self.settings.rdp_shared_folder
        redirect_clipboard = getattr(node, "redirect_clipboard", self.settings.rdp_enable_clipboard)
        redirect_drives = getattr(node, "redirect_drives", self.settings.rdp_enable_drive_redirection)

        raw_sound = getattr(node, "redirect_sound", "BringToThisComputer")
        if isinstance(raw_sound, str):
            redirect_sound = raw_sound.lower() in ("bringtothiscomputer", "true", "1", "yes")
        else:
            redirect_sound = bool(raw_sound)

        colors = getattr(node, "colors", "")

        rdp_engine = RDPEngine(
            hostname=node.hostname,
            port=node.port,
            username=node.username,
            password=node.password,
            domain=node.domain,
            rdp_security=getattr(node, "rdp_security", "Auto"),
            rdp_cert_ignore=getattr(node, "rdp_cert_ignore", True),
            rdp_cert_path=getattr(node, "rdp_cert_path", ""),
            redirect_drives=redirect_drives,
            redirect_clipboard=redirect_clipboard,
            redirect_sound=redirect_sound,
            shared_folder=shared_folder,
            colors=colors
        )

        rdp_container.rdp_engine = rdp_engine
        rdp_container.node = node
        rdp_container.lbl_info = lbl_info

        def start_rdp():
            txt_rdp_log.clear()
            win_id = None
            try:
                win_id = int(embed_widget.winId())
            except Exception:
                pass
            w = embed_widget.width()
            h = embed_widget.height()
            if w < 100 or h < 100:
                # Fallback to a high resolution if the layout hasn't settled yet
                w = 1920
                h = 1080
            rdp_engine.start_session(on_output=rdp_bridge.output_received.emit, win_id=win_id, width=w, height=h)

        btn_reconnect.clicked.connect(start_rdp)

        def toggle_mute(muted: bool):
            if muted:
                btn_mute.setIcon(get_icon("mute"))
                btn_mute.setToolTip("Unmute Audio")
            else:
                btn_mute.setIcon(get_icon("unmute"))
                btn_mute.setToolTip("Mute Audio")

            if rdp_engine.process and rdp_engine.process.poll() is None:
                set_process_audio_muted(rdp_engine.process.pid, muted)

        btn_mute.toggled.connect(toggle_mute)
        
        resize_debounce_timer = QTimer(rdp_container)
        resize_debounce_timer.setSingleShot(True)
        resize_debounce_timer.setInterval(600)
        pending_size = [None, None]

        def _perform_reconnect():
            target_w, target_h = pending_size
            if not target_w or not target_h:
                return
            if not rdp_engine.process or rdp_engine.process.poll() is not None:
                return
            if abs(target_w - rdp_engine.width) > 10 or abs(target_h - rdp_engine.height) > 10:
                rdp_bridge.output_received.emit(f"\n[INFO] Auto-reconnecting to resize desktop to {target_w}x{target_h}...\n")
                rdp_engine.stop_session()
                start_rdp()

        resize_debounce_timer.timeout.connect(_perform_reconnect)

        def on_embed_resized(w, h):
            if not rdp_engine.process or rdp_engine.process.poll() is not None:
                return
            if abs(w - rdp_engine.width) > 10 or abs(h - rdp_engine.height) > 10:
                pending_size[0] = w
                pending_size[1] = h
                resize_debounce_timer.start()

        embed_widget.size_settled.connect(on_embed_resized)

        idx = self.addTab(rdp_container, get_node_icon(node), format_tab_title(node))
        self.setCurrentIndex(idx)
        QTimer.singleShot(150, start_rdp)

    def _open_vnc_session(self, node: ConnectionNode):
        lang = self.settings.language
        vnc_container = QWidget(self)
        vbox = QVBoxLayout(vnc_container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Per-tab action bar
        action_bar = QWidget(vnc_container)
        action_bar.setObjectName("tab_action_bar")
        act_layout = QHBoxLayout(action_bar)
        act_layout.setContentsMargins(6, 2, 6, 2)

        lbl_info = QLabel(format_action_bar_info(node), action_bar)
        lbl_info.setStyleSheet("font-size: 11px; font-weight: normal;")
        act_layout.addWidget(lbl_info)

        act_layout.addStretch()

        btn_toggle_log = QPushButton(tr("sftp_log_btn", lang), action_bar)
        btn_toggle_log.setIcon(get_icon("settings"))
        btn_toggle_log.setCheckable(True)
        btn_toggle_log.setChecked(False)
        act_layout.addWidget(btn_toggle_log)

        btn_reconnect = QPushButton("Reconnect VNC", action_bar)
        btn_reconnect.setIcon(get_icon("refresh"))
        act_layout.addWidget(btn_reconnect)

        vbox.addWidget(action_bar)

        # Splitter: Native VNC Canvas / X11 Embed Container on Top, Diagnostic Log on Bottom
        splitter = QSplitter(Qt.Orientation.Vertical, vnc_container)

        vnc_widget = VNCWidget(hostname=node.hostname, port=node.port if node.port else 5900, password=node.password, parent=splitter)
        splitter.addWidget(vnc_widget)

        embed_widget = X11EmbedWidget(splitter)
        embed_layout = QVBoxLayout(embed_widget)
        lbl_status = QLabel(f"Launching System VNC Client to {node.hostname}:{node.port}...", embed_widget)
        lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_status.setStyleSheet("font-size: 11px; font-weight: normal;")
        embed_layout.addWidget(lbl_status)
        splitter.addWidget(embed_widget)
        embed_widget.setVisible(False)

        # VNC Log Console (Hidden by default)
        group_log = QGroupBox(tr("sftp_log_title", lang), splitter)
        log_vbox = QVBoxLayout(group_log)
        log_vbox.setContentsMargins(2, 2, 2, 2)

        txt_vnc_log = QPlainTextEdit(group_log)
        txt_vnc_log.setReadOnly(True)
        txt_vnc_log.setObjectName("log_console")
        txt_vnc_log.setStyleSheet("QPlainTextEdit#log_console { font-family: Monospace; font-size: 11px; }")
        log_vbox.addWidget(txt_vnc_log)
        splitter.addWidget(group_log)

        group_log.setVisible(False)
        btn_toggle_log.toggled.connect(group_log.setVisible)

        splitter.setSizes([600, 150])
        vbox.addWidget(splitter)

        def append_vnc_log_safe(text: str):
            cursor = txt_vnc_log.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(text)
            txt_vnc_log.setTextCursor(cursor)
            txt_vnc_log.ensureCursorVisible()
            if "[VNC Error]" in text or "[VNC Connection Failed]" in text or "Exited with Return Code:" in text:
                group_log.setVisible(True)
                btn_toggle_log.setChecked(True)

        def on_vnc_connection_failed(error_msg: str):
            append_vnc_log_safe(f"\n[VNC Connection Failed]: {error_msg}\n")

        vnc_widget.log_emitted.connect(append_vnc_log_safe)
        vnc_widget.connection_failed.connect(on_vnc_connection_failed)

        vnc_widget.node = node
        vnc_engine = VNCEngine(hostname=node.hostname, port=node.port if node.port else 5900, password=node.password)
        vnc_container.vnc_engine = vnc_engine
        vnc_container.vnc_widget = vnc_widget
        vnc_container.node = node
        vnc_container.lbl_info = lbl_info

        def trigger_vnc_fallback(reason: str):
            exe_path, _ = VNCEngine.get_vnc_executable()
            if not exe_path:
                msg = (
                    f"\n[VNC Error]: Server requires Security Type 11 (UltraVNC MSLogon / VeNCrypt).\n"
                    f"To view this VNC session embedded inside this tab without external windows, please install TigerVNC:\n"
                    f"  sudo apt install tigervnc-viewer\n"
                )
                append_vnc_log_safe(msg)
                group_log.setVisible(True)
                lbl_status.setText("VNC Type 11 requires 'tigervnc-viewer' (sudo apt install tigervnc-viewer)")
                vnc_widget.setVisible(False)
                embed_widget.setVisible(True)
                return

            append_vnc_log_safe(f"\n[VNC Fallback]: {reason}\nLaunching embedded TigerVNC client (vncviewer -embed)...\n")
            vnc_widget.setVisible(False)
            embed_widget.setVisible(True)
            win_id = None
            try:
                win_id = int(embed_widget.winId())
            except Exception:
                pass
            w = embed_widget.width() if embed_widget.width() > 100 else 1280
            h = embed_widget.height() if embed_widget.height() > 100 else 800
            vnc_engine.start_session(on_output=append_vnc_log_safe, win_id=win_id, width=w, height=h)

        vnc_widget.fallback_required.connect(trigger_vnc_fallback)

        def start_vnc():
            txt_vnc_log.clear()
            if embed_widget.isVisible():
                win_id = None
                try:
                    win_id = int(embed_widget.winId())
                except Exception:
                    pass
                w = embed_widget.width() if embed_widget.width() > 100 else 1280
                h = embed_widget.height() if embed_widget.height() > 100 else 800
                vnc_engine.start_session(on_output=append_vnc_log_safe, win_id=win_id, width=w, height=h)
            else:
                vnc_widget.start_session()

        btn_reconnect.clicked.connect(start_vnc)

        idx = self.addTab(vnc_container, get_node_icon(node), format_tab_title(node))
        self.setCurrentIndex(idx)
        start_vnc()


    def get_active_sessions_count(self) -> int:
        """Returns the number of currently open active remote session tabs (excluding Welcome tab)."""
        count = 0
        for i in range(self.count()):
            if self.tabText(i) not in ("Welcome", "Bienvenido"):
                count += 1
        return count

    def close_all_tabs(self, confirm: bool = False) -> bool:
        """Closes all open session tabs. Returns True if all tabs closed successfully."""
        for i in range(self.count() - 1, -1, -1):
            if not self.close_tab(i, confirm=confirm):
                return False
        return True

    def close_tab(self, index: int, confirm: bool = True) -> bool:
        """Closes tab at specified index, asking user confirmation for active session tabs if confirm is True."""
        if index < 0 or index >= self.count():
            return False

        tab_title = self.tabText(index)
        if tab_title in ("Welcome", "Bienvenido"):
            self.removeTab(index)
            return True

        if confirm:
            lang = self.settings.language
            msg = tr("confirm_close_tab_msg", lang).format(name=tab_title)
            title = tr("confirm_close_tab_title", lang)

            reply = QMessageBox.question(
                self,
                title,
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        widget = self.widget(index)
        if hasattr(widget, "term"):
            try:
                widget.term.close()
            except Exception:
                pass
        if hasattr(widget, "sftp_panel"):
            try:
                widget.sftp_panel.close()
            except Exception:
                pass
        if hasattr(widget, "rdp_engine"):
            try:
                widget.rdp_engine.stop_session()
            except Exception:
                pass
        if hasattr(widget, "vnc_engine"):
            try:
                widget.vnc_engine.stop_session()
            except Exception:
                pass
        if hasattr(widget, "vnc_widget"):
            try:
                widget.vnc_widget.stop_session()
            except Exception:
                pass

        self.removeTab(index)

        if self.count() == 0:
            self._show_welcome_tab()

        return True

    def _show_tab_context_menu(self, pos):
        index = self.tabBar().tabAt(pos)
        if index < 0:
            return

        widget = self.widget(index)
        if not widget or self.tabText(index) in ("Welcome", "Bienvenido"):
            return

        menu = QMenu(self)

        act_rename = QAction(get_icon("settings"), "Rename...", self)
        act_rename.triggered.connect(lambda: self._rename_tab(index))
        menu.addAction(act_rename)

        act_duplicate = QAction(get_icon("add"), "Duplicate", self)
        act_duplicate.triggered.connect(lambda: self._duplicate_tab(index))
        menu.addAction(act_duplicate)

        act_save = QAction(get_icon("save"), "Save Connection", self)
        act_save.triggered.connect(lambda: self._save_tab_connection(index))
        menu.addAction(act_save)

        menu.addSeparator()

        act_close = QAction(get_icon("close"), "Close Tab", self)
        act_close.triggered.connect(lambda: self.close_tab(index))
        menu.addAction(act_close)

        menu.exec(self.tabBar().mapToGlobal(pos))

    def _rename_tab(self, index: int):
        widget = self.widget(index)
        current_title = self.tabText(index)
        new_title, ok = QInputDialog.getText(
            self, "Rename Tab", "Enter new tab name:", QLineEdit.EchoMode.Normal, current_title
        )
        if ok and new_title.strip():
            clean_title = new_title.strip()
            self.setTabText(index, clean_title)
            if hasattr(widget, "node") and widget.node:
                widget.node.name = clean_title
                if hasattr(widget, "lbl_info") and widget.lbl_info:
                    widget.lbl_info.setText(format_action_bar_info(widget.node))

    def _duplicate_tab(self, index: int):
        widget = self.widget(index)
        if hasattr(widget, "node") and widget.node:
            self.open_session(widget.node)

    def update_node_tabs(self, node: ConnectionNode):
        """Updates open session tabs matching node.id with new title, icon, and info label."""
        if not node:
            return
        for i in range(self.count()):
            widget = self.widget(i)
            if hasattr(widget, "node") and widget.node and getattr(widget.node, "id", None) == node.id:
                self.setTabText(i, format_tab_title(node))
                self.setTabIcon(i, get_node_icon(node))
                if hasattr(widget, "lbl_info") and widget.lbl_info:
                    widget.lbl_info.setText(format_action_bar_info(node))

    def _save_tab_connection(self, index: int):
        widget = self.widget(index)
        if hasattr(widget, "node") and widget.node:
            node = widget.node
            main_win = self.window()
            if hasattr(main_win, "tree_widget"):
                parent_node = main_win.tree_widget.get_selected_node() or main_win.tree_widget.root_node
                main_win.tree_widget.add_new_connection(parent_node=parent_node, new_node=node)
                self.setTabText(index, format_tab_title(node))
                self.setTabIcon(index, get_node_icon(node))
                if hasattr(main_win, "_auto_save_connections"):
                    main_win._auto_save_connections()
                if hasattr(main_win, "statusBar"):
                    main_win.statusBar().showMessage(f"Saved connection '{node.name}' to tree.")
