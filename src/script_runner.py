# script_runner.py
import json
import time

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog
)


# --------------------------------------------------------------------------- #
#  Script Runner — executes in its own thread                                  #
# --------------------------------------------------------------------------- #

class ScriptRunner(QThread):
    """
    Executes a list of script steps in a background thread.
    Emits signals that map 1-to-1 onto SerialWorker convenience methods
    so the main thread can connect them without knowing the protocol.

    Supported actions
    -----------------
    { "action": "set_throttle1",  "value": 50.0 }
    { "action": "set_throttle2",  "value": 50.0 }
    { "action": "set_throttle",   "value": 50.0 }   # sets both motors
    { "action": "arm" }
    { "action": "disarm" }
    { "action": "tare1" }
    { "action": "tare2" }
    { "action": "tare" }                             # tares both
    { "action": "calibrate",      "channel": 1, "known_grams": 500.0 }
    { "action": "wait",           "seconds": 5.0 }
    { "action": "ramp",           "motor": 1, "from": 0, "to": 100,
                                  "duration": 10.0, "steps": 20 }
    """

    # --- Signals wired to SerialWorker convenience methods ---
    sig_set_throttle1 = Signal(float)
    sig_set_throttle2 = Signal(float)
    sig_arm           = Signal()
    sig_disarm        = Signal()
    sig_tare1         = Signal()
    sig_tare2         = Signal()
    sig_calibrate     = Signal(int, float)  # channel, known_grams

    # --- UI feedback ---
    script_done = Signal(bool)  # True = completed, False = aborted

    def __init__(self, steps: list[dict], parent=None):
        super().__init__(parent)
        self._steps = steps
        self._abort = False

    @Slot()
    def abort(self):
        self._abort = True

    def run(self):
        for i, step in enumerate(self._steps):
            if self._abort:
                break
            try:
                self._execute(step)
            except (KeyError, TypeError, ValueError):
                self.script_done.emit(False)
                return
            if self._abort:
                break

        self.script_done.emit(not self._abort)

    def _execute(self, step: dict):
        action = step["action"]

        if action == "set_throttle1":
            self.sig_set_throttle1.emit(float(step["value"]))
        elif action == "set_throttle2":
            self.sig_set_throttle2.emit(float(step["value"]))
        elif action == "set_throttle":
            self.sig_set_throttle1.emit(float(step["value"]))
            self.sig_set_throttle2.emit(float(step["value"]))
        elif action == "arm":
            self.sig_arm.emit()
        elif action == "disarm":
            self.sig_disarm.emit()
        elif action == "tare1":
            self.sig_tare1.emit()
        elif action == "tare2":
            self.sig_tare2.emit()
        elif action == "tare":
            self.sig_tare1.emit()
            self.sig_tare2.emit()
        elif action == "calibrate":
            self.sig_calibrate.emit(int(step["channel"]), float(step["known_grams"]))
        elif action == "wait":
            self._interruptible_sleep(float(step["seconds"]))
        elif action == "ramp":
            self._ramp(step)
        else:
            raise ValueError(f"Unknown action '{action}'")

    def _interruptible_sleep(self, seconds: float):
        deadline = time.monotonic() + seconds
        while not self._abort:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.05, remaining))

    def _ramp(self, step: dict):
        motor    = step.get("motor", "both")
        v_from   = float(step["from"])
        v_to     = float(step["to"])
        duration = float(step["duration"])
        n_steps  = int(step.get("steps", max(10, int(duration * 4))))

        for k in range(n_steps + 1):
            if self._abort:
                return
            value = v_from + (v_to - v_from) * (k / n_steps)
            if motor in (1, "1", "both"):
                self.sig_set_throttle1.emit(round(value, 1))
            if motor in (2, "2", "both"):
                self.sig_set_throttle2.emit(round(value, 1))
            if k < n_steps:
                time.sleep(duration / n_steps)


# --------------------------------------------------------------------------- #
#  Script Control Widget — three buttons, vertical                             #
# --------------------------------------------------------------------------- #

class ScriptControlWidget(QWidget):
    """
    Drop-in widget: Load / Run / Abort stacked vertically.

    Wiring (do this after constructing the widget):
        widget.connect_serial(serial_worker)
        widget.connect_logger(csv_logger_backend)   # optional — auto start/stop
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps  = None
        self._runner = None
        self._serial = None
        self._logger = None

        self._load_btn  = QPushButton("📂  Load Script")
        self._run_btn   = QPushButton("▶   Run Script")
        self._abort_btn = QPushButton("⏹   Abort")

        self._run_btn.setEnabled(False)
        self._abort_btn.setEnabled(False)

        for btn in (self._load_btn, self._run_btn, self._abort_btn):
            btn.setFixedSize(200, 30)

        self._apply_btn_style(self._load_btn,  "#2596be")
        self._apply_btn_style(self._run_btn,   "#27ae60")
        self._apply_btn_style(self._abort_btn, "#c0392b")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._load_btn)
        layout.addWidget(self._run_btn)
        layout.addWidget(self._abort_btn)

        self._load_btn.clicked.connect(self._load)
        self._run_btn.clicked.connect(self._run)
        self._abort_btn.clicked.connect(self._abort)

    def connect_serial(self, serial_worker):
        self._serial = serial_worker

    def connect_logger(self, csv_widget):
        """Pass the CsvLoggerWidget (not the backend) so the save dialog fires on completion."""
        self._logger = csv_widget

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Script", "", "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path) as f:
                self._steps = json.load(f)
            self._run_btn.setEnabled(True)
        except Exception:
            pass

    def _run(self):
        if not self._steps or not self._serial:
            return

        self._runner = ScriptRunner(self._steps)
        self._runner.sig_set_throttle1.connect(self._serial.set_throttle1)
        self._runner.sig_set_throttle2.connect(self._serial.set_throttle2)
        self._runner.sig_arm.connect(self._serial.arm)
        self._runner.sig_disarm.connect(self._serial.disarm)
        self._runner.sig_tare1.connect(self._serial.tare1)
        self._runner.sig_tare2.connect(self._serial.tare2)
        self._runner.sig_calibrate.connect(self._serial.calibrate)
        self._runner.script_done.connect(self._on_done)

        if self._logger:
            self._logger.backend.start()

        self._load_btn.setEnabled(False)
        self._run_btn.setEnabled(False)
        self._abort_btn.setEnabled(True)
        self._runner.start()

    def _abort(self):
        if self._runner:
            self._runner.abort()

    @Slot(bool)
    def _on_done(self, _completed: bool):
        if self._logger:
            self._logger._stop()   # calls backend.stop() then prompts save dialog
        self._load_btn.setEnabled(True)
        self._run_btn.setEnabled(True)
        self._abort_btn.setEnabled(False)

    @staticmethod
    def _apply_btn_style(btn: QPushButton, color: str):
        btn.setStyleSheet(
            f"QPushButton {{ background:{color}; color:white; font-weight:bold;"
            f"padding:4px 12px; border-radius:4px; }}"
            f"QPushButton:hover {{ background:{color}dd; }}"
            f"QPushButton:disabled {{ background:#444; color:#777; }}"
        )