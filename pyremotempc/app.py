import sys
import os

# Ensure project root directory is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Force Qt X11 (xcb) platform plugin for 100% reliable XEmbed container window embedding (FreeRDP / RDP)
os.environ["QT_QPA_PLATFORM"] = "xcb"
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from pyremotempc.ui.main_window import MainWindow
from pyremotempc.ui.icon_manager import get_icon


def get_single_instance_name() -> str:
    """Returns a unique IPC server name per Linux user ID."""
    uid = getattr(os, "getuid", lambda: 1000)()
    return f"pyremotempc_single_instance_{uid}"


def try_activate_existing_instance(server_name: str) -> bool:
    """
    Attempts to connect to an existing running instance server.
    If connected, sends ACTIVATE signal and returns True.
    """
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(500):
        socket.write(b"ACTIVATE\n")
        socket.flush()
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return True
    return False


def main():
    """Main entry point for pyRemoteMPC application."""
    app = QApplication(sys.argv)
    app.setApplicationName("pyRemoteMPC")
    app.setOrganizationName("pyRemoteMPC")
    app.setWindowIcon(get_icon("pyremotempc"))

    server_name = get_single_instance_name()

    # Check if an instance is already running for this user
    if try_activate_existing_instance(server_name):
        print(f"pyRemoteMPC is already running for current user (UID {getattr(os, 'getuid', lambda: 1000)()}). Bringing existing window to front.")
        sys.exit(0)

    # Clean stale sockets from previous abnormal terminations
    QLocalServer.removeServer(server_name)

    # Set base application font to 11px normal weight
    font = app.font()
    font.setPixelSize(11)
    font.setBold(False)
    font.setWeight(QFont.Weight.Normal)
    app.setFont(font)

    # Set strict global stylesheet enforcing 11px non-bold for all widgets (theme-neutral)
    app.setStyleSheet("""
        * {
            font-size: 11px;
            font-weight: normal;
        }
    """)

    window = MainWindow()

    # Apply saved theme (Dark, Light, Ocean, Forest) at application startup
    from pyremotempc.ui.theme_manager import apply_theme
    apply_theme(window.settings.theme)

    # Setup single-instance IPC server to listen for new launch attempts by this user
    server = QLocalServer()
    server.listen(server_name)

    def handle_ipc_connection():
        conn = server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(lambda: None)
            window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            window.showNormal()
            window.raise_()
            window.activateWindow()

    server.newConnection.connect(handle_ipc_connection)

    window.show()

    ret = app.exec()
    server.close()
    QLocalServer.removeServer(server_name)
    sys.exit(ret)


if __name__ == "__main__":
    main()
