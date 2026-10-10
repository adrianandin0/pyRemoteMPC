#!/usr/bin/env bash
# ==============================================================================
# pyRemoteMPC Installer Script
# Supports: Debian, Ubuntu, Mint, Pop!_OS, RHEL, CentOS, Fedora, Rocky, Alma,
#           Arch Linux, Manjaro, openSUSE, and derived Linux distributions.
# ==============================================================================

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check root privileges
if [ "$EUID" -ne 0 ]; then
    error "Please run install.sh with root privileges (e.g. sudo ./install.sh)"
fi

info "Detecting Linux distribution..."

# Detect Linux distribution via /etc/os-release
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO_ID="${ID:-unknown}"
    DISTRO_LIKE="${ID_LIKE:-$DISTRO_ID}"
else
    error "Cannot detect Linux distribution (/etc/os-release missing)."
fi

info "Detected OS: ${NAME:-$DISTRO_ID} (ID: ${DISTRO_ID}, LIKE: ${DISTRO_LIKE})"

# Function to install system dependencies per package manager
install_system_dependencies() {
    info "Installing system dependencies for ${DISTRO_ID}..."
    
    if command -v apt-get >/dev/null 2>&1; then
        info "Using APT package manager (Debian, Ubuntu, Mint, Pop!_OS, etc.)..."
        apt-get update -y
        apt-get install -y python3 python3-pip python3-venv python3-dev socat telnet openssh-client sshpass pulseaudio-utils freerdp2-x11 tigervnc-viewer libxcb-cursor0 || \
        apt-get install -y python3 python3-pip python3-venv python3-dev socat telnet openssh-client sshpass pulseaudio-utils freerdp3-x11 tigervnc-viewer libxcb-cursor0 || \
        apt-get install -y python3 python3-pip python3-venv python3-dev socat telnet openssh-client sshpass pulseaudio-utils freerdp2-bin vncviewer || true

    elif command -v dnf >/dev/null 2>&1; then
        info "Using DNF package manager (Fedora, RHEL, CentOS, Rocky, AlmaLinux, etc.)..."
        dnf install -y python3 python3-pip python3-devel socat telnet openssh-clients sshpass pulseaudio-utils freerdp tigervnc libxcb-cursor || \
        dnf install -y python3 python3-pip python3-devel socat telnet openssh-clients sshpass pulseaudio-utils freerdp2 tigervnc libxcb-cursor || true

    elif command -v yum >/dev/null 2>&1; then
        info "Using YUM package manager (RHEL 7, CentOS 7, Amazon Linux, etc.)..."
        yum install -y python3 python3-pip python3-devel socat telnet openssh-clients sshpass pulseaudio-utils freerdp tigervnc || true

    elif command -v pacman >/dev/null 2>&1; then
        info "Using Pacman package manager (Arch Linux, Manjaro, EndeavourOS, etc.)..."
        pacman -Sy --noconfirm python python-pip socat inetutils openssh sshpass libpulse freerdp tigervnc || true

    elif command -v zypper >/dev/null 2>&1; then
        info "Using Zypper package manager (openSUSE, SLES, etc.)..."
        zypper --non-interactive install python3 python3-pip python3-devel socat telnet openssh sshpass pulseaudio-utils freerdp tigervnc-viewer || true

    elif command -v apk >/dev/null 2>&1; then
        info "Using APK package manager (Alpine Linux)..."
        apk add --no-cache python3 py3-pip python3-dev socat telnet openssh-client sshpass pulseaudio-utils freerdp tigervnc || true

    elif command -v xbps-install >/dev/null 2>&1; then
        info "Using XBPS package manager (Void Linux)..."
        xbps-install -Sy python3 python3-pip socat telnet openssh sshpass pulseaudio-utils freerdp tigervnc || true

    elif command -v eopkg >/dev/null 2>&1; then
        info "Using EOPKG package manager (Solus)..."
        eopkg install -y python3 python3-pip socat telnet openssh sshpass pulseaudio-utils freerdp tigervnc || true

    elif command -v emerge >/dev/null 2>&1; then
        info "Using Portage package manager (Gentoo)..."
        emerge --noreplace dev-lang/python dev-python/pip net-misc/socat net-misc/telnet-bsd net-misc/openssh net-misc/sshpass media-sound/pulseaudio-utils net-misc/freerdp net-misc/tigervnc || true

    else
        warn "Package manager not recognized automatically. Ensure Python 3, Pip, FreeRDP, TigerVNC, socat, telnet, pactl (pulseaudio-utils), and OpenSSH are installed."
    fi
}

