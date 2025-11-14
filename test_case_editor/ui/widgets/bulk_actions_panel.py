"""Панель массовых операций"""

from PyQt5.QtWidgets import QFrame, QHBoxLayout, QPushButton, QMessageBox
from PyQt5.QtCore import pyqtSignal

from ...services.test_case_service import TestCaseService


class BulkActionsPanel(QFrame):
    """
    Панель для массовых операций
    
    Соответствует принципу Single Responsibility:
    отвечает только за отображение и обработку массовых операций
    """
    
    # Сигналы
    clear_selection_requested = pyqtSignal()
    bulk_operation_completed = pyqtSignal()
    
    def __init__(self, service: TestCaseService, parent=None):
        super().__init__(parent)
        self.service = service
        self.selected_items = []
        
        self.setup_ui()
    
    def setup_ui(self):
        """Настройка UI"""
        self.setMaximumHeight(60)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)
        
        layout.addStretch()
        
        # Кнопка "Удалить"
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.setMinimumHeight(35)
        self.delete_btn.clicked.connect(self._bulk_delete)
        self.delete_btn.setEnabled(False)
        layout.addWidget(self.delete_btn)
        
        # Кнопка "Сбросить"
        self.clear_btn = QPushButton("✖ Сбросить")
        self.clear_btn.setMinimumHeight(35)
        self.clear_btn.clicked.connect(self._clear_selection)
        layout.addWidget(self.clear_btn)
    
    def update_selected_items(self, items: list):
        """Обновить список выбранных элементов"""
        self.selected_items = items
        self.delete_btn.setEnabled(len(items) > 0)
    
    def _bulk_delete(self):
        """Массовое удаление"""
        if not self.selected_items:
            return
        
        # Подтверждение
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить {len(self.selected_items)} элемент(ов)?\n\n"
            "Это действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Удаляем через сервис
        deleted_count, errors = self.service.bulk_delete_items(self.selected_items)
        
        # Очищаем выбор
        self.selected_items.clear()
        self.delete_btn.setEnabled(False)
        self.bulk_operation_completed.emit()
        
        # Показываем результат
        if errors:
            message = f"Удалено элементов: {deleted_count}\n\nОшибки:\n" + "\n".join(errors[:5])
            QMessageBox.warning(self, "Удаление завершено с ошибками", message)
    
    def _clear_selection(self):
        """Очистить выбор"""
        self.selected_items.clear()
        self.delete_btn.setEnabled(False)
        self.clear_selection_requested.emit()


