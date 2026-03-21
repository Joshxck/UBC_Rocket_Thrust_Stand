# main_window.py

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self._set_title_and_window() # Set the window and label for the main window
        
        self._set_status_bar("N/A") # Set the status bar
    
    
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
            ip_address (str): IP address of the instrument
        """
        status_bar = self.statusBar()
        status_bar.showMessage(
            f'Connected on {port}', 
            timeout=0
            )