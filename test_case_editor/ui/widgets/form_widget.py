"""Виджет формы редактирования тест-кейса"""

from typing import List

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
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

    class _StepCard(QFrame):
        content_changed = pyqtSignal()
        status_changed = pyqtSignal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._status = "pending"
            self._index = 1
            self.setObjectName("StepCard")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(
                UI_METRICS.container_padding,
                UI_METRICS.container_padding,
                UI_METRICS.container_padding,
                UI_METRICS.container_padding,
            )
            layout.setSpacing(UI_METRICS.base_spacing)

            header = QHBoxLayout()
            header.setSpacing(UI_METRICS.base_spacing // 2)
            self.index_label = QLabel("Шаг 1")
            header.addWidget(self.index_label)
            header.addStretch(1)

            self.status_widget = QWidget()
            status_layout = QHBoxLayout(self.status_widget)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setSpacing(UI_METRICS.base_spacing // 2)
            self.status_buttons = []
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
                btn.setProperty("status_value", value)
                btn.setProperty("status_color", color)
                btn.clicked.connect(lambda _checked, val=value: self._on_status_clicked(val))
                status_layout.addWidget(btn)
                self.status_buttons.append(btn)
            self.status_widget.setVisible(False)
            header.addWidget(self.status_widget)
            layout.addLayout(header)

            self.action_edit = QTextEdit()
            self.action_edit.setPlaceholderText("Действие")
            self.action_edit.textChanged.connect(self.content_changed.emit)

            self.expected_edit = QTextEdit()
            self.expected_edit.setPlaceholderText("Ожидаемый результат")
            self.expected_edit.textChanged.connect(self.content_changed.emit)

            body = QHBoxLayout()
            body.setSpacing(10)
            body.addWidget(self.action_edit)
            body.addWidget(self.expected_edit)
            layout.addLayout(body)

        def set_contents(self, action: str, expected: str, status: str):
            self.action_edit.blockSignals(True)
            self.expected_edit.blockSignals(True)
            self.action_edit.setPlainText(action or "")
            self.expected_edit.setPlainText(expected or "")
            self.action_edit.blockSignals(False)
            self.expected_edit.blockSignals(False)
            self.set_status(status or "pending")

        def get_contents(self) -> tuple[str, str]:
            return self.action_edit.toPlainText(), self.expected_edit.toPlainText()

        def set_status(self, status: str):
            self._status = status or "pending"
            for btn in self.status_buttons:
                value = btn.property("status_value")
                color = btn.property("status_color") or "#4CAF50"
                is_active = value == self._status
                btn.setChecked(is_active)
                if is_active:
                    btn.setStyleSheet(
                        f"""
                        QToolButton {{
                            background-color: {color};
                            color: #0f1117;
                            border-radius: 9px;
                            font-weight: 700;
                            padding: 2px 10px;
                        }}
                        """
                    )
                else:
                    btn.setStyleSheet(
                        f"""
                        QToolButton {{
                            border: 1px solid {color};
                            color: {color};
                            border-radius: 9px;
                            padding: 2px 10px;
                        }}
                        QToolButton:hover {{
                            background-color: {color}33;
                        }}
                        """
                    )

        def status(self) -> str:
            return self._status

        def set_index(self, index: int):
            self._index = index
            self.index_label.setText(f"Шаг {index}")

        def set_edit_mode(self, enabled: bool):
            self.action_edit.setReadOnly(not enabled)
            self.expected_edit.setReadOnly(not enabled)

        def set_run_mode(self, enabled: bool):
            self.status_widget.setVisible(enabled)
            for btn in self.status_buttons:
                btn.setEnabled(enabled)

        def sizeHint(self):
            header_height = self.index_label.sizeHint().height() + 16
            line_height = self.action_edit.fontMetrics().lineSpacing()
            min_content_height = line_height * 7

            hints = [
                max(self.action_edit.document().size().height(), min_content_height / 2),
                max(self.expected_edit.document().size().height(), min_content_height / 2),
            ]
            total_height = header_height + sum(hints) + 32
            min_total = header_height + min_content_height + 32
            return QSize(self.width() or 400, int(max(min_total, total_height)))

        def _on_status_clicked(self, status: str):
            if status == self._status:
                return
            self._status = status
            self.set_status(status)
            self.status_changed.emit(status)
    

    # Сигналы
    test_case_saved = pyqtSignal()
    unsaved_changes_state = pyqtSignal(bool)
    
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
        
        # Заголовок
        header = self._create_header()
        layout.addWidget(header)
        
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
        
        # Кнопка сворачивания секций
        self.sections_toggle_btn = QToolButton()
        self.sections_toggle_btn.setArrowType(Qt.DownArrow)
        self.sections_toggle_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.sections_toggle_btn.setCheckable(True)
        self.sections_toggle_btn.setChecked(True)
        self.sections_toggle_btn.setMinimumHeight(max(28, UI_METRICS.control_min_height // 2))
        self.sections_toggle_btn.setMinimumWidth(UI_METRICS.control_min_width)
        self.sections_toggle_btn.clicked.connect(self._toggle_sections)
        form_layout.addWidget(self.sections_toggle_btn, alignment=Qt.AlignLeft)

        self.sections_widgets = []

        # Основная информация
        self.main_info_group = self._create_main_info_group()
        form_layout.addWidget(self.main_info_group)
        self.sections_widgets.append(self.main_info_group)

        # Теги
        self.tags_group = self._create_tags_group()
        form_layout.addWidget(self.tags_group)
        self.sections_widgets.append(self.tags_group)

        # Контекст
        self.domain_group = self._create_domain_group()
        form_layout.addWidget(self.domain_group)
        self.sections_widgets.append(self.domain_group)

        # Описание
        self.description_group = self._create_description_group()
        form_layout.addWidget(self.description_group)
        self.sections_widgets.append(self.description_group)

        # Предусловия
        precond_group = self._create_precondition_group()
        form_layout.addWidget(precond_group)

        # Общий ожидаемый результат
        expected_group = self._create_expected_result_group()
        form_layout.addWidget(expected_group)
        self.sections_widgets.append(expected_group)

        # Шаги тестирования
        steps_group = self._create_steps_group()
        steps_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        form_layout.addWidget(steps_group, 1)
        
        form_layout.addStretch()

        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
    
    def _create_header(self) -> QWidget:
        """Создать заголовок"""
        header = QFrame()
        header.setMinimumHeight(90)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.section_spacing,
            UI_METRICS.container_padding,
            UI_METRICS.section_spacing,
        )
        layout.setSpacing(UI_METRICS.section_spacing)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(UI_METRICS.base_spacing // 2)

        row_layout = QHBoxLayout()
        row_layout.setSpacing(UI_METRICS.base_spacing)

        self.title_edit = QLineEdit()
        self.title_edit.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.title_edit.setPlaceholderText("Название тест-кейса")
        self.title_edit.textChanged.connect(self._mark_changed)
        row_layout.addWidget(self.title_edit, stretch=1)

        self.save_button = QPushButton("Сохранить")
        self.save_button.setMinimumHeight(UI_METRICS.control_min_height)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save)
        row_layout.addWidget(self.save_button, alignment=Qt.AlignRight)

        text_layout.addLayout(row_layout)
        layout.addLayout(text_layout, stretch=1)

        return header
    
    def _toggle_sections(self):
        expanded = self.sections_toggle_btn.isChecked()
        self.sections_toggle_btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        for widget in self.sections_widgets:
            widget.setVisible(expanded)

    def _create_main_info_group(self) -> QGroupBox:
        group = QGroupBox("Основная информация")
        layout = QVBoxLayout(group)
        layout.setSpacing(UI_METRICS.base_spacing)
        layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.base_spacing,
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
        layout.setContentsMargins(10, 8, 10, 8)
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
        layout.setContentsMargins(10, 8, 10, 8)
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
    
    def _create_precondition_group(self) -> QGroupBox:
        """Группа предусловий"""
        group = QGroupBox("Предусловия")
        layout = QVBoxLayout()
        
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
        """Группа шагов тестирования"""
        group = QGroupBox("Шаги тестирования")
        layout = QVBoxLayout()
        layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.base_spacing,
            UI_METRICS.container_padding,
            UI_METRICS.base_spacing,
        )
        layout.setSpacing(UI_METRICS.base_spacing)

        self.steps_list = QListWidget()
        self.steps_list.setSpacing(6)
        self.steps_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.steps_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.steps_list.setFrameShape(QFrame.NoFrame)
        self.steps_list.setStyleSheet(
            """
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                margin: 0;
            }
            """
        )
        self.steps_list.itemSelectionChanged.connect(self._update_step_controls_state)
        self.steps_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.steps_list.customContextMenuRequested.connect(self._show_steps_context_menu)
        layout.addWidget(self.steps_list)
        
        group.setLayout(layout)
        return group
    
    def load_test_case(self, test_case: TestCase):
        """Загрузить тест-кейс в форму"""
        self._is_loading = True
        self.current_test_case = test_case
        self.has_unsaved_changes = False

        if test_case:
            self.title_edit.blockSignals(True)
            self.title_edit.setText(test_case.name)
            self.title_edit.blockSignals(False)

            self.id_label.setText(f"ID: {test_case.id or '-'}")
            created_text = format_datetime(test_case.created_at) if test_case.created_at else "-"
            updated_text = format_datetime(test_case.updated_at) if test_case.updated_at else "-"
            self.created_label.setText(f"Создан: {created_text}")
            self.updated_label.setText(f"Обновлён: {updated_text}")

            self.author_input.blockSignals(True)
            self.author_input.setText(test_case.author)
            self.author_input.blockSignals(False)

            self.owner_input.blockSignals(True)
            self.owner_input.setText(test_case.owner)
            self.owner_input.blockSignals(False)

            self.reviewer_input.blockSignals(True)
            self.reviewer_input.setText(test_case.reviewer)
            self.reviewer_input.blockSignals(False)

            self._set_combo_value(self.status_input, test_case.status)
            self._set_combo_value(self.test_layer_input, test_case.test_layer)
            self._set_combo_value(self.test_type_input, test_case.test_type)
            self._set_combo_value(self.severity_input, test_case.severity)
            self._set_combo_value(self.priority_input, test_case.priority)

            self.tags_input.blockSignals(True)
            self.tags_input.setText('\n'.join(test_case.tags))
            self.tags_input.blockSignals(False)

            self.description_input.blockSignals(True)
            self.description_input.setText(test_case.description)
            self.description_input.blockSignals(False)

            self.precondition_input.blockSignals(True)
            self.precondition_input.setText(test_case.preconditions)
            self.precondition_input.blockSignals(False)

            self.expected_result_input.blockSignals(True)
            self.expected_result_input.setText(test_case.expected_result)
            self.expected_result_input.blockSignals(False)

            self.environment_input.blockSignals(True)
            self.environment_input.setText(test_case.environment)
            self.environment_input.blockSignals(False)

            self.browser_input.blockSignals(True)
            self.browser_input.setText(test_case.browser)
            self.browser_input.blockSignals(False)

            self.test_case_id_input.blockSignals(True)
            self.test_case_id_input.setText(test_case.test_case_id)
            self.test_case_id_input.blockSignals(False)

            self.issue_links_input.blockSignals(True)
            self.issue_links_input.setText(test_case.issue_links)
            self.issue_links_input.blockSignals(False)

            self.test_case_links_input.blockSignals(True)
            self.test_case_links_input.setText(test_case.test_case_links)
            self.test_case_links_input.blockSignals(False)

            self.epic_input.blockSignals(True)
            self.epic_input.setText(test_case.epic)
            self.epic_input.blockSignals(False)

            self.feature_input.blockSignals(True)
            self.feature_input.setText(test_case.feature)
            self.feature_input.blockSignals(False)

            self.story_input.blockSignals(True)
            self.story_input.setText(test_case.story)
            self.story_input.blockSignals(False)

            self.component_input.blockSignals(True)
            self.component_input.setText(test_case.component)
            self.component_input.blockSignals(False)

            self.steps_list.blockSignals(True)
            self.steps_list.clear()
            self.step_statuses = []
            for step in test_case.steps:
                self._add_step(step.description, step.expected_result, step.status or "pending")
            self.steps_list.blockSignals(False)
            self.steps_list.clearSelection()
            self._refresh_step_indices()
            self._update_steps_list_height()
        else:
            self.title_edit.blockSignals(True)
            self.title_edit.setText("Не выбран тест-кейс")
            self.title_edit.blockSignals(False)
            self.id_label.setText("ID: -")
            self.created_label.setText("Создан: -")
            self.updated_label.setText("Обновлён: -")
            self.author_input.clear()
            self.owner_input.clear()
            self.reviewer_input.clear()
            self.status_input.setCurrentIndex(0)
            self.test_layer_input.setCurrentIndex(0)
            self.test_type_input.setCurrentIndex(0)
            self.severity_input.setCurrentIndex(0)
            self.priority_input.setCurrentIndex(0)
            self.environment_input.clear()
            self.browser_input.clear()
            self.test_case_id_input.clear()
            self.issue_links_input.clear()
            self.test_case_links_input.clear()
            self.epic_input.clear()
            self.feature_input.clear()
            self.story_input.clear()
            self.component_input.clear()
            self.tags_input.clear()
            self.description_input.clear()
            self.precondition_input.clear()
            self.expected_result_input.clear()
            self.steps_list.clear()
            self.step_statuses = []
            self._update_steps_list_height()

        self.save_button.setEnabled(False)
        self._is_loading = False
        self.unsaved_changes_state.emit(False)
        self._update_step_controls_state()
    
    def _on_title_edit_finished(self):
        """Завершение редактирования названия"""
        new_title = self.title_edit.text().strip() or "Без названия"
        self.title_edit.setText(new_title)
        if self.current_test_case:
            self._mark_changed()
    
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
        row = self.steps_list.indexAt(pos).row()
        if row != -1:
            self.steps_list.setCurrentRow(row)

        menu = QMenu(self)
        actions = {
            "add_new": menu.addAction("➕ Добавить новый шаг"),
            "insert_above": menu.addAction("⬆️ Вставить шаг выше"),
            "insert_below": menu.addAction("⬇️ Вставить шаг ниже"),
            "move_up": menu.addAction("⇡ Переместить наверх"),
            "move_down": menu.addAction("⇣ Переместить вниз"),
            "remove": menu.addAction("✕ Удалить"),
        }

        if row == -1:
            for key in ("insert_above", "insert_below", "move_up", "move_down", "remove"):
                actions[key].setEnabled(False)
        else:
            actions["move_up"].setEnabled(row > 0)
            actions["move_down"].setEnabled(row < self.steps_list.count() - 1)

        action = menu.exec_(self.steps_list.mapToGlobal(pos))
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
        widget = self._StepCard(self)
        widget.set_contents(step_text, expected_text, status)
        widget.set_edit_mode(self._edit_mode_enabled)
        widget.set_run_mode(self._run_mode_enabled)
        widget.content_changed.connect(self._on_step_card_content_changed)
        widget.status_changed.connect(lambda value, w=widget: self._on_step_status_changed(w, value))

        item = QListWidgetItem()
        if row is None or row >= self.steps_list.count():
            self.steps_list.addItem(item)
            row = self.steps_list.count() - 1
        else:
            self.steps_list.insertItem(row, item)
        self.steps_list.setItemWidget(item, widget)
        self.step_statuses.insert(row, status or "pending")
        self._refresh_step_indices()
        if not self._is_loading:
            self._mark_changed()
        self._update_step_controls_state()
        return row

    def _add_step_to_end(self):
        """Добавить шаг в конец."""
        new_row = self._add_step()
        self.steps_list.setCurrentRow(new_row)

    def _insert_step_above(self):
        """Добавить шаг выше выбранного."""
        row = self.steps_list.currentRow()
        if row < 0:
            self._add_step_to_end()
            return
        new_row = self._add_step(row=row)
        self.steps_list.setCurrentRow(new_row)

    def _insert_step_below(self):
        """Добавить шаг ниже выбранного."""
        row = self.steps_list.currentRow()
        insert_row = row + 1 if row >= 0 else self.steps_list.count()
        new_row = self._add_step(row=insert_row)
        self.steps_list.setCurrentRow(new_row)

    def _move_step_up(self):
        """Переместить выбранный шаг выше."""
        row = self.steps_list.currentRow()
        if row <= 0:
            return
        self._swap_step_rows(row, row - 1)
        self.steps_list.setCurrentRow(row - 1)
        self._mark_changed()
        self._update_step_controls_state()

    def _move_step_down(self):
        """Переместить выбранный шаг ниже."""
        row = self.steps_list.currentRow()
        if row < 0 or row >= self.steps_list.count() - 1:
            return
        self._swap_step_rows(row, row + 1)
        self.steps_list.setCurrentRow(row + 1)
        self._mark_changed()
        self._update_step_controls_state()

    def _swap_step_rows(self, row_a: int, row_b: int):
        """Поменять местами строки шагов."""
        if not (0 <= row_a < self.steps_list.count() and 0 <= row_b < self.steps_list.count()):
            return
        widget_a = self._get_step_widget(row_a)
        widget_b = self._get_step_widget(row_b)
        if not widget_a or not widget_b:
            return
        action_a, expected_a = widget_a.get_contents()
        action_b, expected_b = widget_b.get_contents()
        status_a = widget_a.status()
        status_b = widget_b.status()
        widget_a.set_contents(action_b, expected_b, status_b)
        widget_b.set_contents(action_a, expected_a, status_a)
        if row_a < len(self.step_statuses) and row_b < len(self.step_statuses):
            self.step_statuses[row_a], self.step_statuses[row_b] = (
                self.step_statuses[row_b],
                self.step_statuses[row_a],
            )
        self._refresh_step_indices()
    
    def _remove_step(self):
        """Удалить шаг"""
        row = self.steps_list.currentRow()
        if row >= 0:
            item = self.steps_list.takeItem(row)
            if item:
                widget = self.steps_list.itemWidget(item)
                if widget:
                    widget.deleteLater()
                del item
            if row < len(self.step_statuses):
                self.step_statuses.pop(row)
            self._refresh_step_indices()
            if not self._is_loading:
                self._mark_changed()
        self._update_step_controls_state()

    def _update_step_controls_state(self):
        """Поддерживаем совместимость — пока достаточно ничего не делать."""
        return
    def _mark_changed(self):
        """Пометить как измененное"""
        if self._is_loading:
            return
        
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            self.unsaved_changes_state.emit(True)
        else:
            self.unsaved_changes_state.emit(True)
        self.save_button.setEnabled(True)
    
    def _save(self):
        """Сохранить тест-кейс"""
        if not self.current_test_case:
            return
        
        # Собираем данные
        self.current_test_case.name = self.title_edit.text()
        self.current_test_case.author = self.author_input.text()
        self.current_test_case.owner = self.owner_input.text()
        self.current_test_case.reviewer = self.reviewer_input.text()
        self.current_test_case.status = self.status_input.currentText()
        self.current_test_case.test_layer = self.test_layer_input.currentText()
        self.current_test_case.test_type = self.test_type_input.currentText()
        self.current_test_case.severity = self.severity_input.currentText()
        self.current_test_case.priority = self.priority_input.currentText()
        self.current_test_case.description = self.description_input.toPlainText()
        self.current_test_case.preconditions = self.precondition_input.toPlainText()
        self.current_test_case.expected_result = self.expected_result_input.toPlainText()
        self.current_test_case.environment = self.environment_input.text()
        self.current_test_case.browser = self.browser_input.text()
        self.current_test_case.test_case_id = self.test_case_id_input.text()
        self.current_test_case.issue_links = self.issue_links_input.text()
        self.current_test_case.test_case_links = self.test_case_links_input.text()
        self.current_test_case.epic = self.epic_input.text()
        self.current_test_case.feature = self.feature_input.text()
        self.current_test_case.story = self.story_input.text()
        self.current_test_case.component = self.component_input.text()
        
        # Теги
        tags_text = self.tags_input.toPlainText().strip()
        self.current_test_case.tags = [t.strip() for t in tags_text.split('\n') if t.strip()]
        
        # Шаги
        steps = []
        for row in range(self.steps_list.count()):
            widget = self._get_step_widget(row)
            if not widget:
                continue
            step_text, expected_text = widget.get_contents()
            status = self.step_statuses[row] if row < len(self.step_statuses) else widget.status()
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
            self.save_button.setEnabled(False)
            self.unsaved_changes_state.emit(False)
            self.test_case_saved.emit()
            
            # Обновляем отображение времени обновления
            self.updated_label.setText(f"Обновлён: {format_datetime(self.current_test_case.updated_at)}")

    def set_edit_mode(self, enabled: bool):
        self._edit_mode_enabled = enabled
        widgets_to_toggle = [
            self.author_input,
            self.owner_input,
            self.reviewer_input,
            self.status_input,
            self.test_layer_input,
            self.test_type_input,
            self.severity_input,
            self.priority_input,
            self.tags_input,
            self.description_input,
            self.precondition_input,
            self.expected_result_input,
            self.environment_input,
            self.browser_input,
            self.test_case_id_input,
            self.issue_links_input,
            self.test_case_links_input,
            self.epic_input,
            self.feature_input,
            self.story_input,
            self.component_input,
            self.save_button,
            self.title_edit,
        ]
        for widget in widgets_to_toggle:
            widget.setEnabled(enabled)
        self.sections_toggle_btn.setEnabled(True)

        for row in range(self.steps_list.count()):
            widget = self._get_step_widget(row)
            if widget:
                widget.set_edit_mode(enabled)

        if not enabled:
            self.save_button.setEnabled(False)
        else:
            self.save_button.setEnabled(self.has_unsaved_changes)

    def set_run_mode(self, enabled: bool):
        self._run_mode_enabled = enabled
        for row in range(self.steps_list.count()):
            widget = self._get_step_widget(row)
            if widget:
                widget.set_run_mode(enabled)

    def _ensure_status_capacity(self):
        row_count = self.steps_list.count()
        if len(self.step_statuses) < row_count:
            self.step_statuses.extend(["pending"] * (row_count - len(self.step_statuses)))
        elif len(self.step_statuses) > row_count:
            self.step_statuses = self.step_statuses[:row_count]

    def _rebuild_status_widgets(self):
        self._ensure_status_capacity()
        for row in range(self.steps_list.count()):
            widget = self._get_step_widget(row)
            if widget:
                widget.set_status(self.step_statuses[row] if row < len(self.step_statuses) else "pending")
                widget.set_run_mode(self._run_mode_enabled)
                widget.set_edit_mode(self._edit_mode_enabled)
                item = self.steps_list.item(row)
                if item:
                    item.setSizeHint(widget.sizeHint())

    def _on_step_card_content_changed(self):
        if self._is_loading:
            return
        widget = self.sender()
        if isinstance(widget, self._StepCard):
            row = self._find_widget_row(widget)
            if row >= 0:
                item = self.steps_list.item(row)
                if item:
                    item.setSizeHint(widget.sizeHint())
        self._mark_changed()

    def _on_step_status_changed(self, widget: "TestCaseFormWidget._StepCard", status: str):
        row = self._find_widget_row(widget)
        if row < 0:
            return
        if row >= len(self.step_statuses):
            self.step_statuses.extend(["pending"] * (row - len(self.step_statuses) + 1))
        if self.step_statuses[row] == status:
            return
        self.step_statuses[row] = status
        widget.set_status(status)
        if self.current_test_case and row < len(self.current_test_case.steps):
            self.current_test_case.steps[row].status = status
            self._auto_save_status_change()

    def _get_step_widget(self, row: int):
        item = self.steps_list.item(row)
        if not item:
            return None
        return self.steps_list.itemWidget(item)

    def _find_widget_row(self, widget: "TestCaseFormWidget._StepCard") -> int:
        for idx in range(self.steps_list.count()):
            if self._get_step_widget(idx) is widget:
                return idx
        return -1

    def _refresh_step_indices(self):
        for idx in range(self.steps_list.count()):
            widget = self._get_step_widget(idx)
            if widget:
                widget.set_index(idx + 1)
                item = self.steps_list.item(idx)
                if item:
                    item.setSizeHint(widget.sizeHint())
        self._update_steps_list_height()

    def _update_steps_list_height(self):
        total = 0
        spacing = self.steps_list.spacing()
        for i in range(self.steps_list.count()):
            total += self.steps_list.sizeHintForRow(i) + spacing
        total += 12
        self.steps_list.setMinimumHeight(total)
        self.steps_list.setMaximumHeight(total)

    def _auto_save_status_change(self):
        if not self.current_test_case:
            return
        self.current_test_case.updated_at = get_current_datetime()
        if self.service.save_test_case(self.current_test_case):
            self.has_unsaved_changes = False
            self.save_button.setEnabled(False)
            self.updated_label.setText(f"Обновлён: {format_datetime(self.current_test_case.updated_at)}")
            self.test_case_saved.emit()


