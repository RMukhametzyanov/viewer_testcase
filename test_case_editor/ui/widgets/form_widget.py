"""Виджет формы редактирования тест-кейса"""

import json
from pathlib import Path
from typing import List, Optional, Dict
import shutil
import uuid

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QGroupBox,
    QPushButton,
    QFrame,
    QScrollArea,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QSizePolicy,
    QAbstractItemView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QInputDialog,
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QStyleOptionGroupBox,
    QStyle,
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QSize, QTimer, QRect
from PyQt5.QtGui import QFont, QTextOption, QIcon, QPixmap, QPainter, QColor, QDragEnterEvent, QDropEvent, QDragLeaveEvent, QMouseEvent, QWheelEvent
from PyQt5.QtSvg import QSvgRenderer

from ...models.test_case import TestCase, TestCaseStep
from ...services.test_case_service import TestCaseService
from ...utils.datetime_utils import format_datetime, get_current_datetime
from ..styles.ui_metrics import UI_METRICS


class _ExpandableGroupBox(QGroupBox):
    """QGroupBox с возможностью раскрытия/сворачивания по клику на заголовке."""
    
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._is_expanded = False
        self._toggle_callback = None
        self._base_title = title  # Сохраняем исходное название без стрелки
        self._update_title()
    
    def set_toggle_callback(self, callback):
        """Установить функцию обратного вызова при переключении состояния."""
        self._toggle_callback = callback
    
    def _update_title(self):
        """Обновить заголовок с учетом состояния раскрытия/сворачивания."""
        if self._is_expanded:
            # Стрелка вниз когда развернуто
            self.setTitle(f"{self._base_title} ↓")
        else:
            # Стрелка вверх когда свернуто
            self.setTitle(f"{self._base_title} ↑")
    
    def mousePressEvent(self, event: QMouseEvent):
        """Обработка клика мыши - проверяем, был ли клик на заголовке."""
        if event.button() == Qt.LeftButton:
            # Используем QStyleOptionGroupBox для точного определения области заголовка
            option = QStyleOptionGroupBox()
            self.initStyleOption(option)
            
            # Получаем область заголовка через стиль
            style = self.style()
            header_rect = style.subControlRect(
                QStyle.CC_GroupBox, 
                option, 
                QStyle.SC_GroupBoxLabel, 
                self
            )
            
            # Расширяем область заголовка немного вниз для удобства клика
            header_rect.setBottom(header_rect.bottom() + 10)
            
            if header_rect.contains(event.pos()):
                self._toggle_expanded()
                event.accept()
                return
        super().mousePressEvent(event)
    
    def _toggle_expanded(self):
        """Переключить состояние раскрытия/сворачивания."""
        self._is_expanded = not self._is_expanded
        self._update_title()  # Обновляем заголовок с новой стрелкой
        if self._toggle_callback:
            self._toggle_callback(self._is_expanded)
    
    def is_expanded(self) -> bool:
        """Проверить, раскрыт ли блок."""
        return self._is_expanded


class _NoWheelComboBox(QComboBox):
    """Комбо-бокс без изменения значения колесом мыши, пока меню закрыто."""

    def wheelEvent(self, event):
        popup = self.view()
        if popup and popup.isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()


