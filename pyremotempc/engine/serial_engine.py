import time
import threading
from typing import Callable, Optional
import serial
from pyremotempc.engine.base_engine import BaseProtocolEngine


class SerialEngine(BaseProtocolEngine):
    """
    Serial Port Protocol Engine using pyserial.
    Handles RS-232 / USB Serial communications (/dev/ttyUSB*, /dev/ttyS*, COM*).
    Streams data directly into TerminalWidget (pyte).
    """

    PARITY_MAP = {
        "N": serial.PARITY_NONE,
        "E": serial.PARITY_EVEN,
        "O": serial.PARITY_ODD,
        "M": serial.PARITY_MARK,
        "S": serial.PARITY_SPACE,
    }

    STOPBITS_MAP = {
        1: serial.STOPBITS_ONE,
        1.5: serial.STOPBITS_ONE_POINT_FIVE,
        2: serial.STOPBITS_TWO,
    }

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600,
                 data_bits: int = 8, parity: str = "N", stop_bits: float = 1.0,
                 flow_control: str = "None"):
        super().__init__(hostname=port, port=0, username="", password="")
        self.serial_port = port or "/dev/ttyUSB0"
        self.baudrate = baudrate if baudrate else 9600
        self.data_bits = data_bits if data_bits else 8
        self.parity = parity.upper() if parity else "N"
        self.stop_bits = stop_bits if stop_bits else 1.0
        self.flow_control = flow_control or "None"

        self.ser: Optional[serial.Serial] = None
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def connect(self, on_output: Optional[Callable[[str], None]] = None,
                on_close: Optional[Callable[[], None]] = None,
                term_type: str = "xterm", width: int = 80, height: int = 24) -> bool:
        self.output_callback = on_output
        self.close_callback = on_close

        bytesize = serial.EIGHTBITS
        if self.data_bits == 5:
            bytesize = serial.FIVEBITS
        elif self.data_bits == 6:
            bytesize = serial.SIXBITS
        elif self.data_bits == 7:
            bytesize = serial.SEVENBITS

        ser_parity = self.PARITY_MAP.get(self.parity, serial.PARITY_NONE)
        ser_stopbits = self.STOPBITS_MAP.get(self.stop_bits, serial.STOPBITS_ONE)

        rtscts = False
        xonxoff = False
        if "RTS" in self.flow_control.upper():
            rtscts = True
        elif "XON" in self.flow_control.upper():
            xonxoff = True

        try:
            if self.output_callback:
                self.output_callback(f"Opening Serial Port {self.serial_port} ({self.baudrate} baud, {self.data_bits}{self.parity}{self.stop_bits})...\r\n")

            self.ser = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                bytesize=bytesize,
                parity=ser_parity,
                stopbits=ser_stopbits,
                rtscts=rtscts,
                xonxoff=xonxoff,
                timeout=0.1
            )

            self.is_connected = True
            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True

        except Exception as e:
            if self.output_callback:
                self.output_callback(f"\r\n[Serial Connection Error]: {str(e)}\r\n")
            self.disconnect()
            return False

    def send_input(self, data: str):
        if self.ser and self.is_connected and self.ser.is_open:
            try:
                data_bytes = data.encode("utf-8", errors="replace")
                self.ser.write(data_bytes)
            except Exception:
                pass

    def disconnect(self):
        self._stop_event.set()
        self.is_connected = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None

    def _read_loop(self):
        while not self._stop_event.is_set() and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    raw_data = self.ser.read(self.ser.in_waiting or 1)
                    if raw_data:
                        text = raw_data.decode("utf-8", errors="replace")
                        if self.output_callback:
                            self.output_callback(text)
                else:
                    time.sleep(0.01)
            except Exception:
                break
        self.is_connected = False
        if getattr(self, "close_callback", None):
            try:
                self.close_callback()
            except Exception:
                pass
