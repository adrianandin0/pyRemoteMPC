from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QDialogButtonBox
)
from PySide6.QtCore import Qt
from pyremotempc.ui.icon_manager import get_icon


class ImportFolderDialog(QDialog):
    """
    Dialog prompting user for target folder name and icon before completing import.
    """

    def __init__(self, parent=None, default_name: str = "Imported from File", default_icon: str = "Folder"):
        super().__init__(parent)
        self.setWindowTitle("Import Connections")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Folder Name
        lbl_name = QLabel("Root Folder Name:")
        self.txt_name = QLineEdit(default_name)
        self.txt_name.selectAll()
        layout.addWidget(lbl_name)
        layout.addWidget(self.txt_name)

        # Folder Icon
        lbl_icon = QLabel("Root Folder Icon:")
        self.cbo_icon = QComboBox()

        icons_list = [
            ("Folder", "folder"),
            ("Connections", "connections"),
            ("Server", "server"),
            ("Network", "network"),
            ("Linux", "linux"),
            ("Windows", "windows"),
            ("Database", "database"),
            ("Storage", "storage"),
            ("Virtual Machine", "vm"),
            ("Terminal", "terminal"),
            ("Security", "security"),
        ]

        for label, icon_key in icons_list:
            icon = get_icon(icon_key)
            self.cbo_icon.addItem(icon, label, userData=icon_key)

        # Set default icon selection
        for i in range(self.cbo_icon.count()):
            if self.cbo_icon.itemData(i) == default_icon.lower():
                self.cbo_icon.setCurrentIndex(i)
                break

        layout.addWidget(lbl_icon)
        layout.addWidget(self.cbo_icon)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_folder_name(self) -> str:
        name = self.txt_name.text().strip()
        return name if name else "Imported from File"

    def get_folder_icon(self) -> str:
        return self.cbo_icon.currentData() or "Folder"
