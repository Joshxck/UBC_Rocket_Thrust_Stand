import struct
import serial
from PySide6.QtCore import QThread, Signal
from queue import Queue, Empty
from threading import Event

HEADER = bytes([0xAA, 0x55])
PACKET_SIZE = 23

# Struct layout: 2x uint8 throttle, 2x int32 loadcell, 2x uint16 rpm, 3x uint16 cell_mv
PACKET_FORMAT = '<BBiiHHHHH'  # little-endian

class SerialWorker(QThread):
    data_received = Signal(dict)
    connection_lost = Signal()

    def __init__(self, port, baud=115200):
        super().__init__()
        self.port = port
        self.baud = baud
        self._cmd_queue = Queue()
        self._stop_event = Event()

    def run(self):
        try:
            with serial.Serial(self.port, self.baud, timeout=0.1) as ser:
                buf = bytearray()
                while not self._stop_event.is_set():

                    # --- Send any pending commands ---
                    try:
                        while True:
                            cmd = self._cmd_queue.get_nowait()
                            ser.write((cmd + '\n').encode())
                    except Empty:
                        pass

                    # --- Read incoming bytes into buffer ---
                    chunk = ser.read(64)
                    if chunk:
                        buf.extend(chunk)

                    # --- Parse all complete packets from buffer ---
                    while len(buf) >= PACKET_SIZE:
                        # Hunt for header
                        idx = buf.find(HEADER)
                        if idx == -1:
                            # No header found, discard everything except last byte
                            # (last byte could be 0xAA, start of next header)
                            buf = buf[-1:]
                            break
                        if idx > 0:
                            # Discard garbage before header
                            buf = buf[idx:]
                        if len(buf) < PACKET_SIZE:
                            break

                        packet = self.parse_packet(buf[:PACKET_SIZE])
                        buf = buf[PACKET_SIZE:]  # consume packet regardless of validity

                        if packet:
                            self.data_received.emit(packet)

        except serial.SerialException:
            self.connection_lost.emit()

    def parse_packet(self, raw: bytes) -> dict | None:
        # Verify header
        if raw[0] != 0xAA or raw[1] != 0x55:
            return None

        # Verify checksum (XOR of bytes 2..21)
        chk = 0
        for b in raw[2:22]:
            chk ^= b
        if chk != raw[22]:
            return None

        # Unpack payload (skip 2 header bytes)
        thr1, thr2, lc1, lc2, rpm1, rpm2, c1, c2, c3 = struct.unpack_from(
            PACKET_FORMAT, raw, 2
        )

        return {
            'throttle1':  round(thr1 / 255 * 100, 1),  # back to percent
            'throttle2':  round(thr2 / 255 * 100, 1),
            'loadcell1':  lc1,                          # raw counts, scale in GUI
            'loadcell2':  lc2,
            'rpm1':       rpm1,
            'rpm2':       rpm2,
            'cell1_v':    c1 / 1000.0,
            'cell2_v':    c2 / 1000.0,
            'cell3_v':    c3 / 1000.0,
            'pack_v':     (c1 + c2 + c3) / 1000.0,
        }

    def send_command(self, cmd: str):
        """Called from main thread — all commands are ASCII strings."""
        self._cmd_queue.put(cmd)

    # --- Convenience methods so the GUI doesn't need to know the protocol ---
    def set_throttle1(self, pct: float):
        self._cmd_queue.put(f'T1:{pct:.1f}')

    def set_throttle2(self, pct: float):
        self._cmd_queue.put(f'T2:{pct:.1f}')

    def arm(self):
        self._cmd_queue.put('ARM')

    def disarm(self):
        self._cmd_queue.put('DISARM')

    def tare(self):
        self._cmd_queue.put('TARE')

    def calibrate(self, channel: int, known_grams: float):
        self._cmd_queue.put(f'CAL{channel}:{known_grams:.1f}')

    def stop(self):
        self._stop_event.set()
        self.wait()