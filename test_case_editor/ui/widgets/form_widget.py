"""Виджет формы редактирования тест-кейса"""

from pathlib import Path
from typing import List, Optional
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
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QSize, QTimer
from PyQt5.QtGui import QFont, QTextOption, QIcon, QPixmap, QPainter, QColor, QDragEnterEvent, QDropEvent, QDragLeaveEvent

from ...models.test_case import TestCase, TestCaseStep
from ...services.test_case_service import TestCaseService
from ...utils.datetime_utils import format_datetime, get_current_datetime
from ..styles.ui_metrics import UI_METRICS


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
                ("passed", "✓", "#2ecc71"),
                ("failed", "✕", "#e74c3c"),
                ("skipped", "S", "#95a5a6"),
            ]
        for value, text, color in spec:
            btn = QToolButton()
            btn.setText(text)
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
        
        # Кнопка прикрепления файла (скрепка) - первая в списке
        attach_file_btn = QToolButton()
        attach_file_btn.setText("📎")
        attach_file_btn.setToolTip("Прикрепить файл")
        attach_file_btn.setCursor(Qt.PointingHandCursor)
        attach_file_btn.setAutoRaise(True)
        attach_file_btn.setFixedSize(24, 24)
        attach_file_btn.setStyleSheet(action_button_style)
        attach_file_btn.clicked.connect(lambda: self._attach_file_to_step(row))
        layout.addWidget(attach_file_btn)
        
        add_above_btn = QToolButton()
        add_above_btn.setText("+↑")
        add_above_btn.setToolTip("Добавить шаг выше")
        add_above_btn.setCursor(Qt.PointingHandCursor)
        add_above_btn.setAutoRaise(True)
        add_above_btn.setFixedSize(24, 24)
        add_above_btn.setStyleSheet(action_button_style)
        add_above_btn.clicked.connect(lambda: self._insert_step_above(row))
        layout.addWidget(add_above_btn)
        
        add_below_btn = QToolButton()
        add_below_btn.setText("+↓")
        add_below_btn.setToolTip("Добавить шаг ниже")
        add_below_btn.setCursor(Qt.PointingHandCursor)
        add_below_btn.setAutoRaise(True)
        add_below_btn.setFixedSize(24, 24)
        add_below_btn.setStyleSheet(action_button_style)
        add_below_btn.clicked.connect(lambda: self._insert_step_below(row))
        layout.addWidget(add_below_btn)
        
        move_up_btn = QToolButton()
        move_up_btn.setText("↑")
        move_up_btn.setToolTip("Переместить вверх")
        move_up_btn.setCursor(Qt.PointingHandCursor)
        move_up_btn.setAutoRaise(True)
        move_up_btn.setFixedSize(24, 24)
        move_up_btn.setStyleSheet(action_button_style)
        move_up_btn.clicked.connect(lambda: self._move_step_up(row))
        layout.addWidget(move_up_btn)
        
        move_down_btn = QToolButton()
        move_down_btn.setText("↓")
        move_down_btn.setToolTip("Переместить вниз")
        move_down_btn.setCursor(Qt.PointingHandCursor)
        move_down_btn.setAutoRaise(True)
        move_down_btn.setFixedSize(24, 24)
        move_down_btn.setStyleSheet(action_button_style)
        move_down_btn.clicked.connect(lambda: self._move_step_down(row))
        layout.addWidget(move_down_btn)
        
        remove_btn = QToolButton()
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
    
    def _on_step_status_clicked(self, row: int, status: str):
        """Обработчик клика по статусу шага."""
        if row < 0 or row >= len(self.step_statuses):
            return
        if self.step_statuses[row] == status:
            return
        self.step_statuses[row] = status
        self._update_step_status_widget(row, status)
        if self.current_test_case and row < len(self.current_test_case.steps):
            self.current_test_case.steps[row].status = status
            self._auto_save_status_change()
    
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
            if is_active:
                    btn.setStyleSheet(
                        f"""
                        QToolButton {{
                            background-color: {color};
                            color: #0f1117;
                        border-radius: 4px;
                        font-weight: 600;
                        padding: 0px;
                        min-width: 24px;
                        max-width: 24px;
                        min-height: 24px;
                        max-height: 24px;
                        font-size: 12px;
                        }}
                    """
                )
            else:
                btn.setStyleSheet(
                        f"""
                        QToolButton {{
                            border: 1px solid {color};
                            color: {color};
                        border-radius: 4px;
                        padding: 0px;
                        min-width: 24px;
                        max-width: 24px;
                        min-height: 24px;
                        max-height: 24px;
                        font-size: 12px;
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
    
    def _update_table_row_heights(self):
        """Обновить высоты всех строк таблицы."""
        for row in range(self.steps_table.rowCount()):
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
        title_group = self._create_title_group()
        form_layout.addWidget(title_group)

        # Предусловия
        precond_group = self._create_precondition_group()
        form_layout.addWidget(precond_group)

        # Шаги тестирования
        steps_group = self._create_steps_group()
        steps_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        form_layout.addWidget(steps_group, 1)
        
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
        self._add_labeled_widget(people_row, "Владелец:", self.owner_input)

        self.reviewer_input = self._create_line_edit()
        self._add_labeled_widget(people_row, "Ревьюер:", self.reviewer_input)
        layout.addLayout(people_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(UI_METRICS.base_spacing)
        self.status_input = _NoWheelComboBox()
        self.status_input.addItems(["Draft", "In Progress", "Done", "Blocked", "Deprecated"])
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
    
    def _create_steps_group(self) -> QGroupBox:
        """Группа шагов тестирования в формате TestOps - единая таблица"""
        group = QGroupBox("Шаги тестирования")
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
        
        # Настройка вертикального заголовка для автоматической подстройки высоты строк
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
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

    def set_run_mode(self, enabled: bool):
        self._run_mode_enabled = enabled
        
        # В режиме запуска тестов: показать колонку статусов (3), скрыть колонку действий (4)
        self.steps_table.setColumnHidden(3, not enabled)  # Показать статусы в режиме запуска
        self.steps_table.setColumnHidden(4, enabled)  # Скрыть действия в режиме запуска
        
        # Включаем/выключаем кнопки статусов для всех строк
        for row in range(self.steps_table.rowCount()):
            status_widget = self.steps_table.cellWidget(row, 3)
            if status_widget:
                buttons = status_widget.property("status_buttons")
                if buttons:
                    for btn in buttons:
                        btn.setEnabled(enabled)

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


