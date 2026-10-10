import math
import time
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QCheckBox, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, Signal, QSize, QCoreApplication
from PySide6.QtGui import QIcon
from pyremotempc.ui.icon_manager import get_icon


FLAT_BTN_STYLE = (
    "QPushButton { border: none; background: transparent; padding: 4px 10px; font-size: 11px; } "
    "QPushButton:hover { background-color: rgba(255, 255, 255, 30); border-radius: 4px; } "
    "QPushButton:pressed { background-color: rgba(255, 255, 255, 50); border-radius: 4px; } "
    "QPushButton:disabled { color: #666666; }"
)


def format_bytes(size_bytes: float) -> str:
    """Format bytes to human readable string (B, KB, MB, GB)."""
    if size_bytes <= 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"


def format_seconds(seconds: float) -> str:
    """Format seconds into HH:MM:SS format."""
    if seconds < 0 or math.isinf(seconds) or math.isnan(seconds):
        return "--:--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class SFTPTransferDialog(QDialog):
    """
    Compact, non-blocking SFTP Transfer Progress Dialog.
    Displays individual file progress, total batch progress, current speed, ETA,
    Pause/Resume, Cancel, Overwrite All, and Overwrite conflict prompts.
    """
    pause_toggled_signal = Signal(bool)
    cancel_requested_signal = Signal()
    overwrite_all_toggled_signal = Signal(bool)

    def __init__(self, transfer_type: str = "upload", parent=None):
        super().__init__(parent)
        self.transfer_type = transfer_type.lower()
        self.is_paused = False

        self.setWindowTitle("SFTP Transfer Progress")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        self.resize(640, 200)
        self.setMinimumWidth(600)
        self.setMinimumHeight(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # File Status Label
        self.lbl_file_status = QLabel("Preparing transfer...", self)
        self.lbl_file_status.setStyleSheet("font-size: 11px; font-weight: bold;")
        layout.addWidget(self.lbl_file_status)

        # Current File Progress Bar
        self.progress_file = QProgressBar(self)
        self.progress_file.setRange(0, 100)
        self.progress_file.setValue(0)
        self.progress_file.setTextVisible(True)
        self.progress_file.setFixedHeight(18)
        self.progress_file.setStyleSheet("QProgressBar { font-size: 10px; height: 18px; }")
        layout.addWidget(self.progress_file)

        # Total Batch Status Label
        self.lbl_total_status = QLabel("Overall Progress: 0 of 0 files", self)
        self.lbl_total_status.setStyleSheet("font-size: 11px; color: #aaaaaa;")
        layout.addWidget(self.lbl_total_status)

        # Total Progress Bar
        self.progress_total = QProgressBar(self)
        self.progress_total.setRange(0, 100)
        self.progress_total.setValue(0)
        self.progress_total.setTextVisible(True)
        self.progress_total.setFixedHeight(18)
        self.progress_total.setStyleSheet("QProgressBar { font-size: 10px; height: 18px; }")
        layout.addWidget(self.progress_total)

        # Information Bar (Speed, Transferred Bytes, ETA)
        info_layout = QHBoxLayout()
        info_layout.setSpacing(16)

        self.lbl_speed = QLabel("Speed: 0 B/s", self)
        self.lbl_speed.setStyleSheet("font-size: 11px;")
        info_layout.addWidget(self.lbl_speed)

        self.lbl_bytes = QLabel("Transferred: 0 B / 0 B", self)
        self.lbl_bytes.setStyleSheet("font-size: 11px;")
        info_layout.addWidget(self.lbl_bytes)

        self.lbl_eta = QLabel("ETA: --:--:--", self)
        self.lbl_eta.setStyleSheet("font-size: 11px;")
        info_layout.addWidget(self.lbl_eta)

        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Control Action Bar (Overwrite All, Pause/Resume, Cancel)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)

        self.chk_overwrite_all = QCheckBox("Overwrite All", self)
        self.chk_overwrite_all.setStyleSheet("font-size: 11px;")
        self.chk_overwrite_all.toggled.connect(self._on_overwrite_all_toggled)
        ctrl_layout.addWidget(self.chk_overwrite_all)

        ctrl_layout.addStretch()

        self.btn_pause_resume = QPushButton("Pause", self)
        self.btn_pause_resume.setStyleSheet(FLAT_BTN_STYLE)
        self.btn_pause_resume.setToolTip("Pause / Resume transfer")
        self.btn_pause_resume.clicked.connect(self._toggle_pause)
        ctrl_layout.addWidget(self.btn_pause_resume)

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setStyleSheet(FLAT_BTN_STYLE)
        self.btn_cancel.setToolTip("Cancel transfer")
        self.btn_cancel.clicked.connect(self._on_cancel)
        ctrl_layout.addWidget(self.btn_cancel)

        layout.addLayout(ctrl_layout)

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause_resume.setText("Resume")
            self.lbl_file_status.setText(f"[PAUSED] {self.lbl_file_status.text().replace('[PAUSED] ', '')}")
        else:
            self.btn_pause_resume.setText("Pause")
            self.lbl_file_status.setText(self.lbl_file_status.text().replace('[PAUSED] ', ''))
        self.pause_toggled_signal.emit(self.is_paused)

    def _on_cancel(self):
        self.btn_pause_resume.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.lbl_file_status.setText("Cancelling transfer...")
        self.cancel_requested_signal.emit()

    def _on_overwrite_all_toggled(self, checked: bool):
        self.overwrite_all_toggled_signal.emit(checked)

    def update_progress(self, file_done: int, file_total: int, batch_done: int, batch_total: int,
                        speed_bps: float, eta_secs: float, file_name: str, file_num: int, total_files: int):
        if file_name and file_name.startswith("Scanning:"):
            self.lbl_file_status.setText(file_name)
            self.lbl_total_status.setText(f"Scanning target items... ({total_files} files found so far)")
            return

        # Current file progress
        file_pct = int((file_done / file_total) * 100) if file_total > 0 else 0
        self.progress_file.setValue(min(100, max(0, file_pct)))
        self.progress_file.repaint()

        # Batch progress
        batch_pct = int((batch_done / batch_total) * 100) if batch_total > 0 else 0
        self.progress_total.setValue(min(100, max(0, batch_pct)))
        self.progress_total.repaint()

        action_str = "Uploading" if self.transfer_type == "upload" else "Downloading"
        paused_prefix = "[PAUSED] " if self.is_paused else ""
        self.lbl_file_status.setText(f"{paused_prefix}{action_str}: '{file_name}' ({file_num} of {total_files})")
        self.lbl_file_status.repaint()

        self.lbl_total_status.setText(f"Overall Progress: {batch_pct}% ({file_num} / {total_files} files)")
        self.lbl_total_status.repaint()

        # Stats
        speed_str = f"{format_bytes(speed_bps)}/s" if speed_bps > 0 else "0 B/s"
        bytes_str = f"{format_bytes(batch_done)} / {format_bytes(batch_total)}"
        eta_str = format_seconds(eta_secs)

        self.lbl_speed.setText(f"Speed: {speed_str}")
        self.lbl_speed.repaint()
        self.lbl_bytes.setText(f"Transferred: {bytes_str}")
        self.lbl_bytes.repaint()
        self.lbl_eta.setText(f"ETA: {eta_str}")
        self.lbl_eta.repaint()
        QCoreApplication.processEvents()

    def prompt_conflict(self, item_name: str, is_dir: bool) -> str:
        """
        Prompts user when target file/directory already exists.
        Returns: 'overwrite', 'skip', 'overwrite_all', 'skip_all', or 'cancel'.
        """
        item_type = "directory" if is_dir else "file"
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("File Conflict")
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setText(f"The {item_type} '{item_name}' already exists at destination.\nWhat would you like to do?")

        btn_overwrite = msg_box.addButton("Overwrite", QMessageBox.ButtonRole.AcceptRole)
        btn_skip = msg_box.addButton("Skip", QMessageBox.ButtonRole.RejectRole)
        btn_overwrite_all = msg_box.addButton("Overwrite All", QMessageBox.ButtonRole.ActionRole)
        btn_skip_all = msg_box.addButton("Skip All", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg_box.addButton("Cancel", QMessageBox.ButtonRole.DestructiveRole)

        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == btn_overwrite:
            return "overwrite"
        elif clicked == btn_skip:
            return "skip"
        elif clicked == btn_overwrite_all:
            self.chk_overwrite_all.setChecked(True)
            return "overwrite_all"
        elif clicked == btn_skip_all:
            return "skip_all"
        else:
            return "cancel"

    def set_completed(self, transfer_type: str, total_files: int, total_bytes: int):
        self.progress_file.setValue(100)
        self.progress_total.setValue(100)
        action_past = "Uploaded" if transfer_type.lower() == "upload" else "Downloaded"
        self.lbl_file_status.setText(f"{action_past} {total_files} of {total_files} items (100%).")
        self.lbl_total_status.setText(f"Overall Progress: 100% ({total_files} / {total_files} files)")
        self.lbl_bytes.setText(f"Transferred: {format_bytes(total_bytes)} / {format_bytes(total_bytes)}")
        self.lbl_speed.setText("Speed: 0 B/s")
        self.lbl_eta.setText("ETA: 00:00:00")
        self.btn_pause_resume.setEnabled(False)
        self.btn_cancel.setText("Close")
        self.btn_cancel.setEnabled(True)

    def closeEvent(self, event):
        self._on_cancel()
        super().closeEvent(event)
