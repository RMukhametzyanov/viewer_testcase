"""Панель фильтров для тест-кейсов"""

from typing import Optional, Dict, List, Set
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QFrame,
    QGroupBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from ...models.test_case import TestCase
from ..styles.ui_metrics import UI_METRICS
from ..styles.theme_provider import THEME_PROVIDER
from .checkbox_combo import CheckboxComboBox


class FilterPanel(QWidget):
    """Панель фильтров для тест-кейсов"""
    
    filters_applied = pyqtSignal(dict)  # Сигнал с примененными фильтрами
    filters_reset = pyqtSignal()  # Сигнал сброса фильтров
    
    def __init__(self, parent: Optional[QWidget] = None, test_cases: Optional[List[TestCase]] = None):
        super().__init__(parent)
        self._test_cases = test_cases or []
        self._current_filters: Dict[str, any] = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """Настройка UI панели фильтров"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(UI_METRICS.base_spacing)
        
        # Scrollable область
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
        
        # Заголовок с кнопками
        header_layout = QHBoxLayout()
        title = QLabel("Фильтры")
        title.setStyleSheet("font-weight: 600; font-size: 16px;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        self.apply_button = QPushButton("Применить")
        self.apply_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.apply_button.clicked.connect(self._on_apply_clicked)
        
        self.reset_button = QPushButton("Сбросить")
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: #666;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        
        header_layout.addWidget(self.apply_button)
        header_layout.addWidget(self.reset_button)
        content_layout.addLayout(header_layout)
        
        # Группа: Люди
        people_group = self._create_group("Люди", 3)
        self.author_list = self._create_list_widget()
        self._add_filter_to_group(people_group, "Автор:", self.author_list)
        self.owner_list = self._create_list_widget()
        self._add_filter_to_group(people_group, "Владелец:", self.owner_list)
        self.reviewer_list = self._create_list_widget()
        self._add_filter_to_group(people_group, "Ревьюер:", self.reviewer_list)
        content_layout.addWidget(people_group)
        
        # Группа: Статус и тип
        status_group = self._create_group("Статус и тип", 3)
        self.status_list = self._create_list_widget()
        self._add_filter_to_group(status_group, "Статус:", self.status_list)
        self.test_layer_list = self._create_list_widget()
        self._add_filter_to_group(status_group, "Test Layer:", self.test_layer_list)
        self.test_type_list = self._create_list_widget()
        self._add_filter_to_group(status_group, "Тип теста:", self.test_type_list)
        content_layout.addWidget(status_group)
        
        # Группа: Приоритеты
        priority_group = self._create_group("Приоритеты", 2)
        self.severity_list = self._create_list_widget()
        self._add_filter_to_group(priority_group, "Severity:", self.severity_list)
        self.priority_list = self._create_list_widget()
        self._add_filter_to_group(priority_group, "Priority:", self.priority_list)
        content_layout.addWidget(priority_group)
        
        # Группа: Окружение
        env_group = self._create_group("Окружение", 2)
        self.environment_list = self._create_list_widget()
        self._add_filter_to_group(env_group, "Окружение:", self.environment_list)
        self.browser_list = self._create_list_widget()
        self._add_filter_to_group(env_group, "Браузер:", self.browser_list)
        content_layout.addWidget(env_group)
        
        # Группа: Ссылки
        links_group = self._create_group("Ссылки", 3)
        self.test_case_id_list = self._create_list_widget()
        self._add_filter_to_group(links_group, "Test Case ID:", self.test_case_id_list)
        self.issue_links_list = self._create_list_widget()
        self._add_filter_to_group(links_group, "Issue Links:", self.issue_links_list)
        self.test_case_links_list = self._create_list_widget()
        self._add_filter_to_group(links_group, "TC Links:", self.test_case_links_list)
        content_layout.addWidget(links_group)
        
        # Группа: Контекст
        context_group = self._create_group("Контекст", 4)
        self.epic_list = self._create_list_widget()
        self._add_filter_to_group(context_group, "Epic:", self.epic_list)
        self.feature_list = self._create_list_widget()
        self._add_filter_to_group(context_group, "Feature:", self.feature_list)
        self.story_list = self._create_list_widget()
        self._add_filter_to_group(context_group, "Story:", self.story_list)
        self.component_list = self._create_list_widget()
        self._add_filter_to_group(context_group, "Component:", self.component_list)
        content_layout.addWidget(context_group)
        
        # Группа: Теги и текст
        text_group = self._create_group("Теги и текст", 2)
        self.tags_list = self._create_list_widget()
        self._add_filter_to_group(text_group, "Теги:", self.tags_list)
        
        description_layout = QVBoxLayout()
        description_label = QLabel("Описание (поиск):")
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Введите слово или часть слова...")
        description_layout.addWidget(description_label)
        description_layout.addWidget(self.description_input)
        description_widget = QWidget()
        description_widget.setLayout(description_layout)
        text_group._grid_layout.addWidget(description_widget, 0, 1)
        content_layout.addWidget(text_group)
        
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Заполняем списки
        self._populate_all_lists()
    
    def _create_group(self, title: str, columns: int) -> QGroupBox:
        """Создать группу с сеткой"""
        group = QGroupBox(title)
        grid = QGridLayout(group)
        grid.setSpacing(UI_METRICS.base_spacing)
        grid.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.group_title_spacing,
            UI_METRICS.container_padding,
            UI_METRICS.base_spacing,
        )
        group._grid_layout = grid  # Сохраняем ссылку на layout
        group._columns = columns  # Сохраняем количество колонок
        return group
    
    def _add_filter_to_group(self, group: QGroupBox, label_text: str, widget: QWidget):
        """Добавить фильтр в группу"""
        layout = group._grid_layout
        columns = group._columns
        current_count = layout.count()
        row = current_count // columns
        col = current_count % columns
        
        label = QLabel(label_text)
        label_widget = QWidget()
        label_layout = QVBoxLayout(label_widget)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(4)
        label_layout.addWidget(label)
        label_layout.addWidget(widget)
        
        layout.addWidget(label_widget, row, col)
    
    def _create_list_widget(self) -> CheckboxComboBox:
        """Создать выпадающий список с чекбоксами"""
        combo = CheckboxComboBox()
        return combo
    
    def _populate_all_lists(self):
        """Заполнить все списки значениями из тест-кейсов"""
        # Собираем уникальные значения для каждого поля
        authors = set()
        owners = set()
        reviewers = set()
        statuses = set()
        test_layers = set()
        test_types = set()
        severities = set()
        priorities = set()
        environments = set()
        browsers = set()
        test_case_ids = set()
        issue_links = set()
        test_case_links = set()
        epics = set()
        features = set()
        stories = set()
        components = set()
        tags = set()
        
        for test_case in self._test_cases:
            if test_case.author:
                authors.add(test_case.author.strip())
            else:
                authors.add("пусто")
            
            if hasattr(test_case, 'owner') and test_case.owner:
                owners.add(test_case.owner.strip())
            else:
                owners.add("пусто")
            
            if hasattr(test_case, 'reviewer') and test_case.reviewer:
                reviewers.add(test_case.reviewer.strip())
            else:
                reviewers.add("пусто")
            
            if test_case.status:
                statuses.add(test_case.status.strip())
            else:
                statuses.add("пусто")
            
            if hasattr(test_case, 'test_layer') and test_case.test_layer:
                test_layers.add(test_case.test_layer.strip())
            else:
                test_layers.add("пусто")
            
            if hasattr(test_case, 'test_type') and test_case.test_type:
                test_types.add(test_case.test_type.strip())
            else:
                test_types.add("пусто")
            
            if hasattr(test_case, 'severity') and test_case.severity:
                severities.add(test_case.severity.strip())
            else:
                severities.add("пусто")
            
            if hasattr(test_case, 'priority') and test_case.priority:
                priorities.add(test_case.priority.strip())
            else:
                priorities.add("пусто")
            
            if hasattr(test_case, 'environment') and test_case.environment:
                environments.add(test_case.environment.strip())
            else:
                environments.add("пусто")
            
            if hasattr(test_case, 'browser') and test_case.browser:
                browsers.add(test_case.browser.strip())
            else:
                browsers.add("пусто")
            
            if hasattr(test_case, 'test_case_id') and test_case.test_case_id:
                test_case_ids.add(test_case.test_case_id.strip())
            else:
                test_case_ids.add("пусто")
            
            if hasattr(test_case, 'issue_links') and test_case.issue_links:
                issue_links.add(test_case.issue_links.strip())
            else:
                issue_links.add("пусто")
            
            if hasattr(test_case, 'test_case_links') and test_case.test_case_links:
                test_case_links.add(test_case.test_case_links.strip())
            else:
                test_case_links.add("пусто")
            
            if hasattr(test_case, 'epic') and test_case.epic:
                epics.add(test_case.epic.strip())
            else:
                epics.add("пусто")
            
            if hasattr(test_case, 'feature') and test_case.feature:
                features.add(test_case.feature.strip())
            else:
                features.add("пусто")
            
            if hasattr(test_case, 'story') and test_case.story:
                stories.add(test_case.story.strip())
            else:
                stories.add("пусто")
            
            if hasattr(test_case, 'component') and test_case.component:
                components.add(test_case.component.strip())
            else:
                components.add("пусто")
            
            if test_case.tags:
                for tag in test_case.tags:
                    if tag and tag.strip():
                        tags.add(tag.strip())
            else:
                tags.add("пусто")
        
        # Заполняем списки
        self._populate_list(self.author_list, sorted(authors))
        self._populate_list(self.owner_list, sorted(owners))
        self._populate_list(self.reviewer_list, sorted(reviewers))
        self._populate_list(self.status_list, sorted(statuses))
        self._populate_list(self.test_layer_list, sorted(test_layers))
        self._populate_list(self.test_type_list, sorted(test_types))
        self._populate_list(self.severity_list, sorted(severities))
        self._populate_list(self.priority_list, sorted(priorities))
        self._populate_list(self.environment_list, sorted(environments))
        self._populate_list(self.browser_list, sorted(browsers))
        self._populate_list(self.test_case_id_list, sorted(test_case_ids))
        self._populate_list(self.issue_links_list, sorted(issue_links))
        self._populate_list(self.test_case_links_list, sorted(test_case_links))
        self._populate_list(self.epic_list, sorted(epics))
        self._populate_list(self.feature_list, sorted(features))
        self._populate_list(self.story_list, sorted(stories))
        self._populate_list(self.component_list, sorted(components))
        self._populate_list(self.tags_list, sorted(tags))
    
    def _populate_list(self, combo: CheckboxComboBox, values: List[str]):
        """Заполнить список значениями"""
        combo.setValues(values)
    
    def update_test_cases(self, test_cases: List[TestCase]):
        """Обновить список тест-кейсов и перезаполнить списки"""
        self._test_cases = test_cases
        self._populate_all_lists()
    
    def _get_selected_values(self, combo: CheckboxComboBox) -> List[str]:
        """Получить выбранные значения из списка"""
        selected = combo.getSelectedValues()
        return selected if selected else None
    
    def _on_apply_clicked(self):
        """Обработчик нажатия Применить"""
        filters = {}
        
        # Собираем все фильтры
        author = self._get_selected_values(self.author_list)
        if author is not None:
            filters["author"] = author
        
        owner = self._get_selected_values(self.owner_list)
        if owner is not None:
            filters["owner"] = owner
        
        reviewer = self._get_selected_values(self.reviewer_list)
        if reviewer is not None:
            filters["reviewer"] = reviewer
        
        status = self._get_selected_values(self.status_list)
        if status is not None:
            filters["status"] = status
        
        test_layer = self._get_selected_values(self.test_layer_list)
        if test_layer is not None:
            filters["test_layer"] = test_layer
        
        test_type = self._get_selected_values(self.test_type_list)
        if test_type is not None:
            filters["test_type"] = test_type
        
        severity = self._get_selected_values(self.severity_list)
        if severity is not None:
            filters["severity"] = severity
        
        priority = self._get_selected_values(self.priority_list)
        if priority is not None:
            filters["priority"] = priority
        
        environment = self._get_selected_values(self.environment_list)
        if environment is not None:
            filters["environment"] = environment
        
        browser = self._get_selected_values(self.browser_list)
        if browser is not None:
            filters["browser"] = browser
        
        test_case_id = self._get_selected_values(self.test_case_id_list)
        if test_case_id is not None:
            filters["test_case_id"] = test_case_id
        
        issue_links = self._get_selected_values(self.issue_links_list)
        if issue_links is not None:
            filters["issue_links"] = issue_links
        
        test_case_links = self._get_selected_values(self.test_case_links_list)
        if test_case_links is not None:
            filters["test_case_links"] = test_case_links
        
        epic = self._get_selected_values(self.epic_list)
        if epic is not None:
            filters["epic"] = epic
        
        feature = self._get_selected_values(self.feature_list)
        if feature is not None:
            filters["feature"] = feature
        
        story = self._get_selected_values(self.story_list)
        if story is not None:
            filters["story"] = story
        
        component = self._get_selected_values(self.component_list)
        if component is not None:
            filters["component"] = component
        
        tags = self._get_selected_values(self.tags_list)
        if tags is not None:
            filters["tags"] = tags
        
        description = self.description_input.text().strip()
        if description:
            filters["description"] = description
        
        self._current_filters = filters
        self.filters_applied.emit(filters)
    
    def _on_reset_clicked(self):
        """Обработчик нажатия Сбросить"""
        # Сбрасываем все чекбоксы
        for combo in [
            self.author_list, self.owner_list, self.reviewer_list,
            self.status_list, self.test_layer_list, self.test_type_list,
            self.severity_list, self.priority_list,
            self.environment_list, self.browser_list,
            self.test_case_id_list, self.issue_links_list, self.test_case_links_list,
            self.epic_list, self.feature_list, self.story_list, self.component_list,
            self.tags_list
        ]:
            combo.clearSelection()
        
        self.description_input.clear()
        self._current_filters = {}
        self.filters_reset.emit()

