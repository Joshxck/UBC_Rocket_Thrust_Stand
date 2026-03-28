"""
TelemetryWidget — Bare-bones PySide6 live data widget.

No styling applied — inherits your application stylesheet.

Usage
-----
    widget = TelemetryWidget(
        streams=[
            StreamConfig(name="Thrust", unit="N"),
            StreamConfig(name="Torque", unit="Nm"),
        ],
        history_seconds=30,
        sample_rate_hz=100,
    )

    # Push samples (thread-safe via signal/slot):
    widget.push({"Thrust": 12.34, "Torque": 0.56})
    widget.push_stream("Thrust", 12.34)
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

DEFAULT_COLORS = ["#00E5FF", "#FF6D3A", "#B5FF5A", "#D966FF", "#FFD700"]


@dataclass
class StreamConfig:
    name: str
    unit: str = ""
    color: str = ""       # auto-assigned if empty
    precision: int = 2


class _StreamData:
    def __init__(self, cfg: StreamConfig, maxlen: int):
        self.cfg = cfg
        self.values: deque[float] = deque(maxlen=maxlen)
        self.timestamps: deque[float] = deque(maxlen=maxlen)
        self.latest: Optional[float] = None
        self.color = QColor(cfg.color)

    def append(self, value: float, t: float):
        self.values.append(value)
        self.timestamps.append(t)
        self.latest = value


class _GraphWidget(QWidget):
    def __init__(self, streams: List[_StreamData], history_seconds: float, parent=None):
        super().__init__(parent)
        self.streams = streams
        self.history_seconds = history_seconds
        self.setFixedSize(400, 200)
        # self.setMinimumSize(200, 100)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._draw(p)
        p.end()

    def _draw(self, p: QPainter):
        W, H = self.width(), self.height()
        PAD_L, PAD_R, PAD_T, PAD_B = 48, 8, 8, 24

        rx, ry = PAD_L, PAD_T
        rw, rh = W - PAD_L - PAD_R, H - PAD_T - PAD_B
        if rw <= 0 or rh <= 0:
            return

        now = time.monotonic()
        t_min = now - self.history_seconds

        # Collect visible values for Y range
        all_vals = [
            v for sd in self.streams
            for v, t in zip(sd.values, sd.timestamps)
            if t >= t_min
        ]

        # Border
        p.drawRect(rx, ry, rw, rh)

        # Y range
        if all_vals:
            v_min, v_max = min(all_vals), max(all_vals)
            v_span = v_max - v_min or 1.0
            v_min -= v_span * 0.1
            v_max += v_span * 0.1
            v_span = v_max - v_min
        else:
            v_min, v_max, v_span = 0.0, 1.0, 1.0

        # Horizontal grid + Y labels
        default_pen = p.pen()
        grid_pen = QPen(default_pen)
        grid_pen.setStyle(Qt.DotLine)
        p.setPen(grid_pen)
        for i in range(5):
            frac = i / 4
            y = int(ry + rh - frac * rh)
            p.drawLine(rx, y, rx + rw, y)
            p.setPen(default_pen)
            p.drawText(0, y - 8, PAD_L - 4, 16,
                       Qt.AlignRight | Qt.AlignVCenter, f"{v_min + frac * v_span:.1f}")
            p.setPen(grid_pen)

        # X-axis time labels
        p.setPen(default_pen)
        for i in range(5):
            frac = i / 4
            lx = int(rx + frac * rw)
            t_label = -(self.history_seconds * (1 - frac))
            p.drawText(lx - 16, ry + rh + 4, 32, 16, Qt.AlignCenter, f"{t_label:.0f}s")

        # Plot lines
        for sd in self.streams:
            pts = [(t, v) for t, v in zip(sd.timestamps, sd.values) if t >= t_min]
            if len(pts) < 2:
                continue

            path = QPainterPath()
            first = True
            for t, v in pts:
                x = rx + (t - t_min) / self.history_seconds * rw
                y = ry + rh - (v - v_min) / v_span * rh
                y = max(float(ry), min(float(ry + rh), y))
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)

            pen = QPen(sd.color)
            pen.setWidthF(1.5)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.drawPath(path)

        # Legend (multi-stream only)
        if len(self.streams) > 1:
            p.setPen(default_pen)
            lx, ly = rx + 6, ry + 6
            for sd in self.streams:
                line_pen = QPen(sd.color)
                line_pen.setWidth(2)
                p.setPen(line_pen)
                p.drawLine(lx, ly + 6, lx + 14, ly + 6)
                p.setPen(default_pen)
                p.drawText(lx + 18, ly, 120, 16,
                           Qt.AlignVCenter | Qt.AlignLeft, sd.cfg.name)
                ly += 18


class _ReadoutPanel(QWidget):
    def __init__(self, streams: List[_StreamData], parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 200)
        # self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._value_labels: Dict[str, QLabel] = {}

        for sd in streams:
            header = f"{sd.cfg.name} ({sd.cfg.unit})" if sd.cfg.unit else sd.cfg.name
            layout.addWidget(QLabel(header))
            val_lbl = QLabel("—")
            layout.addWidget(val_lbl)
            self._value_labels[sd.cfg.name] = val_lbl

        layout.addStretch()

    def update_value(self, name: str, value: float, precision: int):
        if name in self._value_labels:
            self._value_labels[name].setText(f"{value:.{precision}f}")


class TelemetryWidget(QWidget):
    """
    Live telemetry widget: value readouts on the left, scrolling graph on the right.

    Parameters
    ----------
    streams : list[StreamConfig]
    history_seconds : float
    sample_rate_hz : float   — sizes the ring buffer
    refresh_ms : int         — graph repaint interval
    """

    new_sample = Signal(str, float)

    def __init__(
        self,
        streams: List[StreamConfig],
        history_seconds: float = 30.0,
        sample_rate_hz: float = 100.0,
        refresh_ms: int = 50,
        parent=None,
    ):
        super().__init__(parent)

        for i, cfg in enumerate(streams):
            if not cfg.color:
                cfg.color = DEFAULT_COLORS[i % len(DEFAULT_COLORS)]

        maxlen = int(history_seconds * sample_rate_hz * 1.2)
        self._streams: Dict[str, _StreamData] = {
            cfg.name: _StreamData(cfg, maxlen) for cfg in streams
        }
        stream_list = list(self._streams.values())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._readout = _ReadoutPanel(stream_list)
        layout.addWidget(self._readout)

        self._graph = _GraphWidget(stream_list, history_seconds)
        layout.addWidget(self._graph, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(refresh_ms)
        self._timer.timeout.connect(self._graph.update)
        self._timer.start()

    @Slot(dict)
    def push(self, data: Dict[str, float]):
        """Push {stream_name: value} at the current time."""
        t = time.monotonic()
        for name, value in data.items():
            if name in self._streams:
                sd = self._streams[name]
                sd.append(value, t)
                self._readout.update_value(name, value, sd.cfg.precision)
                self.new_sample.emit(name, value)

    @Slot(str, float)
    def push_stream(self, name: str, value: float):
        """Push a single (name, value) sample."""
        self.push({name: value})

    def clear(self):
        """Clear all historical data."""
        for sd in self._streams.values():
            sd.values.clear()
            sd.timestamps.clear()
            sd.latest = None


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import random

    app = QApplication(sys.argv)

    widget = TelemetryWidget(
        streams=[
            StreamConfig(name="Thrust", unit="N"),
            StreamConfig(name="Torque", unit="Nm"),
        ],
        history_seconds=20,
        sample_rate_hz=50,
    )
    widget.setWindowTitle("TelemetryWidget")
    widget.resize(700, 250)
    widget.show()

    _t = 0.0
    _sim = QTimer()

    def _tick():
        global _t
        _t += 0.02
        widget.push({
            "Thrust": 15.0 + 8.0 * math.sin(_t * 0.8) + random.gauss(0, 0.3),
            "Torque": 0.45 + 0.2 * math.sin(_t * 1.3) + random.gauss(0, 0.01),
        })

    _sim.timeout.connect(_tick)
    _sim.start(20)

    sys.exit(app.exec())