install_system_dependencies

# Installation directories
INSTALL_DIR="/opt/pyremotempc"
BIN_LINK="/usr/local/bin/pyremotempc"
DESKTOP_DIR="/usr/share/applications"
ICON_DIR="/usr/share/icons/hicolor/256x256/apps"
PIXMAP_DIR="/usr/share/pixmaps"

info "Installing pyRemoteMPC to ${INSTALL_DIR}..."

# Remove old installation if exists
rm -rf "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"

# Determine source directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Copy application files
cp -r "${SCRIPT_DIR}/pyremotempc" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/setup.py" "${INSTALL_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/version.txt" "${INSTALL_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/pyremotempc.desktop" "${INSTALL_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/LICENSE" "${INSTALL_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/README.md" "${INSTALL_DIR}/" 2>/dev/null || true

# Set up virtual environment in /opt/pyremotempc/.venv for isolation and PEP 668 safety
info "Setting up Python virtual environment..."
python3 -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip setuptools wheel
"${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

# Pre-compile Python bytecode for faster startup and syntax validation
info "Pre-compiling Python bytecode..."
"${INSTALL_DIR}/.venv/bin/python3" -m compileall -q "${INSTALL_DIR}/pyremotempc"

# Set secure filesystem permissions for multi-user security
info "Enforcing secure filesystem permissions on ${INSTALL_DIR}..."
find "${INSTALL_DIR}" -type d -exec chmod 755 {} +
find "${INSTALL_DIR}" -type f -exec chmod 644 {} +
chmod -R 755 "${INSTALL_DIR}/.venv/bin"

# Create launcher binary wrapper in /usr/local/bin/pyremotempc
info "Creating launcher executable in ${BIN_LINK}..."
cat << 'EOF' > "${BIN_LINK}"
#!/usr/bin/env bash
export PYTHONPATH="/opt/pyremotempc:${PYTHONPATH}"
if [ -d "/opt/pyremotempc/.venv" ]; then
    exec /opt/pyremotempc/.venv/bin/python3 -m pyremotempc.app "$@"
else
    exec python3 -m pyremotempc.app "$@"
fi
EOF
chmod +x "${BIN_LINK}"

# Install desktop entry and icons
info "Installing Desktop entry and application icon..."
mkdir -p "${DESKTOP_DIR}" "${ICON_DIR}" "${PIXMAP_DIR}"

if [ -f "${INSTALL_DIR}/pyremotempc/ui/iconos/pyremotempc.png" ]; then
    cp "${INSTALL_DIR}/pyremotempc/ui/iconos/pyremotempc.png" "${ICON_DIR}/pyremotempc.png"
    cp "${INSTALL_DIR}/pyremotempc/ui/iconos/pyremotempc.png" "${PIXMAP_DIR}/pyremotempc.png"
fi

cat << 'EOF' > "${DESKTOP_DIR}/pyremotempc.desktop"
[Desktop Entry]
Name=pyRemoteMPC
Comment=Multi-Protocol Remote Connections Manager for Linux
Exec=/usr/local/bin/pyremotempc
Icon=pyremotempc
Terminal=false
Type=Application
Categories=Network;RemoteAccess;Utility;
Keywords=RDP;SSH;VNC;Telnet;mRemoteNG;
EOF
chmod 644 "${DESKTOP_DIR}/pyremotempc.desktop"

# Refresh desktop database & icon cache if tools are available
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi

success "pyRemoteMPC has been successfully installed!"
info "You can start pyRemoteMPC by typing 'pyremotempc' or from your application menu."
