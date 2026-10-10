import glob
import os
from typing import List, Tuple


def get_available_serial_ports() -> List[Tuple[str, str]]:
    """
    Scans system for available physical and virtual serial ports.
    Returns a list of tuples: (device_path, display_label)
    e.g. [('/dev/ttyUSB0', '/dev/ttyUSB0 (FT232R USB UART)'), ...]
    If no active ports are detected, returns [('', 'No ports detected')].
    """
    ports_found: List[Tuple[str, str]] = []
    seen_devices = set()

    try:
        import serial.tools.list_ports
        comports = list(serial.tools.list_ports.comports())

        for p in comports:
            dev = p.device
            dev_upper = dev.upper()
            desc = p.description if p.description and p.description != "n/a" else ""

            # Check if this is an active physical port (USB, ACM, COM, or has hardware description)
            is_usb = "USB" in dev_upper or "ACM" in dev_upper or "COM" in dev_upper
            is_active_hw = bool(desc and desc != dev)

            if is_usb or is_active_hw:
                label = f"{dev} ({desc})" if desc and desc != dev else dev
                ports_found.append((dev, label))
                seen_devices.add(dev)
    except Exception:
        pass

    # Always scan filesystem for active USB / ACM / COM / PTY / Virtual devices in /dev and /tmp
    dev_patterns = [
        "/dev/COM*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/rfcomm*",
        "/dev/ttyAMA*",
        "/tmp/ttyCOM*",
        "/tmp/ttyUSB*",
        "/tmp/ttyACM*",
        "/tmp/tty*",
    ]
    for pattern in dev_patterns:
        for path in sorted(glob.glob(pattern)):
            if path not in seen_devices and os.path.exists(path):
                ports_found.append((path, path))
                seen_devices.add(path)

    # If still empty, return indicator item
    if not ports_found:
        ports_found.append(("", "No ports detected"))

    return ports_found


def get_port_device_list() -> List[str]:
    """Returns just the list of port device paths."""
    ports = get_available_serial_ports()
    return [p[0] for p in ports if p[0]]