class _StepsTableWidget(QTableWidget):
    """Таблица шагов с поддержкой drag & drop для прикрепления файлов."""
    
    files_dropped_on_row = pyqtSignal(int, list)  # row, file_paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self._drag_over_row = -1  # Текущая строка, над которой происходит drag
        
        # Настройка плавной прокрутки по пикселям
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        
        # Применяем стиль для обводки строки при drag & drop
        self.setStyleSheet("""
            QTableWidget::item {
                border: none;
            }
        """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Обработка входа drag & drop."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._update_drag_over_row(event.pos())
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Обработка движения drag & drop."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._update_drag_over_row(event.pos())
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        """Обработка выхода drag & drop."""
        self._clear_drag_over_row()
        super().dragLeaveEvent(event)
    
    def _update_drag_over_row(self, pos):
        """Обновить визуальное выделение строки при drag & drop."""
        row = self.indexAt(pos).row()
        if row != self._drag_over_row:
            # Убираем выделение с предыдущей строки
            self._clear_drag_over_row()
            # Добавляем выделение новой строке
            if row >= 0:
                self._drag_over_row = row
                # Применяем стиль выделения к строке через items (обводка вокруг всей строки)
                # Используем более яркий цвет для лучшей видимости
                highlight_color = QColor(100, 150, 255, 120)  # Более яркий полупрозрачный синий фон
                for col in range(self.columnCount()):
                    item = self.item(row, col)
                    if not item:
                        # Создаем временный item для стилизации, если его нет
                        item = QTableWidgetItem()
                        item.setFlags(Qt.NoItemFlags)  # Не редактируется
                        self.setItem(row, col, item)
                    # Применяем фон выделения (обводка вокруг всей строки)
                    item.setBackground(highlight_color)
    
    def _clear_drag_over_row(self):
        """Убрать визуальное выделение строки."""
        if self._drag_over_row >= 0:
            row = self._drag_over_row
            # Убираем выделение строки
            self.clearSelection()
            # Убираем фон у всех items в строке
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    if item.flags() == Qt.NoItemFlags:
                        # Удаляем временный item, если он был создан только для стилизации
                        self.takeItem(row, col)
                    else:
                        # Убираем фон у существующего item
                        item.setBackground(QColor())
            self._drag_over_row = -1
    
    def wheelEvent(self, event: QWheelEvent):
        """Переопределяем wheelEvent для плавной пиксельной прокрутки."""
        # Получаем вертикальный скроллбар
        v_scrollbar = self.verticalScrollBar()
        if v_scrollbar and v_scrollbar.isVisible():
            # Получаем дельту прокрутки
            delta = event.angleDelta().y()
            
            # Проверяем, есть ли пиксельная дельта (новые версии Qt)
            pixel_delta = event.pixelDelta().y() if not event.pixelDelta().isNull() else None
            
            if pixel_delta is not None:
                # Если есть пиксельная дельта, используем её напрямую
                current_value = v_scrollbar.value()
                new_value = current_value - pixel_delta
                v_scrollbar.setValue(new_value)
            else:
                # Если delta в градусах (обычно 120 градусов за клик), конвертируем в пиксели
                # Используем более плавный коэффициент для пиксельной прокрутки
                # Стандартный шаг - 15 пикселей на 120 градусов (1 клик)
                pixel_delta = (delta / 120.0) * 15
                
                # Прокручиваем на вычисленное количество пикселей
                current_value = v_scrollbar.value()
                new_value = current_value - int(pixel_delta)
                v_scrollbar.setValue(new_value)
            
            event.accept()
        else:
            # Если вертикальный скроллбар не виден, используем стандартное поведение
            super().wheelEvent(event)
    
    def dropEvent(self, event: QDropEvent):
        """Обработка drop файлов."""
        # Убираем выделение
        self._clear_drag_over_row()
        
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        
        # Определяем строку, на которую был выполнен drop
        row = self.indexAt(event.pos()).row()
        if row < 0:
            event.ignore()
            return
        
        # Получаем список файлов
        urls = event.mimeData().urls()
        file_paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
        
        if not file_paths:
            event.ignore()
            return
        
        # Эмитируем сигнал с номером строки и списком файлов
        self.files_dropped_on_row.emit(row, file_paths)
        event.acceptProposedAction()


class TestCaseFormWidget(QWidget):
    """
    Форма редактирования тест-кейса
    
    Соответствует принципу Single Responsibility:
    отвечает только за отображение и редактирование формы
    """
    
    status_changed = pyqtSignal()  # Сигнал об изменении статуса шага
    file_attached_to_step = pyqtSignal()  # Сигнал о прикреплении файла к шагу

    # Методы для работы с таблицей шагов в стиле TestOps
    def _create_step_text_edit(self, placeholder: str) -> QTextEdit:
        """Создать QTextEdit для редактирования шага."""
        edit = QTextEdit()
        edit.setPlaceholderText(placeholder)
        edit.setWordWrapMode(QTextOption.WordWrap)
        edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        edit.setAcceptDrops(False)  # Отключаем drag & drop для QTextEdit, чтобы не вставлялся текст
        edit.textChanged.connect(lambda: self._on_step_content_changed())
        return edit
    
    def _create_step_status_widget(self, row: int) -> QWidget:
        """Создать виджет со статусами шага (вертикально расположенные минималистичные кнопки)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        buttons = []
        spec = [
                ("passed", "#2ecc71"),
                ("failed", "#e74c3c"),
                ("skipped", "#95a5a6"),
            ]
        for value, color in spec:
            btn = QToolButton()
            
            # Загружаем иконку из маппинга с цветом статуса (для неактивного состояния)
            icon_name = self._get_status_icon(value)
            if icon_name:
                # Сохраняем имя иконки для последующей перезагрузки
                btn.setProperty("icon_name", icon_name)
                # Загружаем иконку с цветом статуса для неактивного состояния
                icon = self._load_svg_icon(icon_name, size=16, color=color)
                if icon:
                    btn.setIcon(icon)
                    btn.setIconSize(QSize(16, 16))
                else:
                    # Fallback на текст, если иконка не загрузилась
                    fallback_text = {"passed": "✓", "failed": "✕", "skipped": "S"}.get(value, "?")
                    btn.setText(fallback_text)
            else:
                # Fallback на текст, если иконка не найдена в маппинге
                fallback_text = {"passed": "✓", "failed": "✕", "skipped": "S"}.get(value, "?")
                btn.setText(fallback_text)
            
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setAutoRaise(True)
            btn.setFixedSize(24, 24)  # Компактный размер для вертикального расположения
            btn.setProperty("status_value", value)
            btn.setProperty("status_color", color)
            btn.clicked.connect(lambda _checked, val=value, r=row: self._on_step_status_clicked(r, val))
            layout.addWidget(btn)
            buttons.append(btn)
        
        layout.addStretch()  # Растягиваем пространство, чтобы кнопки были сверху
        # Видимость управляется через скрытие/показ колонки, а не виджета
        widget.setProperty("status_buttons", buttons)
        return widget
    
    def _create_step_actions_widget(self, row: int) -> QWidget:
        """Создать виджет с кнопками управления шагом (вертикально расположенные минималистичные кнопки)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Минималистичные стили для кнопок действий
        action_button_style = """
            QToolButton {
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                font-size: 12px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.2);
            }
        """
        
        # Кнопка прикрепления файла - первая в списке
        attach_file_btn = QToolButton()
        icon_name = self._get_step_action_icon("attach_file")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            if icon:
                attach_file_btn.setIcon(icon)
                attach_file_btn.setIconSize(QSize(16, 16))
            else:
                attach_file_btn.setText("📎")
        else:
            attach_file_btn.setText("📎")
        attach_file_btn.setToolTip("Прикрепить файл")
        attach_file_btn.setCursor(Qt.PointingHandCursor)
        attach_file_btn.setAutoRaise(True)
        attach_file_btn.setFixedSize(24, 24)
        attach_file_btn.setStyleSheet(action_button_style)
        attach_file_btn.clicked.connect(lambda: self._attach_file_to_step(row))
        layout.addWidget(attach_file_btn)
        
        add_above_btn = QToolButton()
        icon_name = self._get_step_action_icon("add_above")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            if icon:
                add_above_btn.setIcon(icon)
                add_above_btn.setIconSize(QSize(16, 16))
            else:
                add_above_btn.setText("+↑")
        else:
            add_above_btn.setText("+↑")
        add_above_btn.setToolTip("Добавить шаг выше")
        add_above_btn.setCursor(Qt.PointingHandCursor)
        add_above_btn.setAutoRaise(True)
        add_above_btn.setFixedSize(24, 24)
        add_above_btn.setStyleSheet(action_button_style)
        add_above_btn.clicked.connect(lambda: self._insert_step_above(row))
        layout.addWidget(add_above_btn)
        
        add_below_btn = QToolButton()
        icon_name = self._get_step_action_icon("add_below")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            if icon:
                add_below_btn.setIcon(icon)
                add_below_btn.setIconSize(QSize(16, 16))
            else:
                add_below_btn.setText("+↓")
        else:
            add_below_btn.setText("+↓")
        add_below_btn.setToolTip("Добавить шаг ниже")
        add_below_btn.setCursor(Qt.PointingHandCursor)
        add_below_btn.setAutoRaise(True)
        add_below_btn.setFixedSize(24, 24)
        add_below_btn.setStyleSheet(action_button_style)
        add_below_btn.clicked.connect(lambda: self._insert_step_below(row))
        layout.addWidget(add_below_btn)
        
        move_up_btn = QToolButton()
        icon_name = self._get_step_action_icon("move_up")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            if icon:
                move_up_btn.setIcon(icon)
                move_up_btn.setIconSize(QSize(16, 16))
            else:
                move_up_btn.setText("↑")
        else:
            move_up_btn.setText("↑")
        move_up_btn.setToolTip("Переместить вверх")
        move_up_btn.setCursor(Qt.PointingHandCursor)
        move_up_btn.setAutoRaise(True)
        move_up_btn.setFixedSize(24, 24)
        move_up_btn.setStyleSheet(action_button_style)
        move_up_btn.clicked.connect(lambda: self._move_step_up(row))
        layout.addWidget(move_up_btn)
        
        move_down_btn = QToolButton()
        icon_name = self._get_step_action_icon("move_down")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            if icon:
                move_down_btn.setIcon(icon)
                move_down_btn.setIconSize(QSize(16, 16))
            else:
                move_down_btn.setText("↓")
        else:
            move_down_btn.setText("↓")
        move_down_btn.setToolTip("Переместить вниз")
        move_down_btn.setCursor(Qt.PointingHandCursor)
        move_down_btn.setAutoRaise(True)
        move_down_btn.setFixedSize(24, 24)
        move_down_btn.setStyleSheet(action_button_style)
        move_down_btn.clicked.connect(lambda: self._move_step_down(row))
        layout.addWidget(move_down_btn)
        
        remove_btn = QToolButton()
        icon_name = self._get_step_action_icon("delete")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            if icon:
                remove_btn.setIcon(icon)
                remove_btn.setIconSize(QSize(16, 16))
            else:
                remove_btn.setText("×")
        else:
            remove_btn.setText("×")
        remove_btn.setToolTip("Удалить шаг")
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setAutoRaise(True)
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet(action_button_style)
        remove_btn.clicked.connect(lambda: self._remove_step_by_row(row))
        layout.addWidget(remove_btn)
        
        layout.addStretch()  # Растягиваем пространство, чтобы кнопки были сверху
        
        # Видимость управляется через скрытие/показ колонки, а не виджета
        widget.setProperty("move_up_btn", move_up_btn)
        widget.setProperty("move_down_btn", move_down_btn)
        return widget
    
    class SkipReasonDialog(QDialog):
        """Диалог для выбора причины пропуска тест-кейса"""
        
        def __init__(self, parent=None, skip_reasons: Optional[List[str]] = None):
            super().__init__(parent)
            self.setWindowTitle("Причина пропуска")
            self.setMinimumWidth(400)
            self.skip_reasons = skip_reasons or ['Автотесты', 'Нагрузочное тестирование', 'Другое']
            self._setup_ui()
        
        def _setup_ui(self):
            layout = QVBoxLayout(self)
            
            # Инструкция
            label = QLabel("Выберите причину пропуска:")
            layout.addWidget(label)
            
            # Дропдаун с причинами (пустой пункт по умолчанию)
            self.reason_combo = QComboBox()
            self.reason_combo.addItem("")  # Пустой пункт по умолчанию
            # Добавляем причины из настроек
            if self.skip_reasons:
                self.reason_combo.addItems(self.skip_reasons)
            else:
                # Fallback на значения по умолчанию
                self.reason_combo.addItems(["Автотесты", "Нагрузочное тестирование", "Другое"])
            self.reason_combo.setCurrentIndex(0)  # Выбираем пустой пункт
            self.reason_combo.currentTextChanged.connect(self._on_reason_changed)
            layout.addWidget(self.reason_combo)
            
            # Поле для комментария (видно только при выборе "Другое")
            self.comment_label = QLabel("Комментарий:")
            self.comment_label.setVisible(False)
            layout.addWidget(self.comment_label)
            
            self.comment_edit = QLineEdit()
            self.comment_edit.setPlaceholderText("Введите причину пропуска...")
            self.comment_edit.setVisible(False)
            self.comment_edit.textChanged.connect(self._on_comment_changed)
            layout.addWidget(self.comment_edit)
            
            # Кнопки
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(self.accept)
            button_box.rejected.connect(self.reject)
            self.ok_button = button_box.button(QDialogButtonBox.Ok)
            self.ok_button.setEnabled(False)  # По умолчанию заблокирована
            layout.addWidget(button_box)
        
        def _on_reason_changed(self, text):
            # Показываем поле комментария только для "Другое"
            is_other = text == "Другое"
            self.comment_label.setVisible(is_other)
            self.comment_edit.setVisible(is_other)
            # Обновляем состояние кнопки ОК
            self._update_ok_button()
        
        def _on_comment_changed(self):
            self._update_ok_button()
        
        def _update_ok_button(self):
            # Кнопка ОК активна, если выбрана причина (не пустая) или введен комментарий
            if not hasattr(self, 'ok_button') or not self.ok_button:
                return
            try:
                reason = self.reason_combo.currentText().strip()
                if not reason:
                    # Если не выбрана причина, проверяем комментарий
                    comment = self.comment_edit.text().strip()
                    self.ok_button.setEnabled(bool(comment))
                elif reason == "Другое":
                    # Если выбрано "Другое", нужен комментарий
                    comment = self.comment_edit.text().strip()
                    self.ok_button.setEnabled(bool(comment))
                else:
                    # Если выбрана любая другая причина, кнопка активна
                    self.ok_button.setEnabled(True)
            except Exception:
                # В случае ошибки оставляем кнопку заблокированной
                if self.ok_button:
                    self.ok_button.setEnabled(False)
        
        def get_skip_reason(self) -> str:
            """Получить причину пропуска"""
            reason = self.reason_combo.currentText().strip()
            if not reason:
                # Если не выбрана причина, возвращаем комментарий
                return self.comment_edit.text().strip()
            elif reason == "Другое":
                # Если выбрано "Другое", возвращаем комментарий
                return self.comment_edit.text().strip()
            else:
                # Если выбрана другая причина, возвращаем её значение
                return reason
    
    def _on_step_status_clicked(self, row: int, status: str):
        """Обработчик клика по статусу шага."""
        try:
            if row < 0 or row >= len(self.step_statuses):
                return
            if self.step_statuses[row] == status:
                return
            
            # Если выбран статус "skipped", показываем диалог выбора причины
            if status == "skipped":
                skip_reason = self._show_skip_reason_dialog()
                if skip_reason is None:  # Пользователь отменил диалог
                    return
                # Устанавливаем статус и причину
                self.step_statuses[row] = status
                self._update_step_status_widget(row, status)
                if self.current_test_case and row < len(self.current_test_case.steps):
                    step = self.current_test_case.steps[row]
                    step.status = status
                    step.skip_reason = skip_reason or ""  # Убеждаемся, что это строка
                self._auto_save_status_change()
            else:
                # Для других статусов работаем как раньше
                self.step_statuses[row] = status
                self._update_step_status_widget(row, status)
                if self.current_test_case and row < len(self.current_test_case.steps):
                    step = self.current_test_case.steps[row]
                    step.status = status
                    # Очищаем skipReason при изменении статуса на failed или passed
                    if status in ("failed", "passed"):
                        step.skip_reason = ""
                self._auto_save_status_change()
            
            self._update_statistics()  # Обновляем статистику при изменении статуса
            # Эмитируем сигнал для обновления статистики в главном окне
            if hasattr(self, 'status_changed'):
                self.status_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при изменении статуса шага: {str(e)}")
    
    def _show_skip_reason_dialog(self) -> Optional[str]:
        """Показать диалог выбора причины пропуска"""
        try:
            # Получаем список причин, проверяя наличие атрибута
            skip_reasons = getattr(self, '_skip_reasons', None)
            if not skip_reasons:
                skip_reasons = ['Автотесты', 'Нагрузочное тестирование', 'Другое']
            
            dialog = self.SkipReasonDialog(self, skip_reasons)
            if dialog.exec_() == QDialog.Accepted:
                return dialog.get_skip_reason()
            return None
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при открытии диалога выбора причины: {str(e)}")
            return None
    
    def _update_step_status_widget(self, row: int, status: str):
        """Обновить виджет статуса для указанной строки."""
        status_widget = self.steps_table.cellWidget(row, 3)
        if not status_widget:
            return
        buttons = status_widget.property("status_buttons")
        if not buttons:
            return
        for btn in buttons:
            value = btn.property("status_value")
            color = btn.property("status_color") or "#4CAF50"
            is_active = value == status
            btn.setChecked(is_active)
            
            # Перезагружаем иконку в зависимости от состояния
            icon_name = btn.property("icon_name")
            if icon_name:
                if is_active:
                    # Для активного состояния: белая иконка
                    icon = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                else:
                    # Для неактивного состояния: иконка с цветом статуса
                    icon = self._load_svg_icon(icon_name, size=16, color=color)
                if icon:
                    btn.setIcon(icon)
                    btn.setIconSize(QSize(16, 16))
            
            if is_active:
                # Активное состояние: цветной фон, белая иконка, без рамки
                btn.setStyleSheet(
                    f"""
                    QToolButton {{
                        background-color: {color};
                        border: none;
                        border-radius: 4px;
                        padding: 0px;
                        min-width: 24px;
                        max-width: 24px;
                        min-height: 24px;
                        max-height: 24px;
                    }}
                    """
                )
            else:
                # Неактивное состояние: без рамки, прозрачный фон, иконка с цветом статуса
                btn.setStyleSheet(
                    f"""
                    QToolButton {{
                        background-color: transparent;
                        border: none;
                        border-radius: 4px;
                        padding: 0px;
                        min-width: 24px;
                        max-width: 24px;
                        min-height: 24px;
                        max-height: 24px;
                    }}
                    QToolButton:hover {{
                        background-color: {color}33;
                    }}
                    """
                )

    def _on_step_content_changed(self):
        """Обработчик изменения содержимого шага."""
        if self._is_loading:
            return
        # Обновляем высоту всех строк таблицы для корректного отображения
        QTimer.singleShot(0, self._update_table_row_heights)
        self._mark_changed()
    
    def _calculate_text_edit_height(self, text_edit: QTextEdit, lines: int) -> int:
        """Вычислить высоту QTextEdit для указанного количества строк"""
        metrics = text_edit.fontMetrics()
        line_height = metrics.lineSpacing()
        margins = text_edit.contentsMargins()
        doc_margin = text_edit.document().documentMargin()
        return int(lines * line_height + doc_margin * 2 + margins.top() + margins.bottom() + 10)
    
    def _calculate_widget_height(self, widget: QWidget) -> int:
        """Вычислить высоту виджета на основе его содержимого"""
        if not widget:
            return 0
        
        # Пробуем получить реальную высоту через sizeHint
        hint_height = widget.sizeHint().height()
        if hint_height > 0:
            return hint_height
        
        # Если sizeHint не работает, вычисляем на основе layout
        layout = widget.layout()
        if layout:
            # Получаем margins layout
            margins = layout.getContentsMargins()
            total_margins = margins[1] + margins[3]  # top + bottom
            
            # Подсчитываем высоту всех виджетов в layout
            total_widgets_height = 0
            spacing = layout.spacing()
            widget_count = 0
            
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    widget_item = item.widget()
                    # Если это QToolButton, используем его фиксированный размер
                    if hasattr(widget_item, 'height') and widget_item.height() > 0:
                        total_widgets_height += widget_item.height()
                    elif hasattr(widget_item, 'sizeHint'):
                        widget_hint = widget_item.sizeHint()
                        if widget_hint.isValid():
                            total_widgets_height += widget_hint.height()
                        else:
                            # Fallback для кнопок: 24px
                            total_widgets_height += 24
                    else:
                        total_widgets_height += 24  # Fallback
                    widget_count += 1
            
            # Добавляем spacing между виджетами (widget_count - 1)
            if widget_count > 1:
                total_widgets_height += spacing * (widget_count - 1)
            
            return total_widgets_height + total_margins
        
        # Если layout нет, возвращаем минимальную высоту
        return 50
    
    def _update_table_row_heights(self):
        """Обновить высоты всех строк таблицы индивидуально."""
        # Обновляем высоту каждой строки отдельно на основе её содержимого
        # Это позволяет иметь разную высоту для разных строк
        for row in range(self.steps_table.rowCount()):
            # Получаем виджеты в строке для расчета высоты
            action_edit = self.steps_table.cellWidget(row, 1)
            expected_edit = self.steps_table.cellWidget(row, 2)
            status_widget = self.steps_table.cellWidget(row, 3)  # Виджет статусов (в режиме запуска)
            actions_widget = self.steps_table.cellWidget(row, 4)  # Виджет действий (в режиме редактирования)
            
            if action_edit and expected_edit:
                # Вычисляем высоту для 20 строк (максимум)
                max_text_height_20_lines = max(
                    self._calculate_text_edit_height(action_edit, 20),
                    self._calculate_text_edit_height(expected_edit, 20)
                )
                
                # Вычисляем реальную высоту текста
                action_doc_height = action_edit.document().size().height()
                action_margins = action_edit.contentsMargins()
                action_real_height = action_doc_height + action_margins.top() + action_margins.bottom() + 10
                
                expected_doc_height = expected_edit.document().size().height()
                expected_margins = expected_edit.contentsMargins()
                expected_real_height = expected_doc_height + expected_margins.top() + expected_margins.bottom() + 10
                
                # Вычисляем минимальную высоту (1 строка)
                min_text_height = max(
                    self._calculate_text_edit_height(action_edit, 1),
                    self._calculate_text_edit_height(expected_edit, 1)
                )
                
                # Применяем ограничение в 20 строк для каждого QTextEdit
                # Если текст превышает 20 строк, устанавливаем максимальную высоту и включаем скролл
                if action_real_height > max_text_height_20_lines:
                    action_edit.setMinimumHeight(min_text_height)
                    action_edit.setMaximumHeight(max_text_height_20_lines)
                    action_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    action_height = max_text_height_20_lines
                else:
                    action_edit.setMinimumHeight(min_text_height)
                    action_edit.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX - убираем ограничение
                    action_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                    action_height = action_real_height
                
                if expected_real_height > max_text_height_20_lines:
                    expected_edit.setMinimumHeight(min_text_height)
                    expected_edit.setMaximumHeight(max_text_height_20_lines)
                    expected_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    expected_height = max_text_height_20_lines
                else:
                    expected_edit.setMinimumHeight(min_text_height)
                    expected_edit.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX - убираем ограничение
                    expected_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                    expected_height = expected_real_height
                
                text_height = max(action_height, expected_height)
                
                # Вычисляем высоту виджета действий (колонка 4) - виден в режиме редактирования
                actions_widget_height = 0
                if actions_widget and not self.steps_table.isColumnHidden(4):
                    actions_widget_height = self._calculate_widget_height(actions_widget)
                    # В режиме редактирования: 6 кнопок по 24px + spacing + margins
                    if actions_widget_height <= 0:
                        actions_widget_height = 6 * 24 + 5 * 2 + 2 * 2  # 158px fallback
                
                # Вычисляем высоту виджета статусов (колонка 3) - виден в режиме запуска тестов
                status_widget_height = 0
                if status_widget and not self.steps_table.isColumnHidden(3):
                    status_widget_height = self._calculate_widget_height(status_widget)
                    # В режиме запуска тестов: 3 кнопки по 24px + spacing + margins
                    if status_widget_height <= 0:
                        status_widget_height = 3 * 24 + 2 * 2 + 2 * 2  # 80px fallback
                
                # Берем максимальную высоту из всех элементов строки
                min_height = 50
                max_height = max(text_height, actions_widget_height, status_widget_height, min_height)
                
                # Устанавливаем высоту строки на основе содержимого
                self.steps_table.setRowHeight(row, int(max_height))
            else:
                # Если виджеты еще не созданы, используем стандартный метод
                self.steps_table.resizeRowToContents(row)
        
        # Также обновляем ширину колонки с номером
        self.steps_table.resizeColumnToContents(0)
    

    # Сигналы
    test_case_saved = pyqtSignal()
    unsaved_changes_state = pyqtSignal(bool)
    before_save = pyqtSignal(object)  # Сигнал перед сохранением с передачей тест-кейса
    
    def __init__(self, service: TestCaseService, parent=None):
        super().__init__(parent)
        self.service = service
        self.current_test_case = None
        self.has_unsaved_changes = False
        self._is_loading = False
        self._edit_mode_enabled = True
        self._run_mode_enabled = False
        self.step_statuses: List[str] = []
        self._step_attachments: List[List[str]] = []  # Список attachments для каждого шага
        self._skip_reasons: List[str] = ['Автотесты', 'Нагрузочное тестирование', 'Другое']  # Значения по умолчанию
        
        # Загружаем маппинг иконок
        self._icon_mapping = self._load_icon_mapping()
    
    def _load_icon_mapping(self) -> Dict[str, Dict[str, str]]:
        """Загрузить маппинг иконок из JSON файла."""
        # Определяем путь к файлу маппинга относительно корня проекта
        project_root = Path(__file__).parent.parent.parent.parent
        mapping_file = project_root / "icons" / "icon_mapping.json"
        
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Поддерживаем как старый формат (плоский), так и новый (с секциями)
                    if isinstance(data, dict) and any(key in data for key in ['panels', 'context_menu', 'panel_buttons', 'status_icons', 'bulk_operations', 'step_actions']):
                        return data
                    else:
                        # Старый формат - возвращаем с секциями
                        return {
                            'panels': data if isinstance(data, dict) else {},
                            'context_menu': {},
                            'panel_buttons': {},
                            'status_icons': {},
                            'bulk_operations': {},
                            'step_actions': {}
                        }
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка загрузки маппинга иконок: {e}")
        
        # Возвращаем значения по умолчанию, если файл не найден
        return {
            'panels': {},
            'context_menu': {},
            'panel_buttons': {},
            'status_icons': {
                "passed": "check-circle.svg",
                "failed": "x-circle.svg",
                "skipped": "skip-forward.svg"
            },
            'bulk_operations': {
                "mark_all_passed": "fast-forward.svg",
                "reset_statuses": "refresh-ccw.svg"
            },
            'step_actions': {
                "attach_file": "file.svg",
                "add_above": "corner-up-left.svg",
                "add_below": "corner-down-left.svg",
                "move_up": "chevron-up.svg",
                "move_down": "chevron-down.svg",
                "delete": "x.svg"
            }
        }

    def _get_status_icon(self, status: str) -> Optional[str]:
        """Получить имя файла иконки для статуса по ключу."""
        status_icons_mapping = self._icon_mapping.get('status_icons', {})
        return status_icons_mapping.get(status)

    def _get_bulk_operation_icon(self, icon_key: str) -> Optional[str]:
        """Получить имя файла иконки для массовых операций по ключу."""
        bulk_operations_mapping = self._icon_mapping.get('bulk_operations', {})
        return bulk_operations_mapping.get(icon_key)

    def _get_step_action_icon(self, icon_key: str) -> Optional[str]:
        """Получить имя файла иконки для действий со шагами по ключу."""
        step_actions_mapping = self._icon_mapping.get('step_actions', {})
        return step_actions_mapping.get(icon_key)

    def _load_svg_icon(self, icon_name: str, size: int = 16, color: Optional[str] = None) -> Optional[QIcon]:
        """Загрузить SVG иконку из файла и вернуть QIcon.
        
        Args:
            icon_name: Имя файла иконки (например, "check-circle.svg")
            size: Размер иконки в пикселях
            color: Цвет иконки в формате "#RRGGBB" или None для использования цвета по умолчанию
        """
        # Определяем путь к папке с иконками относительно корня проекта
        project_root = Path(__file__).parent.parent.parent.parent
        icon_path = project_root / "icons" / icon_name
        
        if not icon_path.exists():
            print(f"Иконка не найдена: {icon_path}")
            return None
        
        try:
            # Читаем содержимое SVG файла
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # Если указан цвет, заменяем currentColor на конкретный цвет
            if color:
                svg_content = svg_content.replace('currentColor', color)
                svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{color}"')
                svg_content = svg_content.replace('fill="currentColor"', f'fill="{color}"')
            
            # Создаем рендерер SVG из модифицированного содержимого
            renderer = QSvgRenderer(svg_content.encode('utf-8'))
            if not renderer.isValid():
                print(f"Невалидный SVG файл: {icon_path}")
                return None
            
            # Создаем пиксмап нужного размера
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            # Рендерим SVG на пиксмап
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            renderer.render(painter)
            painter.end()
            
            # Создаем иконку из пиксмапа
            icon = QIcon(pixmap)
            return icon
        except Exception as e:
            print(f"Ошибка загрузки иконки {icon_name}: {e}")
            return None
    
    def set_skip_reasons(self, reasons: List[str]):
        """Установить список причин пропуска из настроек"""
        if reasons and isinstance(reasons, list):
            self._skip_reasons = reasons

        self.setup_ui()

    def _init_auto_resizing_text_edit(self, text_edit: QTextEdit, *, min_lines: int = 3, max_lines: int = 12):
        """Настроить QTextEdit так, чтобы он подстраивал высоту под содержимое."""
        text_edit.setWordWrapMode(QTextOption.WordWrap)
        text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        min_height = self._calculate_text_edit_height(text_edit, min_lines)
        max_height = self._calculate_text_edit_height(text_edit, max_lines)
        text_edit.setMinimumHeight(min_height)
        text_edit.setMaximumHeight(max_height)

        def _resize():
            self._auto_resize_text_edit(text_edit, min_height, max_height)

        text_edit.textChanged.connect(_resize)
        QTimer.singleShot(0, _resize)

    @staticmethod
    def _calculate_text_edit_height(text_edit: QTextEdit, lines: int) -> int:
        metrics = text_edit.fontMetrics()
        line_height = metrics.lineSpacing()
        margins = text_edit.contentsMargins()
        doc_margin = text_edit.document().documentMargin()
        return int(lines * line_height + doc_margin * 2 + margins.top() + margins.bottom() + 8)

    @staticmethod
    def _auto_resize_text_edit(text_edit: QTextEdit, min_height: int, max_height: int):
        doc = text_edit.document()
        margins = text_edit.contentsMargins()
        doc_height = doc.size().height() + doc.documentMargin() * 2 + margins.top() + margins.bottom() + 6
        new_height = max(min_height, min(max_height, int(doc_height)))
        if text_edit.height() != new_height:
            text_edit.setFixedHeight(new_height)
    
    def setup_ui(self):
        """Настройка UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(UI_METRICS.base_spacing)
        
        # Scrollable форма
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(UI_METRICS.section_spacing)
        form_layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        
        # Название тест-кейса
        self.title_group = self._create_title_group()
        form_layout.addWidget(self.title_group)

        # Предусловия
        self.precond_group = self._create_precondition_group()
        form_layout.addWidget(self.precond_group)

        # Массовые операции (только в режиме запуска тестов)
        self.bulk_operations_group = self._create_bulk_operations_group()
        self.bulk_operations_group.setVisible(False)
        form_layout.addWidget(self.bulk_operations_group)

        # Шаги тестирования (раскрывающийся блок)
        self.steps_group = self._create_steps_group()
        self.steps_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.steps_group.set_toggle_callback(self._on_steps_group_toggle)
        form_layout.addWidget(self.steps_group, 1)
        
        # Сохраняем ссылку на form_layout для управления видимостью
        self.form_layout = form_layout
        
        form_layout.addStretch()

        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
        self.scroll_area = scroll  # Сохраняем ссылку для прокрутки

    def _create_main_info_group(self) -> QGroupBox:
        group = QGroupBox("Основная информация")
        layout = QVBoxLayout(group)
        layout.setSpacing(UI_METRICS.base_spacing)
        layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.group_title_spacing,  # Отступ сверху для заголовка
            UI_METRICS.container_padding,
            UI_METRICS.base_spacing,
        )

        info_line = QHBoxLayout()
        self.id_label = QLabel("ID: -")
        self.created_label = QLabel("Создан: -")
        self.updated_label = QLabel("Обновлён: -")
        for widget in (self.id_label, self.created_label, self.updated_label):
            info_line.addWidget(widget)
            info_line.addStretch(1)
        layout.addLayout(info_line)

        people_row = QHBoxLayout()
        people_row.setSpacing(UI_METRICS.base_spacing)
        self.author_input = self._create_line_edit()
        self._add_labeled_widget(people_row, "Автор:", self.author_input)

        self.owner_input = self._create_line_edit()
        self._add_labeled_widget(people_row, "Исполнитель:", self.owner_input)

        self.reviewer_input = self._create_line_edit()
        self._add_labeled_widget(people_row, "Ревьюер:", self.reviewer_input)
        layout.addLayout(people_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(UI_METRICS.base_spacing)
        self.status_input = _NoWheelComboBox()
        self.status_input.addItems(["Draft", "Design", "Review", "Done"])
        self.status_input.setEditable(True)
        self.status_input.currentTextChanged.connect(self._mark_changed)
        self._add_labeled_widget(status_row, "Статус:", self.status_input)

        self.test_layer_input = _NoWheelComboBox()
        self.test_layer_input.addItems(["Unit", "Component", "API", "UI", "E2E", "Integration"])
        self.test_layer_input.setEditable(True)
        self.test_layer_input.currentTextChanged.connect(self._mark_changed)
        self._add_labeled_widget(status_row, "Test Layer:", self.test_layer_input)

        self.test_type_input = _NoWheelComboBox()
        self.test_type_input.addItems(["manual", "automated", "hybrid"])
        self.test_type_input.setEditable(True)
        self.test_type_input.currentTextChanged.connect(self._mark_changed)
        self._add_labeled_widget(status_row, "Тип теста:", self.test_type_input)
        layout.addLayout(status_row)

        quality_row = QHBoxLayout()
        quality_row.setSpacing(UI_METRICS.base_spacing)
        self.severity_input = _NoWheelComboBox()
        self.severity_input.addItems(["BLOCKER", "CRITICAL", "MAJOR", "NORMAL", "MINOR"])
        self.severity_input.setEditable(True)
        self.severity_input.currentTextChanged.connect(self._mark_changed)
        self._add_labeled_widget(quality_row, "Severity:", self.severity_input)

        self.priority_input = _NoWheelComboBox()
        self.priority_input.addItems(["HIGHEST", "HIGH", "MEDIUM", "LOW", "LOWEST"])
        self.priority_input.setEditable(True)
        self.priority_input.currentTextChanged.connect(self._mark_changed)
        self._add_labeled_widget(quality_row, "Priority:", self.priority_input)
        layout.addLayout(quality_row)

        environment_row = QHBoxLayout()
        environment_row.setSpacing(UI_METRICS.base_spacing)
        self.environment_input = self._create_line_edit()
        self._add_labeled_widget(environment_row, "Окружение:", self.environment_input)

        self.browser_input = self._create_line_edit()
        self._add_labeled_widget(environment_row, "Браузер:", self.browser_input)
        layout.addLayout(environment_row)

        links_row = QHBoxLayout()
        links_row.setSpacing(UI_METRICS.base_spacing)
        self.test_case_id_input = self._create_line_edit()
        self._add_labeled_widget(links_row, "Test Case ID:", self.test_case_id_input)

        self.issue_links_input = self._create_line_edit()
        self._add_labeled_widget(links_row, "Issue Links:", self.issue_links_input)

        self.test_case_links_input = self._create_line_edit()
        self._add_labeled_widget(links_row, "TC Links:", self.test_case_links_input)
        layout.addLayout(links_row)

        return group

    def _create_tags_group(self) -> QGroupBox:
        group = QGroupBox("Теги")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, UI_METRICS.group_title_spacing, 10, 8)  # Отступ сверху для заголовка
        layout.setSpacing(6)

        self.tags_input = QTextEdit()
        self.tags_input.setPlaceholderText("Введите теги, каждый с новой строки")
        self.tags_input.textChanged.connect(self._mark_changed)
        self._init_auto_resizing_text_edit(self.tags_input, min_lines=2, max_lines=10)
        layout.addWidget(self.tags_input)
        return group

    def _create_description_group(self) -> QGroupBox:
        group = QGroupBox("Описание")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, UI_METRICS.group_title_spacing, 10, 8)  # Отступ сверху для заголовка
        layout.setSpacing(6)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Подробное описание тест-кейса")
        self.description_input.textChanged.connect(self._mark_changed)
        self._init_auto_resizing_text_edit(self.description_input, min_lines=4, max_lines=12)
        layout.addWidget(self.description_input)
        return group

    def _create_domain_group(self) -> QGroupBox:
        group = QGroupBox("Контекст (epic / feature / story / component)")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(10, UI_METRICS.group_title_spacing, 10, 8)  # Отступ сверху для заголовка
        layout.setSpacing(12)

        self.epic_input = self._create_line_edit()
        self.epic_input.setPlaceholderText("Epic")
        self._add_labeled_widget(layout, "Epic:", self.epic_input)

        self.feature_input = self._create_line_edit()
        self.feature_input.setPlaceholderText("Feature")
        self._add_labeled_widget(layout, "Feature:", self.feature_input)

        self.story_input = self._create_line_edit()
        self.story_input.setPlaceholderText("Story")
        self._add_labeled_widget(layout, "Story:", self.story_input)

        self.component_input = self._create_line_edit()
        self.component_input.setPlaceholderText("Component")
        self._add_labeled_widget(layout, "Component:", self.component_input)

        return group
    
    def _create_title_group(self) -> QGroupBox:
        """Группа названия тест-кейса"""
        group = QGroupBox("Название")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, UI_METRICS.group_title_spacing, 0, 0)  # Отступ сверху для заголовка
        
        self.title_edit = self._create_line_edit()
        self.title_edit.setPlaceholderText("Название тест-кейса")
        layout.addWidget(self.title_edit)
        
        group.setLayout(layout)
        return group
    
    def _create_precondition_group(self) -> QGroupBox:
        """Группа предусловий"""
        group = QGroupBox("Предусловия")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, UI_METRICS.group_title_spacing, 0, 0)  # Отступ сверху для заголовка
        
        self.precondition_input = QTextEdit()
        self.precondition_input.setPlaceholderText("Предусловия для выполнения тест-кейса")
        self.precondition_input.textChanged.connect(self._mark_changed)
        self._init_auto_resizing_text_edit(self.precondition_input, min_lines=3, max_lines=10)
        layout.addWidget(self.precondition_input)
        
        group.setLayout(layout)
        return group

    def _create_bulk_operations_group(self) -> QGroupBox:
        """Группа массовых операций по шагам тест-кейса (только в режиме запуска тестов)"""
        group = QGroupBox("Массовые операции")
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, UI_METRICS.group_title_spacing, 0, 0)
        
        # Статистика по шагам
        self.stats_label = QLabel("Статистика по шагам")
        self.stats_label.setStyleSheet("padding: 8px; background-color: rgba(255, 255, 255, 0.05); border-radius: 4px; font-size: 12px;")
        self.stats_label.setWordWrap(True)
        main_layout.addWidget(self.stats_label)
        
        # Кнопки операций
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 8, 0, 0)
        
        # Кнопка "Все пройдено"
        self.mark_all_passed_btn = QPushButton("Все пройдено")
        # Загружаем иконку из маппинга (зеленый цвет для passed)
        icon_name = self._get_bulk_operation_icon("mark_all_passed")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=16, color="#2ecc71")
            if icon:
                self.mark_all_passed_btn.setIcon(icon)
                self.mark_all_passed_btn.setIconSize(QSize(16, 16))
        self.mark_all_passed_btn.setToolTip("Отметить все шаги как пройденные")
        self.mark_all_passed_btn.clicked.connect(self._mark_all_steps_passed)
        buttons_layout.addWidget(self.mark_all_passed_btn)
        
        # Кнопка "Сброс статусов"
        self.reset_statuses_btn = QPushButton("Сброс статусов")
        # Загружаем иконку из маппинга
        icon_name = self._get_bulk_operation_icon("reset_statuses")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            if icon:
                self.reset_statuses_btn.setIcon(icon)
                self.reset_statuses_btn.setIconSize(QSize(16, 16))
        self.reset_statuses_btn.setToolTip("Сбросить статусы всех шагов выбранного тест-кейса")
        self.reset_statuses_btn.clicked.connect(self._reset_all_step_statuses)
        buttons_layout.addWidget(self.reset_statuses_btn)
        
        buttons_layout.addStretch()
        main_layout.addLayout(buttons_layout)
        
        group.setLayout(main_layout)
        return group

    def _create_expected_result_group(self) -> QGroupBox:
        group = QGroupBox("Общий ожидаемый результат")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, UI_METRICS.group_title_spacing, 0, 0)  # Отступ сверху для заголовка

        self.expected_result_input = QTextEdit()
        self.expected_result_input.setPlaceholderText("Что должно получиться по завершении кейса")
        self.expected_result_input.textChanged.connect(self._mark_changed)
        self._init_auto_resizing_text_edit(self.expected_result_input, min_lines=3, max_lines=10)
        layout.addWidget(self.expected_result_input)

        group.setLayout(layout)
        return group

    def _create_line_edit(self) -> QLineEdit:
        edit = QLineEdit()
        edit.textChanged.connect(self._mark_changed)
        return edit

    def _add_labeled_widget(self, parent_layout: QHBoxLayout, label_text: str, widget):
        container = QVBoxLayout()
        label = QLabel(label_text)
        container.addWidget(label)
        container.addWidget(widget)
        parent_layout.addLayout(container)
        return widget


    def _set_combo_value(self, combo: QComboBox, value: str):
        combo.blockSignals(True)
        if value:
            idx = combo.findText(value)
            if idx == -1:
                combo.addItem(value)
                idx = combo.findText(value)
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)
    
    def _create_steps_group(self) -> _ExpandableGroupBox:
        """Группа шагов тестирования в формате TestOps - единая таблица"""
        group = _ExpandableGroupBox("Шаги тестирования")
        layout = QVBoxLayout()
        layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.group_title_spacing,  # Отступ сверху для заголовка
            UI_METRICS.container_padding,
            UI_METRICS.base_spacing,
        )
        layout.setSpacing(UI_METRICS.base_spacing)

        # Таблица шагов в стиле TestOps
        self.steps_table = _StepsTableWidget(self)  # 5 колонок: №, Действие, Ожидаемый результат, Статус, Действия
        self.steps_table.setColumnCount(5)
        
        # Убираем заголовки таблицы
        self.steps_table.horizontalHeader().setVisible(False)
        
        # Настройка колонок
        self.steps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # № - автоматическая ширина
        self.steps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # Действие - растягивается
        self.steps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # Ожидаемый результат - растягивается
        self.steps_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)  # Статус - фиксированная
        self.steps_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)  # Действия - фиксированная
        
        # Устанавливаем минимальную ширину для колонки с номером
        self.steps_table.horizontalHeader().setMinimumSectionSize(30)  # Минимальная ширина для всех колонок
        self.steps_table.setColumnWidth(0, 40)   # № - начальная ширина (будет автоматически подстраиваться)
        self.steps_table.setColumnWidth(3, 60)   # Статус (уменьшено для вертикальных кнопок)
        self.steps_table.setColumnWidth(4, 60)   # Действия (уменьшено для вертикальных кнопок)
        
        # Настройка вертикального заголовка для индивидуальной высоты строк
        self.steps_table.verticalHeader().setVisible(False)
        # Используем Interactive вместо ResizeToContents, чтобы каждая строка могла иметь свою высоту
        # ResizeToContents может синхронизировать высоты всех строк, делая их одинаковыми
        # uniformRowHeights по умолчанию False в QTableWidget, что позволяет разную высоту строк
        self.steps_table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.steps_table.verticalHeader().setMinimumSectionSize(50)
        
        # Настройка таблицы
        self.steps_table.setShowGrid(True)
        self.steps_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.steps_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.steps_table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # Редактирование через виджеты
        # Убираем чередующиеся цвета строк - единый стиль для всей таблицы
        self.steps_table.setAlternatingRowColors(False)
        
        # Подключение сигналов
        self.steps_table.itemSelectionChanged.connect(self._update_step_controls_state)
        self.steps_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.steps_table.customContextMenuRequested.connect(self._show_steps_context_menu)
        
        # Подключаем сигнал drop файлов
        self.steps_table.files_dropped_on_row.connect(self._on_files_dropped_on_step)
        
        # Устанавливаем видимость колонок по умолчанию (режим редактирования)
        # В режиме редактирования: скрыть статусы (колонка 3), показать действия (колонка 4)
        self.steps_table.setColumnHidden(3, True)  # Статусы скрыты по умолчанию (режим редактирования)
        self.steps_table.setColumnHidden(4, False)  # Действия видны по умолчанию (режим редактирования)
        
        layout.addWidget(self.steps_table)
        
        group.setLayout(layout)
        return group
    
    def _on_steps_group_toggle(self, is_expanded: bool):
        """Обработчик переключения состояния блока 'Шаги тестирования'."""
        if not hasattr(self, 'form_layout') or not hasattr(self, 'title_group'):
            return
        
        if is_expanded:
            # Раскрываем: скрываем другие блоки, растягиваем steps_group на всю высоту
            self.title_group.setVisible(False)
            self.precond_group.setVisible(False)
            # bulk_operations_group скрываем только если не в режиме запуска тестов
            # В режиме запуска тестов она должна оставаться видимой
            if hasattr(self, 'bulk_operations_group'):
                self.bulk_operations_group.setVisible(False)
            
            # Увеличиваем stretch factor для steps_group, чтобы он занял всё доступное пространство
            self.form_layout.setStretchFactor(self.steps_group, 10)
        else:
            # Сворачиваем: показываем все блоки, возвращаем исходный stretch factor
            self.title_group.setVisible(True)
            self.precond_group.setVisible(True)
            # bulk_operations_group показываем только в режиме запуска тестов
            if hasattr(self, 'bulk_operations_group'):
                self.bulk_operations_group.setVisible(getattr(self, '_run_mode_enabled', False))
            
            # Возвращаем исходный stretch factor
            self.form_layout.setStretchFactor(self.steps_group, 1)
    
    def load_test_case(self, test_case: TestCase):
        """Загрузить тест-кейс в форму"""
        self._is_loading = True
        self.current_test_case = test_case
        self.has_unsaved_changes = False

        if test_case:
            self.title_edit.blockSignals(True)
            self.title_edit.setText(test_case.name or "")
            self.title_edit.blockSignals(False)

            self.precondition_input.blockSignals(True)
            self.precondition_input.setText(test_case.preconditions or "")
            self.precondition_input.blockSignals(False)

            self.steps_table.blockSignals(True)
            self.steps_table.setRowCount(0)
            self.step_statuses = []
            # Сохраняем attachments из шагов при загрузке
            self._step_attachments = []
            for step in test_case.steps:
                step_attachments = list(step.attachments) if step.attachments else []
                self._add_step(
                    step.description, 
                    step.expected_result, 
                    step.status or "pending",
                    attachments=step_attachments
                )
            self.steps_table.blockSignals(False)
            self.steps_table.clearSelection()
            self._refresh_step_indices()
            self._update_table_row_heights()
        else:
            self.title_edit.blockSignals(True)
            self.title_edit.setText("Не выбран тест-кейс")
            self.title_edit.blockSignals(False)
            self.precondition_input.clear()
            self.steps_table.setRowCount(0)
            self.step_statuses = []
            self._step_attachments = []
            self._update_table_row_heights()

        self._is_loading = False
        self.unsaved_changes_state.emit(False)
        self._update_step_controls_state()
        self._update_statistics()  # Обновляем статистику при загрузке тест-кейса
    
    def _create_step_control_button(self, text: str, tooltip: str) -> QToolButton:
        """Создает кнопку панели управления шагами."""
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setAutoRaise(True)
        btn.setMinimumHeight(max(32, UI_METRICS.control_min_height - 6))
        btn.setMinimumWidth(max(32, UI_METRICS.control_min_width))
        return btn

    def _show_steps_context_menu(self, pos):
        if not self._edit_mode_enabled:
            return
        row = self.steps_table.indexAt(pos).row()
        if row != -1:
            self.steps_table.selectRow(row)

        menu = QMenu(self)
        actions = {
            "add_new": menu.addAction("➕ Добавить новый шаг"),
            "insert_above": menu.addAction("↑ Вставить шаг выше"),
            "insert_below": menu.addAction("↓ Вставить шаг ниже"),
            "move_up": menu.addAction("⇡ Переместить наверх"),
            "move_down": menu.addAction("⇣ Переместить вниз"),
            "remove": menu.addAction("✕ Удалить"),
        }

        if row == -1:
            for key in ("insert_above", "insert_below", "move_up", "move_down", "remove"):
                actions[key].setEnabled(False)
        else:
            actions["move_up"].setEnabled(row > 0)
            actions["move_down"].setEnabled(row < self.steps_table.rowCount() - 1)

        action = menu.exec_(self.steps_table.mapToGlobal(pos))
        if not action:
            return

        if action == actions["add_new"]:
            self._add_step_to_end()
        elif action == actions["insert_above"]:
            self._insert_step_above()
        elif action == actions["insert_below"]:
            self._insert_step_below()
        elif action == actions["move_up"]:
            self._move_step_up()
        elif action == actions["move_down"]:
            self._move_step_down()
        elif action == actions["remove"]:
            self._remove_step()

    def _add_step(self, step_text="", expected_text="", status="pending", row=None, attachments=None):
        """Добавить шаг в таблицу."""
        if row is None or row >= self.steps_table.rowCount():
            row = self.steps_table.rowCount()
            self.steps_table.insertRow(row)
        else:
            self.steps_table.insertRow(row)
        
        # Колонка 0: № (номер шага)
        index_item = QTableWidgetItem(str(row + 1))
        index_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        index_item.setFlags(Qt.ItemIsEnabled)  # Не редактируется
        self.steps_table.setItem(row, 0, index_item)
        
        # Колонка 1: Действие
        action_edit = self._create_step_text_edit("Действие...")
        action_edit.blockSignals(True)
        action_edit.setPlainText(step_text or "")
        action_edit.setReadOnly(not self._edit_mode_enabled)
        action_edit.blockSignals(False)
        self.steps_table.setCellWidget(row, 1, action_edit)
        
        # Колонка 2: Ожидаемый результат
        expected_edit = self._create_step_text_edit("Ожидаемый результат...")
        expected_edit.blockSignals(True)
        expected_edit.setPlainText(expected_text or "")
        expected_edit.setReadOnly(not self._edit_mode_enabled)
        expected_edit.blockSignals(False)
        self.steps_table.setCellWidget(row, 2, expected_edit)
        
        # Колонка 3: Статус
        status_widget = self._create_step_status_widget(row)
        self.steps_table.setCellWidget(row, 3, status_widget)
        
        # Колонка 4: Действия (кнопки управления)
        actions_widget = self._create_step_actions_widget(row)
        self.steps_table.setCellWidget(row, 4, actions_widget)
        
        # Сохраняем статус
        self.step_statuses.insert(row, status or "pending")
        
        # Сохраняем attachments
        if attachments is None:
            attachments = []
        self._step_attachments.insert(row, list(attachments) if attachments else [])
        
        # Обновляем статус виджета
        self._update_step_status_widget(row, status or "pending")
        
        # Обновляем индексы и высоты строк
        self._refresh_step_indices()
        self._update_table_row_heights()
        self._update_step_controls_state()
        
        if not self._is_loading:
            self._mark_changed()
        
        return row

    def _add_step_to_end(self):
        """Добавить шаг в конец."""
        new_row = self._add_step()
        self.steps_table.selectRow(new_row)
        self._scroll_to_step_and_focus(new_row)

    def _insert_step_above(self, row=None):
        """Добавить шаг выше выбранного или указанной строки."""
        if row is None:
            row = self.steps_table.currentRow()
        if row < 0:
            self._add_step_to_end()
            return
        new_row = self._add_step(row=row)
        self.steps_table.selectRow(new_row)
        self._scroll_to_step_and_focus(new_row)

    def _insert_step_below(self, row=None):
        """Добавить шаг ниже выбранного или указанной строки."""
        if row is None:
            row = self.steps_table.currentRow()
        insert_row = row + 1 if row >= 0 else self.steps_table.rowCount()
        new_row = self._add_step(row=insert_row)
        self.steps_table.selectRow(new_row)
        self._scroll_to_step_and_focus(new_row)

    def _move_step_up(self, row=None):
        """Переместить шаг выше."""
        if row is None:
            row = self.steps_table.currentRow()
        if row <= 0:
            return
        self._swap_step_rows(row, row - 1)
        self.steps_table.selectRow(row - 1)
        self._mark_changed()
        self._update_step_controls_state()

    def _move_step_down(self, row=None):
        """Переместить шаг ниже."""
        if row is None:
            row = self.steps_table.currentRow()
        if row < 0 or row >= self.steps_table.rowCount() - 1:
            return
        self._swap_step_rows(row, row + 1)
        self.steps_table.selectRow(row + 1)
        self._mark_changed()
        self._update_step_controls_state()
    
    def _remove_step_by_row(self, row: int):
        """Удалить шаг по номеру строки."""
        if row < 0 or row >= self.steps_table.rowCount():
            return
        self.steps_table.removeRow(row)
        if row < len(self.step_statuses):
            self.step_statuses.pop(row)
        if row < len(self._step_attachments):
            self._step_attachments.pop(row)
        self._refresh_step_indices()
        self._update_table_row_heights()
        if not self._is_loading:
            self._mark_changed()
        self._update_step_controls_state()

    def _swap_step_rows(self, row_a: int, row_b: int):
        """Поменять местами строки шагов."""
        if not (0 <= row_a < self.steps_table.rowCount() and 0 <= row_b < self.steps_table.rowCount()):
            return
        
        # Получаем содержимое ячеек
        action_edit_a = self.steps_table.cellWidget(row_a, 1)
        expected_edit_a = self.steps_table.cellWidget(row_a, 2)
        action_edit_b = self.steps_table.cellWidget(row_b, 1)
        expected_edit_b = self.steps_table.cellWidget(row_b, 2)
        
        if not all([action_edit_a, expected_edit_a, action_edit_b, expected_edit_b]):
            return
        
        # Сохраняем содержимое
        action_a = action_edit_a.toPlainText()
        expected_a = expected_edit_a.toPlainText()
        action_b = action_edit_b.toPlainText()
        expected_b = expected_edit_b.toPlainText()
        status_a = self.step_statuses[row_a] if row_a < len(self.step_statuses) else "pending"
        status_b = self.step_statuses[row_b] if row_b < len(self.step_statuses) else "pending"
        
        # Меняем местами
        action_edit_a.blockSignals(True)
        expected_edit_a.blockSignals(True)
        action_edit_b.blockSignals(True)
        expected_edit_b.blockSignals(True)
        
        action_edit_a.setPlainText(action_b)
        expected_edit_a.setPlainText(expected_b)
        action_edit_b.setPlainText(action_a)
        expected_edit_b.setPlainText(expected_a)
        
        action_edit_a.blockSignals(False)
        expected_edit_a.blockSignals(False)
        action_edit_b.blockSignals(False)
        expected_edit_b.blockSignals(False)
        
        # Меняем статусы местами
        if row_a < len(self.step_statuses) and row_b < len(self.step_statuses):
            self.step_statuses[row_a], self.step_statuses[row_b] = (
                self.step_statuses[row_b],
                self.step_statuses[row_a],
            )
            self._update_step_status_widget(row_a, self.step_statuses[row_a])
            self._update_step_status_widget(row_b, self.step_statuses[row_b])
        
        # Меняем attachments местами
        if row_a < len(self._step_attachments) and row_b < len(self._step_attachments):
            self._step_attachments[row_a], self._step_attachments[row_b] = (
                self._step_attachments[row_b],
                self._step_attachments[row_a],
            )
        
        self._refresh_step_indices()
        self._update_table_row_heights()
    
    def _scroll_to_step_and_focus(self, row: int):
        """Прокрутить к шагу и установить фокус на поле 'Действия'"""
        if row < 0 or row >= self.steps_table.rowCount():
            return
        
        # Прокручиваем QScrollArea к блоку шагов
        steps_group = None
        for widget in self.findChildren(QGroupBox):
            if widget.title() == "Шаги тестирования":
                steps_group = widget
                break
        
        if steps_group and hasattr(self, 'scroll_area'):
            self._scroll_to_widget(steps_group)
        
        # Прокручиваем таблицу к нужной строке
        QTimer.singleShot(50, lambda: self.steps_table.scrollToItem(
            self.steps_table.item(row, 0), 
            QAbstractItemView.PositionAtCenter
        ))
        
        # Устанавливаем фокус на поле "Действия" с задержкой
        action_edit = self.steps_table.cellWidget(row, 1)
        if action_edit:
            QTimer.singleShot(150, lambda: action_edit.setFocus())
    
    def _scroll_to_widget(self, widget: QWidget):
        """Прокрутить QScrollArea к указанному виджету"""
        if not hasattr(self, 'scroll_area') or not self.scroll_area:
            return
        
        # Получаем координаты виджета относительно виджета внутри scroll_area
        scroll_widget = self.scroll_area.widget()
        if not scroll_widget:
            return
        
        # Получаем координаты виджета относительно scroll_widget
        widget_pos = widget.mapTo(scroll_widget, widget.rect().topLeft())
        
        # Прокручиваем с небольшим отступом сверху
        scroll_y = max(0, widget_pos.y() - 20)
        self.scroll_area.verticalScrollBar().setValue(scroll_y)
    
    def _remove_step(self):
        """Удалить выбранный шаг"""
        row = self.steps_table.currentRow()
        self._remove_step_by_row(row)

    def _update_step_controls_state(self):
        """Обновить состояние кнопок управления шагами."""
        if not self._edit_mode_enabled:
            return
        
        for row in range(self.steps_table.rowCount()):
            actions_widget = self.steps_table.cellWidget(row, 4)
            if actions_widget:
                move_up_btn = actions_widget.property("move_up_btn")
                move_down_btn = actions_widget.property("move_down_btn")
                if move_up_btn:
                    move_up_btn.setEnabled(row > 0)
                if move_down_btn:
                    move_down_btn.setEnabled(row < self.steps_table.rowCount() - 1)
    
    def _mark_changed(self):
        """Пометить как измененное"""
        if self._is_loading:
            return
        
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            self.unsaved_changes_state.emit(True)
    
    def save(self):
        """Сохранить тест-кейс"""
        if not self.current_test_case:
            return
        
        # Эмитируем сигнал перед сохранением, чтобы обновить данные из панели информации
        self.before_save.emit(self.current_test_case)
        
        # Собираем данные из формы (только название, предусловия и шаги)
        self.current_test_case.name = self.title_edit.text().strip()
        self.current_test_case.preconditions = self.precondition_input.toPlainText()
        
        # Шаги (сохраняем attachments из текущего тест-кейса, если они есть)
        steps = []
        for row in range(self.steps_table.rowCount()):
            action_edit = self.steps_table.cellWidget(row, 1)
            expected_edit = self.steps_table.cellWidget(row, 2)
            if not action_edit or not expected_edit:
                continue
            step_text = action_edit.toPlainText()
            expected_text = expected_edit.toPlainText()
            status = self.step_statuses[row] if row < len(self.step_statuses) else "pending"
            
            # Сохраняем attachments из _step_attachments (источник истины для формы)
            attachments = []
            if row < len(self._step_attachments):
                attachments = list(self._step_attachments[row])
            elif row < len(self.current_test_case.steps):
                # Если в _step_attachments нет, берем из текущего тест-кейса
                existing_step = self.current_test_case.steps[row]
                if existing_step.attachments:
                    attachments = list(existing_step.attachments)
            
            # Получаем ID шага из текущего тест-кейса, если шаг существует
            step_id = None
            if row < len(self.current_test_case.steps):
                step_id = self.current_test_case.steps[row].id
            if not step_id:
                step_id = str(uuid.uuid4())
            
            steps.append(
                TestCaseStep(
                    id=step_id,
                    name=f"Шаг {row + 1}",
                    description=step_text,
                    expected_result=expected_text,
                    status=status,
                    attachments=attachments,
                )
            )
        
        self.current_test_case.steps = steps
        
        # Обновляем время изменения
        self.current_test_case.updated_at = get_current_datetime()
        
        # Сохраняем через сервис
        if self.service.save_test_case(self.current_test_case):
            self.has_unsaved_changes = False
            self.unsaved_changes_state.emit(False)
            self.test_case_saved.emit()

    def set_edit_mode(self, enabled: bool):
        self._edit_mode_enabled = enabled
        widgets_to_toggle = [
            self.precondition_input,
            self.title_edit,
        ]
        for widget in widgets_to_toggle:
            widget.setEnabled(enabled)

        # Обновляем режим редактирования для всех шагов
        for row in range(self.steps_table.rowCount()):
            action_edit = self.steps_table.cellWidget(row, 1)
            expected_edit = self.steps_table.cellWidget(row, 2)
            if action_edit:
                action_edit.setReadOnly(not enabled)
            if expected_edit:
                expected_edit.setReadOnly(not enabled)
        
        # В режиме редактирования: скрыть колонку статусов (3), показать колонку действий (4)
        self.steps_table.setColumnHidden(3, enabled)  # Скрыть статусы в режиме редактирования
        self.steps_table.setColumnHidden(4, not enabled)  # Показать действия в режиме редактирования
        
        self._update_step_controls_state()
        # Обновляем высоту строк после изменения видимости колонок
        QTimer.singleShot(0, self._update_table_row_heights)

    def set_run_mode(self, enabled: bool):
        self._run_mode_enabled = enabled
        
        # В режиме запуска тестов: показать колонку статусов (3), скрыть колонку действий (4)
        self.steps_table.setColumnHidden(3, not enabled)  # Показать статусы в режиме запуска
        self.steps_table.setColumnHidden(4, enabled)  # Скрыть действия в режиме запуска
        
        # Показываем/скрываем группу массовых операций
        if hasattr(self, 'bulk_operations_group'):
            self.bulk_operations_group.setVisible(enabled)
            if enabled:
                self._update_statistics()  # Обновляем статистику при включении режима запуска
        
        # Включаем/выключаем кнопки статусов для всех строк
        for row in range(self.steps_table.rowCount()):
            status_widget = self.steps_table.cellWidget(row, 3)
            if status_widget:
                buttons = status_widget.property("status_buttons")
                if buttons:
                    for btn in buttons:
                        btn.setEnabled(enabled)
        
        # Обновляем высоту строк после изменения видимости колонок
        QTimer.singleShot(0, self._update_table_row_heights)

    def _refresh_step_indices(self):
        """Обновить номера шагов в колонке №."""
        for idx in range(self.steps_table.rowCount()):
            index_item = self.steps_table.item(idx, 0)
            if index_item:
                index_item.setText(str(idx + 1))
            else:
                index_item = QTableWidgetItem(str(idx + 1))
                index_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                index_item.setFlags(Qt.ItemIsEnabled)
                self.steps_table.setItem(idx, 0, index_item)
        self._update_table_row_heights()

    def _auto_save_status_change(self):
        if not self.current_test_case:
            return
        self.current_test_case.updated_at = get_current_datetime()
        if self.service.save_test_case(self.current_test_case):
            self.has_unsaved_changes = False
            self.unsaved_changes_state.emit(False)
            self.test_case_saved.emit()

    def _on_files_dropped_on_step(self, row: int, file_paths: List[Path]):
        """Обработчик drop файлов на строку шага."""
        if not self.current_test_case:
            QMessageBox.warning(
                self,
                "Нет выбранного тест-кейса",
                "Пожалуйста, сначала выберите тест-кейс для прикрепления файлов."
            )
            return
        
        if row < 0 or row >= self.steps_table.rowCount():
            return
        
        # Получаем шаг из текущего тест-кейса (нужен его id)
        if row >= len(self.current_test_case.steps):
            # Если шаг еще не сохранен, создаем временный id
            step_id = str(uuid.uuid4())
        else:
            step = self.current_test_case.steps[row]
            step_id = step.id or str(uuid.uuid4())
        
        test_case_id = self.current_test_case.id or ""
        if not test_case_id:
            QMessageBox.warning(
                self,
                "Нет ID тест-кейса",
                "Не удалось определить ID тест-кейса. Файлы не могут быть прикреплены."
            )
            return
        
        # Получаем директорию _attachment
        if not self.current_test_case._filepath:
            QMessageBox.warning(
                self,
                "Нет пути к тест-кейсу",
                "Не удалось определить путь к тест-кейсу. Файлы не могут быть прикреплены."
            )
            return
        
        test_case_dir = self.current_test_case._filepath.parent
        attachment_dir = test_case_dir / "_attachment"
        attachment_dir.mkdir(exist_ok=True)
        
        # Обрабатываем каждый файл
        for source_file in file_paths:
            if not source_file.exists() or not source_file.is_file():
                continue
            
            # Формируем новое имя: {id тест-кейса}-{id шага}_{оригинальное имя}.{расширение}
            original_name = source_file.stem  # Имя без расширения
            extension = source_file.suffix  # Расширение с точкой
            new_name = f"{test_case_id}-{step_id}_{original_name}{extension}"
            target_file = attachment_dir / new_name
            
            # Проверяем, существует ли уже такой файл
            if target_file.exists():
                # Предлагаем переименовать
                new_name_custom, ok = QInputDialog.getText(
                    self,
                    "Файл уже существует",
                    f"Файл '{new_name}' уже существует.\nВведите новое имя (без расширения):",
                    text=original_name
                )
                
                if not ok or not new_name_custom.strip():
                    continue  # Пропускаем этот файл
                
                new_name = f"{test_case_id}-{step_id}_{new_name_custom.strip()}{extension}"
                target_file = attachment_dir / new_name
                
                # Проверяем еще раз на случай, если пользователь ввел имя, которое тоже существует
                if target_file.exists():
                    QMessageBox.warning(
                        self,
                        "Файл уже существует",
                        f"Файл '{new_name}' также уже существует. Файл пропущен."
                    )
                    continue
            
            try:
                # Копируем файл
                shutil.copy2(source_file, target_file)
                
                # Сохраняем относительный путь для attachments
                try:
                    relative_path = target_file.relative_to(attachment_dir)
                    file_path_str = str(relative_path)
                except ValueError:
                    file_path_str = target_file.name
                
                # Добавляем в attachments шага
                if row >= len(self._step_attachments):
                    # Расширяем список если нужно
                    while len(self._step_attachments) <= row:
                        self._step_attachments.append([])
                
                if file_path_str not in self._step_attachments[row]:
                    self._step_attachments[row].append(file_path_str)
                
                # Обновляем attachments в текущем тест-кейсе (если шаг существует)
                if row < len(self.current_test_case.steps):
                    step = self.current_test_case.steps[row]
                    if file_path_str not in step.attachments:
                        step.attachments.append(file_path_str)
                
                # Эмитируем сигнал о прикреплении файла для обновления панели "Файлы"
                self.file_attached_to_step.emit()
                
                self._mark_changed()
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Ошибка копирования",
                    f"Не удалось скопировать файл '{source_file.name}':\n{str(e)}"
                )
    
    def _attach_file_to_step(self, row: int):
        """Обработчик клика по кнопке прикрепления файла."""
        if not self.current_test_case:
            QMessageBox.warning(
                self,
                "Нет выбранного тест-кейса",
                "Пожалуйста, сначала выберите тест-кейс для прикрепления файлов."
            )
            return
        
        if row < 0 or row >= self.steps_table.rowCount():
            return
        
        # Открываем диалог выбора файлов
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для прикрепления",
            "",
            "Все файлы (*.*)",
        )
        
        if not files:
            return
        
        # Преобразуем пути в Path объекты
        file_paths = [Path(path) for path in files]
        
        # Используем существующий метод для обработки файлов
        self._on_files_dropped_on_step(row, file_paths)
    
    def _mark_all_steps_passed(self):
        """Отметить все шаги как пройденные"""
        if not self.current_test_case:
            return
        for row in range(self.steps_table.rowCount()):
            self._on_step_status_clicked(row, "passed")
        self._auto_save_status_change()
        self._update_statistics()  # Обновляем статистику после массовой операции
    
    def _reset_all_step_statuses(self):
        """Сбросить статусы всех шагов выбранного тест-кейса"""
        if not self.current_test_case:
            return
        for row in range(self.steps_table.rowCount()):
            self._on_step_status_clicked(row, "pending")
        self._auto_save_status_change()
        self._update_statistics()  # Обновляем статистику после массовой операции
    
    def _update_statistics(self):
        """Обновить статистику по шагам в группе массовых операций"""
        if not hasattr(self, "stats_label"):
            return
        
        if not self.current_test_case or not self.current_test_case.steps:
            self.stats_label.setText("Шаги: нет данных")
            return
        
        steps = self.current_test_case.steps
        total = len(steps)
        passed = sum(1 for step in steps if step.status == "passed")
        failed = sum(1 for step in steps if step.status == "failed")
        skipped = sum(1 for step in steps if step.status == "skipped")
        pending = sum(1 for step in steps if not step.status or step.status == "pending")
        
        # Формируем текст статистики
        stats_text = f"<b>Статистика по шагам:</b><br>"
        stats_text += f"Всего: {total} | "
        stats_text += f"Пройдено: <span style='color: #6CC24A;'>{passed}</span> | "
        stats_text += f"Осталось: <span style='color: #FFA931;'>{pending}</span> | "
        stats_text += f"Не пройдено: <span style='color: #F5555D;'>{failed + skipped}</span>"
        self.stats_label.setText(stats_text)


