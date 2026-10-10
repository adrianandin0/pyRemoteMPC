import os
import re
import time
import datetime
from typing import Optional
import html
from collections import defaultdict
import pyte
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QFileDialog, QMessageBox, QMenu
from PySide6.QtGui import QFont, QTextCursor, QKeyEvent, QInputMethodEvent
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from pyremotempc.engine.ssh_engine import SSHEngine
from pyremotempc.engine.ssh1_engine import SSH1Engine
from pyremotempc.engine.telnet_engine import TelnetEngine
from pyremotempc.engine.serial_engine import SerialEngine
from pyremotempc.config.settings import SettingsManager

_DEBUG_TERM = os.environ.get("PYREMOTEMPC_DEBUG_TERMINAL", "").strip() in ("1", "true", "yes")


def term_debug(msg: str):
    if not _DEBUG_TERM:
        return
    try:
        with open("/tmp/terminal_debug.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


THEME_STYLES = {
    "Classic Dark": "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; selection-background-color: #264f78; }",
    "Green / Matrix": "QPlainTextEdit { background-color: #0c100c; color: #00ff66; selection-background-color: #005522; }",
    "Amber": "QPlainTextEdit { background-color: #120c02; color: #ffb000; selection-background-color: #664400; }",
    "Light": "QPlainTextEdit { background-color: #f5f5f5; color: #111111; selection-background-color: #b3d7ff; }",
    "Dark": "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; selection-background-color: #264f78; }",
    "Classic Green": "QPlainTextEdit { background-color: #0c100c; color: #00ff66; selection-background-color: #005522; }",
}

THEME_DEFAULTS = {
    "Classic Dark": ("#d4d4d4", "#1e1e1e"),
    "Green / Matrix": ("#00ff66", "#0c100c"),
    "Amber": ("#ffb000", "#120c02"),
    "Light": ("#111111", "#f5f5f5"),
    "Dark": ("#d4d4d4", "#1e1e1e"),
    "Classic Green": ("#00ff66", "#0c100c"),
}

COLOR_PALETTE = {
    'black': '#1e1e1e',
    'red': '#cd3131',
    'green': '#0dbc79',
    'brown': '#e5e510',
    'yellow': '#e5e510',
    'blue': '#2472c8',
    'magenta': '#bc3fbc',
    'cyan': '#11a8cd',
    'white': '#e5e5e5',
    'bright_black': '#666666',
    'bright_red': '#f14c4c',
    'bright_green': '#23d18b',
    'bright_brown': '#f5f543',
    'bright_yellow': '#f5f543',
    'bright_blue': '#3b8ee0',
    'bright_magenta': '#d670d6',
    'bright_cyan': '#29b8db',
    'bright_white': '#ffffff',
}


def resolve_color(c_val, is_bright=False, default_color=None):
    if not c_val or c_val == 'default':
        return default_color
    if is_bright and isinstance(c_val, str) and c_val in COLOR_PALETTE:
        bright_key = 'bright_' + c_val
        if bright_key in COLOR_PALETTE:
            return COLOR_PALETTE[bright_key]
    if isinstance(c_val, str) and c_val in COLOR_PALETTE:
        return COLOR_PALETTE[c_val]
    if isinstance(c_val, str) and len(c_val) == 6 and all(ch in '0123456789abcdefABCDEF' for ch in c_val):
        return '#' + c_val
    return default_color


def row_to_html(row, columns: int, default_fg: str = '#d4d4d4', default_bg: str = '#1e1e1e', cursor_x: int = -1) -> str:
    """Converts a pyte screen/history row into styled HTML paragraph block with full ANSI/256/TrueColor support and real-time block cursor."""
    spans = []
    curr_attr = None
    curr_text = []

    for col in range(columns):
        if isinstance(row, (dict, defaultdict)):
            char = row.get(col)
        elif isinstance(row, (list, tuple)):
            char = row[col] if col < len(row) else None
        else:
            char = None

        ch_data = char.data if char else ' '

        fg = char.fg if char else 'default'
        bg = char.bg if char else 'default'
        bold = getattr(char, 'bold', False) if char else False
        italics = getattr(char, 'italics', False) if char else False
        underscore = getattr(char, 'underscore', False) if char else False
        reverse = getattr(char, 'reverse', False) if char else False

        is_cursor = (col == cursor_x)

        if reverse:
            fg, bg = bg, fg
            if fg == 'default':
                fg = 'black'
            if bg == 'default':
                bg = 'yellow'

        fg_hex = resolve_color(fg, is_bright=bold, default_color=default_fg)
        bg_hex = resolve_color(bg, is_bright=False, default_color=None)

        if is_cursor:
            fg_hex = default_bg
            bg_hex = '#ffffff' if default_bg != '#f5f5f5' else '#000000'

        attr_key = (fg_hex, bg_hex, bold, italics, underscore, is_cursor)

        if attr_key != curr_attr:
            if curr_text:
                text_str = html.escape(''.join(curr_text))
                if curr_attr:
                    c_fg, c_bg, c_bold, c_ital, c_und, c_cur = curr_attr
                    if c_cur:
                        text_str = text_str.replace(' ', '&nbsp;')
                    styles = []
                    if c_fg and c_fg != default_fg:
                        styles.append(f'color:{c_fg}')
                    if c_bg and c_bg != default_bg:
                        styles.append(f'background-color:{c_bg}')
                    if c_bold:
                        styles.append('font-weight:bold')
                    if c_ital:
                        styles.append('font-style:italic')
                    if c_und:
                        styles.append('text-decoration:underline')

                    if styles:
                        style_str = ";".join(styles)
                        spans.append(f'<span style="{style_str}">{text_str}</span>')
                    else:
                        spans.append(text_str)
                else:
                    spans.append(text_str)
                curr_text = []
            curr_attr = attr_key

        curr_text.append(ch_data)

    if curr_text:
        text_str = html.escape(''.join(curr_text))
        if curr_attr:
            c_fg, c_bg, c_bold, c_ital, c_und, c_cur = curr_attr
            if c_cur:
                text_str = text_str.replace(' ', '&nbsp;')
            styles = []
            if c_fg and c_fg != default_fg:
                styles.append(f'color:{c_fg}')
            if c_bg and c_bg != default_bg:
                styles.append(f'background-color:{c_bg}')
            if c_bold:
                styles.append('font-weight:bold')
            if c_ital:
                styles.append('font-style:italic')
            if c_und:
                styles.append('text-decoration:underline')

            if styles:
                style_str = ";".join(styles)
                spans.append(f'<span style="{style_str}">{text_str}</span>')
            else:
                spans.append(text_str)
        else:
            spans.append(text_str)

    line_content = ''.join(spans).rstrip()
    if not line_content:
        line_content = '&nbsp;'
    return f'<p style="margin:0px; padding:0px; -qt-block-indent:0; text-indent:0px; white-space:pre;">{line_content}</p>'


class OutputBridge(QObject):
    """Bridge QObject to thread-safely emit signals from SSH background thread to Qt GUI thread."""
    output_received = Signal(str)
    session_closed = Signal()


class SSHPlainTextEdit(QPlainTextEdit):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._terminal_widget = parent
        self.setTabChangesFocus(False)
        # Force all keys to bypass Wayland InputMethod and go directly to keyPressEvent
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)

    def focusNextPrevChild(self, next: bool) -> bool:
        """Prevents Tab and Shift+Tab from navigating away from the terminal widget."""
        return False

    def insertFromMimeData(self, source):
        if source.hasText():
            text = source.text()
            if self.engine:
                self.engine.send_input(text)
        else:
            super().insertFromMimeData(source)

    def inputMethodEvent(self, event):
        """Catch text inserted via Input Method (Wayland) that bypasses keyPressEvent."""
        text = event.commitString()
        if text and self.engine:
            term_debug(f"SENDING TEXT (IME): {repr(text)}")
            self.engine.send_input(text)

    def contextMenuEvent(self, event):
        """Custom context menu for SSH terminal: Copy, Paste, Select All, Clear Screen, Export TXT."""
        menu = QMenu(self)

        copy_action = menu.addAction("Copy (Ctrl+Shift+C)")
        copy_action.triggered.connect(self.copy)
        if not self.textCursor().hasSelection():
            copy_action.setEnabled(False)

        paste_action = menu.addAction("Paste (Ctrl+Shift+V)")
        paste_action.triggered.connect(self.paste)

        menu.addSeparator()

        select_all_action = menu.addAction("Select All")
        select_all_action.triggered.connect(self.selectAll)

        menu.addSeparator()

        if self._terminal_widget:
            clear_action = menu.addAction("Clear Screen and History")
            clear_action.triggered.connect(self._terminal_widget.clear_terminal)

            export_action = menu.addAction("Export to TXT...")
            export_action.triggered.connect(self._terminal_widget.export_to_txt)

        menu.exec(event.globalPos())

    def keyPressEvent(self, event: QKeyEvent):
        if not self.engine:
            return super().keyPressEvent(event)

        key = event.key()
        text = event.text()
        modifiers = event.modifiers()

        ctrl_pressed = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift_pressed = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        alt_pressed = bool(modifiers & Qt.KeyboardModifier.AltModifier)

        # Ctrl+Shift+C -> Copy, Ctrl+Shift+V -> Paste
        if ctrl_pressed and shift_pressed:
            if key == Qt.Key.Key_C:
                self.copy()
                return
            elif key == Qt.Key.Key_V:
                self.paste()
                return

        # Handle Ctrl + Key combinations (A-Z)
        if ctrl_pressed and not shift_pressed and not alt_pressed:
            if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
                ctrl_code = chr(key - Qt.Key.Key_A + 1)
                self.engine.send_input(ctrl_code)
                return
            elif key == Qt.Key.Key_BracketLeft:
                self.engine.send_input("\x1b")
                return
            elif key == Qt.Key.Key_Backslash:
                self.engine.send_input("\x1c")
                return
            elif key == Qt.Key.Key_BracketRight:
                self.engine.send_input("\x1d")
                return

        # Check DECCKM (Application Cursor Keys Mode) tracked by pyte
        is_app_cursor = False
        if hasattr(self._terminal_widget, "screen") and self._terminal_widget.screen:
            is_app_cursor = bool({1, 32} & set(self._terminal_widget.screen.mode))

        # Arrow Keys
        if key == Qt.Key.Key_Up:
            self.engine.send_input("\x1bOA" if is_app_cursor else "\x1b[A")
            return
        elif key == Qt.Key.Key_Down:
            self.engine.send_input("\x1bOB" if is_app_cursor else "\x1b[B")
            return
        elif key == Qt.Key.Key_Right:
            self.engine.send_input("\x1bOC" if is_app_cursor else "\x1b[C")
            return
        elif key == Qt.Key.Key_Left:
            self.engine.send_input("\x1bOD" if is_app_cursor else "\x1b[D")
            return

        # Special Navigation Keys
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self.engine.send_input("\r")
            return
        elif key == Qt.Key.Key_Backspace:
            self.engine.send_input("\x7f")
            return
        elif key == Qt.Key.Key_Delete:
            self.engine.send_input("\x1b[3~")
            return
        elif key == Qt.Key.Key_Insert:
            self.engine.send_input("\x1b[2~")
            return
        elif key == Qt.Key.Key_Escape:
            self.engine.send_input("\x1b")
            return
        elif key == Qt.Key.Key_Tab:
            if shift_pressed:
                self.engine.send_input("\x1b[Z")
            else:
                self.engine.send_input("\t")
            return
        elif key == Qt.Key.Key_PageUp:
            self.engine.send_input("\x1b[5~")
            return
        elif key == Qt.Key.Key_PageDown:
            self.engine.send_input("\x1b[6~")
            return
        elif key == Qt.Key.Key_Home:
            self.engine.send_input("\x1b[H")
            return
        elif key == Qt.Key.Key_End:
            self.engine.send_input("\x1b[F")
            return

        # Function Keys (F1 - F12)
        elif key == Qt.Key.Key_F1:
            self.engine.send_input("\x1bOP")
            return
        elif key == Qt.Key.Key_F2:
            self.engine.send_input("\x1bOQ")
            return
        elif key == Qt.Key.Key_F3:
            self.engine.send_input("\x1bOR")
            return
        elif key == Qt.Key.Key_F4:
            self.engine.send_input("\x1bOS")
            return
        elif key == Qt.Key.Key_F5:
            self.engine.send_input("\x1b[15~")
            return
        elif key == Qt.Key.Key_F6:
            self.engine.send_input("\x1b[17~")
            return
        elif key == Qt.Key.Key_F7:
            self.engine.send_input("\x1b[18~")
            return
        elif key == Qt.Key.Key_F8:
            self.engine.send_input("\x1b[19~")
            return
        elif key == Qt.Key.Key_F9:
            self.engine.send_input("\x1b[20~")
            return
        elif key == Qt.Key.Key_F10:
            self.engine.send_input("\x1b[21~")
            return
        elif key == Qt.Key.Key_F11:
            self.engine.send_input("\x1b[23~")
            return
        elif key == Qt.Key.Key_F12:
            self.engine.send_input("\x1b[24~")
            return

        # Alt + key prefix
        elif alt_pressed and text:
            self.engine.send_input("\x1b" + text)
            return

        # Standard text input
        elif text:
            self.engine.send_input(text)
            return

        event.accept()


