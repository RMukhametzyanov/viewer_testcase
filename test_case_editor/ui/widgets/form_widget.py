"""Виджет формы редактирования тест-кейса"""

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
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QSize
from PyQt5.QtGui import QFont

from ...models.test_case import TestCase, TestCaseStep
from ...services.test_case_service import TestCaseService
from ...utils.datetime_utils import format_datetime, get_current_datetime


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
            self.setStyleSheet(
                """
                QFrame#StepCard {
                    background-color: #111821;
                    border: 1px solid #1F2A36;
                    border-radius: 10px;
                }
                QTextEdit {
                    background: transparent;
                    border: 1px solid #2B3945;
                    border-radius: 6px;
                    color: #E1E3E6;
                    padding: 6px;
                    font-size: 11pt;
                }
                QTextEdit:read-only {
                    border: 1px solid #1B2530;
                    color: #94A0AE;
                }
                """
            )

            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)

            header = QHBoxLayout()
            header.setSpacing(6)
            self.index_label = QLabel("Шаг 1")
            self.index_label.setStyleSheet("color: #8B9099; font-weight: 600;")
            header.addWidget(self.index_label)
            header.addStretch(1)

            self.status_widget = QWidget()
            status_layout = QHBoxLayout(self.status_widget)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setSpacing(4)
            self.status_buttons = []
            spec = [
                ("passed", "✓", "#4CAF50"),
                ("failed", "✕", "#F44336"),
                ("skipped", "S", "#B0BEC5"),
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
                color = btn.property("status_color")
                is_active = value == self._status
                btn.setChecked(is_active)
                if is_active:
                    btn.setStyleSheet(
                        f"""
                        QToolButton {{
                            background-color: {color};
                            border-radius: 4px;
                            color: #0F1520;
                            font-weight: 600;
                            padding: 2px 6px;
                        }}
                        """
                    )
                else:
                    btn.setStyleSheet(
                        f"""
                        QToolButton {{
                            border: none;
                            color: {color};
                            font-weight: 600;
                            padding: 2px 6px;
                        }}
                        QToolButton::hover {{
                            background-color: rgba(255,255,255,0.08);
                            border-radius: 4px;
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
            def _doc_height(edit: QTextEdit) -> float:
                doc = edit.document()
                width = edit.viewport().width()
                if width <= 0:
                    width = 320
                doc.setTextWidth(width - 4)
                return doc.size().height()

            header_height = self.index_label.sizeHint().height() + 32
            action_height = _doc_height(self.action_edit) + 24
            expected_height = _doc_height(self.expected_edit) + 24
            total_height = int(header_height + action_height + expected_height)
            return QSize(self.width() or 400, max(140, total_height))

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
    
    def setup_ui(self):
        """Настройка UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Заголовок
        header = self._create_header()
        layout.addWidget(header)
        
        # Scrollable форма
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(15)
        form_layout.setContentsMargins(15, 15, 15, 15)
        
        # Кнопка сворачивания секций
        self.sections_toggle_btn = QToolButton()
        self.sections_toggle_btn.setArrowType(Qt.DownArrow)
        self.sections_toggle_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.sections_toggle_btn.setCheckable(True)
        self.sections_toggle_btn.setChecked(True)
        self.sections_toggle_btn.setFixedSize(24, 24)
        self.sections_toggle_btn.setStyleSheet(
            """
            QToolButton {
                background: transparent;
                border: none;
                color: #E1E3E6;
            }
            QToolButton:hover {
                color: #3D6A98;
            }
            """
        )
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
        header.setStyleSheet("background-color: #1E2732; border-bottom: 2px solid #2B3945;")
        header.setMinimumHeight(90)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(24)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)

        static_title = QLabel("Редактирование тест-кейса")
        static_title.setFont(QFont("Segoe UI", 11, QFont.Normal))
        static_title.setStyleSheet("color: #8B9099; border: none;")
        text_layout.addWidget(static_title)

        row_layout = QHBoxLayout()
        row_layout.setSpacing(12)

        self.title_container = QWidget()
        self.title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QVBoxLayout(self.title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)

        self.title_label = QLabel("Не выбран тест-кейс")
        self.title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.title_label.setStyleSheet("color: #5288C1; border: none;")
        self.title_label.setWordWrap(True)
        self.title_label.mousePressEvent = self._on_title_clicked
        title_layout.addWidget(self.title_label)

        self.title_edit = QLineEdit()
        self.title_edit.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.title_edit.setStyleSheet(
            """
            QLineEdit {
                background-color: #1E2732;
                border: 2px solid #5288C1;
                border-radius: 6px;
                padding: 6px 8px;
                color: #5288C1;
            }
            """
        )
        self.title_edit.setVisible(False)
        self.title_edit.returnPressed.connect(self._on_title_edit_finished)
        self.title_edit.editingFinished.connect(self._on_title_edit_finished)
        title_layout.addWidget(self.title_edit)

        row_layout.addWidget(self.title_container, stretch=1)

        self.save_button = QPushButton("Сохранить")
        self.save_button.setMinimumHeight(40)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save)
        self.save_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2B5278;
                border: 1px solid #3D6A98;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 0 24px;
                font-size: 12pt;
                font-weight: 600;
            }
            QPushButton:disabled {
                background-color: #1E2732;
                border: 1px solid #2B3945;
                color: #6B7380;
            }
            QPushButton:hover:!disabled {
                background-color: #3D6A98;
            }
            QPushButton:pressed:!disabled {
                background-color: #1D3F5F;
            }
            """
        )
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
        layout.setSpacing(8)
        layout.setContentsMargins(10, 8, 10, 8)

        info_line = QHBoxLayout()
        self.id_label = QLabel("ID: -")
        self.created_label = QLabel("Создан: -")
        self.updated_label = QLabel("Обновлён: -")
        for widget in (self.id_label, self.created_label, self.updated_label):
            widget.setStyleSheet("color: #E1E3E6;")
            info_line.addWidget(widget)
            info_line.addStretch(1)
        layout.addLayout(info_line)

        people_row = QHBoxLayout()
        people_row.setSpacing(12)
        self.author_input = self._create_line_edit()
        self._add_labeled_widget(people_row, "Автор:", self.author_input)

        self.owner_input = self._create_line_edit()
        self._add_labeled_widget(people_row, "Владелец:", self.owner_input)

        self.reviewer_input = self._create_line_edit()
        self._add_labeled_widget(people_row, "Ревьюер:", self.reviewer_input)
        layout.addLayout(people_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        self.status_input = QComboBox()
        self.status_input.addItems(["Draft", "In Progress", "Done", "Blocked", "Deprecated"])
        self.status_input.currentTextChanged.connect(self._mark_changed)
        self._add_labeled_widget(status_row, "Статус:", self.status_input)

        self.test_layer_input = QComboBox()
        self.test_layer_input.addItems(["Unit", "Component", "API", "UI", "E2E", "Integration"])
        self.test_layer_input.setEditable(True)
        self.test_layer_input.currentTextChanged.connect(self._mark_changed)
        self._add_labeled_widget(status_row, "Test Layer:", self.test_layer_input)

        self.test_type_input = QComboBox()
        self.test_type_input.addItems(["manual", "automated", "hybrid"])
        self.test_type_input.setEditable(True)
        self.test_type_input.currentTextChanged.connect(self._mark_changed)
        self._add_labeled_widget(status_row, "Тип теста:", self.test_type_input)
        layout.addLayout(status_row)

        quality_row = QHBoxLayout()
        quality_row.setSpacing(12)
        self.severity_input = QComboBox()
        self.severity_input.addItems(["BLOCKER", "CRITICAL", "MAJOR", "NORMAL", "MINOR"])
        self.severity_input.setEditable(True)
        self.severity_input.currentTextChanged.connect(self._mark_changed)
        self._add_labeled_widget(quality_row, "Severity:", self.severity_input)

        self.priority_input = QComboBox()
        self.priority_input.addItems(["HIGHEST", "HIGH", "MEDIUM", "LOW", "LOWEST"])
        self.priority_input.setEditable(True)
        self.priority_input.currentTextChanged.connect(self._mark_changed)
        self._add_labeled_widget(quality_row, "Priority:", self.priority_input)
        layout.addLayout(quality_row)

        environment_row = QHBoxLayout()
        environment_row.setSpacing(12)
        self.environment_input = self._create_line_edit()
        self._add_labeled_widget(environment_row, "Окружение:", self.environment_input)

        self.browser_input = self._create_line_edit()
        self._add_labeled_widget(environment_row, "Браузер:", self.browser_input)
        layout.addLayout(environment_row)

        links_row = QHBoxLayout()
        links_row.setSpacing(12)
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
        self.tags_input.setMaximumHeight(100)
        self.tags_input.textChanged.connect(self._mark_changed)
        layout.addWidget(self.tags_input)
        return group

    def _create_description_group(self) -> QGroupBox:
        group = QGroupBox("Описание")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Подробное описание тест-кейса")
        self.description_input.setMaximumHeight(100)
        self.description_input.textChanged.connect(self._mark_changed)
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
        self.precondition_input.setMinimumHeight(80)
        self.precondition_input.setMaximumHeight(120)
        self.precondition_input.textChanged.connect(self._mark_changed)
        layout.addWidget(self.precondition_input)
        
        group.setLayout(layout)
        return group

    def _create_expected_result_group(self) -> QGroupBox:
        group = QGroupBox("Общий ожидаемый результат")
        layout = QVBoxLayout()

        self.expected_result_input = QTextEdit()
        self.expected_result_input.setPlaceholderText("Что должно получиться по завершении кейса")
        self.expected_result_input.setMinimumHeight(60)
        self.expected_result_input.setMaximumHeight(120)
        self.expected_result_input.textChanged.connect(self._mark_changed)
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
        label.setStyleSheet("color: #8B9099;")
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
        
        controls_panel = QFrame()
        controls_layout = QHBoxLayout(controls_panel)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        self.step_add_end_btn = self._create_step_control_button("＋", "Добавить шаг в конец")
        self.step_add_end_btn.clicked.connect(self._add_step_to_end)
        controls_layout.addWidget(self.step_add_end_btn)

        self.step_insert_above_btn = self._create_step_control_button("＋↑", "Вставить шаг выше выбранного")
        self.step_insert_above_btn.clicked.connect(self._insert_step_above)
        controls_layout.addWidget(self.step_insert_above_btn)

        self.step_insert_below_btn = self._create_step_control_button("＋↓", "Вставить шаг ниже выбранного")
        self.step_insert_below_btn.clicked.connect(self._insert_step_below)
        controls_layout.addWidget(self.step_insert_below_btn)

        self.step_move_up_btn = self._create_step_control_button("↑", "Переместить шаг выше")
        self.step_move_up_btn.clicked.connect(self._move_step_up)
        controls_layout.addWidget(self.step_move_up_btn)

        self.step_move_down_btn = self._create_step_control_button("↓", "Переместить шаг ниже")
        self.step_move_down_btn.clicked.connect(self._move_step_down)
        controls_layout.addWidget(self.step_move_down_btn)

        self.step_remove_btn = self._create_step_control_button("✕", "Удалить выбранный шаг")
        self.step_remove_btn.clicked.connect(self._remove_step)
        controls_layout.addWidget(self.step_remove_btn)

        controls_layout.addStretch()

        layout.addWidget(controls_panel)

        # Список шагов
        self.steps_list = QListWidget()
        self.steps_list.setSpacing(6)
        self.steps_list.setStyleSheet(
            """
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                margin-bottom: 8px;
            }
            QListWidget::item:selected {
                background: transparent;
            }
            """
        )
        self.steps_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.steps_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.steps_list.itemSelectionChanged.connect(self._update_step_controls_state)
        layout.addWidget(self.steps_list)
        
        group.setLayout(layout)
        return group
    
    def load_test_case(self, test_case: TestCase):
        """Загрузить тест-кейс в форму"""
        self._is_loading = True
        self.current_test_case = test_case
        self.has_unsaved_changes = False

        if test_case:
            self.title_label.setText(test_case.name)
            self.title_label.setVisible(True)
            self.title_edit.setVisible(False)

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
            self.title_label.setText("Не выбран тест-кейс")
            self.title_label.setVisible(True)
            self.title_edit.setVisible(False)
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
    
    def _on_title_clicked(self, event):
        """Клик по названию"""
        if not self.current_test_case:
            return
        
        self.title_label.setVisible(False)
        self.title_edit.setVisible(True)
        self.title_edit.setText(self.title_label.text())
        self.title_edit.setFocus()
        self.title_edit.selectAll()
    
    def _on_title_edit_finished(self):
        """Завершение редактирования названия"""
        if not self.title_edit.isVisible():
            return
        
        new_title = self.title_edit.text().strip() or "Без названия"
        self.title_label.setText(new_title)
        self.title_edit.setVisible(False)
        self.title_label.setVisible(True)
        
        if self.current_test_case:
            self._mark_changed()
    
    def _create_step_control_button(self, text: str, tooltip: str) -> QToolButton:
        """Создает кнопку панели управления шагами."""
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setAutoRaise(True)
        btn.setFixedSize(28, 28)
        btn.setStyleSheet(
            """
            QToolButton {
                background-color: #1E2732;
                border: 1px solid #2B3945;
                border-radius: 6px;
                color: #E1E3E6;
                font-size: 14px;
                font-weight: 600;
            }
            QToolButton:hover {
                background-color: #2B3945;
            }
            QToolButton:disabled {
                color: #4C515A;
                background-color: #151E27;
            }
            """
        )
        return btn

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
        """Обновить доступность кнопок управления шагами."""
        row_count = self.steps_list.count()
        current_row = self.steps_list.currentRow()
        has_selection = 0 <= current_row < row_count

        self.step_remove_btn.setEnabled(has_selection)
        self.step_insert_above_btn.setEnabled(has_selection)
        self.step_insert_below_btn.setEnabled(has_selection)
        self.step_move_up_btn.setEnabled(has_selection and current_row > 0)
        self.step_move_down_btn.setEnabled(has_selection and current_row < row_count - 1)
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
        self.current_test_case.name = self.title_label.text()
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
        self.title_label.setEnabled(enabled)
        self.step_add_end_btn.setEnabled(enabled)
        self.step_insert_above_btn.setEnabled(enabled)
        self.step_insert_below_btn.setEnabled(enabled)
        self.step_move_up_btn.setEnabled(enabled)
        self.step_move_down_btn.setEnabled(enabled)
        self.step_remove_btn.setEnabled(enabled)
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


