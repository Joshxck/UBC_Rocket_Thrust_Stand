# main.py

from PySide6.QtWidgets import QApplication, QDialog

from src.main_window import MainWindow
from pathlib import Path
import sys


def load_stylesheet(filename: Path):
    with filename.open("r") as file:
        return file.read()


def main():
    app = QApplication(sys.argv)
    
    # Load and set stylesheet
    stylesheet_path = Path(r"styles\style.qss")
    stylesheet = load_stylesheet(stylesheet_path)
    app.setStyleSheet(stylesheet)

    # Creates the main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec()) # When the main window closes, exit the app
    


if __name__ == "__main__":
    main()
