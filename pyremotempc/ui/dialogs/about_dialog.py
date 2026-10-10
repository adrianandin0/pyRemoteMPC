import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt
from pyremotempc.ui.icon_manager import get_icon
from pyremotempc.config.version import get_version


# Text color for links per theme — matches the main text color of each theme exactly
_THEME_LINK_COLOR = {
    "Dark":   "#cccccc",
    "Light":  "#1c1c1e",
    "Ocean":  "#e0e6ed",
    "Forest": "#e2e8f0",
}


class AboutDialog(QDialog):
    """
    About pyRemoteMPC dialog. Fully theme-aware.
    Displays version, supported protocols, author contacts, and graphic credits.
    """

    def __init__(self, parent=None, theme: str = "Dark"):
        super().__init__(parent)
        self.setWindowTitle("About pyRemoteMPC")
        self.setFixedSize(620, 680)
        self._link_color = _THEME_LINK_COLOR.get(theme, "#cccccc")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        # ── Top Header ────────────────────────────────────────────────────
        header_frame = QFrame(self)
        header_frame.setObjectName("about_card")
        header_frame.setStyleSheet(
            "QFrame#about_card { border: 1px solid rgba(128,128,128,0.3); border-radius: 8px; }"
        )

        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(14)

        lbl_icon = QLabel(header_frame)
        lbl_icon.setPixmap(get_icon("pyremotempc").pixmap(56, 56))
        header_layout.addWidget(lbl_icon, 0, Qt.AlignmentFlag.AlignTop)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)

        lbl_title = QLabel("<b>pyRemoteMPC</b>", header_frame)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold;")
        title_vbox.addWidget(lbl_title)

        lbl_sub = QLabel(
            "<b>py</b>thon <b>Remote</b> <b>M</b>ulti-<b>P</b>rotocol <b>C</b>onnections",
            header_frame,
        )
        lbl_sub.setStyleSheet("font-size: 12px;")
        title_vbox.addWidget(lbl_sub)

        version_str = get_version()
        lbl_version = QLabel(f"<b>Version:</b> {version_str}", header_frame)
        lbl_version.setStyleSheet("font-size: 12px; font-weight: bold;")
        title_vbox.addWidget(lbl_version)

        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        layout.addWidget(header_frame)

        # ── Body ──────────────────────────────────────────────────────────
        body_frame = QFrame(self)
        body_frame.setObjectName("about_card")
        body_frame.setStyleSheet(
            "QFrame#about_card { border: 1px solid rgba(128,128,128,0.3); border-radius: 8px; }"
        )

        body_layout = QVBoxLayout(body_frame)
        body_layout.setContentsMargins(18, 16, 18, 16)
        body_layout.setSpacing(0)

        lc = self._link_color
        body_html = f"""
        <div style="font-size: 11px; font-weight: normal; line-height: 1.6;">
            <p style="margin-top: 0; margin-bottom: 10px; font-size: 13px;">
                <b>Native Python Multi-Protocol Remote Connections Manager for GNU/Linux.</b>
            </p>
            <p style="margin-bottom: 4px; font-weight: bold; font-size: 12px;">Supported Protocols &amp; Features:</p>
            <ul style="margin-top: 2px; margin-bottom: 10px; padding-left: 18px;">
                <li style="margin-bottom: 4px;"><b>SSH2 &amp; SSH1</b> &mdash; Terminal sessions (VT100/xterm), key support, legacy ciphers &amp; KEX.</li>
                <li style="margin-bottom: 4px;"><b>SFTP, FTP &amp; SCP</b> &mdash; Tab-integrated dual-pane file manager with drag-and-drop, permissions editor, and background file transfers.</li>
                <li style="margin-bottom: 4px;"><b>RDP</b> &mdash; Remote Desktop Protocol with native container window embedding (FreeRDP), clipboard sharing, and shared drive mapping.</li>
                <li style="margin-bottom: 4px;"><b>VNC</b> &mdash; Remote desktop support (UltraVNC MSLogon / Standard VNC authentication).</li>
                <li style="margin-bottom: 4px;"><b>TELNET &amp; SERIAL</b> &mdash; Telnet and TTY/COM serial ports with auto-detection and baud rate selection.</li>
                <li style="margin-bottom: 4px;"><b>Multi-Format Import / Export</b> &mdash; mRemoteNG XML, SecureCRT XML, Asbr&uacute; YAML, and Microsoft RDCMan (.rdg).</li>
                <li style="margin-bottom: 4px;"><b>Security Layer</b> &mdash; Master Password, PBKDF2-HMAC-SHA256, AES-256-GCM, startup auth, and Read-Only mode.</li>
            </ul>
            <hr style="border: none; border-top: 1px solid rgba(128,128,128,0.3); margin: 8px 0;" />
            <p style="margin: 4px 0;"><b>Author:</b> <a href="https://www.linkedin.com/in/adrianandino/" style="color: {lc}; text-decoration: underline;">Adrián Andino</a></p>
            <p style="margin: 4px 0;"><b>Contact:</b> <a href="mailto:adrianandino@pm.me" style="color: {lc}; text-decoration: underline;">adrianandino@pm.me</a></p>
            <p style="margin: 4px 0;"><b>X:</b> <a href="https://x.com/adrian_and_ino" style="color: {lc}; text-decoration: underline;">@adrian_and_ino</a></p>
            <p style="margin: 4px 0;"><b>Repo:</b> <a href="https://github.com/adrianandin0/pyRemoteMPC" style="color: {lc}; text-decoration: underline;">pyRemoteMPC</a></p>
            <p style="margin: 4px 0;"><b>Credits:</b> Icons and graphical assets from <a href="https://www.flaticon.com/" style="color: {lc}; text-decoration: underline;">Flaticon</a> by <a href="https://www.flaticon.com/authors/magnific" style="color: {lc}; text-decoration: underline;">Magnific</a>.</p>
        </div>
        """
        lbl_body = QLabel(body_frame)
        lbl_body.setWordWrap(True)
        lbl_body.setTextFormat(Qt.TextFormat.RichText)
        lbl_body.setOpenExternalLinks(True)
        lbl_body.setText(body_html)
        body_layout.addWidget(lbl_body)

        layout.addWidget(body_frame)

        # ── Close Button ──────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close / Cerrar", self)
        btn_close.setFixedWidth(130)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
