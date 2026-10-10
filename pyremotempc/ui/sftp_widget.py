import os
import shutil
import time
from typing import Optional, List, Dict, Any, Tuple, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QPushButton, QLabel, QMessageBox, QFileDialog, QHeaderView, QPlainTextEdit, QGroupBox, QCheckBox,
    QMenu, QInputDialog
)
from PySide6.QtCore import Qt, QSize, QThread, Signal, QObject
from PySide6.QtGui import QIcon, QTextCursor
from pyremotempc.engine.file_transfer import UnifiedFileTransferEngine
from pyremotempc.config.settings import SettingsManager
from pyremotempc.config.i18n import tr
from pyremotempc.ui.icon_manager import get_icon


class LogBridge(QObject):
    log_received = Signal(str)


class SFTPConnectWorker(QThread):
    finished_signal = Signal(bool, str, list, str)

    def __init__(self, sftp_engine, remote_path=".", parent=None):
        super().__init__(parent)
        self.sftp_engine = sftp_engine
        self.remote_path = remote_path

    def run(self):
        try:
            connected = self.sftp_engine.connect()
            if not connected:
                self.finished_signal.emit(False, "", [], "Could not establish SFTP connection.")
                return

            current_dir = self.sftp_engine.get_current_dir()
            target_path = self.remote_path if self.remote_path and self.remote_path != "." else (current_dir if current_dir != "." else "/")
            items = self.sftp_engine.list_remote_dir(target_path)
            self.finished_signal.emit(True, target_path, items, "")
        except Exception as e:
            self.sftp_engine.disconnect()
            self.finished_signal.emit(False, "", [], str(e))


class SFTPListWorker(QThread):
    finished_signal = Signal(bool, str, list, str)

    def __init__(self, sftp_engine, remote_path, parent=None):
        super().__init__(parent)
        self.sftp_engine = sftp_engine
        self.remote_path = remote_path

    def run(self):
        try:
            items = self.sftp_engine.list_remote_dir(self.remote_path)
            self.finished_signal.emit(True, self.remote_path, items, "")
        except Exception as e:
            self.finished_signal.emit(False, self.remote_path, [], str(e))


from threading import Event
from pyremotempc.ui.sftp_transfer_dialog import SFTPTransferDialog


