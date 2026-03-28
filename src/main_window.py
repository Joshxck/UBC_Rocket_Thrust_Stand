# main_window.py

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
)
import serial
import serial.tools.list_ports
from src.connection_widget import ConnectionWidget
from src.serial_thread import SerialWorker
from src.plotter_widget import TelemetryWidget, StreamConfig
from src.dsp import MovingAverageFilter, LeakyIntegrator
from src.throttle_sender import ThrottleControlWidget
from src.csv_logger import CsvLoggerWidget



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        ma_size = 6
        li_alpha = 0.95

        self.ma1 = MovingAverageFilter(ma_size)
        self.li1 = LeakyIntegrator(li_alpha)

        self.ma2 = MovingAverageFilter(ma_size)
        self.li2 = LeakyIntegrator(li_alpha)

        self._set_title_and_window() # Set the window and label for the main window
        
        self._set_status_bar("N/A") # Set the status bar

        self.central = QWidget()
        self.setCentralWidget(self.central)

        self.main_layout = QVBoxLayout(self.central)

        # TITLE LAYOUT
        title_row = QHBoxLayout()
        title = QLabel("UBC Rocket TVR thrust stand GUI")
        title.setAlignment(Qt.AlignLeft)
        title.setObjectName('title')

        picture = QLabel()
        pixmap = QPixmap("images/ubc-rocket-logo.png")
        scaled = pixmap.scaled(100, 50)  # fixed size
        picture.setPixmap(scaled)
        picture.setAlignment(Qt.AlignRight | Qt.AlignTop)

        title_row.addWidget(title)
        title_row.addWidget(picture)

        self.main_layout.addLayout(title_row)

        # CONNECT LAYOUT
        self.connection_widget = ConnectionWidget()
        self.connection_widget.connection_established.connect(self.on_connected)

        self.main_layout.addWidget(self.connection_widget)

        self.col = QHBoxLayout()
        self.main_layout.addLayout(self.col)

        self.controls_layout = QVBoxLayout()
        self.controls_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.data_layout = QVBoxLayout()
        self.col.addLayout(self.controls_layout)
        self.col.addLayout(self.data_layout)

        # CONTROLS LAYOUT

        self.throttle_sender = ThrottleControlWidget()
        self.throttle_sender.send_throttle.connect(self._send_throttle)
        self.controls_layout.addWidget(self.throttle_sender)

        self.controls_layout.addSpacing(10)

        self.thrust_tare_btn = QPushButton("Tare Thrust")
        self.torque_tare_btn = QPushButton("Tare Torque")
        self.thrust_tare_btn.pressed.connect(self._tare_thrust)
        self.torque_tare_btn.pressed.connect(self._tare_torque)
        self.thrust_tare_btn.setFixedSize(200, 30)
        self.torque_tare_btn.setFixedSize(200, 30)
        self.controls_layout.addWidget(self.thrust_tare_btn,alignment=Qt.AlignmentFlag.AlignHCenter)
        self.controls_layout.addWidget(self.torque_tare_btn,alignment=Qt.AlignmentFlag.AlignHCenter)

        self.controls_layout.addSpacing(10)

        self.set_thrust_btn = QPushButton("Set Thrust Scale")
        self.set_torque_btn = QPushButton("Set Thrust Scale")
        self.set_thrust_btn.pressed.connect(self._cal_thrust_50)
        self.set_torque_btn.pressed.connect(self._cal_torque_50)
        self.set_thrust_btn.setFixedSize(200, 30)
        self.set_torque_btn.setFixedSize(200, 30)
        self.controls_layout.addWidget(self.set_thrust_btn,alignment=Qt.AlignmentFlag.AlignHCenter)
        self.controls_layout.addWidget(self.set_torque_btn,alignment=Qt.AlignmentFlag.AlignHCenter)

        self.controls_layout.addSpacing(10)

        self.logger = CsvLoggerWidget()
        self.controls_layout.addWidget(self.logger)

        self.controls_layout.addStretch()

        # FIRST ROW
        self.first_row = QHBoxLayout()

        self.thrust_widget = TelemetryWidget(
            streams=[
                StreamConfig(name="Thrust", unit="g")
            ],
            history_seconds=30,
            sample_rate_hz=100,
        )

        self.torque_widget = TelemetryWidget(
            streams=[
                StreamConfig(name="Torque", unit="g*mm")
            ],
            history_seconds=30,
            sample_rate_hz=100,
        )

        self.first_row.addWidget(self.thrust_widget, stretch=1)
        self.first_row.addWidget(self.torque_widget, stretch=1)

        self.data_layout.addLayout(self.first_row)

        # SECOND ROW

        self.second_row = QHBoxLayout()

        self.throttle_widget_1 = TelemetryWidget(
            streams=[
                StreamConfig(name="Throttle 1", unit="%"),
                StreamConfig(name="Throttle 2", unit="%")
            ],
            history_seconds=30,
            sample_rate_hz=100,
        )

        self.throttle_widget_2 = TelemetryWidget(
            streams=[
                StreamConfig(name="Average Throttle", unit="%"),
                StreamConfig(name="Diff Throttle (1-2)", unit="%"),
            ],
            history_seconds=30,
            sample_rate_hz=100,
        )

        self.second_row.addWidget(self.throttle_widget_1, stretch=1)
        self.second_row.addWidget(self.throttle_widget_2, stretch=1)

        self.data_layout.addLayout(self.second_row)

        # THIRD ROW

        self.third_row = QHBoxLayout()

        self.rpm_widget = TelemetryWidget(
            streams=[
                StreamConfig(name="RPM 1", unit="RPM"),
                StreamConfig(name="RPM 2", unit="RPM")
            ],
            history_seconds=30,
            sample_rate_hz=100,
        )

        self.voltage_widget = TelemetryWidget(
            streams=[
                StreamConfig(name="V1", unit="V"),
                StreamConfig(name="V2", unit="V"),
                StreamConfig(name="V3", unit="V")
            ],
            history_seconds=30,
            sample_rate_hz=100,
        )

        self.third_row.addWidget(self.rpm_widget, stretch=1)
        self.third_row.addWidget(self.voltage_widget, stretch=1)

        self.data_layout.addLayout(self.third_row)
    

    def _send_throttle(self, throttle1:float, throttle2:float):
        self.worker.set_throttle1(throttle1)
        self.worker.set_throttle2(throttle2)
    

    def _tare_thrust(self):
        self.worker.tare2()


    def _tare_torque(self):
        self.worker.tare1()
    

    def _cal_thrust_50(self):
        self.worker.calibrate(2,50.0)


    def _cal_torque_50(self):
        self.worker.calibrate(1,50.0)

    def on_connected(self, device:str):
        self.worker = SerialWorker(device)
        self.worker.data_received.connect(self.handle_data)
        self.worker.start()

        self.worker.data_received.connect(
            self.logger.backend.on_data_received
        )

        # Optional: show a live row counter in your status bar
        self.logger.backend.row_written.connect(
            lambda n: self.statusBar().showMessage(f"Logging… {n} rows")
        )


    def handle_data(self, data:dict):
        # Thrust/Torque
        self.thrust_widget.push_stream("Thrust", data["loadcell2"])

        self.torque_widget.push_stream("Torque", data["loadcell1"])

        # Throttle

        self.throttle_widget_1.push_stream("Throttle 1", data["throttle1"])
        self.throttle_widget_1.push_stream("Throttle 2", data["throttle2"])

        av = (data["throttle1"] + data["throttle1"])/2
        diff = data["throttle1"] - data["throttle2"]

        self.throttle_widget_2.push_stream("Average Throttle", av)
        self.throttle_widget_2.push_stream("Diff Throttle", diff)

        # Filter RPM data

        rpm1 = self.li1.update(self.ma1.update(data["rpm1"]))
        rpm2 = self.li2.update(self.ma2.update(data["rpm2"]))

        self.rpm_widget.push_stream("RPM 1", rpm1)
        self.rpm_widget.push_stream("RPM 2", rpm2)

        # Voltages

        self.voltage_widget.push_stream("V1", data["cell1_v"])
        self.voltage_widget.push_stream("V2", data["cell2_v"])
        self.voltage_widget.push_stream("V3", data["cell3_v"])
    
    
    def _set_title_and_window(self) -> None:
        """Set the title and window
        """
        self.setWindowTitle("UBC Rocket TVR Thust Stand GUI")
        my_icon = QIcon()
        my_icon.addFile('images\\ubc-rocket-logo.ico')
        self.setWindowIcon(my_icon)
    
    
    def _set_status_bar(self, port:str) -> None:
        """Set the status bar of the Main window

        Args:
            Port (str): port number
        """
        status_bar = self.statusBar()
        status_bar.showMessage(
            f'Connected on {port}', 
            timeout=0
            )
