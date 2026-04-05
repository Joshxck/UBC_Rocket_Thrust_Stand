# csv_logger.py
import csv
import io
import tempfile
import os
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtCore import QObject, Signal, Slot, QMutex, QMutexLocker


class CsvLoggerBackend(QObject):
    """
    Handles all logging logic. Lives in whatever thread you need —
    connect data_received to your serial worker's signal directly.
    """
    row_written = Signal(int)   # emits total row count after each write

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._buffer: list[dict] = []
        self._fieldnames: list[str] | None = None
        self._logging = False

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    @property
    def is_logging(self) -> bool:
        return self._logging

    @Slot()
    def start(self):
        with QMutexLocker(self._mutex):
            self._buffer.clear()
            self._fieldnames = None
            self._logging = True

    @Slot()
    def stop(self):
        with QMutexLocker(self._mutex):
            self._logging = False

    @Slot(dict)
    def on_data_received(self, data: dict):
        """Connect your serial worker's signal here."""
        with QMutexLocker(self._mutex):
            if not self._logging:
                return
            # Prepend timestamp so it's always the first column
            stamped = {"timestamp": datetime.now().isoformat(timespec="milliseconds")} | data
            # Capture column order from the first packet
            if self._fieldnames is None:
                self._fieldnames = list(stamped.keys())
            self._buffer.append(stamped)
        self.row_written.emit(len(self._buffer))

    def save_to_file(self, filepath: str) -> int:
        """
        Write the in-memory buffer to *filepath*.
        Returns the number of rows written, or raises on error.
        """
        with QMutexLocker(self._mutex):
            buf = list(self._buffer)
            fields = list(self._fieldnames) if self._fieldnames else []

        if not buf:
            return 0

        # Collect any keys that appeared in later packets but not the first
        extra = []
        seen = set(fields)
        for row in buf:
            for k in row:
                if k not in seen:
                    extra.append(k)
                    seen.add(k)
        fields += extra

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(buf)

        return len(buf)


class CsvLoggerWidget(QWidget):
    """
    Drop-in widget: a single button that toggles between
    'Start Logging' and 'Stop Logging', then opens a save dialog.

    Usage
    -----
        self.csv_widget = CsvLoggerWidget()
        # Connect your serial worker signal:
        self.serial_worker.data_received.connect(
            self.csv_widget.backend.on_data_received
        )
        # Optionally show live row count somewhere:
        self.csv_widget.backend.row_written.connect(self.on_row_count_changed)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.backend = CsvLoggerBackend()

        self._btn = QPushButton("⏺  Start Logging")
        self._btn.setCheckable(False)
        self._btn.clicked.connect(self._on_button_clicked)
        self._apply_style(logging=False)
        self._btn.setFixedSize(200,30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._btn)

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _on_button_clicked(self):
        if not self.backend.is_logging:
            self._start()
        else:
            self._stop()

    def _start(self):
        self.backend.start()
        self._btn.setText("⏹  Stop Logging")
        self._apply_style(logging=True)

    def _stop(self):
        self.backend.stop()
        self._btn.setText("⏺  Start Logging")
        self._apply_style(logging=False)
        self._prompt_save()

    def _prompt_save(self):
        default_name = datetime.now().strftime("log_%Y%m%d_%H%M%S.csv")
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV Log",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not filepath:
            # User cancelled — ask whether to discard or keep in memory
            ans = QMessageBox.question(
                self,
                "Discard log?",
                "No file selected. Discard the recorded data?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans == QMessageBox.StandardButton.No:
                # Re-enter logging-stopped state without clearing the buffer
                # so they can try saving again via save_current_buffer()
                pass
            return

        try:
            rows = self.backend.save_to_file(filepath)
            QMessageBox.information(
                self,
                "Log Saved",
                f"Saved {rows} rows to:\n{filepath}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))

    def _apply_style(self, logging: bool):
        if logging:
            self._btn.setStyleSheet(
                "QPushButton { background-color: #c0392b; color: white;"
                "font-weight: bold; padding: 6px 14px; border-radius: 4px; }"
                "QPushButton:hover { background-color: #e74c3c; }"
            )
        else:
            self._btn.setStyleSheet(
                "QPushButton { background-color: #2596be; color: white;"
                "font-weight: bold; padding: 6px 14px; border-radius: 4px; }"
                "QPushButton:hover { background-color: #2ecc71; }"
            )

    # ------------------------------------------------------------------ #
    #  Convenience                                                         #
    # ------------------------------------------------------------------ #

    def save_current_buffer(self, filepath: str) -> int:
        """Call this if you want to trigger a save programmatically."""
        return self.backend.save_to_file(filepath)