# connection_widget.py

from PySide6.QtGui import QIcon, QPixmap, QFont
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton
)
from PySide6.QtCore import (
    Qt,
    Signal
)
import serial
import serial.tools.list_ports


class ConnectionWidget(QWidget):
    connection_established = Signal(str)

    BAUD_RATE = 115200
    TIMEOUT = 1.0   # seconds

    def __init__(self):
        super().__init__()

        connect_row = QHBoxLayout(self)

        port_label = QLabel("Port: ")
        port_label.setFixedSize(50, 20)

        self.combo = QComboBox()
        self.combo.setMinimumWidth(180)
        self.combo.setToolTip("Select the COM port for thrust stand")
        self.combo.currentIndexChanged.connect(self._on_combo_changed)

        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setFixedWidth(32)
        self.btn_refresh.setToolTip("Refresh port list")
        self.btn_refresh.clicked.connect(self.refresh_ports)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setEnabled(False)
        self.btn_connect.clicked.connect(self._on_connect)

        self.status = QLabel("Not Connected")
        font = QFont()
        font.setItalic(True)
        self.status.setFont(font)

        connect_row.addWidget(port_label)
        connect_row.addWidget(self.combo)
        connect_row.addWidget(self.btn_refresh)
        connect_row.addWidget(self.btn_connect)
        connect_row.addWidget(self.status)

        self.refresh_ports()
    

    def _on_combo_changed(self, index: int):
        has_real_port = self.combo.itemData(index) is not None
        self.btn_connect.setEnabled(has_real_port)
    

    def refresh_ports(self):
        """Re-scan available COM ports and repopulate the combo box."""
        self.combo.clear()
 
        ports = sorted(
            serial.tools.list_ports.comports(),
            key=lambda p: p.device
        )
 
        if not ports:
            self.combo.addItem("No ports found")
            self.btn_connect.setEnabled(False)
            return
 
        for port in ports:
            # Show device name + description for easy Teensy identification
            label = f"{port.device}"
            if port.description and port.description != "n/a":
                label += f"  —  {port.description}"
            self.combo.addItem(label, userData=port.device)
 
        self.combo.setCurrentIndex(0)
        self.btn_connect.setEnabled(True)


    def _on_connect(self):
        device = self.combo.currentData()
        if not device:
            return
 
        # try:
        #     port = serial.Serial(
        #         port=device,
        #         baudrate=self.BAUD_RATE,
        #         timeout=self.TIMEOUT,
        #     )
        # except serial.SerialException as exc:
        #     self._set_status(f"Error: {exc}", error=True)
        #     return
 
        # self.serial_port = port
        self._lock_controls()
        self._set_status(f"Connected:  {device}")
        self.connection_established.emit(device)


    def _lock_controls(self):
        """Disable combo, refresh, and connect button after a successful connection."""
        self.combo.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.btn_connect.setEnabled(False)
 
    def _set_status(self, message: str, error: bool = False):
        self.status.setText(message)
        color = "#c0392b" if error else "#27ae60"
        self.status.setStyleSheet(f"color: {color};")