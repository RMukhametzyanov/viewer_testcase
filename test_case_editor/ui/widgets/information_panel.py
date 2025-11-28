"""Панель информации о тест-кейсе"""

from typing import Optional, List

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QGroupBox,
    QScrollArea,
    QFrame,
)
from typing import List
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QTextOption

from ...models import TestCase
from ...utils.datetime_utils import format_datetime
from ..styles.ui_metrics import UI_METRICS


class _NoWheelComboBox(QComboBox):
    """Комбо-бокс без изменения значения колесом мыши, пока меню закрыто."""

    def wheelEvent(self, event):
        popup = self.view()
        if popup and popup.isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()


class InformationPanel(QWidget):
    """Панель отображения и редактирования информации о тест-кейсе"""

    # Сигнал о том, что данные изменились
    data_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_test_case: Optional[TestCase] = None
        self._is_loading = False
        self._testers_list: List[str] = []  # Список тестировщиков из настроек
        # Видимость элементов (по умолчанию все видимы)
        self._visibility_settings = {
            # Метаданные
            'id': True,
            'created': True,
            'updated': True,
            # Люди
            'author': True,
            'owner': True,
            'reviewer': True,
            # Статус и тип
            'status': True,
            'test_layer': True,
            'test_type': True,
            # Severity и Priority
            'severity': True,
            'priority': True,
            # Окружение и Браузер
            'environment': True,
            'browser': True,
            # Ссылки
            'test_case_id': True,
            'issue_links': True,
            'test_case_links': True,
            # Группы
            'tags': True,
            # Контекст
            'epic': True,
            'feature': True,
            'story': True,
            'component': True,
            'description': True,
            'expected_result': True,
        }
        self._setup_ui()

    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(UI_METRICS.base_spacing)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(UI_METRICS.section_spacing)
        content_layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )

        # Описание (в самом верху)
        self.description_group = self._create_description_group()
        content_layout.addWidget(self.description_group)

        # Основная информация
        self.main_info_group = self._create_main_info_group()
        content_layout.addWidget(self.main_info_group)

        # Теги
        self.tags_group = self._create_tags_group()
        content_layout.addWidget(self.tags_group)

        # Контекст
        self.domain_group = self._create_domain_group()
        content_layout.addWidget(self.domain_group)

        # Общий ожидаемый результат
        self.expected_result_group = self._create_expected_result_group()
        content_layout.addWidget(self.expected_result_group)

        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Сохраняем ссылку на content_layout для управления видимостью
        self.content_layout = content_layout
        
        # Применяем настройки видимости
        self._apply_visibility_settings()

    def _create_main_info_group(self) -> QGroupBox:
        """Создать группу основной информации"""
        group = QGroupBox("Основная информация")
        layout = QVBoxLayout(group)
        layout.setSpacing(UI_METRICS.base_spacing)
        layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.group_title_spacing,  # Отступ сверху для заголовка
            UI_METRICS.container_padding,
            UI_METRICS.base_spacing,
        )

        # ID, Created, Updated - сохраняем виджеты для управления видимостью
        meta_layout = QHBoxLayout()
        self.id_label = QLabel("ID: -")
        self.created_label = QLabel("Создан: -")
        self.updated_label = QLabel("Обновлён: -")
        meta_layout.addWidget(self.id_label)
        meta_layout.addStretch(1)
        meta_layout.addWidget(self.created_label)
        meta_layout.addStretch(1)
        meta_layout.addWidget(self.updated_label)
        meta_layout.addStretch(1)
        layout.addLayout(meta_layout)

        # Люди: Автор, Владелец, Ревьюер - сохраняем контейнеры
        people_layout = QHBoxLayout()
        people_layout.setSpacing(UI_METRICS.base_spacing)
        self.author_input = self._create_tester_combo()
        self.author_container = self._add_labeled_widget(people_layout, "Автор:", self.author_input)

        self.owner_input = self._create_tester_combo()
        self.owner_container = self._add_labeled_widget(people_layout, "Исполнитель:", self.owner_input)

        self.reviewer_input = self._create_tester_combo()
        self.reviewer_container = self._add_labeled_widget(people_layout, "Ревьюер:", self.reviewer_input)
        layout.addLayout(people_layout)

        # Статус, Test Layer, Тип теста - сохраняем контейнеры
        status_layout = QHBoxLayout()
        status_layout.setSpacing(UI_METRICS.base_spacing)
        self.status_input = _NoWheelComboBox()
        self.status_input.addItems(["Draft", "Design", "Review", "Done"])
        self.status_input.setEditable(True)
        self.status_input.currentTextChanged.connect(self._on_changed)
        self.status_container = self._add_labeled_widget(status_layout, "Статус:", self.status_input)

        self.test_layer_input = _NoWheelComboBox()
        self.test_layer_input.addItems(["Unit", "Component", "API", "UI", "E2E", "Integration"])
        self.test_layer_input.setEditable(True)
        self.test_layer_input.currentTextChanged.connect(self._on_changed)
        self.test_layer_container = self._add_labeled_widget(status_layout, "Test Layer:", self.test_layer_input)

        self.test_type_input = _NoWheelComboBox()
        self.test_type_input.addItems(["manual", "automated", "hybrid"])
        self.test_type_input.setEditable(True)
        self.test_type_input.currentTextChanged.connect(self._on_changed)
        self.test_type_container = self._add_labeled_widget(status_layout, "Тип теста:", self.test_type_input)
        layout.addLayout(status_layout)

        # Severity, Priority - сохраняем контейнеры
        quality_layout = QHBoxLayout()
        quality_layout.setSpacing(UI_METRICS.base_spacing)
        self.severity_input = _NoWheelComboBox()
        self.severity_input.addItems(["BLOCKER", "CRITICAL", "MAJOR", "NORMAL", "MINOR"])
        self.severity_input.setEditable(True)
        self.severity_input.currentTextChanged.connect(self._on_changed)
        self.severity_container = self._add_labeled_widget(quality_layout, "Severity:", self.severity_input)

        self.priority_input = _NoWheelComboBox()
        self.priority_input.addItems(["HIGHEST", "HIGH", "MEDIUM", "LOW", "LOWEST"])
        self.priority_input.setEditable(True)
        self.priority_input.currentTextChanged.connect(self._on_changed)
        self.priority_container = self._add_labeled_widget(quality_layout, "Priority:", self.priority_input)
        layout.addLayout(quality_layout)

        # Окружение, Браузер - сохраняем контейнеры
        environment_layout = QHBoxLayout()
        environment_layout.setSpacing(UI_METRICS.base_spacing)
        self.environment_input = self._create_line_edit()
        self.environment_container = self._add_labeled_widget(environment_layout, "Окружение:", self.environment_input)

        self.browser_input = self._create_line_edit()
        self.browser_container = self._add_labeled_widget(environment_layout, "Браузер:", self.browser_input)
        layout.addLayout(environment_layout)

        # Test Case ID, Issue Links, TC Links - сохраняем контейнеры
        links_layout = QHBoxLayout()
        links_layout.setSpacing(UI_METRICS.base_spacing)
        self.test_case_id_input = self._create_line_edit()
        self.test_case_id_container = self._add_labeled_widget(links_layout, "Test Case ID:", self.test_case_id_input)

        self.issue_links_input = self._create_line_edit()
        self.issue_links_container = self._add_labeled_widget(links_layout, "Issue Links:", self.issue_links_input)

        self.test_case_links_input = self._create_line_edit()
        self.test_case_links_container = self._add_labeled_widget(links_layout, "TC Links:", self.test_case_links_input)
        layout.addLayout(links_layout)

        return group

    def _create_tags_group(self) -> QGroupBox:
        """Создать группу тегов"""
        group = QGroupBox("Теги")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, UI_METRICS.group_title_spacing, 10, 8)  # Отступ сверху для заголовка
        layout.setSpacing(6)

        self.tags_input = QTextEdit()
        self.tags_input.setPlaceholderText("Введите теги, каждый с новой строки")
        self.tags_input.textChanged.connect(self._on_changed)
        self._init_auto_resizing_text_edit(self.tags_input, min_lines=2, max_lines=10)
        layout.addWidget(self.tags_input)
        return group

    def _create_description_group(self) -> QGroupBox:
        """Создать группу описания"""
        group = QGroupBox("Описание")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, UI_METRICS.group_title_spacing, 10, 8)  # Отступ сверху для заголовка
        layout.setSpacing(6)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Подробное описание тест-кейса")
        self.description_input.textChanged.connect(self._on_changed)
        self._init_auto_resizing_text_edit(self.description_input, min_lines=4, max_lines=12)
        layout.addWidget(self.description_input)
        return group

    def _create_domain_group(self) -> QGroupBox:
        """Создать группу контекста"""
        group = QGroupBox("Контекст (epic / feature / story / component)")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(10, UI_METRICS.group_title_spacing, 10, 8)  # Отступ сверху для заголовка
        layout.setSpacing(12)

        self.epic_input = self._create_line_edit()
        self.epic_input.setPlaceholderText("Epic")
        self.epic_container = self._add_labeled_widget(layout, "Epic:", self.epic_input)

        self.feature_input = self._create_line_edit()
        self.feature_input.setPlaceholderText("Feature")
        self.feature_container = self._add_labeled_widget(layout, "Feature:", self.feature_input)

        self.story_input = self._create_line_edit()
        self.story_input.setPlaceholderText("Story")
        self.story_container = self._add_labeled_widget(layout, "Story:", self.story_input)

        self.component_input = self._create_line_edit()
        self.component_input.setPlaceholderText("Component")
        self.component_container = self._add_labeled_widget(layout, "Component:", self.component_input)

        return group

    def _create_expected_result_group(self) -> QGroupBox:
        """Создать группу общего ожидаемого результата"""
        group = QGroupBox("Общий ожидаемый результат")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, UI_METRICS.group_title_spacing, 0, 0)  # Отступ сверху для заголовка

        self.expected_result_input = QTextEdit()
        self.expected_result_input.setPlaceholderText("Что должно получиться по завершении кейса")
        self.expected_result_input.textChanged.connect(self._on_changed)
        self._init_auto_resizing_text_edit(self.expected_result_input, min_lines=3, max_lines=10)
        layout.addWidget(self.expected_result_input)

        group.setLayout(layout)
        return group

    def _create_line_edit(self) -> QLineEdit:
        """Создать LineEdit с подключением сигнала изменения"""
        edit = QLineEdit()
        edit.textChanged.connect(self._on_changed)
        # Устанавливаем выравнивание по левому краю и показываем начало строки
        edit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return edit
    
    def _create_tester_combo(self) -> QComboBox:
        """Создать ComboBox для выбора тестировщика"""
        combo = _NoWheelComboBox()
        combo.setEditable(True)  # Разрешаем ввод произвольного значения
        combo.currentTextChanged.connect(self._on_changed)
        self._update_tester_combo(combo)
        return combo
    
    def _update_tester_combo(self, combo: QComboBox):
        """Обновить список тестировщиков в ComboBox"""
        current_text = combo.currentText()
        combo.clear()
        combo.addItem("")  # Пустой элемент
        for tester in self._testers_list:
            combo.addItem(tester)
        # Восстанавливаем текущий текст, если он был
        if current_text:
            index = combo.findText(current_text, Qt.MatchFixedString)
            if index >= 0:
                combo.setCurrentIndex(index)
            else:
                combo.setEditText(current_text)
    
    def set_testers(self, testers: List[str]):
        """Установить список тестировщиков из настроек"""
        self._testers_list = testers if testers else []
        # Обновляем все ComboBox
        if hasattr(self, 'author_input'):
            self._update_tester_combo(self.author_input)
        if hasattr(self, 'owner_input'):
            self._update_tester_combo(self.owner_input)
        if hasattr(self, 'reviewer_input'):
            self._update_tester_combo(self.reviewer_input)

    def _add_labeled_widget(self, parent_layout: QHBoxLayout, label_text: str, widget):
        """Добавить виджет с подписью и вернуть контейнер для управления видимостью"""
        container = QVBoxLayout()
        label = QLabel(label_text)
        container.addWidget(label)
        container.addWidget(widget)
        parent_layout.addLayout(container)
        # Сохраняем ссылку на label для удобства
        setattr(widget, '_label', label)
        # Возвращаем контейнер для сохранения ссылки
        return container

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

    @staticmethod
    def _calculate_text_edit_height(text_edit: QTextEdit, lines: int) -> int:
        """Вычислить высоту TextEdit для указанного количества строк"""
        metrics = text_edit.fontMetrics()
        line_height = metrics.lineSpacing()
        margins = text_edit.contentsMargins()
        doc_margin = text_edit.document().documentMargin()
        return int(lines * line_height + doc_margin * 2 + margins.top() + margins.bottom() + 8)

    @staticmethod
    def _auto_resize_text_edit(text_edit: QTextEdit, min_height: int, max_height: int):
        """Автоматически изменить высоту TextEdit под содержимое"""
        doc = text_edit.document()
        margins = text_edit.contentsMargins()
        doc_height = doc.size().height() + doc.documentMargin() * 2 + margins.top() + margins.bottom() + 6
        new_height = max(min_height, min(max_height, int(doc_height)))
        if text_edit.height() != new_height:
            text_edit.setFixedHeight(new_height)

    def _set_combo_value(self, combo: QComboBox, value: str):
        """Установить значение в ComboBox"""
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

    def _on_changed(self):
        """Обработчик изменения любого поля"""
        if not self._is_loading:
            self.data_changed.emit()

    def load_test_case(self, test_case: Optional[TestCase]):
        """Загрузить данные тест-кейса в панель"""
        self._is_loading = True
        self.current_test_case = test_case

        if test_case:
            # ID, Created, Updated
            self.id_label.setText(f"ID: {test_case.id or '-'}")
            created_text = format_datetime(test_case.created_at) if test_case.created_at else "-"
            updated_text = format_datetime(test_case.updated_at) if test_case.updated_at else "-"
            self.created_label.setText(f"Создан: {created_text}")
            self.updated_label.setText(f"Обновлён: {updated_text}")

            # Люди (для ComboBox используем setCurrentText или setEditText)
            self.author_input.blockSignals(True)
            author_text = test_case.author or ""
            index = self.author_input.findText(author_text, Qt.MatchFixedString)
            if index >= 0:
                self.author_input.setCurrentIndex(index)
            else:
                self.author_input.setEditText(author_text)
            self.author_input.blockSignals(False)

            self.owner_input.blockSignals(True)
            owner_text = test_case.owner or ""
            index = self.owner_input.findText(owner_text, Qt.MatchFixedString)
            if index >= 0:
                self.owner_input.setCurrentIndex(index)
            else:
                self.owner_input.setEditText(owner_text)
            self.owner_input.blockSignals(False)

            self.reviewer_input.blockSignals(True)
            reviewer_text = test_case.reviewer or ""
            index = self.reviewer_input.findText(reviewer_text, Qt.MatchFixedString)
            if index >= 0:
                self.reviewer_input.setCurrentIndex(index)
            else:
                self.reviewer_input.setEditText(reviewer_text)
            self.reviewer_input.blockSignals(False)

            # Статусы
            self._set_combo_value(self.status_input, test_case.status or "")
            self._set_combo_value(self.test_layer_input, test_case.test_layer or "")
            self._set_combo_value(self.test_type_input, test_case.test_type or "")
            self._set_combo_value(self.severity_input, test_case.severity or "")
            self._set_combo_value(self.priority_input, test_case.priority or "")

            # Текстовые поля
            self.tags_input.blockSignals(True)
            self.tags_input.setText('\n'.join(test_case.tags) if test_case.tags else "")
            self.tags_input.blockSignals(False)

            self.description_input.blockSignals(True)
            self.description_input.setText(test_case.description or "")
            self.description_input.blockSignals(False)

            self.expected_result_input.blockSignals(True)
            self.expected_result_input.setText(test_case.expected_result or "")
            self.expected_result_input.blockSignals(False)

            # Окружение
            self.environment_input.blockSignals(True)
            self.environment_input.setText(test_case.environment or "")
            self.environment_input.blockSignals(False)

            self.browser_input.blockSignals(True)
            self.browser_input.setText(test_case.browser or "")
            self.browser_input.blockSignals(False)

            # Ссылки
            self.test_case_id_input.blockSignals(True)
            self.test_case_id_input.setText(test_case.test_case_id or "")
            self.test_case_id_input.blockSignals(False)

            self.issue_links_input.blockSignals(True)
            self.issue_links_input.setText(test_case.issue_links or "")
            self.issue_links_input.blockSignals(False)

            self.test_case_links_input.blockSignals(True)
            self.test_case_links_input.setText(test_case.test_case_links or "")
            self.test_case_links_input.blockSignals(False)

            # Контекст
            self.epic_input.blockSignals(True)
            self.epic_input.setText(test_case.epic or "")
            self.epic_input.blockSignals(False)

            self.feature_input.blockSignals(True)
            self.feature_input.setText(test_case.feature or "")
            self.feature_input.blockSignals(False)

            self.story_input.blockSignals(True)
            self.story_input.setText(test_case.story or "")
            self.story_input.blockSignals(False)

            self.component_input.blockSignals(True)
            self.component_input.setText(test_case.component or "")
            self.component_input.blockSignals(False)
        else:
            # Очистить все поля
            self.id_label.setText("ID: -")
            self.created_label.setText("Создан: -")
            self.updated_label.setText("Обновлён: -")
            self.author_input.setCurrentIndex(0)  # Устанавливаем пустой элемент
            self.owner_input.setCurrentIndex(0)
            self.reviewer_input.setCurrentIndex(0)
            self._set_combo_value(self.status_input, "")
            self._set_combo_value(self.test_layer_input, "")
            self._set_combo_value(self.test_type_input, "")
            self._set_combo_value(self.severity_input, "")
            self._set_combo_value(self.priority_input, "")
            self.tags_input.clear()
            self.description_input.clear()
            self.expected_result_input.clear()
            self.environment_input.clear()
            self.browser_input.clear()
            self.test_case_id_input.clear()
            self.issue_links_input.clear()
            self.test_case_links_input.clear()
            self.epic_input.clear()
            self.feature_input.clear()
            self.story_input.clear()
            self.component_input.clear()

        self._is_loading = False

    def update_test_case(self, test_case: TestCase):
        """Обновить тест-кейс данными из панели"""
        if not test_case:
            return

        test_case.author = self.author_input.currentText()
        test_case.owner = self.owner_input.currentText()
        test_case.reviewer = self.reviewer_input.currentText()
        test_case.status = self.status_input.currentText()
        test_case.test_layer = self.test_layer_input.currentText()
        test_case.test_type = self.test_type_input.currentText()
        test_case.severity = self.severity_input.currentText()
        test_case.priority = self.priority_input.currentText()
        test_case.description = self.description_input.toPlainText()
        test_case.expected_result = self.expected_result_input.toPlainText()
        test_case.environment = self.environment_input.text()
        test_case.browser = self.browser_input.text()
        test_case.test_case_id = self.test_case_id_input.text()
        test_case.issue_links = self.issue_links_input.text()
        test_case.test_case_links = self.test_case_links_input.text()
        test_case.epic = self.epic_input.text()
        test_case.feature = self.feature_input.text()
        test_case.story = self.story_input.text()
        test_case.component = self.component_input.text()

        # Теги
        tags_text = self.tags_input.toPlainText().strip()
        test_case.tags = [t.strip() for t in tags_text.split('\n') if t.strip()]

    def set_edit_mode(self, enabled: bool):
        """Установить режим редактирования"""
        widgets = [
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
        ]
        for widget in widgets:
            widget.setEnabled(enabled)
    
    def set_visibility_settings(self, visibility_settings: dict):
        """Установить настройки видимости элементов"""
        self._visibility_settings.update(visibility_settings)
        self._apply_visibility_settings()
    
    def _apply_visibility_settings(self):
        """Применить настройки видимости элементов (каждый элемент отдельно)"""
        # Метаданные - отдельные элементы
        if hasattr(self, 'id_label'):
            self.id_label.setVisible(self._visibility_settings.get('id', True))
        if hasattr(self, 'created_label'):
            self.created_label.setVisible(self._visibility_settings.get('created', True))
        if hasattr(self, 'updated_label'):
            self.updated_label.setVisible(self._visibility_settings.get('updated', True))
        
        # Люди - отдельные элементы (через контейнеры)
        self._set_container_visibility('author_container', 'author')
        self._set_container_visibility('owner_container', 'owner')
        self._set_container_visibility('reviewer_container', 'reviewer')
        
        # Статус, Test Layer, Тип теста - отдельные элементы
        self._set_container_visibility('status_container', 'status')
        self._set_container_visibility('test_layer_container', 'test_layer')
        self._set_container_visibility('test_type_container', 'test_type')
        
        # Severity, Priority - отдельные элементы
        self._set_container_visibility('severity_container', 'severity')
        self._set_container_visibility('priority_container', 'priority')
        
        # Окружение, Браузер - отдельные элементы
        self._set_container_visibility('environment_container', 'environment')
        self._set_container_visibility('browser_container', 'browser')
        
        # Ссылки - отдельные элементы
        self._set_container_visibility('test_case_id_container', 'test_case_id')
        self._set_container_visibility('issue_links_container', 'issue_links')
        self._set_container_visibility('test_case_links_container', 'test_case_links')
        
        # Теги
        if hasattr(self, 'tags_group'):
            tags_visible = self._visibility_settings.get('tags', True)
            self.tags_group.setVisible(tags_visible)
        
        # Контекст - отдельные элементы
        if hasattr(self, 'domain_group'):
            self._set_container_visibility('epic_container', 'epic')
            self._set_container_visibility('feature_container', 'feature')
            self._set_container_visibility('story_container', 'story')
            self._set_container_visibility('component_container', 'component')
            
            # Если все элементы контекста скрыты, скрываем всю группу
            context_visible = (
                self._visibility_settings.get('epic', True) or
                self._visibility_settings.get('feature', True) or
                self._visibility_settings.get('story', True) or
                self._visibility_settings.get('component', True)
            )
            self.domain_group.setVisible(context_visible)
        
        # Описание
        if hasattr(self, 'description_group'):
            description_visible = self._visibility_settings.get('description', True)
            self.description_group.setVisible(description_visible)
        
        # Общий ожидаемый результат
        if hasattr(self, 'expected_result_group'):
            expected_result_visible = self._visibility_settings.get('expected_result', True)
            self.expected_result_group.setVisible(expected_result_visible)
        
        # Если все элементы из основной информации скрыты, скрываем всю группу
        if hasattr(self, 'main_info_group'):
            main_info_visible = (
                self._visibility_settings.get('id', True) or
                self._visibility_settings.get('created', True) or
                self._visibility_settings.get('updated', True) or
                self._visibility_settings.get('author', True) or
                self._visibility_settings.get('owner', True) or
                self._visibility_settings.get('reviewer', True) or
                self._visibility_settings.get('status', True) or
                self._visibility_settings.get('test_layer', True) or
                self._visibility_settings.get('test_type', True) or
                self._visibility_settings.get('severity', True) or
                self._visibility_settings.get('priority', True) or
                self._visibility_settings.get('environment', True) or
                self._visibility_settings.get('browser', True) or
                self._visibility_settings.get('test_case_id', True) or
                self._visibility_settings.get('issue_links', True) or
                self._visibility_settings.get('test_case_links', True)
            )
            self.main_info_group.setVisible(main_info_visible)
    
    def _set_container_visibility(self, container_attr_name: str, setting_key: str):
        """Установить видимость контейнера с виджетом и его подписью"""
        if not hasattr(self, container_attr_name):
            return
        
        container = getattr(self, container_attr_name)
        if not container:
            return
        
        visible = self._visibility_settings.get(setting_key, True)
        
        # Скрываем/показываем все виджеты в контейнере
        for i in range(container.count()):
            item = container.itemAt(i)
            if item and item.widget():
                item.widget().setVisible(visible)

