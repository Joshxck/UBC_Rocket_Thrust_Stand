from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QDoubleSpinBox, QPushButton
)
from PySide6.QtCore import Qt, Signal

class ThrottleControlWidget(QWidget):
    send_throttle = Signal(float,float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.throttle1_input = QDoubleSpinBox()
        self.throttle2_input = QDoubleSpinBox()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addLayout(self._make_percent_row("Throttle 1:", self.throttle1_input))
        layout.addLayout(self._make_percent_row("Throttle 2:", self.throttle2_input))

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self._on_send)
        self.send_button.setFixedSize(200, 30)
        layout.addWidget(self.send_button)

    def _make_percent_row(self, label_text: str, spinbox: QDoubleSpinBox) -> QHBoxLayout:
        row = QHBoxLayout()
        spinbox.setRange(0.0, 100.0)
        spinbox.setValue(0.0)
        spinbox.setSingleStep(1.0)
        spinbox.setDecimals(1)
        spinbox.setSuffix(" %")
        row.addWidget(QLabel(label_text))
        row.addWidget(spinbox)
        return row

    def get_values(self) -> tuple[float, float]:
        return self.throttle1_input.value(), self.throttle2_input.value()

    def _on_send(self):
        throttle1, throttle2 = self.get_values()
        self.send_throttle.emit(throttle1, throttle2)