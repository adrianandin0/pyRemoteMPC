# pyRemoteMPC

**pyRemoteMPC** ( **py**thon **Remote** **M**ulti-**P**rotocol **C**onnections ) is a native multi-protocol remote connections manager designed specifically for GNU/Linux environments.

The project serves as a **modern, native Python replacement and spiritual successor to mRemoteNG for Linux**, built with PySide6 (Qt6) and native connectivity engines.

---

## Current Version
- **Version**: `0.1b` (First Beta Release)

---

## Key Features

- **Multi-Format Connection Import Engine**:
  - **mRemoteNG**: Full import and export compatibility for `confCons.xml` (v2.5 and v2.6+ AEAD GCM) files.
  - **SecureCRT**: Import XML session configurations (`<VanDyke>`).
  - **Asbrú Connection Manager**: Import YAML configurations (`.yml` / `.yaml`) with automatic ` - copy` cleaning.
  - **Microsoft RDCMan**: Import `.rdg` and XML remote desktop trees (`<RDCMan>`).
  - **Interactive Import Dialog**: Choose a custom root container name and icon for imported folders.
- **Modern & Fluid Qt6 UI**:
  - Dockable sidebar with horizontal slide toggle button.
  - Hierarchical connection tree with dedicated icons per OS / service (`windows`, `terminal`, `vnc`, `serial`, `connections`, etc.).
  - Context menu options: **Up**, **Down**, and **Clone** (Duplicate node). Root container node is protected against deletion or move.
  - Real-time search filter across names, hostnames/IPs, usernames, and descriptions.
  - Property Inspector (`PropertyGridWidget`) collapsible vertically with a dedicated toggle button.
  - Window Geometry & State Persistence: Automatically saves and restores position, window dimensions, active screen, and maximized state upon application restart.
  - Enforced 11px font size across the entire application interface for clean, consistent UI readability.
- **Single Instance per User**:
  - Automatically detects if pyRemoteMPC is already open for the active Linux user ID via IPC sockets (`QLocalServer`/`QLocalSocket`). If launched again, it smoothly brings the existing window to the front and exits. Different Linux user accounts can run their own independent instances concurrently.
- **Quick Connect Toolbar**: Connect instantly or save entries directly specifying `IP/HOSTNAME` / `SERIAL PORT` - `PROTOCOL` - `BAUD / PORT` - `DOMAIN` - `USER` - `PASSWORD`.
- **Standardized Session Titles & Info Banners**:
  - Saved Connections: `PROTOCOL: SavedName (IP:Port / SerialPort)`
  - Quick Connections: `PROTOCOL: Host (IP:Port / SerialPort)`
- **Advanced Security & Access Control**:
  - Master Password management in **Preferences & Options -> Security** tab.
  - **Startup Password Option**: Choose whether to require the Master Password on application startup (`require_master_password_on_startup`).
  - **Continue Without Passwords (Read-Only Mode)**: Allows opening the app to view, browse, and copy the full connection tree structure without decrypting passwords. Disk auto-saving is automatically blocked in this mode to protect the owner's encrypted `confCons.xml` on disk.
  - **Zero Plaintext Storage**: Only salted PBKDF2-HMAC-SHA256 hashes (200,000 iterations + 16-byte random salt) are saved to `settings.json`. Connections are encrypted with AES-256-GCM / AES-128-CBC.

---

## Supported Connection Protocols

| Protocol | Internal Engine | Highlight Features |
| :--- | :--- | :--- |
| **SSH2** | `paramiko` + `pyte` | Integrated VT100/xterm terminal emulator, infinite scrollback buffer, SSH private key support (RSA, ED25519, ECDSA, OpenSSH PEM, PuTTY `.ppk`), visual key selector dialog, and integrated **SFTP/FTP/SCP** file manager per session. |
| **SSH1** | Legacy Crypto Engine | Compatibility engine specifically designed for legacy routers, switches, and ancient network hardware requiring obsolete ciphers (`3des-cbc`, `blowfish-cbc`, `diffie-hellman-group1-sha1`, `ssh-rsa`). |
| **SFTP / FTP / SCP** | `paramiko` / `ftplib` / `scp` | Integrated tabbed file transfer interface per active session with upload, download, and local/remote filesystem browsing supporting SFTP, FTP, and SCP protocols. |
| **RDP** | `xfreerdp` (FreeRDP 2/3) | Native tab embedding via X11 XEmbed container (`xcb` backend). Dynamic resolution matching, clipboard sharing, local shared drive mapping, and credential redirection. |
| **VNC** | Native / `vncviewer` | Remote desktop support with UltraVNC MSLogon (Type 11), Standard VNC (Type 2), or Auto security negotiation. |
| **TELNET** | `telnetlib` + `pyte` | Interactive terminal console for unencrypted network devices. |
| **SERIAL** | `pyserial` + `pyte` | Direct serial port communication (`/dev/ttyUSB*`, `/dev/ttyACM*`, `/dev/COM*`, `/dev/ttyS*`, `/dev/rfcomm*`, `/tmp/ttyCOM*` virtual `socat` ports) with dropdown port selector and rescan button (**`🔄`**). |

---

## Architecture & Directory Structure

