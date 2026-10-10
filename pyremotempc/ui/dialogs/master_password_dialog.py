from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox
)

DEFAULT_MASTER_PASSWORD = "mR3m"


class MasterPasswordDialog(QDialog):
    """
    Dialog for prompting master password when opening/importing an encrypted connections file.
    Supports continuing without decrypting passwords (loads tree structure only).
    """

    def __init__(self, parent=None, is_default: bool = True, show_skip_passwords: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Master Encryption Password")
        self.setMinimumWidth(440)
        self._skip_passwords = False

        layout = QVBoxLayout(self)

        lbl = QLabel("Enter master password to decrypt connections file:")
        layout.addWidget(lbl)

        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        if is_default:
            self.txt_password.setText(DEFAULT_MASTER_PASSWORD)
        layout.addWidget(self.txt_password)

        self.chk_default = QCheckBox("Use default master password")
        self.chk_default.setChecked(is_default)
        layout.addWidget(self.chk_default)

        # Connect signals for dynamic syncing
        self.chk_default.toggled.connect(self._on_default_toggled)
        self.txt_password.textChanged.connect(self._on_text_changed)

        btn_layout = QHBoxLayout()

        if show_skip_passwords:
            btn_skip = QPushButton("Continue Without Passwords")
            btn_skip.setToolTip("Opens the connection tree without decrypting or loading saved passwords")
            btn_skip.clicked.connect(self._on_skip_clicked)
            btn_layout.addWidget(btn_skip)

        btn_layout.addStretch()

        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _on_skip_clicked(self):
        self._skip_passwords = True
        self.accept()

    def is_skip_passwords(self) -> bool:
        return self._skip_passwords

    def _on_default_toggled(self, checked: bool):
        self.txt_password.blockSignals(True)
        if checked:
            self.txt_password.setText(DEFAULT_MASTER_PASSWORD)
        else:
            if self.txt_password.text() == DEFAULT_MASTER_PASSWORD:
                self.txt_password.clear()
        self.txt_password.blockSignals(False)

    def _on_text_changed(self, text: str):
        self.chk_default.blockSignals(True)
        if text == DEFAULT_MASTER_PASSWORD:
            self.chk_default.setChecked(True)
        else:
            self.chk_default.setChecked(False)
        self.chk_default.blockSignals(False)

    def get_password(self) -> str:
        return self.txt_password.text() or DEFAULT_MASTER_PASSWORD
