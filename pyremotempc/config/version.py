import os


def get_version() -> str:
    """Reads version string from version.txt dynamically."""
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    v_path = os.path.join(pkg_dir, "version.txt")
    if os.path.exists(v_path):
        try:
            with open(v_path, "r", encoding="utf-8") as f:
                ver = f.read().strip()
                if ver:
                    return ver
        except Exception:
            pass

    root_dir = os.path.dirname(pkg_dir)
    v_path_root = os.path.join(root_dir, "version.txt")
    if os.path.exists(v_path_root):
        try:
            with open(v_path_root, "r", encoding="utf-8") as f:
                ver = f.read().strip()
                if ver:
                    return ver
        except Exception:
            pass

    return "0.1b"
