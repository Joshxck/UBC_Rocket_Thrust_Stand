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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

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
    

    def on_connected(self, device:str):
        self.worker = SerialWorker(device)
        self.worker.data_received.connect(self.handle_data)
        self.worker.start()


    def handle_data(self):
        return
    
    
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
