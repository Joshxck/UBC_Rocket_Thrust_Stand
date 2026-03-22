import serial
from PySide6.QtCore import QThread, Signal
from queue import Queue, Empty
from threading import Event

class SerialWorker(QThread):
    data_received = Signal(dict)

    def __init__(self, port, baud=115200):
        super().__init__()
        self.port = port
        self.baud = baud
        self.running = True
        self._cmd_queue = Queue()
        self._stop_event = Event()

    def run(self):
        with serial.Serial(self.port, self.baud, timeout=0.1) as ser:
            while not self._stop_event.is_set():
                # Drain any pending commands first
                try:
                    while True:
                        cmd = self._cmd_queue.get_nowait()
                        ser.write((cmd + '\n').encode())
                except Empty:
                    pass

                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("DATA,"):
                    parsed = self.parse_data(line)
                    if parsed:
                        self.data_received.emit(parsed)

    def send_command(self, cmd: str):
        self._cmd_queue.put(cmd)  # thread-safe, called from main thread

    def stop(self):
        self._stop_event.set()
        self.wait()
    
    def parse_data(self, line):
        parts = line.split(',')
        if len(parts) != 10:
            return None
        keys = ['thrust','torque','rpm1','rpm2','v1','v2','v3','pwm1','pwm2']
        try:
            return {k: float(v) for k, v in zip(keys, parts[1:])}
        except ValueError:
            return None