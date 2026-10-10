import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QRadioButton, QButtonGroup,
    QListWidget, QListWidgetItem, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt
from pyremotempc.utils.key_loader import KeyLoader


class KeySelectorDialog(QDialog):
    """
    Dialog for selecting SSH private keys (file-based or ssh-agent identity).
    """

    def __init__(self, parent=None, current_key_path: str = "", current_auth_method: str = "key"):
        super().__init__(parent)
        self.setWindowTitle("Select SSH Private Key / Identity")
        self.resize(520, 380)

        self.selected_key_path = current_key_path
        self.selected_auth_method = current_auth_method
        self.passphrase = ""

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Auth Source Selection Group
        self.radio_group = QButtonGroup(self)
        
        self.radio_file = QRadioButton("Private Key File")
        self.radio_agent = QRadioButton("SSH Agent Identity (SSH_AUTH_SOCK)")
        
        self.radio_group.addButton(self.radio_file, 0)
        self.radio_group.addButton(self.radio_agent, 1)

        if self.selected_auth_method == "agent":
            self.radio_agent.setChecked(True)
        else:
            self.radio_file.setChecked(True)

        layout.addWidget(self.radio_file)

        # File Selection Box
        file_box = QGroupBox("Key File Settings")
        file_layout = QVBoxLayout(file_box)

        path_layout = QHBoxLayout()
        self.line_key_path = QLineEdit(self.selected_key_path)
        self.line_key_path.setPlaceholderText("Path to id_rsa, id_ed25519, etc.")
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_file)

        path_layout.addWidget(self.line_key_path)
        path_layout.addWidget(btn_browse)
        file_layout.addLayout(path_layout)

        pass_layout = QHBoxLayout()
        pass_layout.addWidget(QLabel("Key Passphrase (optional):"))
        self.line_passphrase = QLineEdit()
        self.line_passphrase.setEchoMode(QLineEdit.Password)
        pass_layout.addWidget(self.line_passphrase)
        file_layout.addLayout(pass_layout)

        layout.addWidget(file_box)

        # SSH Agent Group
        layout.addWidget(self.radio_agent)
        agent_box = QGroupBox("Available SSH Agent Keys")
        agent_layout = QVBoxLayout(agent_box)
        self.agent_list = QListWidget()
        agent_layout.addWidget(self.agent_list)
        layout.addWidget(agent_box)

        self._load_agent_keys()

        # Connect radio buttons
        self.radio_file.toggled.connect(self._on_auth_type_changed)
        self._on_auth_type_changed()

        # Dialog Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self._on_accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _load_agent_keys(self):
        self.agent_list.clear()
        agent_keys = KeyLoader.get_agent_keys()
        if not agent_keys:
            item = QListWidgetItem("No SSH Agent identities found or SSH_AUTH_SOCK not active.")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.agent_list.addItem(item)
        else:
            for fingerprint, display_text in agent_keys:
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, fingerprint)
                self.agent_list.addItem(item)

    def _browse_file(self):
        default_dir = os.path.expanduser("~/.ssh")
        if not os.path.exists(default_dir):
            default_dir = os.path.expanduser("~")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Private Key", default_dir,
            "SSH Private Keys (id_* *);;All Files (*)"
        )
        if file_path:
            self.line_key_path.setText(file_path)

    def _on_auth_type_changed(self):
        use_file = self.radio_file.isChecked()
        self.line_key_path.setEnabled(use_file)
        self.line_passphrase.setEnabled(use_file)
        self.agent_list.setEnabled(not use_file)

    def _on_accept(self):
        if self.radio_file.isChecked():
            key_path = self.line_key_path.text().strip()
            if not key_path:
                QMessageBox.warning(self, "Warning", "Please select a private key file path.")
                return
            if not os.path.exists(key_path):
                QMessageBox.warning(self, "Warning", f"The specified key file does not exist:\n{key_path}")
                return
            
            # Test loading key
            passphrase = self.line_passphrase.text() or None
            pkey, err = KeyLoader.load_private_key(key_path, passphrase=passphrase)
            if err and err == "Passphrase required" and not passphrase:
                QMessageBox.warning(self, "Passphrase Required", "This key file is encrypted. Please enter its passphrase.")
                return
            elif err and "Passphrase" in err:
                QMessageBox.warning(self, "Invalid Passphrase", "Failed to decrypt private key. Incorrect passphrase.")
                return
            
            self.selected_key_path = key_path
            self.selected_auth_method = "key"
            self.passphrase = passphrase or ""
        else:
            self.selected_key_path = ""
            self.selected_auth_method = "agent"

        self.accept()
