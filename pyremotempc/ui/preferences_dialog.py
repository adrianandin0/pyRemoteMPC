import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel,
    QLineEdit, QSpinBox, QCheckBox, QPushButton, QComboBox, QFileDialog,
    QMessageBox, QFormLayout, QGroupBox
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from pyremotempc.config.settings import SettingsManager
from pyremotempc.config.i18n import tr
from pyremotempc.crypto.master_key_manager import MasterKeyManager
from pyremotempc.ui.icon_manager import get_icon


def open_directory_in_file_manager(path: str, parent=None):
    """Opens directory path in OS native file manager."""
    expanded = os.path.expanduser(path.strip())
    if not os.path.exists(expanded):
        try:
            os.makedirs(expanded, exist_ok=True)
        except Exception:
            QMessageBox.warning(parent, "Error", f"Directory does not exist and could not be created:\n{expanded}")
            return
    QDesktopServices.openUrl(QUrl.fromLocalFile(expanded))


class PreferencesDialog(QDialog):
    """
    Preferences and Options Dialog for pyRemoteMPC.
    Tab 1: General (Language, Console Color, Font, Size, Theme, Default Directory)
    Tab 2: Terminal and Logs (Logs Directory, Enable Logging, Max Lines)
    Tab 3: Remote Desktop (RDP Clipboard, Drive Redirection Info)
    Tab 4: Security (Startup Auth, Change Master Key, Reset Master Key, Config Directory)
    """

    def __init__(self, settings_manager: SettingsManager, initial_tab: int = 0, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        self.lang = self.settings.language
        self.master_key_mgr = MasterKeyManager(self.settings)

        self.setWindowTitle(f"{tr('preferences', self.lang)} - pyRemoteMPC")
        self.setMinimumSize(720, 540)
        self.resize(720, 540)

        main_layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)

        # Tabs
        self._init_general_tab()
        self._init_terminal_logging_tab()
        self._init_rdp_tab()
        self._init_security_tab()

        if 0 <= initial_tab < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(initial_tab)

        # Bottom OK / Cancel Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_save = QPushButton(tr("save_apply", self.lang), self)
        self.btn_save.setIcon(get_icon("check"))
        self.btn_save.clicked.connect(self._on_save)
        btn_box.addWidget(self.btn_save)

        self.btn_cancel = QPushButton(tr("cancel", self.lang), self)
        self.btn_cancel.setIcon(get_icon("close"))
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        main_layout.addLayout(btn_box)

    def _init_general_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("User Preferences & Appearance", tab)
        form = QFormLayout(group)

        # Language Selector
        self.combo_lang = QComboBox(group)
        self.combo_lang.addItem("English", "en")
        self.combo_lang.addItem("Español", "es")
        current_lang = self.settings.language
        idx = self.combo_lang.findData(current_lang)
        self.combo_lang.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow(tr("language", self.lang) + ":", self.combo_lang)

        # Console Color Theme Selector
        self.combo_console = QComboBox(group)
        self.combo_console.addItems(["Classic Dark", "Green / Matrix", "Amber", "Light"])
        self.combo_console.setCurrentText(self.settings.get("console_theme", "Classic Dark"))
        form.addRow("Console Color:", self.combo_console)

        # Font Family Selector
        self.combo_font = QComboBox(group)
        self.combo_font.addItems(["Monospace", "DejaVu Sans Mono", "Courier New", "Consolas", "Liberation Mono"])
        self.combo_font.setCurrentText(self.settings.font_family)
        form.addRow(tr("font_family", self.lang) + ":", self.combo_font)

        # Font Size Selector
        self.spin_font_size = QSpinBox(group)
        self.spin_font_size.setRange(8, 28)
        self.spin_font_size.setValue(self.settings.font_size)
        form.addRow(tr("font_size", self.lang) + ":", self.spin_font_size)

        # Application Theme Selector (Dark / Light / Ocean / Forest)
        self.combo_theme = QComboBox(group)
        self.combo_theme.addItems(["Dark", "Light", "Ocean", "Forest"])
        current_theme = self.settings.theme if self.settings.theme in ("Dark", "Light", "Ocean", "Forest") else "Dark"
        self.combo_theme.setCurrentText(current_theme)
        form.addRow("App Theme:", self.combo_theme)

        # Default Directory (SFTP/SCP & RDP Mapping)
        dir_layout = QHBoxLayout()
        default_dir_val = self.settings.get("default_directory", self.settings.get("rdp_shared_folder", os.path.expanduser("~/RDP_Shared")))
        self.edit_default_dir = QLineEdit(group)
        self.edit_default_dir.setText(default_dir_val)
        dir_layout.addWidget(self.edit_default_dir)

        btn_browse_def = QPushButton(group)
        btn_browse_def.setIcon(get_icon("browse"))
        btn_browse_def.setToolTip("Browse Directory...")
        btn_browse_def.clicked.connect(self._browse_default_dir)
        dir_layout.addWidget(btn_browse_def)

        btn_open_def = QPushButton(group)
        btn_open_def.setIcon(get_icon("folder"))
        btn_open_def.setToolTip("Open Directory in File Manager")
        btn_open_def.clicked.connect(lambda: open_directory_in_file_manager(self.edit_default_dir.text(), self))
        dir_layout.addWidget(btn_open_def)

        form.addRow("Default Directory (SFTP/SCP & RDP):", dir_layout)

        layout.addWidget(group)
        layout.addStretch()
        self.tab_widget.addTab(tab, get_icon("settings"), "General")

    def _init_terminal_logging_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Logging Group
        group_log = QGroupBox("Logging & Session Output", tab)
        form_log = QFormLayout(group_log)

        self.chk_logging = QCheckBox(tr("enable_logging", self.lang), group_log)
        self.chk_logging.setChecked(self.settings.enable_logging)
        form_log.addRow(self.chk_logging)

        dir_layout = QHBoxLayout()
        self.edit_log_dir = QLineEdit(group_log)
        self.edit_log_dir.setText(self.settings.get("log_directory", "~/.config/pyremotempc/logs"))
        dir_layout.addWidget(self.edit_log_dir)

        btn_browse = QPushButton(group_log)
        btn_browse.setIcon(get_icon("browse"))
        btn_browse.setToolTip("Browse Logs Directory...")
        btn_browse.clicked.connect(self._browse_log_dir)
        dir_layout.addWidget(btn_browse)

        btn_open = QPushButton(group_log)
        btn_open.setIcon(get_icon("folder"))
        btn_open.setToolTip("Open Logs Directory in File Manager")
        btn_open.clicked.connect(lambda: open_directory_in_file_manager(self.edit_log_dir.text(), self))
        dir_layout.addWidget(btn_open)

        form_log.addRow("Logs Directory:", dir_layout)
        layout.addWidget(group_log)

        # Terminal Scrollback Group
        group_term = QGroupBox("Terminal Scrollback Buffer", tab)
        form_term = QFormLayout(group_term)

        self.spin_scrollback = QSpinBox(group_term)
        self.spin_scrollback.setRange(0, 1000000)
        self.spin_scrollback.setSingleStep(1000)
        self.spin_scrollback.setValue(self.settings.scrollback_lines)
        self.spin_scrollback.setSpecialValueText(tr("infinite_lines", self.lang))
        form_term.addRow("Max Lines:", self.spin_scrollback)

        lbl_info = QLabel("Note: Set to 0 for no limit on console scrollback lines.", group_term)
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #888888; font-size: 11px; font-weight: normal;")
        form_term.addRow(lbl_info)

        layout.addWidget(group_term)
        layout.addStretch()
        self.tab_widget.addTab(tab, get_icon("log"), "Terminal and Logs")

    def _init_rdp_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group_rdp = QGroupBox("Remote Desktop (RDP) Integration", tab)
        vbox_rdp = QVBoxLayout(group_rdp)

        form_rdp = QFormLayout()

        self.chk_rdp_clipboard = QCheckBox("Enable Clipboard Sharing (+clipboard)", group_rdp)
        self.chk_rdp_clipboard.setChecked(self.settings.rdp_enable_clipboard)
        form_rdp.addRow(self.chk_rdp_clipboard)

        self.chk_rdp_drive = QCheckBox("Map Local Shared Directory as Network Drive (/drive:Shared)", group_rdp)
        self.chk_rdp_drive.setChecked(self.settings.rdp_enable_drive_redirection)
        form_rdp.addRow(self.chk_rdp_drive)

        vbox_rdp.addLayout(form_rdp)

        lbl_info = QLabel(group_rdp)
        lbl_info.setWordWrap(True)
        lbl_info.setTextFormat(Qt.TextFormat.RichText)
        lbl_info.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        lbl_info.setStyleSheet(
            "QLabel { color: #3b82f6; font-size: 11px; font-weight: normal; "
            "background-color: #1e1e1e; border: 1px solid #3c3c3c; border-radius: 4px; padding: 10px; margin-top: 10px; text-align: left; }"
        )
        lbl_info.setText(
            "<b>Shared Drive Mapping:</b> Uses the Default Directory configured in the General tab mapped as a network drive "
            "('<i>\\\\tsclient\\Shared</i>' or drive letter) inside all remote Windows RDP sessions.<br><br>"
            "<b>Clipboard:</b> Allows seamless copy and paste of text and data between Linux and RDP servers."
        )
        vbox_rdp.addWidget(lbl_info)

        layout.addWidget(group_rdp)
        layout.addStretch()
        self.tab_widget.addTab(tab, get_icon("windows"), "Remote Desktop")

    def _init_security_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Startup Authentication Group
        group_startup = QGroupBox("Application Startup Security", tab)
        vbox_startup = QVBoxLayout(group_startup)

        self.chk_require_startup = QCheckBox("Ask for Master Password on application startup", group_startup)
        self.chk_require_startup.setChecked(self.settings.get("require_master_password_on_startup", False))
        self.chk_require_startup.toggled.connect(self._on_startup_toggled)
        vbox_startup.addWidget(self.chk_require_startup)

        self.lbl_startup_info = QLabel("If unchecked, pyRemoteMPC opens automatically without prompting for a password on startup.", group_startup)
        self.lbl_startup_info.setWordWrap(True)
        self.lbl_startup_info.setStyleSheet("color: #888888; font-size: 11px; margin-top: 4px;")
        vbox_startup.addWidget(self.lbl_startup_info)
        layout.addWidget(group_startup)

        # Master Password Change & Reset Group
        group_sec = QGroupBox("Master Password & Encryption Key", tab)
        form_sec = QFormLayout(group_sec)

        lbl_sec_info = QLabel(
            "Security Guarantee: Master Passwords use PBKDF2-HMAC-SHA256 (200,000 iterations + Salt). "
            "All saved connection passwords are AES-encrypted on disk. Plaintext passwords are NEVER saved in any file or configuration.",
            group_sec
        )
        lbl_sec_info.setWordWrap(True)
        lbl_sec_info.setStyleSheet("color: #4ec9b0; font-size: 11px; font-weight: normal; margin-bottom: 6px;")
        form_sec.addRow(lbl_sec_info)

        # Status badge label
        self.lbl_sec_status = QLabel(group_sec)
        self.lbl_sec_status.setWordWrap(True)
        form_sec.addRow(self.lbl_sec_status)

        self.edit_curr_pass = QLineEdit(group_sec)
        self.edit_curr_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form_sec.addRow(tr("current_pass", self.lang) + ":", self.edit_curr_pass)

        self.edit_new_pass = QLineEdit(group_sec)
        self.edit_new_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form_sec.addRow(tr("new_pass", self.lang) + ":", self.edit_new_pass)

        self.edit_confirm_pass = QLineEdit(group_sec)
        self.edit_confirm_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form_sec.addRow(tr("confirm_pass", self.lang) + ":", self.edit_confirm_pass)

        btn_sec_layout = QHBoxLayout()
        btn_change_key = QPushButton(tr("update_key", self.lang), group_sec)
        btn_change_key.setIcon(get_icon("security"))
        btn_change_key.clicked.connect(self._change_master_key)
        btn_sec_layout.addWidget(btn_change_key)

        btn_reset_key = QPushButton(tr("reset_default_key", self.lang), group_sec)
        btn_reset_key.setIcon(get_icon("refresh"))
        btn_reset_key.clicked.connect(self._reset_default_master_key)
        btn_sec_layout.addWidget(btn_reset_key)

        form_sec.addRow(btn_sec_layout)
        layout.addWidget(group_sec)

        # Config Directory Group
        group_cfg = QGroupBox("Application Configuration Storage", tab)
        form_cfg = QFormLayout(group_cfg)

        cfg_dir_layout = QHBoxLayout()
        default_cfg_dir = os.path.expanduser("~/.config/pyremotempc")
        self.edit_config_dir = QLineEdit(group_cfg)
        self.edit_config_dir.setText(self.settings.get("config_directory", default_cfg_dir))
        cfg_dir_layout.addWidget(self.edit_config_dir)

        btn_browse_cfg = QPushButton(group_cfg)
        btn_browse_cfg.setIcon(get_icon("browse"))
        btn_browse_cfg.setToolTip("Browse Config Directory...")
        btn_browse_cfg.clicked.connect(self._browse_config_dir)
        cfg_dir_layout.addWidget(btn_browse_cfg)

        btn_open_cfg = QPushButton(group_cfg)
        btn_open_cfg.setIcon(get_icon("folder"))
        btn_open_cfg.setToolTip("Open Config Directory in File Manager")
        btn_open_cfg.clicked.connect(lambda: open_directory_in_file_manager(self.edit_config_dir.text(), self))
        cfg_dir_layout.addWidget(btn_open_cfg)

        form_cfg.addRow("Config Directory:", cfg_dir_layout)
        layout.addWidget(group_cfg)

        self._update_security_status_display()
        self._on_startup_toggled(self.chk_require_startup.isChecked())

        layout.addStretch()
        self.tab_widget.addTab(tab, get_icon("security"), "Security")

    def _update_security_status_display(self):
        """Updates Master Password status banner and input placeholders dynamically."""
        is_set = self.master_key_mgr.is_master_key_set()
        if not is_set:
            self.lbl_sec_status.setText(f"● {tr('sec_status_default', self.lang)}")
            self.lbl_sec_status.setStyleSheet(
                "color: #eab308; font-size: 11px; font-weight: bold; padding: 5px 10px; "
                "background-color: rgba(234, 179, 8, 0.12); border: 1px solid rgba(234, 179, 8, 0.35); border-radius: 4px; margin-bottom: 6px;"
            )
            self.edit_curr_pass.setPlaceholderText(tr("current_pass_placeholder_default", self.lang))
        else:
            self.lbl_sec_status.setText(f"● {tr('sec_status_configured', self.lang)}")
            self.lbl_sec_status.setStyleSheet(
                "color: #4ec9b0; font-size: 11px; font-weight: bold; padding: 5px 10px; "
                "background-color: rgba(78, 201, 176, 0.12); border: 1px solid rgba(78, 201, 176, 0.35); border-radius: 4px; margin-bottom: 6px;"
            )
            self.edit_curr_pass.setPlaceholderText(tr("current_pass_placeholder_set", self.lang))

    def _on_startup_toggled(self, checked: bool):
        if checked and not self.master_key_mgr.is_master_key_set():
            self.lbl_startup_info.setText(tr("sec_startup_default_hint", self.lang))
            self.lbl_startup_info.setStyleSheet("color: #eab308; font-size: 11px; margin-top: 4px;")
        else:
            self.lbl_startup_info.setText("If unchecked, pyRemoteMPC opens automatically without prompting for a password on startup.")
            self.lbl_startup_info.setStyleSheet("color: #888888; font-size: 11px; margin-top: 4px;")

    def _browse_default_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Default Directory", os.path.expanduser(self.edit_default_dir.text())
        )
        if directory:
            self.edit_default_dir.setText(directory)

    def _browse_log_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Log Output Directory", os.path.expanduser(self.edit_log_dir.text())
        )
        if directory:
            self.edit_log_dir.setText(directory)

    def _browse_config_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Config Directory", os.path.expanduser(self.edit_config_dir.text())
        )
        if directory:
            self.edit_config_dir.setText(directory)

    def _change_master_key(self):
        curr_pass = self.edit_curr_pass.text()
        new_pass = self.edit_new_pass.text()
        confirm_pass = self.edit_confirm_pass.text()

        # If a custom master password was already set, require verifying current password
        if self.master_key_mgr.is_master_key_set():
            if not self.master_key_mgr.verify_master_key(curr_pass):
                QMessageBox.warning(self, tr("sec_error_title", self.lang), tr("sec_pass_incorrect_err", self.lang))
                return
        else:
            # First-time configuration: empty string or default "mR3m" are accepted
            if curr_pass and not self.master_key_mgr.verify_master_key(curr_pass):
                QMessageBox.warning(self, tr("sec_error_title", self.lang), tr("sec_pass_incorrect_err", self.lang))
                return

        if not new_pass:
            QMessageBox.warning(self, tr("sec_error_title", self.lang), tr("sec_pass_empty_err", self.lang))
            return

        if new_pass != confirm_pass:
            QMessageBox.warning(self, tr("sec_error_title", self.lang), tr("sec_pass_mismatch_err", self.lang))
            return

        self.master_key_mgr.set_master_key(new_pass)

        # Update parent main window master password in RAM and re-save encrypted file
        if self.parent() and hasattr(self.parent(), "master_password"):
            self.parent().master_password = new_pass
            if hasattr(self.parent(), "_auto_save_connections"):
                self.parent()._auto_save_connections()

        self.edit_curr_pass.clear()
        self.edit_new_pass.clear()
        self.edit_confirm_pass.clear()
        self._update_security_status_display()
        self._on_startup_toggled(self.chk_require_startup.isChecked())
        QMessageBox.information(self, tr("sec_updated_title", self.lang), tr("sec_update_success", self.lang))

    def _reset_default_master_key(self):
        # If a custom master password is set, verify current password first to prevent unauthorized resets
        if self.master_key_mgr.is_master_key_set():
            curr_pass = self.edit_curr_pass.text()
            if not curr_pass or not self.master_key_mgr.verify_master_key(curr_pass):
                QMessageBox.warning(
                    self,
                    tr("sec_error_title", self.lang),
                    tr("sec_pass_incorrect_err", self.lang)
                )
                self.edit_curr_pass.setFocus()
                return

        reply = QMessageBox.question(
            self,
            tr("sec_reset_confirm_title", self.lang),
            tr("sec_reset_confirm_msg", self.lang),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.master_key_mgr.reset_to_default()
            if self.parent() and hasattr(self.parent(), "master_password"):
                self.parent().master_password = "mR3m"
                if hasattr(self.parent(), "_auto_save_connections"):
                    self.parent()._auto_save_connections()

            self.edit_curr_pass.clear()
            self.edit_new_pass.clear()
            self.edit_confirm_pass.clear()
            self._update_security_status_display()
            self._on_startup_toggled(self.chk_require_startup.isChecked())
            QMessageBox.information(self, tr("sec_reset_success_title", self.lang), tr("sec_reset_success", self.lang))

    def _on_save(self):
        selected_lang = self.combo_lang.currentData()
        self.settings.set("language", selected_lang)
        new_theme = self.combo_theme.currentText()
        self.settings.set("theme", new_theme)
        self.settings.set("console_theme", self.combo_console.currentText())
        self.settings.set("font_family", self.combo_font.currentText())
        self.settings.set("font_size", self.spin_font_size.value())
        self.settings.set("default_directory", self.edit_default_dir.text().strip())
        self.settings.set("enable_logging", self.chk_logging.isChecked())
        self.settings.set("log_directory", self.edit_log_dir.text().strip())
        self.settings.set("scrollback_lines", self.spin_scrollback.value())
        self.settings.set("require_master_password_on_startup", self.chk_require_startup.isChecked())
        self.settings.set("rdp_enable_clipboard", self.chk_rdp_clipboard.isChecked())
        self.settings.set("rdp_enable_drive_redirection", self.chk_rdp_drive.isChecked())
        self.settings.set("rdp_shared_folder", self.edit_default_dir.text().strip())
        self.settings.set("config_directory", self.edit_config_dir.text().strip())

        from pyremotempc.ui.theme_manager import apply_theme
        apply_theme(new_theme)
        self.accept()
