"""Выпадающий список с чекбоксами"""

from typing import List, Optional
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QLabel,
    QApplication,
    QLineEdit,
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QSize, QEvent
from PyQt5.QtGui import QColor, QPainter, QPolygon

from ..styles.theme_provider import THEME_PROVIDER


class _ComboButton(QPushButton):
    """Кнопка со стрелкой вниз"""
    
    def paintEvent(self, event):
        """Кастомная отрисовка кнопки со стрелкой"""
        super().paintEvent(event)
        
        # Рисуем стрелку вниз справа
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = THEME_PROVIDER.colors
        painter.setPen(QColor(colors.text_primary))
        painter.setBrush(QColor(colors.text_primary))
        
        # Стрелка вниз (треугольник)
        arrow_size = 6
        button_rect = self.rect()
        arrow_x = button_rect.right() - 12
        arrow_y = button_rect.center().y()
        
        arrow = QPolygon([
            QPoint(arrow_x, arrow_y - arrow_size // 2),
            QPoint(arrow_x + arrow_size, arrow_y - arrow_size // 2),
            QPoint(arrow_x + arrow_size // 2, arrow_y + arrow_size // 2)
        ])
        painter.drawPolygon(arrow)


class CheckboxComboBox(QWidget):
    """Выпадающий список с чекбоксами"""
    
    selection_changed = pyqtSignal(list)  # Сигнал с выбранными значениями
    
    def __init__(self, parent: Optional[QWidget] = None, enable_search: bool = False):
        super().__init__(parent)
        self._selected_values: List[str] = []
        self._all_values: List[str] = []
        self._enable_search = enable_search
        self._search_edit: Optional[QLineEdit] = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Настройка UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Кнопка, которая выглядит как QComboBox
        self.button = _ComboButton()
        self.button.setStyleSheet(self._get_button_style())
        self.button.clicked.connect(self._toggle_dropdown)
        layout.addWidget(self.button)
        
        # Выпадающий список (будет установлен как независимое окно при показе)
        self.dropdown = QFrame()
        self.dropdown.setFrameShape(QFrame.Box)
        self.dropdown.hide()
        
        dropdown_layout = QVBoxLayout(self.dropdown)
        dropdown_layout.setContentsMargins(0, 0, 0, 0)
        dropdown_layout.setSpacing(0)
        
        # Добавляем строку поиска, если включена
        if self._enable_search:
            self._search_edit = QLineEdit()
            self._search_edit.setPlaceholderText("Поиск...")
            self._search_edit.setStyleSheet(self._get_search_style())
            self._search_edit.textChanged.connect(self._on_search_text_changed)
            dropdown_layout.addWidget(self._search_edit)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(self._get_list_style())
        self.list_widget.setMaximumHeight(200)
        self.list_widget.itemChanged.connect(self._on_item_changed)
        dropdown_layout.addWidget(self.list_widget)
        
        self.dropdown.setLayout(dropdown_layout)
        
        # Обновляем текст кнопки после создания list_widget
        self._update_button_text()
    
    def _get_button_style(self) -> str:
        """Получить стиль для кнопки"""
        colors = THEME_PROVIDER.colors
        return f"""
            QPushButton {{
                background-color: {colors.input_background};
                border: 1px solid {colors.input_border};
                border-radius: 4px;
                color: {colors.text_primary};
                padding: 4px 24px 4px 8px;
                text-align: left;
                min-height: 24px;
            }}
            QPushButton:hover {{
                border-color: {colors.border_hover};
            }}
            QPushButton:pressed {{
                background-color: {colors.background_hover};
            }}
        """
    
    
    def _get_list_style(self) -> str:
        """Получить стиль для списка"""
        colors = THEME_PROVIDER.colors
        return f"""
            QListWidget {{
                background-color: {colors.background_elevated};
                border: 1px solid {colors.border_primary};
                border-radius: 4px;
                color: {colors.text_primary};
            }}
            QListWidget::item {{
                padding: 4px;
                border-radius: 2px;
            }}
            QListWidget::item:selected {{
                background-color: {colors.selection_background};
                color: {colors.selection_text};
            }}
            QListWidget::item:hover {{
                background-color: {colors.background_hover};
            }}
        """
    
    def _get_search_style(self) -> str:
        """Получить стиль для строки поиска"""
        colors = THEME_PROVIDER.colors
        return f"""
            QLineEdit {{
                background-color: {colors.input_background};
                border: 1px solid {colors.input_border};
                border-radius: 4px;
                color: {colors.text_primary};
                padding: 4px 8px;
                margin: 4px;
            }}
            QLineEdit:focus {{
                border-color: {colors.border_hover};
            }}
        """
    
    def setValues(self, values: List[str]):
        """Установить список значений"""
        self._all_values = sorted(values)
        self._apply_filter()
        self._update_button_text()
    
    def _apply_filter(self, search_text: str = ""):
        """Применить фильтр к списку"""
        self.list_widget.clear()
        search_lower = search_text.lower().strip()
        
        for value in self._all_values:
            # Если есть поиск, фильтруем по тексту
            if search_lower and search_lower not in value.lower():
                continue
            
            item = QListWidgetItem(value)
            # Сохраняем состояние чекбокса, если значение было выбрано
            if value in self._selected_values:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)
    
    def _on_search_text_changed(self, text: str):
        """Обработчик изменения текста поиска"""
        self._apply_filter(text)
    
    def getSelectedValues(self) -> List[str]:
        """Получить выбранные значения"""
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                value = item.text()
                if value == "пусто":
                    selected.append("")
                else:
                    selected.append(value)
        return selected
    
    def clearSelection(self):
        """Очистить выбор"""
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.Unchecked)
        self._selected_values = []
        self._update_button_text()
        self.selection_changed.emit([])
    
    def _update_button_text(self):
        """Обновить текст кнопки"""
        if not hasattr(self, 'list_widget'):
            self.button.setText("Выберите...")
            return
        
        selected = self.getSelectedValues()
        if not selected:
            self.button.setText("Выберите...")
        elif len(selected) == 1:
            self.button.setText(selected[0] if selected[0] else "пусто")
        else:
            self.button.setText(f"Выбрано: {len(selected)}")
    
    def _on_item_changed(self, item: QListWidgetItem):
        """Обработчик изменения чекбокса"""
        self._selected_values = self.getSelectedValues()
        self._update_button_text()
        self.selection_changed.emit(self._selected_values)
    
    def _toggle_dropdown(self):
        """Показать/скрыть выпадающий список"""
        if self.dropdown.isVisible():
            self.dropdown.hide()
            QApplication.instance().removeEventFilter(self)
        else:
            self._show_dropdown()
    
    def _show_dropdown(self):
        """Показать выпадающий список"""
        # Получаем глобальную позицию кнопки
        button_global_pos = self.button.mapToGlobal(QPoint(0, 0))
        button_bottom_global = self.button.mapToGlobal(QPoint(0, self.button.height()))
        
        # Вычисляем высоту списка
        row_height = self.list_widget.sizeHintForRow(0) if self.list_widget.count() > 0 else 20
        max_rows = min(10, self.list_widget.count())
        dropdown_height = row_height * max_rows + 4
        
        # Добавляем высоту строки поиска, если она есть
        if self._enable_search and self._search_edit:
            search_height = self._search_edit.sizeHint().height() + 8  # +8 для отступов
            dropdown_height += search_height
        
        # Устанавливаем dropdown как независимое popup окно
        # Важно: сначала устанавливаем флаги, потом убираем родителя
        self.dropdown.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.dropdown.setParent(None)
        
        # Позиционируем выпадающий список под кнопкой в глобальных координатах
        # Используем move() и resize() для более надежного позиционирования
        self.dropdown.move(button_global_pos.x(), button_bottom_global.y())
        self.dropdown.resize(self.button.width(), dropdown_height)
        
        self.dropdown.show()
        self.dropdown.raise_()
        
        # Очищаем строку поиска при открытии
        if self._enable_search and self._search_edit:
            self._search_edit.clear()
            self._search_edit.setFocus()
        else:
            self.list_widget.setFocus()
        
        # Устанавливаем обработчик событий для закрытия при клике вне виджета
        QApplication.instance().installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Обработчик событий для закрытия выпадающего списка при клике вне"""
        if event.type() == QEvent.MouseButtonPress:
            if self.dropdown.isVisible():
                # Проверяем, был ли клик вне выпадающего списка и кнопки
                click_pos = event.globalPos()
                dropdown_global = self.dropdown.mapToGlobal(QPoint(0, 0))
                dropdown_rect = self.dropdown.geometry()
                dropdown_rect.moveTopLeft(dropdown_global)
                
                button_global = self.button.mapToGlobal(QPoint(0, 0))
                button_rect = self.button.geometry()
                button_rect.moveTopLeft(button_global)
                
                if not dropdown_rect.contains(click_pos) and not button_rect.contains(click_pos):
                    self.dropdown.hide()
                    QApplication.instance().removeEventFilter(self)
                    return True
        
        return super().eventFilter(obj, event)
    
    def hideEvent(self, event):
        """Скрыть выпадающий список при скрытии виджета"""
        if self.dropdown.isVisible():
            self.dropdown.hide()
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)