class TerminalWidget(QWidget):
    """
    Interactive VT100 / xterm Terminal Widget for SSH & Telnet sessions in pyRemoteMPC.
    Uses 'pyte' full screen terminal emulator for perfect vim, htop, nano, bash navigation,
    scrollback history, automatic file logging, TXT export, themes, and keyboard PTY forwarding.
    """
    session_closed = Signal(bool)

    def __init__(self, node, settings_manager: Optional[SettingsManager] = None, parent=None):
        super().__init__(parent)
        self.node = node
        self.settings = settings_manager or SettingsManager()
        self.log_file = None
        self._was_connected = False

        self.bridge = OutputBridge(self)
        self.bridge.output_received.connect(self.append_text)
        self.bridge.session_closed.connect(self._on_engine_closed)

        # Setup pyte VT100/xterm screen emulator
        scroll_limit = self.settings.scrollback_lines if self.settings.scrollback_lines > 0 else 100000
        self.screen = pyte.HistoryScreen(80, 24, history=scroll_limit)
        self.screen.mode.add(pyte.modes.LNM)
        self.stream = pyte.Stream(self.screen)

        proto = (node.protocol or "SSH2").upper()
        key_file = getattr(node, "key_path", "") or getattr(node, "private_key_file", "")

        if proto == "SERIAL":
            self.engine = SerialEngine(
                port=getattr(node, "serial_port", "") or node.hostname or "/dev/ttyUSB0",
                baudrate=getattr(node, "baudrate", 9600),
                data_bits=getattr(node, "data_bits", 8),
                parity=getattr(node, "parity", "N"),
                stop_bits=getattr(node, "stop_bits", 1.0),
                flow_control=getattr(node, "flow_control", "None")
            )
        elif proto == "TELNET":
            self.engine = TelnetEngine(
                hostname=node.hostname,
                port=node.port if node.port else 23,
                username=node.username,
                password=node.password
            )
        elif proto == "SSH1":
            self.engine = SSH1Engine(
                hostname=node.hostname,
                port=node.port if node.port else 22,
                username=node.username,
                password=node.password,
                key_filename=key_file
            )
        else:
            self.engine = SSHEngine(
                hostname=node.hostname,
                port=node.port if node.port else 22,
                username=node.username,
                password=node.password,
                key_filename=key_file,
                key_passphrase=getattr(node, "key_passphrase", ""),
                legacy_mode=getattr(node, "legacy_ssh", True),
                protocol=proto,
                agent_forwarding=getattr(node, "agent_forwarding", False),
                auto_reconnect=getattr(node, "auto_reconnect", False)
            )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Incremental render state and stream throttle timer
        self._num_history_rendered = 0
        self._last_render_time = 0.0
        self._render_interval = 0.025  # Max ~40 FPS during continuous data streams
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_screen)

        self.text_edit = SSHPlainTextEdit(self.engine, self)
        self.text_edit.setReadOnly(True)
        self.apply_settings()

        self.text_edit.setUndoRedoEnabled(False)
        self.text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text_edit)

        # File Logging Setup
        self.log_file = None
        if self.settings.enable_logging:
            self._init_session_logger()

    def _full_render(self):
        """Forces a clean, complete re-render of the entire terminal buffer and history."""
        if hasattr(self, "_render_timer") and self._render_timer.isActive():
            self._render_timer.stop()
        self.text_edit.clear()
        self._num_history_rendered = 0
        self._render_screen()

    def apply_settings(self):
        """Applies font, size, scrollback buffer lines and theme from settings."""
        font = QFont(self.settings.font_family, self.settings.font_size)
        self.text_edit.setFont(font)

        c_theme = self.settings.console_theme
        style = THEME_STYLES.get(c_theme, THEME_STYLES["Classic Dark"])
        self.text_edit.setStyleSheet(style)
        self._full_render()

    def _init_session_logger(self):
        try:
            log_dir = self.settings.log_directory
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                log_dir = os.path.expanduser("~/.config/pyremotempc/logs")
                os.makedirs(log_dir, exist_ok=True)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            proto = (self.node.protocol or "SSH2").upper()
            clean_host = re.sub(r'[^a-zA-Z0-9_\.-]', '_', self.node.hostname or self.node.name or "session")
            filename = f"{proto}_{clean_host}_{timestamp}.log"
            filepath = os.path.join(log_dir, filename)
            self.log_file = open(filepath, "a", encoding="utf-8")
        except Exception:
            self.log_file = None

    def _safe_resize_screen(self, new_lines: int, new_columns: int):
        """
        Safely resizes pyte.HistoryScreen without destroying top lines when height decreases.
        Standard pyte.Screen.resize() calls delete_lines() from top, destroying terminal content.
        This method pushes cut-off lines to screen.history.top so zero content is lost.
        """
        old_lines = self.screen.lines
        old_columns = self.screen.columns

        if new_lines == old_lines and new_columns == old_columns:
            return

        # 1. Update columns if changed
        if new_columns != old_columns:
            self.screen.columns = new_columns
            for line in list(self.screen.buffer.values()):
                if new_columns < old_columns:
                    for x in range(new_columns, old_columns):
                        line.pop(x, None)

        # 2. Update lines if changed
        if new_lines != old_lines:
            if new_lines < old_lines:
                # Find max non-empty row index or cursor row
                max_row = self.screen.cursor.y
                for r in range(old_lines - 1, self.screen.cursor.y, -1):
                    row_str = "".join(self.screen.buffer[r][c].data for c in range(self.screen.columns)).rstrip()
                    if row_str:
                        max_row = r
                        break

                needed_lines = max_row + 1
                if needed_lines <= new_lines:
                    # Content fits in new height, trim bottom empty lines
                    for r in range(new_lines, old_lines):
                        self.screen.buffer.pop(r, None)
                    self.screen.lines = new_lines
                else:
                    # Content exceeds new height; push top overflow lines to history.top
                    shift = needed_lines - new_lines
                    for r in range(shift):
                        if r in self.screen.buffer:
                            self.screen.history.top.append(self.screen.buffer[r])

                    new_buf = defaultdict(self.screen.buffer.default_factory)
                    for r in range(shift, old_lines):
                        if r in self.screen.buffer:
                            new_buf[r - shift] = self.screen.buffer[r]
                    self.screen.buffer = new_buf
                    self.screen.lines = new_lines
                    self.screen.cursor.y = max(0, self.screen.cursor.y - shift)
            else:
                # Expanding height: pull lines from history.top back into display if available
                avail_history = len(self.screen.history.top)
                shift = min(avail_history, new_lines - old_lines)
                if shift > 0:
                    pulled_lines = [self.screen.history.top.pop() for _ in range(shift)][::-1]
                    new_buf = defaultdict(self.screen.buffer.default_factory)
                    for i, line in enumerate(pulled_lines):
                        new_buf[i] = line
                    for r in range(old_lines):
                        if r in self.screen.buffer:
                            new_buf[r + shift] = self.screen.buffer[r]
                    self.screen.buffer = new_buf
                    self.screen.cursor.y = min(new_lines - 1, self.screen.cursor.y + shift)
                self.screen.lines = new_lines

        self.screen.dirty.update(range(new_lines))
        self.screen.set_margins()

    def _update_pty_dimensions(self):
        if not hasattr(self, "text_edit") or not hasattr(self, "screen"):
            return
        fm = self.text_edit.fontMetrics()
        char_w = max(1, fm.horizontalAdvance("M"))
        char_h = max(1, fm.height())
        vp_w = self.text_edit.viewport().width()
        vp_h = self.text_edit.viewport().height()

        if vp_w < 100 or vp_h < 100:
            win = self.window()
            if win and win.width() > 500:
                vp_w = max(800, win.width() - 300)
                vp_h = max(400, win.height() - 180)
            else:
                vp_w = 1200
                vp_h = 700

        cols = max(40, vp_w // char_w)
        rows = max(10, vp_h // char_h)

        if cols != self.screen.columns or rows != self.screen.lines:
            self._safe_resize_screen(rows, cols)
            if hasattr(self.engine, "resize_pty"):
                self.engine.resize_pty(cols, rows)
            self._full_render()

    def start_session(self):
        """Starts SSH connection."""
        self.screen.reset()
        self.screen.mode.add(pyte.modes.LNM)
        self._update_pty_dimensions()
        self.append_text(f"Connecting to {self.node.hostname}:{self.node.port} via {self.node.protocol}...\r\n")
        self._was_connected = False
        connected = self.engine.connect(
            on_output=self.bridge.output_received.emit,
            on_close=self.bridge.session_closed.emit,
            term_type="xterm",
            width=self.screen.columns,
            height=self.screen.lines
        )
        if not connected:
            self.session_closed.emit(False)
        else:
            self._was_connected = True

    def _on_engine_closed(self):
        """Handler called when engine background thread finishes."""
        recent_text = self.text_edit.toPlainText()[-1000:].lower()
        fatal_errors = [
            "permission denied",
            "connection refused",
            "connection timed out",
            "could not resolve hostname",
            "host key verification failed",
            "no route to host",
            "name or service not known",
            "authentication failed",
            "access denied"
        ]
        has_error = any(err in recent_text for err in fatal_errors)
        clean_exit = self._was_connected and not has_error
        self.session_closed.emit(clean_exit)

    def append_text(self, text: str):
        """Feeds output into pyte VT100 screen emulator and schedules incremental UI rendering."""
        term_debug(f"RECV: {repr(text)}")
        if text:
            self.stream.feed(text)

            # Clear scrollback history when clear command (\x1b[2J or \x1b[3J) is received
            if "\x1b[2J" in text or "\x1b[3J" in text:
                self.screen.history.top.clear()

        # Write raw received text to session log file if enabled
        log_f = getattr(self, "log_file", None)
        if log_f and not log_f.closed:
            try:
                log_f.write(text)
                log_f.flush()
            except Exception:
                pass

        now = time.time()
        elapsed = now - self._last_render_time
        if elapsed >= self._render_interval:
            self._render_screen()
        else:
            if not self._render_timer.isActive():
                rem_ms = max(1, int((self._render_interval - elapsed) * 1000))
                self._render_timer.start(rem_ms)

    def _render_screen(self):
        """Renders newly accumulated history lines and active pyte screen buffer incrementally into QPlainTextEdit."""
        self._last_render_time = time.time()
        doc = self.text_edit.document()
        curr_hist_len = len(self.screen.history.top)

        # Reset document if history was cleared or shrunk (e.g. clear command or terminal resize)
        if curr_hist_len < self._num_history_rendered:
            self.text_edit.clear()
            self._num_history_rendered = 0

        vbar = self.text_edit.verticalScrollBar()
        was_at_bottom = (vbar.value() >= vbar.maximum() - 10)

        cursor = QTextCursor(doc)
        if self._num_history_rendered > 0:
            start_block = doc.findBlockByNumber(self._num_history_rendered)
            if start_block.isValid():
                pos = max(0, start_block.position() - 1)
                cursor.setPosition(pos)
                cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
            else:
                cursor.movePosition(QTextCursor.MoveOperation.End)
        else:
            cursor.setPosition(0)
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()

        c_theme = self.settings.console_theme
        default_fg, default_bg = THEME_DEFAULTS.get(c_theme, THEME_DEFAULTS["Classic Dark"])
        cols = self.screen.columns

        # 1. Append newly scrolled history lines
        if curr_hist_len > self._num_history_rendered:
            for idx in range(self._num_history_rendered, curr_hist_len):
                r = self.screen.history.top[idx]
                h = row_to_html(r, cols, default_fg, default_bg, cursor_x=-1)
                if doc.isEmpty():
                    cursor.insertHtml(h)
                else:
                    cursor.insertBlock()
                    cursor.insertHtml(h)
            self._num_history_rendered = curr_hist_len

        # 2. Append active screen lines
        cursor_y = self.screen.cursor.y
        cursor_x = self.screen.cursor.x

        max_active_row = cursor_y
        for r_idx in range(self.screen.lines - 1, cursor_y, -1):
            row_str = "".join(self.screen.buffer[r_idx][c].data for c in range(cols)).rstrip()
            if row_str:
                max_active_row = r_idx
                break

        for r_idx in range(max_active_row + 1):
            c_x = cursor_x if r_idx == cursor_y else -1
            h = row_to_html(self.screen.buffer[r_idx], cols, default_fg, default_bg, cursor_x=c_x)
            if doc.isEmpty():
                cursor.insertHtml(h)
            else:
                cursor.insertBlock()
                cursor.insertHtml(h)

        # 3. Position cursor to match pyte virtual cursor coordinates
        cursor_line_idx = self._num_history_rendered + cursor_y
        block = doc.findBlockByNumber(min(cursor_line_idx, max(0, doc.blockCount() - 1)))
        if block.isValid():
            char_col = min(cursor_x, max(0, block.length() - 1))
            pos = block.position() + char_col
            tc = self.text_edit.textCursor()
            tc.setPosition(pos)
            self.text_edit.setTextCursor(tc)

        if was_at_bottom:
            self.text_edit.ensureCursorVisible()
            vbar.setValue(vbar.maximum())

        self.text_edit.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pty_dimensions()

    def clear_terminal(self):
        """Clears pyte virtual screen buffer and history."""
        self.screen.reset()
        self.screen.mode.add(pyte.modes.LNM)
        self.screen.history.top.clear()
        self._full_render()

    def export_to_txt(self):
        """Prompts user and exports current session terminal buffer to a TXT file."""
        default_name = f"{self.node.name}_session.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Session Output to TXT", default_name, "Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return

        try:
            content = self.text_edit.toPlainText()
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, "Export Successful", f"Session output saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save TXT file:\n{str(e)}")

    def closeEvent(self, event):
        if hasattr(self, "_render_timer") and self._render_timer.isActive():
            self._render_timer.stop()
        if self.log_file and not self.log_file.closed:
            try:
                self.log_file.close()
            except Exception:
                pass
        self.engine.disconnect()
        super().closeEvent(event)
