import json
import os
from typing import Dict, Any

DEFAULT_MASTER_PASSWORD = "pyRemoteMPC1234@"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "language": "en",  # Default to English
    "enable_logging": True,
    "log_directory": os.path.expanduser("~/.config/pyremotempc/logs"),
    "scrollback_lines": 0,  # 0 = Infinite scrollback lines
    "font_family": "Monospace",
    "font_size": 10,
    "theme": "Dark",
    "console_theme": "Classic Dark",
    "master_key_salt": "",
    "master_key_hash": "",
    "sidebar_width": 260,
    "sidebar_splitter_sizes": [670, 330],
    "window_geometry": "",
    "window_state": "",
    "rdp_shared_folder": os.path.expanduser("~/RDP_Shared"),
    "rdp_enable_clipboard": True,
    "rdp_enable_drive_redirection": True,
}


class SettingsManager:
    """Manages application-wide settings and preferences stored at ~/.config/pyremotempc/settings.json."""

    def __init__(self, config_dir: str = "~/.config/pyremotempc"):
        self.config_dir = os.path.expanduser(config_dir)
        self.settings_path = os.path.join(self.config_dir, "settings.json")
        self.settings: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        """Loads settings from JSON file if exists, falling back to defaults."""
        os.makedirs(self.config_dir, exist_ok=True)
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception:
                self.settings = dict(DEFAULT_SETTINGS)
        else:
            self.save()

    def save(self):
        """Saves current settings dictionary to JSON file."""
        os.makedirs(self.config_dir, exist_ok=True)
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, DEFAULT_SETTINGS.get(key, default))

    def set(self, key: str, value: Any):
        self.settings[key] = value
        self.save()

    @property
    def language(self) -> str:
        return str(self.get("language", "en"))

    @property
    def log_directory(self) -> str:
        path = self.get("log_directory", DEFAULT_SETTINGS["log_directory"])
        expanded = os.path.expanduser(path)
        os.makedirs(expanded, exist_ok=True)
        return expanded

    @property
    def scrollback_lines(self) -> int:
        return int(self.get("scrollback_lines", 0))

    @property
    def font_family(self) -> str:
        return str(self.get("font_family", "Monospace"))

    @property
    def font_size(self) -> int:
        return int(self.get("font_size", 10))

    @property
    def theme(self) -> str:
        return str(self.get("theme", "Dark"))

    @property
    def console_theme(self) -> str:
        return str(self.get("console_theme", "Classic Dark"))

    @property
    def enable_logging(self) -> bool:
        return bool(self.get("enable_logging", True))

    @property
    def sidebar_width(self) -> int:
        return int(self.get("sidebar_width", 260))

    @property
    def sidebar_splitter_sizes(self) -> list:
        return list(self.get("sidebar_splitter_sizes", [670, 330]))

    @property
    def rdp_shared_folder(self) -> str:
        path = str(self.get("rdp_shared_folder", os.path.expanduser("~/RDP_Shared")))
        expanded = os.path.expanduser(path)
        try:
            os.makedirs(expanded, exist_ok=True)
        except Exception:
            pass
        return expanded

    @property
    def rdp_enable_clipboard(self) -> bool:
        return bool(self.get("rdp_enable_clipboard", True))

    @property
    def rdp_enable_drive_redirection(self) -> bool:
        return bool(self.get("rdp_enable_drive_redirection", True))