class SFTPTransferWorker(QThread):
    # progress_signal: (file_bytes_done, file_size, batch_bytes_done, batch_bytes_total, speed_bps, eta_secs, file_name, file_num, total_files)
    progress_signal = Signal(int, int, int, int, float, float, str, int, int)
    # conflict_requested_signal: (item_name, is_dir)
    conflict_requested_signal = Signal(str, bool)
    # finished_signal: (success, error_msg)
    finished_signal = Signal(bool, str)

    def __init__(self, sftp_engine, transfer_type: str, items: list, source_dir: str, target_dir: str, parent=None):
        super().__init__(parent)
        self.sftp_engine = sftp_engine
        self.transfer_type = transfer_type.lower()  # "upload" or "download"
        self.items = items
        self.source_dir = source_dir
        self.target_dir = target_dir

        self.is_paused = False
        self.is_cancelled = False
        self.overwrite_all = False
        self.skip_all = False

        self.conflict_event = Event()
        self.conflict_action = "overwrite"

        self.batch_bytes_done = 0
        self.batch_bytes_total = 0
        self.start_time = time.time()

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def cancel(self):
        self.is_cancelled = True
        self.conflict_event.set()

    def set_conflict_resolution(self, action: str):
        self.conflict_action = action
        if action == "overwrite_all":
            self.overwrite_all = True
        elif action == "skip_all":
            self.skip_all = True
        elif action == "cancel":
            self.is_cancelled = True
        self.conflict_event.set()

    def run(self):
        try:
            tasks = self._collect_tasks()
            self.batch_bytes_total = sum(t["size"] for t in tasks)
            total_files = len(tasks)
            self.start_time = time.time()

            if total_files == 0:
                self.finished_signal.emit(True, "")
                return

            for idx, task in enumerate(tasks, start=1):
                if self.is_cancelled:
                    break

                src_path = task["src"]
                dst_path = task["dst"]
                file_size = task["size"]
                file_name = task["name"]

                target_exists = False
                if self.transfer_type == "upload":
                    target_exists = self.sftp_engine.remote_exists(dst_path)
                else:
                    target_exists = os.path.exists(dst_path)

                if target_exists:
                    if self.skip_all:
                        self.batch_bytes_done += file_size
                        continue
                    elif not self.overwrite_all:
                        self.conflict_event.clear()
                        self.conflict_requested_signal.emit(file_name, False)
                        self.conflict_event.wait()

                        if self.is_cancelled or self.conflict_action == "cancel":
                            break
                        if self.conflict_action in ("skip", "skip_all"):
                            self.batch_bytes_done += file_size
                            continue

                self._transfer_file(src_path, dst_path, file_size, idx, total_files, file_name)

            if self.is_cancelled:
                self.finished_signal.emit(False, "Transfer cancelled by user.")
            else:
                self.finished_signal.emit(True, "")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def _collect_tasks(self) -> list:
        tasks = []
        for item in self.items:
            if self.is_cancelled:
                break
            name = item["name"]
            src_path = item["path"]
            is_dir = item["is_dir"]
            dst_path = os.path.join(self.target_dir, name).replace("\\", "/")

            self.progress_signal.emit(0, 0, 0, 0, 0, 0, f"Scanning: {name}", len(tasks), len(tasks))

            if not is_dir:
                size = 0
                if self.transfer_type == "upload":
                    try:
                        size = os.path.getsize(src_path)
                    except Exception:
                        size = 0
                else:
                    size = item.get("size", 0)
                tasks.append({"src": src_path, "dst": dst_path, "size": size, "name": name})
            else:
                if self.transfer_type == "upload":
                    base_dir = os.path.dirname(src_path)
                    for root, dirs, files in os.walk(src_path):
                        if self.is_cancelled:
                            break
                        rel_path = os.path.relpath(root, base_dir)
                        rem_dir = os.path.join(self.target_dir, rel_path).replace("\\", "/")
                        for f in files:
                            l_file = os.path.join(root, f)
                            r_file = os.path.join(rem_dir, f).replace("\\", "/")
                            try:
                                f_size = os.path.getsize(l_file)
                            except Exception:
                                f_size = 0
                            tasks.append({"src": l_file, "dst": r_file, "size": f_size, "name": f})
                            self.progress_signal.emit(0, 0, 0, 0, 0, 0, f"Scanning: {f}", len(tasks), len(tasks))
                else:
                    base_dir = os.path.dirname(src_path.rstrip("/"))
                    self._collect_remote_tasks(src_path, base_dir, tasks)
        return tasks

    def _collect_remote_tasks(self, rem_dir: str, base_dir: str, tasks: list):
        try:
            items = self.sftp_engine.list_remote_dir(rem_dir)
            rel_path = os.path.relpath(rem_dir, base_dir) if base_dir else rem_dir
            loc_dir = os.path.join(self.target_dir, rel_path)
            for item in items:
                if self.is_cancelled:
                    break
                r_name = item["name"]
                if r_name in (".", ".."):
                    continue
                r_path = os.path.join(rem_dir, r_name).replace("\\", "/")
                l_path = os.path.join(loc_dir, r_name)
                if item["is_dir"]:
                    self._collect_remote_tasks(r_path, base_dir, tasks)
                else:
                    tasks.append({"src": r_path, "dst": l_path, "size": item.get("size", 0), "name": r_name})
                    self.progress_signal.emit(0, 0, 0, 0, 0, 0, f"Scanning: {r_name}", len(tasks), len(tasks))
        except Exception:
            pass

    def _transfer_file(self, src_path: str, dst_path: str, file_size: int,
                        file_num: int, total_files: int, file_name: str):
        if self.transfer_type == "upload":
            dst_dir = os.path.dirname(dst_path)
            if dst_dir and dst_dir != ".":
                try:
                    self.sftp_engine.create_remote_dir(dst_dir)
                except Exception:
                    pass
        else:
            dst_dir = os.path.dirname(dst_path)
            if dst_dir:
                os.makedirs(dst_dir, exist_ok=True)

        file_bytes_done = 0

        # Reset current file progress bar to 0% immediately upon starting file transfer
        self.progress_signal.emit(
            0, file_size, self.batch_bytes_done, self.batch_bytes_total,
            0.0, 0.0, file_name, file_num, total_files
        )

        def _cb(transferred, total):
            if self.is_cancelled:
                raise Exception("Transfer cancelled by user.")
            while self.is_paused and not self.is_cancelled:
                time.sleep(0.1)

            nonlocal file_bytes_done
            diff = transferred - file_bytes_done
            if diff > 0:
                file_bytes_done = transferred
                self.batch_bytes_done += diff

            now = time.time()
            elapsed = now - self.start_time
            speed = self.batch_bytes_done / elapsed if elapsed > 0 else 0
            rem_bytes = self.batch_bytes_total - self.batch_bytes_done
            eta = rem_bytes / speed if speed > 0 else 0

            tot = total if total > 0 else file_size
            self.progress_signal.emit(
                transferred, tot, self.batch_bytes_done, self.batch_bytes_total,
                speed, eta, file_name, file_num, total_files
            )

        if self.transfer_type == "upload":
            self.sftp_engine.upload_file(src_path, dst_path, progress_callback=_cb)
        else:
            self.sftp_engine.download_file(src_path, dst_path, progress_callback=_cb)




