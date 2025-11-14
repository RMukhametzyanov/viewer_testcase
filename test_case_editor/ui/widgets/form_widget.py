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
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QToolButton,
    QSizePolicy,
    QStyledItemDelegate,
    QAbstractItemDelegate,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
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
    
    class _StepsTableDelegate(QStyledItemDelegate):
        """Делегат редактирования ячеек таблицы шагов с поддержкой Ctrl+Enter."""

        def __init__(self, form_widget: "TestCaseFormWidget", table: QTableWidget):
            super().__init__(table)
            self._form_widget = form_widget
            self._table = table
            self._current_index = None

        def createEditor(self, parent, option, index):
            editor = QTextEdit(parent)
            editor.setAcceptRichText(False)
            editor.setFrameShape(QFrame.NoFrame)
            editor.setStyleSheet(
                """
                QTextEdit {
                    background-color: #111821;
                    border: 1px solid #2B3945;
                    border-radius: 6px;
                    color: #E1E3E6;
                    padding: 6px;
                    font-size: 11pt;
                }
                QTextEdit:focus {
                    border: 1px solid #5288C1;
                }
                """
            )
            editor.installEventFilter(self)
            self._current_index = index
            editor.textChanged.connect(lambda ed=editor: self._on_editor_text_changed(ed))

            row_height = max(self._table.rowHeight(index.row()), 60)
            editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            editor.setFixedHeight(row_height)
            return editor

        def setEditorData(self, editor, index):
            text = index.model().data(index, Qt.EditRole) or ""
            editor.setPlainText(text)
            cursor = editor.textCursor()
            cursor.movePosition(cursor.End)
            editor.setTextCursor(cursor)

        def setModelData(self, editor, model, index):
            model.setData(index, editor.toPlainText(), Qt.EditRole)
            if index.isValid():
                self._form_widget._adjust_row_height(index.row())
                self._sync_editor_height_with_row(editor, index.row())

        def eventFilter(self, editor, event):
            if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ControlModifier:
                    editor.insertPlainText("\n")
                    return True

                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QAbstractItemDelegate.NoHint)

                if self._current_index is not None and self._table.rowCount() > 0:
                    next_row = min(self._current_index.row() + 1, self._table.rowCount() - 1)
                    column = self._current_index.column()
                    if next_row != self._current_index.row():
                        self._table.setCurrentCell(next_row, column)
                    else:
                        self._table.setCurrentCell(self._current_index.row(), column)
                    self._form_widget._update_step_controls_state()
                return True

            return super().eventFilter(editor, event)

        def destroyEditor(self, editor, index):
            super().destroyEditor(editor, index)
            self._current_index = None

        def _on_editor_text_changed(self, editor: QTextEdit):
            if self._current_index is None:
                return
            row = self._current_index.row()
            if row < 0:
                return

            document = editor.document()
            document.setTextWidth(editor.viewport().width())
            contents_height = document.size().height()

            top, left, bottom, right = editor.getContentsMargins()
            padding = top + bottom + 12  # дополнительный запас
            total_height = int(contents_height + padding)

            min_height = 60
            current_row_height = self._table.rowHeight(row)
            desired_height = max(min_height, current_row_height, total_height)
            self._table.setRowHeight(row, desired_height)
            self._sync_editor_height_with_row(editor, row)

        def _sync_editor_height_with_row(self, editor: QTextEdit, row: int):
            row_height = self._table.rowHeight(row)
            if row_height <= 0:
                row_height = 60
            editor.setFixedHeight(row_height)

    # Сигналы
    test_case_saved = pyqtSignal()
    unsaved_changes_state = pyqtSignal(bool)
    
    def __init__(self, service: TestCaseService, parent=None):
        super().__init__(parent)
        self.service = service
        self.current_test_case = None
        self.has_unsaved_changes = False
        self._is_loading = False
        
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

        # Таблица шагов
        self.steps_table = QTableWidget()
        self.steps_table.setColumnCount(2)
        self.steps_table.setHorizontalHeaderLabels(["Действие", "Ожидаемый результат"])
        header = self.steps_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStretchLastSection(True)
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.setWordWrap(True)
        self.steps_table.setTextElideMode(Qt.ElideNone)
        self.steps_table.setMinimumHeight(250)
        self.steps_table.setStyleSheet(
            """
            QTableWidget::item {
                padding: 8px;
            }
            """
        )
        self.steps_table.itemChanged.connect(self._on_step_item_changed)
        self.steps_table.itemSelectionChanged.connect(self._update_step_controls_state)
        self.steps_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.steps_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.steps_table.verticalScrollBar().setSingleStep(20)
        self.steps_table.horizontalScrollBar().setSingleStep(20)
        self.steps_delegate = self._StepsTableDelegate(self, self.steps_table)
        self.steps_table.setItemDelegate(self.steps_delegate)
        layout.addWidget(self.steps_table)
        
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

            self.steps_table.blockSignals(True)
            self.steps_table.setRowCount(0)
            for step in test_case.steps:
                self._add_step(step.description, step.expected_result)
            self.steps_table.blockSignals(False)
            self.steps_table.clearSelection()
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
            self.steps_table.setRowCount(0)

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

    def _add_step(self, step_text="", expected_text="", row=None):
        """Добавить шаг"""
        if row is None:
            row = self.steps_table.rowCount()
        self.steps_table.insertRow(row)

        was_blocked = self.steps_table.signalsBlocked()
        self.steps_table.blockSignals(True)
        action_item = QTableWidgetItem(step_text)
        action_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.steps_table.setItem(row, 0, action_item)

        expected_item = QTableWidgetItem(expected_text)
        expected_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.steps_table.setItem(row, 1, expected_item)
        self.steps_table.blockSignals(was_blocked)
        self._adjust_row_height(row)
        
        if not self._is_loading:
            self._mark_changed()
        self._update_step_controls_state()
        return row

    def _add_step_to_end(self):
        """Добавить шаг в конец."""
        new_row = self._add_step()
        self.steps_table.setCurrentCell(new_row, 0)

    def _insert_step_above(self):
        """Добавить шаг выше выбранного."""
        row = self.steps_table.currentRow()
        if row < 0:
            self._add_step_to_end()
            return
        new_row = self._add_step(row=row)
        self.steps_table.setCurrentCell(new_row, 0)

    def _insert_step_below(self):
        """Добавить шаг ниже выбранного."""
        row = self.steps_table.currentRow()
        insert_row = row + 1 if row >= 0 else self.steps_table.rowCount()
        new_row = self._add_step(row=insert_row)
        self.steps_table.setCurrentCell(new_row, 0)

    def _move_step_up(self):
        """Переместить выбранный шаг выше."""
        row = self.steps_table.currentRow()
        if row <= 0:
            return
        self._swap_step_rows(row, row - 1)
        self.steps_table.setCurrentCell(row - 1, self.steps_table.currentColumn() or 0)
        self._mark_changed()
        self._update_step_controls_state()

    def _move_step_down(self):
        """Переместить выбранный шаг ниже."""
        row = self.steps_table.currentRow()
        if row < 0 or row >= self.steps_table.rowCount() - 1:
            return
        self._swap_step_rows(row, row + 1)
        self.steps_table.setCurrentCell(row + 1, self.steps_table.currentColumn() or 0)
        self._mark_changed()
        self._update_step_controls_state()

    def _swap_step_rows(self, row_a: int, row_b: int):
        """Поменять местами строки шагов."""
        if not (0 <= row_a < self.steps_table.rowCount() and 0 <= row_b < self.steps_table.rowCount()):
            return

        was_blocked = self.steps_table.signalsBlocked()
        self.steps_table.blockSignals(True)
        for col in range(self.steps_table.columnCount()):
            item_a = self.steps_table.item(row_a, col)
            item_b = self.steps_table.item(row_b, col)
            text_a = item_a.text() if item_a else ""
            text_b = item_b.text() if item_b else ""

            if item_a is None:
                item_a = QTableWidgetItem()
                self.steps_table.setItem(row_a, col, item_a)
            if item_b is None:
                item_b = QTableWidgetItem()
                self.steps_table.setItem(row_b, col, item_b)

            item_a.setText(text_b)
            item_b.setText(text_a)
        self.steps_table.blockSignals(was_blocked)
        self._adjust_row_height(row_a)
        self._adjust_row_height(row_b)
    
    def _remove_step(self):
        """Удалить шаг"""
        row = self.steps_table.currentRow()
        if row >= 0:
            self.steps_table.removeRow(row)
            if not self._is_loading:
                self._mark_changed()
        self._update_step_controls_state()
    
    def _on_step_item_changed(self, _item):
        """Обработчик изменения ячейки в таблице шагов."""
        if self._is_loading:
            return

        row = _item.row() if _item else -1
        if row >= 0:
            self._adjust_row_height(row)
        self._mark_changed()

    def _update_step_controls_state(self):
        """Обновить доступность кнопок управления шагами."""
        row_count = self.steps_table.rowCount()
        current_row = self.steps_table.currentRow()
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
        for row in range(self.steps_table.rowCount()):
            step_item = self.steps_table.item(row, 0)
            expected_item = self.steps_table.item(row, 1)
            
            step_text = step_item.text() if step_item else ""
            expected_text = expected_item.text() if expected_item else ""
            
            steps.append(
                TestCaseStep(
                    name=f"Шаг {row + 1}",
                    description=step_text,
                    expected_result=expected_text,
                    status="pending",
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

    def _adjust_row_height(self, row: int):
        """Автоматически подстроить высоту строки под содержимое."""
        if row < 0 or row >= self.steps_table.rowCount():
            return

        min_height = 60
        self.steps_table.resizeRowToContents(row)
        current_height = self.steps_table.rowHeight(row)
        if current_height < min_height:
            self.steps_table.setRowHeight(row, min_height)

    def _adjust_all_row_heights(self):
        """Подстроить высоту всех строк."""
        for row in range(self.steps_table.rowCount()):
            self._adjust_row_height(row)


