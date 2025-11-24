"""Виджет с поддержкой drag & drop для панели файлов."""

from pathlib import Path
from typing import List

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QMessageBox
from PyQt5.QtGui import QDragEnterEvent, QDropEvent


class DraggableContentWidget(QWidget):
    """Виджет контента с поддержкой drag & drop."""
    
    files_dropped = pyqtSignal(list)  # Сигнал с списком путей к файлам
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Обработка входа drag & drop."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Обработка движения drag & drop."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Обработка drop файлов."""
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        
        urls = event.mimeData().urls()
        file_paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
        
        if not file_paths:
            event.ignore()
            return
        
        self.files_dropped.emit(file_paths)
        event.acceptProposedAction()