class CustomTreeWidgetItem(QTreeWidgetItem):
    """
    Custom QTreeWidgetItem for sorting Name alphabetically and Size numerically,
    while keeping directories grouped at the top and '..' permanently at row 0.
    """
    def __lt__(self, other):
        tree = self.treeWidget()
        col = tree.sortColumn() if tree else 0
        is_asc = True
        if tree and tree.header():
            is_asc = (tree.header().sortIndicatorOrder() == Qt.SortOrder.AscendingOrder)

        if self.text(0) == "..":
            return is_asc
        if other.text(0) == "..":
            return not is_asc

        is_dir_self = bool(self.data(1, Qt.ItemDataRole.UserRole))
        is_dir_other = bool(other.data(1, Qt.ItemDataRole.UserRole))

        if is_dir_self != is_dir_other:
            return (is_dir_self > is_dir_other) if is_asc else (is_dir_self < is_dir_other)

        if col == 1:
            size_self = self.data(1, Qt.ItemDataRole.UserRole + 1) or 0
            size_other = other.data(1, Qt.ItemDataRole.UserRole + 1) or 0
            return size_self < size_other

        return self.text(col).lower() < other.text(col).lower()


class SFTPWidget(QWidget):
    """
    Integrated SFTP File Manager Widget.
    Provides dual-panel file management (Local Linux system vs Remote Host) per active session.
    Includes live Diagnostic Log console for immediate troubleshooting.
    """

    def __init__(self, node, ssh_engine=None, settings_manager: Optional[SettingsManager] = None, parent=None):
        super().__init__(parent)
        self.node = node
        self.ssh_engine = ssh_engine
        self.settings = settings_manager or SettingsManager()
        self.lang = self.settings.language

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Top Control Bar
        top_bar = QHBoxLayout()
        self.lbl_status = QLabel(f"SFTP Session: {self.node.username}@{self.node.hostname}:{self.node.port}", self)
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()

        self.btn_toggle_log = QPushButton(tr("sftp_log_btn", self.lang), self)
        self.btn_toggle_log.setIcon(get_icon("log"))
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.clicked.connect(self._toggle_log_view)
        top_bar.addWidget(self.btn_toggle_log)

        self.btn_connect = QPushButton(self)
        self.btn_connect.setIcon(get_icon("connect"))
        self.btn_connect.setToolTip(tr("connect_sftp", self.lang))
        self.btn_connect.clicked.connect(self.connect_sftp)
        top_bar.addWidget(self.btn_connect)

        self.chk_show_hidden = QCheckBox(tr("show_hidden_files", self.lang), self)
        self.chk_show_hidden.setChecked(False)
        self.chk_show_hidden.toggled.connect(self.refresh_all)
        top_bar.addWidget(self.chk_show_hidden)

        FLAT_BTN_STYLE = (
            "QPushButton { border: none; background: transparent; padding: 2px; } "
            "QPushButton:hover { background-color: rgba(255, 255, 255, 30); border-radius: 4px; } "
            "QPushButton:pressed { background-color: rgba(255, 255, 255, 50); border-radius: 4px; }"
        )

        self.btn_refresh = QPushButton(self)
        self.btn_refresh.setIcon(get_icon("refresh"))
        self.btn_refresh.setIconSize(QSize(20, 20))
        self.btn_refresh.setFixedSize(28, 28)
        self.btn_refresh.setStyleSheet(FLAT_BTN_STYLE)
        self.btn_refresh.setToolTip(tr("refresh", self.lang))
        self.btn_refresh.clicked.connect(self.refresh_all)
        top_bar.addWidget(self.btn_refresh)

        layout.addLayout(top_bar)

        # Main Vertical Splitter: Files on Top, Diagnostic Log on Bottom
        main_vsplitter = QSplitter(Qt.Orientation.Vertical, self)
        main_vsplitter.setHandleWidth(1)
        main_vsplitter.setStyleSheet("QSplitter::handle { background-color: transparent; height: 0px; border: none; image: none; }")

        # Dual Panel Splitter (Local vs Remote)
        splitter = QSplitter(Qt.Orientation.Horizontal, main_vsplitter)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; width: 0px; border: none; image: none; }")

        # --- Left Panel: Local Machine ---
        local_container = QWidget()
        local_vbox = QVBoxLayout(local_container)
        local_vbox.setContentsMargins(0, 0, 0, 0)
        self.lbl_local_title = QLabel(f"{tr('local_machine', self.lang)}")
        self.lbl_local_title.setStyleSheet("font-size: 11px; font-weight: normal;")
        local_vbox.addWidget(self.lbl_local_title)

        loc_nav = QHBoxLayout()
        self.edit_local_path = QLineEdit(os.path.expanduser("~"))
        self.edit_local_path.returnPressed.connect(self.load_local_dir)
        loc_nav.addWidget(self.edit_local_path)
        self.btn_loc_up = QPushButton(self)
        self.btn_loc_up.setIcon(get_icon("up"))
        self.btn_loc_up.setIconSize(QSize(20, 20))
        self.btn_loc_up.setFixedSize(28, 28)
        self.btn_loc_up.setStyleSheet(FLAT_BTN_STYLE)
        self.btn_loc_up.setToolTip(tr("up", self.lang))
        self.btn_loc_up.clicked.connect(self._local_up)
        loc_nav.addWidget(self.btn_loc_up)

        self.btn_loc_home = QPushButton(self)
        self.btn_loc_home.setIcon(get_icon("home"))
        self.btn_loc_home.setIconSize(QSize(20, 20))
        self.btn_loc_home.setFixedSize(28, 28)
        self.btn_loc_home.setStyleSheet(FLAT_BTN_STYLE)
        self.btn_loc_home.setToolTip("Home")
        self.btn_loc_home.clicked.connect(self._go_local_home)
        loc_nav.addWidget(self.btn_loc_home)
        local_vbox.addLayout(loc_nav)

        self.tree_local = QTreeWidget(self)
        self.tree_local.setHeaderLabels([tr("col_name", self.lang), tr("col_size", self.lang), tr("col_perms", self.lang)])
        self.tree_local.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree_local.header().setStretchLastSection(False)
        self.tree_local.setColumnWidth(0, 260)
        self.tree_local.setColumnWidth(1, 90)
        self.tree_local.setColumnWidth(2, 90)
        self.tree_local.setSortingEnabled(True)
        self.tree_local.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_local.customContextMenuRequested.connect(self._show_local_context_menu)
        self.tree_local.itemDoubleClicked.connect(self._on_local_double_click)
        self.tree_local.itemActivated.connect(self._on_local_double_click)
        local_vbox.addWidget(self.tree_local)

        splitter.addWidget(local_container)

        # --- Transfer Action Buttons Panel (Center) ---
        transfer_bar = QVBoxLayout()
        transfer_bar.setContentsMargins(2, 0, 2, 0)
        transfer_bar.setSpacing(8)
        transfer_bar.addStretch()

        self.btn_upload = QPushButton(self)
        self.btn_upload.setIcon(get_icon("forward"))
        self.btn_upload.setIconSize(QSize(26, 26))
        self.btn_upload.setFixedSize(36, 36)
        self.btn_upload.setStyleSheet(FLAT_BTN_STYLE)
        self.btn_upload.setToolTip(f"{tr('upload', self.lang)} ➔")
        self.btn_upload.clicked.connect(self.upload_selected)
        transfer_bar.addWidget(self.btn_upload, 0, Qt.AlignmentFlag.AlignCenter)

        self.btn_download = QPushButton(self)
        self.btn_download.setIcon(get_icon("back"))
        self.btn_download.setIconSize(QSize(26, 26))
        self.btn_download.setFixedSize(36, 36)
        self.btn_download.setStyleSheet(FLAT_BTN_STYLE)
        self.btn_download.setToolTip(f"⬅ {tr('download', self.lang)}")
        self.btn_download.clicked.connect(self.download_selected)
        transfer_bar.addWidget(self.btn_download, 0, Qt.AlignmentFlag.AlignCenter)

        transfer_bar.addStretch()

        transfer_widget = QWidget()
        transfer_widget.setLayout(transfer_bar)
        transfer_widget.setFixedWidth(44)
        splitter.addWidget(transfer_widget)

        # --- Right Panel: Remote Server ---
        remote_container = QWidget()
        remote_vbox = QVBoxLayout(remote_container)
        remote_vbox.setContentsMargins(0, 0, 0, 0)
        self.lbl_remote_title = QLabel(f"{tr('remote_host', self.lang)} ({self.node.hostname})")
        self.lbl_remote_title.setStyleSheet("font-size: 11px; font-weight: normal;")
        remote_vbox.addWidget(self.lbl_remote_title)

        rem_nav = QHBoxLayout()
        self.edit_remote_path = QLineEdit("/")
        self.edit_remote_path.returnPressed.connect(self.load_remote_dir)
        rem_nav.addWidget(self.edit_remote_path)
        self.btn_rem_up = QPushButton(self)
        self.btn_rem_up.setIcon(get_icon("up"))
        self.btn_rem_up.setIconSize(QSize(20, 20))
        self.btn_rem_up.setFixedSize(28, 28)
        self.btn_rem_up.setStyleSheet(FLAT_BTN_STYLE)
        self.btn_rem_up.setToolTip(tr("up", self.lang))
        self.btn_rem_up.clicked.connect(self._remote_up)
        rem_nav.addWidget(self.btn_rem_up)

        self.btn_rem_home = QPushButton(self)
        self.btn_rem_home.setIcon(get_icon("home"))
        self.btn_rem_home.setIconSize(QSize(20, 20))
        self.btn_rem_home.setFixedSize(28, 28)
        self.btn_rem_home.setStyleSheet(FLAT_BTN_STYLE)
        self.btn_rem_home.setToolTip("Home")
        self.btn_rem_home.clicked.connect(self._go_remote_home)
        rem_nav.addWidget(self.btn_rem_home)
        remote_vbox.addLayout(rem_nav)

        self.tree_remote = QTreeWidget(self)
        self.tree_remote.setHeaderLabels([tr("col_name", self.lang), tr("col_size", self.lang), tr("col_perms", self.lang)])
        self.tree_remote.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree_remote.header().setStretchLastSection(False)
        self.tree_remote.setColumnWidth(0, 260)
        self.tree_remote.setColumnWidth(1, 90)
        self.tree_remote.setColumnWidth(2, 90)
        self.tree_remote.setSortingEnabled(True)
        self.tree_remote.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_remote.customContextMenuRequested.connect(self._show_remote_context_menu)
        self.tree_remote.itemDoubleClicked.connect(self._on_remote_double_click)
        self.tree_remote.itemActivated.connect(self._on_remote_double_click)
        remote_vbox.addWidget(self.tree_remote)

        splitter.addWidget(remote_container)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)
        main_vsplitter.addWidget(splitter)

        # --- Bottom Panel: Live Diagnostic Log ---
        self.group_log = QGroupBox(tr("sftp_log_title", self.lang), main_vsplitter)
        log_vbox = QVBoxLayout(self.group_log)
        log_vbox.setContentsMargins(2, 2, 2, 2)

        self.txt_log = QPlainTextEdit(self.group_log)
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #111111; color: #4ec9b0; font-family: Monospace; font-size: 11px;")
        log_vbox.addWidget(self.txt_log)

        main_vsplitter.addWidget(self.group_log)
        self.group_log.setVisible(False)
        main_vsplitter.setSizes([450, 150])

        layout.addWidget(main_vsplitter)

        self.log_bridge = LogBridge(self)
        self.log_bridge.log_received.connect(self.append_log)

        # Instantiate UnifiedFileTransferEngine with thread-safe log_callback signal
        self.sftp_engine = UnifiedFileTransferEngine(
            hostname=node.hostname,
            port=node.port,
            username=node.username,
            password=node.password,
            key_filename=getattr(node, "key_path", "") or getattr(node, "private_key_file", ""),
            ssh_version=getattr(node, "protocol", "SSH2"),
            ssh_engine=self.ssh_engine,
            log_callback=self.log_bridge.log_received.emit
        )


        # Load local directory right away
        self.load_local_dir()

    def append_log(self, text: str):
        cursor = self.txt_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.txt_log.setTextCursor(cursor)
        self.txt_log.ensureCursorVisible()

    def _toggle_log_view(self):
        self.group_log.setVisible(self.btn_toggle_log.isChecked())

    def connect_sftp(self):
        """Initializes SFTP connection to the remote host asynchronously."""
        self.lbl_status.setText(f"{tr('connect_sftp', self.lang)}...")
        self.btn_connect.setEnabled(False)
        self.btn_refresh.setEnabled(False)

        self.connect_worker = SFTPConnectWorker(self.sftp_engine, self.edit_remote_path.text().strip(), self)
        self.connect_worker.finished_signal.connect(self._on_connect_finished)
        self.connect_worker.start()

    def _on_connect_finished(self, success: bool, target_path: str, items: list, error_msg: str):
        self.btn_connect.setEnabled(True)
        self.btn_refresh.setEnabled(True)

        if success:
            self.lbl_status.setText(f"SFTP Connected: {self.node.username}@{self.node.hostname}")
            if target_path and target_path != ".":
                self.edit_remote_path.setText(target_path)
            self._populate_remote_tree(target_path, items)
        else:
            self.lbl_status.setText("SFTP Connection Failed.")
            self.group_log.setVisible(True)
            self.btn_toggle_log.setChecked(True)
            QMessageBox.critical(self, "SFTP Connection Error", f"SFTP Failed:\n{error_msg}")

    def refresh_all(self):
        self.load_local_dir()
        if not self.sftp_engine.is_connected:
            self.connect_sftp()
        else:
            self.load_remote_dir()

    def load_local_dir(self):
        path = os.path.expanduser(self.edit_local_path.text().strip())
        if not os.path.isdir(path):
            return

        self.tree_local.clear()
        try:
            entries = os.listdir(path)

            def _safe_is_dir(entry_name):
                try:
                    return os.path.isdir(os.path.join(path, entry_name))
                except Exception:
                    return False

            entries.sort(key=lambda x: (not _safe_is_dir(x), x.lower()))

            # Add parent directory ".."
            parent_path = os.path.dirname(path)
            if parent_path != path:
                parent_item = CustomTreeWidgetItem(["..", "<DIR>", ""])
                parent_item.setIcon(0, get_icon("folder"))
                parent_item.setData(0, Qt.ItemDataRole.UserRole, parent_path)
                parent_item.setData(1, Qt.ItemDataRole.UserRole, True)
                parent_item.setData(1, Qt.ItemDataRole.UserRole + 1, 0)
                self.tree_local.addTopLevelItem(parent_item)

            for entry in entries:
                if not self.chk_show_hidden.isChecked() and entry.startswith('.'):
                    continue

                full_path = os.path.join(path, entry)
                is_dir = False
                size_bytes = 0
                size_str = "0 B"

                try:
                    is_dir = os.path.isdir(full_path)
                    if is_dir:
                        size_str = "<DIR>"
                    else:
                        try:
                            size_bytes = os.path.getsize(full_path)
                            size_str = f"{size_bytes} B"
                        except Exception:
                            size_str = "<LINK>"
                except Exception:
                    is_dir = False
                    size_str = "<LINK>"

                item = CustomTreeWidgetItem([entry, size_str, "rw-r--r--"])
                item.setIcon(0, get_icon("folder") if is_dir else get_icon("file"))
                item.setData(0, Qt.ItemDataRole.UserRole, full_path)
                item.setData(1, Qt.ItemDataRole.UserRole, is_dir)
                item.setData(1, Qt.ItemDataRole.UserRole + 1, size_bytes)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                self.tree_local.addTopLevelItem(item)
        except Exception as e:
            QMessageBox.warning(self, "Local File Error", f"Cannot read directory:\n{str(e)}")

    def load_remote_dir(self):
        if not self.sftp_engine.is_connected:
            return

        path = self.edit_remote_path.text().strip()
        self.btn_refresh.setEnabled(False)

        self.list_worker = SFTPListWorker(self.sftp_engine, path, self)
        self.list_worker.finished_signal.connect(self._on_list_finished)
        self.list_worker.start()

    def _on_list_finished(self, success: bool, target_path: str, items: list, error_msg: str):
        self.btn_refresh.setEnabled(True)
        if success:
            self._populate_remote_tree(target_path, items)
        else:
            self.group_log.setVisible(True)
            self.btn_toggle_log.setChecked(True)
            QMessageBox.warning(self, "Remote SFTP Error", f"Cannot list remote dir:\n{error_msg}")

    def _populate_remote_tree(self, path: str, items: list):
        self.tree_remote.clear()

        # Add parent directory ".." for remote tree
        if path and path != "/":
            parent_path = os.path.dirname(path.rstrip("/"))
            if not parent_path:
                parent_path = "/"
            parent_item = CustomTreeWidgetItem(["..", "<DIR>", ""])
            parent_item.setIcon(0, get_icon("folder"))
            parent_item.setData(0, Qt.ItemDataRole.UserRole, parent_path)
            parent_item.setData(1, Qt.ItemDataRole.UserRole, True)
            parent_item.setData(1, Qt.ItemDataRole.UserRole + 1, 0)
            self.tree_remote.addTopLevelItem(parent_item)

        for item in items:
            name = item.get("name", "")
            if not self.chk_show_hidden.isChecked() and name.startswith('.') and name != "..":
                continue

            is_dir = item.get("is_dir", False)
            size_bytes = item.get("size", 0) if not is_dir else 0
            size_str = "<DIR>" if is_dir else f"{size_bytes} B"
            tree_item = CustomTreeWidgetItem([name, size_str, item.get("permissions", "")])
            tree_item.setIcon(0, get_icon("folder") if is_dir else get_icon("file"))
            tree_item.setData(0, Qt.ItemDataRole.UserRole, os.path.join(path, name))
            tree_item.setData(1, Qt.ItemDataRole.UserRole, is_dir)
            tree_item.setData(1, Qt.ItemDataRole.UserRole + 1, size_bytes)
            tree_item.setFlags(tree_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            tree_item.setCheckState(0, Qt.CheckState.Unchecked)
            self.tree_remote.addTopLevelItem(tree_item)

    def _local_up(self):
        curr = os.path.expanduser(self.edit_local_path.text().strip())
        parent = os.path.dirname(curr)
        if parent and parent != curr:
            self.edit_local_path.setText(parent)
            self.load_local_dir()

    def _remote_up(self):
        curr = self.edit_remote_path.text().strip()
        parent = os.path.dirname(curr.rstrip("/"))
        if not parent:
            parent = "/"
        self.edit_remote_path.setText(parent)
        self.load_remote_dir()

    def _on_local_double_click(self, item: QTreeWidgetItem, column: int):
        if not item:
            return
        full_path = item.data(0, Qt.ItemDataRole.UserRole)
        is_dir = item.data(1, Qt.ItemDataRole.UserRole) or (full_path and os.path.isdir(full_path))
        if is_dir:
            self.edit_local_path.setText(full_path)
            self.load_local_dir()

    def _on_remote_double_click(self, item: QTreeWidgetItem, column: int):
        if not item:
            return
        full_path = item.data(0, Qt.ItemDataRole.UserRole)
        is_dir = item.data(1, Qt.ItemDataRole.UserRole) or item.text(1) == "<DIR>"
        if is_dir:
            self.edit_remote_path.setText(full_path)
            self.load_remote_dir()

    def _get_selected_items(self, tree: QTreeWidget) -> list:
        items = []
        root = tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.text(0) == "..":
                continue
            if item.checkState(0) == Qt.CheckState.Checked:
                items.append({
                    "name": item.text(0),
                    "path": item.data(0, Qt.ItemDataRole.UserRole),
                    "is_dir": bool(item.data(1, Qt.ItemDataRole.UserRole)),
                    "size": item.data(1, Qt.ItemDataRole.UserRole + 1) or 0
                })

        if items:
            return items

        curr = tree.currentItem()
        if curr and curr.text(0) != "..":
            return [{
                "name": curr.text(0),
                "path": curr.data(0, Qt.ItemDataRole.UserRole),
                "is_dir": bool(curr.data(1, Qt.ItemDataRole.UserRole)),
                "size": curr.data(1, Qt.ItemDataRole.UserRole + 1) or 0
            }]

        return []

    def upload_selected(self):
        if not self.sftp_engine.is_connected:
            QMessageBox.warning(self, "SFTP Upload", "SFTP is not connected. Click 'Connect SFTP' first.")
            return

        items = self._get_selected_items(self.tree_local)
        if not items:
            QMessageBox.warning(self, "SFTP Upload", "Please select or check at least one local item to upload.")
            return

        remote_dir = self.edit_remote_path.text().strip()
        local_dir = os.path.expanduser(self.edit_local_path.text().strip())

        self._start_transfer("upload", items, local_dir, remote_dir)

    def download_selected(self):
        if not self.sftp_engine.is_connected:
            QMessageBox.warning(self, "SFTP Download", "SFTP is not connected. Click 'Connect SFTP' first.")
            return

        items = self._get_selected_items(self.tree_remote)
        if not items:
            QMessageBox.warning(self, "SFTP Download", "Please select or check at least one remote item to download.")
            return

        remote_dir = self.edit_remote_path.text().strip()
        local_dir = os.path.expanduser(self.edit_local_path.text().strip())

        self._start_transfer("download", items, remote_dir, local_dir)

    def _start_transfer(self, transfer_type: str, items: list, source_dir: str, target_dir: str):
        self.btn_upload.setEnabled(False)
        self.btn_download.setEnabled(False)

        self.transfer_dialog = SFTPTransferDialog(transfer_type=transfer_type, parent=self)
        self.transfer_worker = SFTPTransferWorker(
            sftp_engine=self.sftp_engine,
            transfer_type=transfer_type,
            items=items,
            source_dir=source_dir,
            target_dir=target_dir,
            parent=self
        )

        self.transfer_worker.progress_signal.connect(self.transfer_dialog.update_progress)
        self.transfer_worker.conflict_requested_signal.connect(self._on_conflict_requested)
        self.transfer_worker.finished_signal.connect(lambda success, err: self._on_transfer_finished(success, transfer_type, err))

        self.transfer_dialog.pause_toggled_signal.connect(self._on_dialog_pause_toggled)
        self.transfer_dialog.cancel_requested_signal.connect(self.transfer_worker.cancel)
        self.transfer_dialog.overwrite_all_toggled_signal.connect(self._on_dialog_overwrite_all_toggled)

        self.transfer_dialog.show()
        self.transfer_worker.start()

    def _on_dialog_pause_toggled(self, paused: bool):
        if paused:
            self.transfer_worker.pause()
        else:
            self.transfer_worker.resume()

    def _on_dialog_overwrite_all_toggled(self, checked: bool):
        self.transfer_worker.overwrite_all = checked

    def _on_conflict_requested(self, item_name: str, is_dir: bool):
        choice = self.transfer_dialog.prompt_conflict(item_name, is_dir)
        self.transfer_worker.set_conflict_resolution(choice)

    def _on_transfer_finished(self, success: bool, transfer_type: str, error_msg: str):
        self.btn_upload.setEnabled(True)
        self.btn_download.setEnabled(True)
        self.lbl_status.setText(f"SFTP Connected: {self.node.username}@{self.node.hostname}")

        if success:
            if hasattr(self, "transfer_dialog") and self.transfer_dialog:
                total_files = getattr(self.transfer_worker, "total_files", 1) if hasattr(self, "transfer_worker") else 1
                total_bytes = getattr(self.transfer_worker, "batch_bytes_total", 0) if hasattr(self, "transfer_worker") else 0
                self.transfer_dialog.set_completed(transfer_type, total_files, total_bytes)

            action_past = "uploaded" if transfer_type == "upload" else "downloaded"
            QMessageBox.information(
                self,
                "Transfer Complete",
                f"Successfully {action_past} all selected items."
            )

            if hasattr(self, "transfer_dialog") and self.transfer_dialog:
                self.transfer_dialog.accept()
                self.transfer_dialog = None
        else:
            if hasattr(self, "transfer_dialog") and self.transfer_dialog:
                self.transfer_dialog.reject()
                self.transfer_dialog = None

            if error_msg and "cancelled" not in error_msg.lower():
                self.group_log.setVisible(True)
                self.btn_toggle_log.setChecked(True)
                QMessageBox.critical(
                    self,
                    "Transfer Error",
                    f"SFTP transfer failed:\n{error_msg}"
                )

        if transfer_type == "upload":
            self.load_remote_dir()
        else:
            self.load_local_dir()

    def _go_local_home(self):
        self.edit_local_path.setText(os.path.expanduser("~"))
        self.load_local_dir()

    def _go_remote_home(self):
        if self.sftp_engine.is_connected:
            current = self.sftp_engine.get_current_dir()
            self.edit_remote_path.setText(current)
            self.load_remote_dir()
        else:
            self.edit_remote_path.setText("/")

    def _show_local_context_menu(self, pos):
        item = self.tree_local.itemAt(pos)
        menu = QMenu(self)

        upload_action = menu.addAction("Upload to Remote Host")
        upload_action.triggered.connect(self.upload_selected)
        if not item or item.text(0) == "..":
            upload_action.setEnabled(False)

        menu.addSeparator()

        mkdir_action = menu.addAction("New Directory...")
        mkdir_action.triggered.connect(self.create_local_dir)

        if item and item.text(0) != "..":
            rename_action = menu.addAction("Rename...")
            rename_action.triggered.connect(self.rename_local)

            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(self.delete_local)

        menu.addSeparator()

        refresh_action = menu.addAction("Refresh")
        refresh_action.triggered.connect(self.load_local_dir)

        menu.exec(self.tree_local.viewport().mapToGlobal(pos))

    def _show_remote_context_menu(self, pos):
        item = self.tree_remote.itemAt(pos)
        menu = QMenu(self)

        download_action = menu.addAction("Download to Local Machine")
        download_action.triggered.connect(self.download_selected)
        if not item or item.text(0) == "..":
            download_action.setEnabled(False)

        menu.addSeparator()

        mkdir_action = menu.addAction("New Directory...")
        mkdir_action.triggered.connect(self.create_remote_dir)

        if item and item.text(0) != "..":
            rename_action = menu.addAction("Rename...")
            rename_action.triggered.connect(self.rename_remote)

            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(self.delete_remote)

        menu.addSeparator()

        refresh_action = menu.addAction("Refresh")
        refresh_action.triggered.connect(self.load_remote_dir)

        menu.exec(self.tree_remote.viewport().mapToGlobal(pos))

    def create_local_dir(self):
        parent_dir = os.path.expanduser(self.edit_local_path.text().strip())
        folder_name, ok = QInputDialog.getText(self, "New Local Directory", "Directory name:")
        if ok and folder_name.strip():
            new_path = os.path.join(parent_dir, folder_name.strip())
            try:
                os.makedirs(new_path, exist_ok=True)
                self.load_local_dir()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create directory:\n{str(e)}")

    def rename_local(self):
        item = self.tree_local.currentItem()
        if not item or item.text(0) == "..":
            return
        old_path = item.data(0, Qt.ItemDataRole.UserRole)
        old_name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, "Rename Local Item", "New name:", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            new_path = os.path.join(os.path.dirname(old_path), new_name.strip())
            try:
                os.rename(old_path, new_path)
                self.load_local_dir()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename item:\n{str(e)}")

    def delete_local(self):
        item = self.tree_local.currentItem()
        if not item or item.text(0) == "..":
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        name = os.path.basename(path)
        reply = QMessageBox.question(self, "Confirm Delete", f"Permanently delete '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.load_local_dir()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete item:\n{str(e)}")

    def create_remote_dir(self):
        if not self.sftp_engine.is_connected:
            QMessageBox.warning(self, "SFTP Error", "SFTP is not connected.")
            return
        parent_dir = self.edit_remote_path.text().strip()
        folder_name, ok = QInputDialog.getText(self, "New Remote Directory", "Directory name:")
        if ok and folder_name.strip():
            new_path = os.path.join(parent_dir, folder_name.strip()).replace("\\", "/")
            try:
                self.sftp_engine.create_remote_dir(new_path)
                self.load_remote_dir()
            except Exception as e:
                QMessageBox.critical(self, "SFTP Error", f"Failed to create remote directory:\n{str(e)}")

    def rename_remote(self):
        if not self.sftp_engine.is_connected:
            QMessageBox.warning(self, "SFTP Error", "SFTP is not connected.")
            return
        item = self.tree_remote.currentItem()
        if not item or item.text(0) == "..":
            return
        old_path = item.data(0, Qt.ItemDataRole.UserRole)
        old_name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, "Rename Remote Item", "New name:", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            new_path = os.path.join(os.path.dirname(old_path), new_name.strip()).replace("\\", "/")
            try:
                self.sftp_engine.rename_remote(old_path, new_path)
                self.load_remote_dir()
            except Exception as e:
                QMessageBox.critical(self, "SFTP Error", f"Failed to rename remote item:\n{str(e)}")

    def delete_remote(self):
        if not self.sftp_engine.is_connected:
            QMessageBox.warning(self, "SFTP Error", "SFTP is not connected.")
            return
        item = self.tree_remote.currentItem()
        if not item or item.text(0) == "..":
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        name = os.path.basename(path)
        is_dir = item.data(1, Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "Confirm Remote Delete", f"Permanently delete '{name}' on remote server?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if is_dir:
                    self.sftp_engine.remove_remote_dir(path)
                else:
                    self.sftp_engine.remove_remote_file(path)
                self.load_remote_dir()
            except Exception as e:
                QMessageBox.critical(self, "SFTP Error", f"Failed to delete remote item:\n{str(e)}")

    def close(self):
        try:
            self.sftp_engine.disconnect()
        except Exception:
            pass
        return super().close()

    def closeEvent(self, event):
        self.sftp_engine.disconnect()
        super().closeEvent(event)

