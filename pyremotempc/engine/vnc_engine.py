import os
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Optional, List, Callable, Tuple
from pyremotempc.engine.base_engine import BaseProtocolEngine


class VNCEngine(BaseProtocolEngine):
    """
    Universal VNC Engine supporting TigerVNC, TightVNC, RealVNC, Vinagre, and Remmina.
    Handles process logging, passwords via temporary pass files, and clean shutdown.
    Inherits from BaseProtocolEngine.
    """

    @staticmethod
    def get_vnc_executable() -> Tuple[str, str]:
        """Finds available XEmbed-compliant VNC client executable (TigerVNC/TightVNC/SSVNC)."""
        for client in ["vncviewer", "tigervncviewer", "tightvncviewer", "xvncviewer", "gtkvncviewer", "ssvnc"]:
            path = shutil.which(client)
            if path:
                return path, "vncviewer"
        return "", "none"

    @staticmethod
    def _get_x11_window_ids() -> set:
        """Returns set of all top-level window IDs on X11 root window."""
        try:
            from ctypes import cdll, c_void_p, c_ulong, c_int, c_uint, POINTER, byref, c_char_p
            x11 = cdll.LoadLibrary("libX11.so.6")
            x11.XOpenDisplay.argtypes = [c_char_p]
            x11.XOpenDisplay.restype = c_void_p
            x11.XCloseDisplay.argtypes = [c_void_p]
            x11.XDefaultRootWindow.argtypes = [c_void_p]
            x11.XDefaultRootWindow.restype = c_ulong
            x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_ulong)), POINTER(c_uint)]
            x11.XQueryTree.restype = c_int
            x11.XFree.argtypes = [c_void_p]

            display = x11.XOpenDisplay(None)
            if not display:
                return set()
            root = x11.XDefaultRootWindow(display)
            root_r = c_ulong()
            parent_r = c_ulong()
            children_r = POINTER(c_ulong)()
            nchildren_r = c_uint()
            wins = set()
            if x11.XQueryTree(display, root, byref(root_r), byref(parent_r), byref(children_r), byref(nchildren_r)) != 0:
                for i in range(nchildren_r.value):
                    wins.add(children_r[i])
                x11.XFree(children_r)
            x11.XCloseDisplay(display)
            return wins
        except Exception:
            return set()

    def __init__(self, hostname: str, port: int = 5900, username: str = "", password: str = ""):
        super().__init__(hostname, port, username, password)

        self.process: Optional[subprocess.Popen] = None
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.pass_file: Optional[str] = None

    def connect(self, on_output: Optional[Callable[[str], None]] = None,
                term_type: str = "xterm", width: int = 1280, height: int = 800, win_id: Optional[int] = None) -> bool:
        """BaseProtocolEngine interface implementation."""
        return self.start_session(on_output=on_output, win_id=win_id, width=width, height=height)

    def disconnect(self):
        """BaseProtocolEngine interface implementation."""
        self.stop_session()

    def send_input(self, data: str):
        """BaseProtocolEngine interface implementation."""
        pass

    def start_session(self, on_output: Optional[Callable[[str], None]] = None, win_id: Optional[int] = None, width: int = 1280, height: int = 800) -> bool:
        """Launches VNC client process and embeds window into win_id if provided."""
        self.output_callback = on_output
        exe_path, client_type = self.get_vnc_executable()

        if not exe_path:
            if self.output_callback:
                self.output_callback("[VNC Error]: No VNC client found. Please install vncviewer, tigervnc, or remmina.\n")
            return False

        # Snapshot pre-existing X11 windows before spawning VNC client
        initial_wins = self._get_x11_window_ids() if win_id else set()

        cmd: List[str] = [exe_path]

        if client_type == "vncviewer":
            if win_id:
                cmd.extend(["-embed", str(win_id)])
            cmd.extend(["-SecurityTypes", "VncAuth,None,TLSVnc,TLSNone"])
            cmd.append(f"{self.hostname}:{self.port}")
            if self.password:
                try:
                    self.pass_file = self._create_vnc_passwd_file(self.password)
                    if self.pass_file:
                        cmd.extend(["-passwd", self.pass_file])
                except Exception as e:
                    if self.output_callback:
                        self.output_callback(f"[VNC Passwd Warning]: {str(e)}\n")

        elif client_type == "vinagre":
            cmd.extend([f"vnc://{self.hostname}:{self.port}"])

        elif client_type == "remmina":
            cmd.extend(["--disable-toolbar", "-c", f"vnc://{self.hostname}:{self.port}"])

        try:
            if self.output_callback:
                self.output_callback(f"[VNC Command]: {' '.join(cmd)}\nLaunching VNC Session to {self.hostname}:{self.port}...\n")

            env = os.environ.copy()
            # Force X11 backend so XEmbed / XReparentWindow works under Wayland compositors
            if "WAYLAND_DISPLAY" in env:
                del env["WAYLAND_DISPLAY"]
            env["GDK_BACKEND"] = "x11"
            env["QT_QPA_PLATFORM"] = "xcb"

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )

            if win_id and self.process and client_type != "vncviewer":
                self._reparent_x11_window(self.process.pid, win_id, initial_wins, width, height)

            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True

        except Exception as e:
            if self.output_callback:
                self.output_callback(f"[VNC Launch Error]: {str(e)}\n")
            return False

    def _reparent_x11_window(self, target_pid: int, parent_win_id: int, initial_wins: set, width: int = 1280, height: int = 800):
        """Asynchronously polls X11 root window for VNC client window and reparents it into parent_win_id."""
        def _worker():
            try:
                from ctypes import cdll, c_void_p, c_ulong, c_int, c_uint, c_long, POINTER, byref, c_char_p, c_ubyte, Structure, CFUNCTYPE

                class MwmHints(Structure):
                    _fields_ = [
                        ('flags', c_ulong),
                        ('functions', c_ulong),
                        ('decorations', c_ulong),
                        ('input_mode', c_long),
                        ('status', c_ulong)
                    ]

                x11 = cdll.LoadLibrary("libX11.so.6")
                XErrorHandler = CFUNCTYPE(c_int, c_void_p, c_void_p)
                def _dummy_x_err(d, e):
                    return 0
                c_dummy_err = XErrorHandler(_dummy_x_err)
                try:
                    x11.XSetErrorHandler.argtypes = [XErrorHandler]
                    x11.XSetErrorHandler.restype = c_void_p
                    x11.XSetErrorHandler(c_dummy_err)
                except Exception:
                    pass

                x11.XOpenDisplay.argtypes = [c_char_p]
                x11.XOpenDisplay.restype = c_void_p
                x11.XCloseDisplay.argtypes = [c_void_p]
                x11.XDefaultRootWindow.argtypes = [c_void_p]
                x11.XDefaultRootWindow.restype = c_ulong
                x11.XInternAtom.argtypes = [c_void_p, c_char_p, c_int]
                x11.XInternAtom.restype = c_ulong
                x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_ulong)), POINTER(c_uint)]
                x11.XQueryTree.restype = c_int
                x11.XGetWindowProperty.argtypes = [
                    c_void_p, c_ulong, c_ulong, c_long, c_long, c_int, c_ulong,
                    POINTER(c_ulong), POINTER(c_int), POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_ubyte))
                ]
                x11.XGetWindowProperty.restype = c_int
                x11.XChangeProperty.argtypes = [
                    c_void_p, c_ulong, c_ulong, c_ulong, c_int, c_int,
                    c_void_p, c_int
                ]
                x11.XChangeProperty.restype = c_int
                x11.XReparentWindow.argtypes = [c_void_p, c_ulong, c_ulong, c_int, c_int]
                x11.XReparentWindow.restype = c_int
                x11.XMoveResizeWindow.argtypes = [c_void_p, c_ulong, c_int, c_int, c_uint, c_uint]
                x11.XMoveResizeWindow.restype = c_int
                x11.XMapWindow.argtypes = [c_void_p, c_ulong]
                x11.XMapWindow.restype = c_int
                x11.XFlush.argtypes = [c_void_p]
                x11.XFree.argtypes = [c_void_p]

                start_t = time.time()
                display = None
                while time.time() - start_t < 10.0:
                    if self.process and self.process.poll() is not None:
                        break
                    if not display:
                        display = x11.XOpenDisplay(None)
                    if display:
                        root = x11.XDefaultRootWindow(display)
                        atom_pid = x11.XInternAtom(display, b"_NET_WM_PID", 1)
                        atom_wm_class = x11.XInternAtom(display, b"WM_CLASS", 1)
                        atom_net_name = x11.XInternAtom(display, b"_NET_WM_NAME", 1)
                        atom_wm_name = x11.XInternAtom(display, b"WM_NAME", 1)
                        atom_motif = x11.XInternAtom(display, b"_MOTIF_WM_HINTS", 0)

                        found_win = None
                        root_r = c_ulong()
                        parent_r = c_ulong()
                        children_r = POINTER(c_ulong)()
                        nchildren_r = c_uint()

                        if x11.XQueryTree(display, root, byref(root_r), byref(parent_r), byref(children_r), byref(nchildren_r)) != 0:
                            children = [children_r[i] for i in range(nchildren_r.value)]
                            x11.XFree(children_r)

                            # Prioritize new windows spawned since start_session
                            candidate_pool = [w for w in children if w not in initial_wins and w != parent_win_id and w != root]
                            if not candidate_pool:
                                candidate_pool = [w for w in children if w != parent_win_id and w != root]

                            for child in candidate_pool:
                                is_match = False
                                # Check 1: _NET_WM_PID
                                if atom_pid:
                                    type_r, format_r, nitems_r, bytes_after_r = c_ulong(), c_int(), c_ulong(), c_ulong()
                                    prop_r = POINTER(c_ubyte)()
                                    if x11.XGetWindowProperty(display, child, atom_pid, 0, 1, 0, 0, byref(type_r), byref(format_r), byref(nitems_r), byref(bytes_after_r), byref(prop_r)) == 0:
                                        if prop_r and nitems_r.value > 0:
                                            pid_val = POINTER(c_ulong)(prop_r)[0]
                                            if pid_val == target_pid:
                                                is_match = True
                                            x11.XFree(prop_r)

                                # Check 2: WM_CLASS
                                if not is_match and atom_wm_class:
                                    type_r, format_r, nitems_r, bytes_after_r = c_ulong(), c_int(), c_ulong(), c_ulong()
                                    prop_r = POINTER(c_ubyte)()
                                    if x11.XGetWindowProperty(display, child, atom_wm_class, 0, 1024, 0, 0, byref(type_r), byref(format_r), byref(nitems_r), byref(bytes_after_r), byref(prop_r)) == 0:
                                        if prop_r and nitems_r.value > 0:
                                            wm_cls = bytes(prop_r[:nitems_r.value]).decode('utf-8', errors='ignore').lower()
                                            if any(k in wm_cls for k in ["remmina", "vnc", "vinagre", "tigervnc", "tightvnc"]):
                                                is_match = True
                                            x11.XFree(prop_r)

                                # Check 3: Window Title (_NET_WM_NAME / WM_NAME)
                                if not is_match:
                                    for a_name in [atom_net_name, atom_wm_name]:
                                        if not a_name:
                                            continue
                                        type_r, format_r, nitems_r, bytes_after_r = c_ulong(), c_int(), c_ulong(), c_ulong()
                                        prop_r = POINTER(c_ubyte)()
                                        if x11.XGetWindowProperty(display, child, a_name, 0, 1024, 0, 0, byref(type_r), byref(format_r), byref(nitems_r), byref(bytes_after_r), byref(prop_r)) == 0:
                                            if prop_r and nitems_r.value > 0:
                                                title_val = bytes(prop_r[:nitems_r.value]).decode('utf-8', errors='ignore').lower()
                                                if self.hostname.lower() in title_val or str(self.port) in title_val or "vnc" in title_val:
                                                    is_match = True
                                                x11.XFree(prop_r)
                                            if is_match:
                                                break

                                if is_match:
                                    found_win = child
                                    break

                        if found_win:
                            # Strip window decorations (header bar, borders) via _MOTIF_WM_HINTS
                            if atom_motif:
                                hints = MwmHints(flags=2, functions=0, decorations=0, input_mode=0, status=0)
                                x11.XChangeProperty(display, found_win, atom_motif, atom_motif, 32, 0, byref(hints), 5)

                            x11.XReparentWindow(display, found_win, c_ulong(parent_win_id), 0, 0)
                            x11.XMoveResizeWindow(display, found_win, 0, 0, width, height)
                            x11.XMapWindow(display, found_win)
                            x11.XFlush(display)
                            x11.XCloseDisplay(display)
                            return
                    time.sleep(0.12)
                if display:
                    x11.XCloseDisplay(display)
            except Exception:
                pass

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    @classmethod
    def _create_vnc_passwd_file(cls, password: str) -> Optional[str]:
        """
        Creates a temporary password file for vncviewer.
        Uses vncpasswd binary if present, or generates standard VNC obfuscated DES format natively in Python.
        Ensures strict 0600 file permissions and safe location.
        """
        if not password:
            return None

        # 1. Try vncpasswd binary if installed
        vncpasswd_bin = shutil.which("vncpasswd")
        if vncpasswd_bin:
            try:
                res = subprocess.run([vncpasswd_bin, "-f"], input=password.encode("utf-8"), capture_output=True, timeout=5)
                if res.returncode == 0 and res.stdout:
                    return cls._write_secure_temp_file(res.stdout)
            except Exception:
                pass

        # 2. Pure Python native generation using standard VNC DES obfuscation
        try:
            try:
                from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
            except ImportError:
                from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES
            from cryptography.hazmat.primitives.ciphers import Cipher, modes

            vnc_fixed_key = bytes([0x17, 0x52, 0x6b, 0x06, 0x23, 0x4e, 0x58, 0x07])
            pass_bytes = password.encode("latin-1", errors="ignore")[:8].ljust(8, b"\x00")
            cipher = Cipher(TripleDES(vnc_fixed_key * 3), modes.ECB())
            encryptor = cipher.encryptor()
            encrypted_bytes = encryptor.update(pass_bytes) + encryptor.finalize()
            return cls._write_secure_temp_file(encrypted_bytes)
        except Exception as e:
            print(f"Native VNC password file generation notice: {e}")
            return None

    @classmethod
    def _write_secure_temp_file(cls, data: bytes) -> Optional[str]:
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        target_dir = os.path.join(runtime_dir, "pyremotempc") if runtime_dir and os.path.isdir(runtime_dir) else None
        if target_dir:
            try:
                os.makedirs(target_dir, mode=0o700, exist_ok=True)
            except Exception:
                target_dir = None

        tf = tempfile.NamedTemporaryFile(delete=False, dir=target_dir, prefix="vnc_pass_")
        try:
            os.chmod(tf.name, 0o600)
            tf.write(data)
            tf.flush()
            return tf.name
        finally:
            tf.close()

    def _read_loop(self):
        if not self.process or not self.process.stdout:
            return

        while not self._stop_event.is_set() and self.process.poll() is None:
            line = self.process.stdout.readline()
            if line:
                if self.output_callback:
                    self.output_callback(line)
            else:
                time.sleep(0.05)

        ret = self.process.poll() if self.process else None
        if self.output_callback:
            self.output_callback(f"\n[VNC Process Exited with Return Code: {ret}]\n")

        self.cleanup()

    def stop_session(self):
        self._stop_event.set()
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None
        self.cleanup()

    def stop(self):
        """Alias for stop_session for engine interface consistency."""
        self.stop_session()

    def cleanup(self):
        """Removes temporary VNC password file if created."""
        if self.pass_file and os.path.exists(self.pass_file):
            try:
                os.remove(self.pass_file)
            except Exception:
                pass
            self.pass_file = None