```
pyRemoteMPC/
├── version.txt                   # Application version identifier (0.1b)
├── run.sh                        # Convenience launcher script
├── install.sh                    # Automated cross-distro installation script
├── uninstall.sh                  # Automated cross-distro uninstallation script
├── pyremotempc.desktop            # Linux desktop launcher entry
├── requirements.txt              # Python PIP dependencies
├── setup.py                      # Package setup script
└── pyremotempc/
    ├── app.py                    # Main Qt application entry point
    ├── version.txt               # Package version identifier
    ├── config/
    │   ├── models.py             # Data models (ConnectionNode, etc.)
    │   ├── settings.py           # JSON preferences manager (~/.config/pyremotempc/settings.json)
    │   ├── i18n.py               # Localization system (English)
    │   ├── version.py            # Dynamic version reader module
    │   ├── xml_parser.py         # mRemoteNG confCons.xml import/export parser
    │   ├── securecrt_parser.py   # SecureCRT XML session parser
    │   ├── asbru_parser.py       # Asbrú Connection Manager YAML parser
    │   └── rdcman_parser.py      # Microsoft RDCMan RDG/XML parser
    ├── crypto/
    │   ├── aead_gcm.py           # AEAD GCM cipher engine
    │   ├── rijndael_legacy.py    # Legacy Rijndael CBC cipher engine
    │   └── master_key_manager.py # AES encryption and PBKDF2 Master Password security
    ├── engine/
    │   ├── rdp_engine.py         # RDP session orchestrator using xfreerdp
    │   ├── ssh_engine.py         # SSH2 engine with Paramiko and pyte
    │   ├── ssh1_engine.py        # SSH1 engine for legacy hardware
    │   ├── serial_engine.py      # Serial engine using pyserial and pyte
    │   ├── vnc_engine.py         # VNC session engine
    │   ├── telnet_engine.py      # Telnet console engine
    │   └── sftp_engine.py        # SFTP/FTP file manager engine
    ├── plugins/
    │   ├── plugin_manager.py     # Protocol plugin registry manager
    │   ├── ssh_plugin.py         # SSH protocol plugin
    │   ├── rdp_plugin.py         # RDP protocol plugin
    │   ├── serial_plugin.py      # Serial protocol plugin
    │   ├── vnc_plugin.py         # VNC protocol plugin
    │   └── telnet_plugin.py     # Telnet protocol plugin
    ├── utils/
    │   ├── key_loader.py         # Private key parsing helper
    │   └── serial_utils.py       # Serial port system scanning helper
    └── ui/
        ├── main_window.py        # Main window, layouts, toolbars, and menus
        ├── tree_widget.py        # Hierarchical connection tree
        ├── property_grid.py      # Node property inspector
        ├── tab_widget.py         # Active session tab manager
        ├── terminal_widget.py    # Terminal console renderer
        ├── preferences_dialog.py # Preferences & Options (General, Terminal, RDP, Security)
        ├── sftp_transfer_dialog.py # SFTP background transfer progress dialog
        ├── sftp_widget.py        # Graphical file transfer interface
        ├── theme_manager.py      # QSS visual styling & dark theme manager
        ├── vnc_widget.py         # VNC rendering widget
        ├── icon_manager.py       # PNG icon loader per protocol and node type
        ├── dialogs/
        │   ├── about_dialog.py   # About pyRemoteMPC information dialog
        │   ├── import_folder_dialog.py # Custom import root folder naming dialog
        │   ├── key_selector_dialog.py # SSH key selection dialog
        │   └── master_password_dialog.py # Master key & Continue Without Passwords dialog
        └── iconos/               # Application icon assets (`pyremotempc.png`, `serial.png`, etc.)
```

---

## Installation & Setup

### Prerequisites
- **Python**: 3.10 or higher.
- **Operating System**: GNU/Linux.
- **System Packages**: `python3`, `python3-pip`, `python3-venv`, `python3-dev`, `freerdp` (or `freerdp2-x11`/`freerdp3-x11`), `tigervnc` (or `tigervnc-viewer`), `socat`, `telnet`, `openssh-client`, `sshpass`, `pulseaudio-utils` (`pactl`).
- **Python Dependencies** (installed automatically via `requirements.txt` / installer): `PySide6>=6.5.0`, `cryptography>=41.0.0`, `paramiko>=3.0.0`, `pyte>=0.8.0`, `pyserial>=3.5`, `pyyaml>=6.0`.

### Automated Cross-Distro Installer
`install.sh` automatically detects your package manager and installs all required system and Python dependencies across major Linux distributions:
- **APT**: Debian, Ubuntu, Linux Mint, Pop!_OS, Kali, Elementary, Zorin, Deepin.
- **DNF**: Fedora, RHEL 8/9, CentOS Stream, Rocky Linux, AlmaLinux.
- **YUM**: RHEL 7, CentOS 7, Amazon Linux.
- **Pacman**: Arch Linux, Manjaro, EndeavourOS, Garuda.
- **Zypper**: openSUSE (Leap & Tumbleweed), SLES.
- **APK**: Alpine Linux.
- **XBPS**: Void Linux.
- **EOPKG**: Solus.
- **Portage / Emerge**: Gentoo.

Run the installer with root privileges:
```bash
chmod +x install.sh
sudo ./install.sh
```

To uninstall:
```bash
chmod +x uninstall.sh
sudo ./uninstall.sh
```

### Manual Quick Start
```bash
# 1. Clone the repository
git clone https://github.com/adrianandin0/pyRemoteMPC.git
cd pyRemoteMPC

# 2. Run convenience script
./run.sh
```

---

## Author & Contact Information

- **Author**: Adrián Andino
- **Contact**: [adrianandino@pm.me](mailto:adrianandino@pm.me)
- **X**: [@adrian_and_ino](https://x.com/adrian_and_ino)
- **GitHub Repository**: [https://github.com/adrianandin0/pyRemoteMPC](https://github.com/adrianandin0/pyRemoteMPC)

---

## Credits & Acknowledgements

Icons and graphical assets from [Flaticon](https://www.flaticon.com/) by [magnific](https://www.flaticon.com/authors/magnific).

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
