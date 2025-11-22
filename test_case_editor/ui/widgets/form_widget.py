"""Виджет формы редактирования тест-кейса"""

from typing import List

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
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QSize, QTimer
from PyQt5.QtGui import QFont, QTextOption, QIcon, QPixmap, QPainter, QColor

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
        # Обновляем высоту строки таблицы
        current_row = self.steps_table.currentRow()
        if current_row >= 0:
            QTimer.singleShot(0, lambda: self.steps_table.resizeRowToContents(current_row))
            QTimer.singleShot(10, self._update_table_row_heights)
        self._mark_changed()
    
    def _update_table_row_heights(self):
        """Обновить высоты всех строк таблицы."""
        for row in range(self.steps_table.rowCount()):
            self.steps_table.resizeRowToContents(row)
    

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
        self.steps_table = QTableWidget(0, 5, self)  # 5 колонок: №, Действие, Ожидаемый результат, Статус, Действия
        
        # Убираем заголовки таблицы
        self.steps_table.horizontalHeader().setVisible(False)
        
        # Настройка колонок
        self.steps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)  # № - фиксированная
        self.steps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # Действие - растягивается
        self.steps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # Ожидаемый результат - растягивается
        self.steps_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)  # Статус - фиксированная
        self.steps_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)  # Действия - фиксированная
        
        self.steps_table.setColumnWidth(0, 50)   # №
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
            for step in test_case.steps:
                self._add_step(step.description, step.expected_result, step.status or "pending")
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

    def _add_step(self, step_text="", expected_text="", status="pending", row=None):
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
        
        # Шаги
        steps = []
        for row in range(self.steps_table.rowCount()):
            action_edit = self.steps_table.cellWidget(row, 1)
            expected_edit = self.steps_table.cellWidget(row, 2)
            if not action_edit or not expected_edit:
                continue
            step_text = action_edit.toPlainText()
            expected_text = expected_edit.toPlainText()
            status = self.step_statuses[row] if row < len(self.step_statuses) else "pending"
            steps.append(
                TestCaseStep(
                    name=f"Шаг {row + 1}",
                    description=step_text,
                    expected_result=expected_text,
                    status=status,
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


