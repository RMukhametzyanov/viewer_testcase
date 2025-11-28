"""Панель фильтров для тест-кейсов"""

import json
from pathlib import Path
from typing import Optional, Dict, List, Set
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QScrollArea,
    QFrame,
    QGroupBox,
    QMenu,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

from ...models.test_case import TestCase
from ...utils.resource_path import get_icon_path, get_icons_dir
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
        
        # Определяем все доступные поля для фильтрации
        self._all_fields = {
            "author": "Автор",
            "owner": "Исполнитель",
            "reviewer": "Ревьювер",
            "status": "Статус",
            "resolved": "Resolved",
            "test_layer": "Test Layer",
            "test_type": "Тип теста",
            "severity": "Severity",
            "priority": "Priority",
            "environment": "Окружение",
            "browser": "Браузер",
            "test_case_id": "Test Case ID",
            "issue_links": "Issue Links",
            "test_case_links": "TC Links",
            "epic": "Epic",
            "feature": "Feature",
            "story": "Story",
            "component": "Component",
            "tags": "Теги",
        }
        
        # Поля, которые показываются по умолчанию
        self._default_fields = ["author", "owner", "reviewer", "status", "resolved"]
        
        # Отслеживаем видимые поля
        self._visible_fields: Set[str] = set(self._default_fields)
        
        # Хранилище виджетов для каждого поля
        self._field_widgets: Dict[str, CheckboxComboBox] = {}
        
        # Основной контейнер для полей
        self._fields_container: Optional[QWidget] = None
        self._fields_layout: Optional[QVBoxLayout] = None
        
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
        
        # Загружаем маппинг иконок
        icon_mapping = self._load_icon_mapping()
        
        # Размер кнопок соответствует размеру заголовка (font-size: 16px обычно дает высоту ~24px)
        button_size = 28  # Немного больше заголовка для лучшей видимости
        icon_size = 20  # Размер иконки внутри кнопки
        
        # Базовый стиль для кнопок с иконками
        base_button_style = f"""
            QToolButton {{
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
                min-width: {button_size}px;
                max-width: {button_size}px;
                min-height: {button_size}px;
                max-height: {button_size}px;
            }}
            QToolButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.2);
            }}
        """
        
        # Стиль для кнопки "Применить" с зеленой обводкой при hover
        apply_button_style = f"""
            QToolButton {{
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
                min-width: {button_size}px;
                max-width: {button_size}px;
                min-height: {button_size}px;
                max-height: {button_size}px;
            }}
            QToolButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid #4CAF50;
            }}
        """
        
        # Кнопка добавления полей
        add_icon_name = icon_mapping.get("add_field", "plus.svg")
        self.add_field_button = QToolButton()
        add_icon = self._load_svg_icon(add_icon_name, size=icon_size, color="#ffffff")
        if add_icon:
            self.add_field_button.setIcon(add_icon)
            self.add_field_button.setIconSize(QSize(icon_size, icon_size))
        self.add_field_button.setToolTip("Добавить поле")
        self.add_field_button.setCursor(Qt.PointingHandCursor)
        self.add_field_button.setAutoRaise(True)
        self.add_field_button.setFixedSize(button_size, button_size)
        self.add_field_button.setStyleSheet(base_button_style)
        self.add_field_button.clicked.connect(self._show_add_field_menu)
        header_layout.addWidget(self.add_field_button)
        
        # Кнопка применения фильтров
        apply_icon_name = icon_mapping.get("apply", "play.svg")
        self.apply_button = QToolButton()
        apply_icon = self._load_svg_icon(apply_icon_name, size=icon_size, color="#ffffff")
        if apply_icon:
            self.apply_button.setIcon(apply_icon)
            self.apply_button.setIconSize(QSize(icon_size, icon_size))
        self.apply_button.setToolTip("Применить")
        self.apply_button.setCursor(Qt.PointingHandCursor)
        self.apply_button.setAutoRaise(True)
        self.apply_button.setFixedSize(button_size, button_size)
        self.apply_button.setStyleSheet(apply_button_style)
        self.apply_button.clicked.connect(self._on_apply_clicked)
        header_layout.addWidget(self.apply_button)
        
        # Кнопка сброса фильтров
        reset_icon_name = icon_mapping.get("reset", "refresh-ccw.svg")
        self.reset_button = QToolButton()
        reset_icon = self._load_svg_icon(reset_icon_name, size=icon_size, color="#ffffff")
        if reset_icon:
            self.reset_button.setIcon(reset_icon)
            self.reset_button.setIconSize(QSize(icon_size, icon_size))
        self.reset_button.setToolTip("Сбросить")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.setAutoRaise(True)
        self.reset_button.setFixedSize(button_size, button_size)
        self.reset_button.setStyleSheet(base_button_style)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        header_layout.addWidget(self.reset_button)
        content_layout.addLayout(header_layout)
        
        # Контейнер для полей фильтрации
        self._fields_container = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_container)
        self._fields_layout.setSpacing(UI_METRICS.section_spacing)
        self._fields_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._fields_container)
        
        # Создаем виджеты для всех полей (но не добавляем их в UI)
        for field_key in self._all_fields.keys():
            widget = self._create_list_widget()
            self._field_widgets[field_key] = widget
        
        # Показываем только поля по умолчанию
        self._update_visible_fields()
        
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Заполняем списки
        self._populate_all_lists()
    
    def _show_add_field_menu(self):
        """Показать меню для добавления полей"""
        menu = QMenu(self)
        
        # Добавляем только те поля, которые еще не видны
        for field_key, field_label in self._all_fields.items():
            if field_key not in self._visible_fields:
                action = menu.addAction(field_label)
                # Используем замыкание для правильного захвата переменной
                def make_handler(key):
                    return lambda checked: self._add_field(key)
                action.triggered.connect(make_handler(field_key))
        
        if menu.isEmpty():
            # Если все поля уже добавлены, показываем сообщение
            no_action = menu.addAction("Все поля уже добавлены")
            no_action.setEnabled(False)
        
        # Показываем меню под кнопкой
        button_pos = self.add_field_button.mapToGlobal(self.add_field_button.rect().bottomLeft())
        menu.exec_(button_pos)
    
    def _add_field(self, field_key: str):
        """Добавить поле в форму"""
        if field_key not in self._visible_fields:
            self._visible_fields.add(field_key)
            self._update_visible_fields()
    
    def _remove_field(self, field_key: str):
        """Удалить поле из формы"""
        if field_key in self._visible_fields and field_key not in self._default_fields:
            self._visible_fields.remove(field_key)
            self._update_visible_fields()
    
    def _update_visible_fields(self):
        """Обновить видимые поля в UI"""
        # Очищаем контейнер
        while self._fields_layout.count():
            child = self._fields_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Группируем поля для лучшей организации
        groups = {
            "Люди": ["author", "owner", "reviewer"],
            "Статус": ["status", "resolved"],
            "Дополнительно": []
        }
        
        # Распределяем остальные поля в группу "Дополнительно"
        for field_key in self._visible_fields:
            if field_key not in groups["Люди"] and field_key not in groups["Статус"]:
                groups["Дополнительно"].append(field_key)
        
        # Создаем группы и добавляем поля
        for group_title, field_keys in groups.items():
            if not field_keys:
                continue
            
            # Создаем группу
            group = QGroupBox(group_title)
            grid = QGridLayout(group)
            grid.setSpacing(UI_METRICS.base_spacing)
            grid.setContentsMargins(
                UI_METRICS.container_padding,
                UI_METRICS.group_title_spacing,
                UI_METRICS.container_padding,
                UI_METRICS.base_spacing,
            )
            
            # Добавляем поля в группу
            for idx, field_key in enumerate(field_keys):
                if field_key in self._field_widgets:
                    widget = self._field_widgets[field_key]
                    label_text = f"{self._all_fields[field_key]}:"
                    
                    # Создаем контейнер для поля с возможностью удаления
                    field_container = QWidget()
                    field_layout = QVBoxLayout(field_container)
                    field_layout.setContentsMargins(0, 0, 0, 0)
                    field_layout.setSpacing(4)
                    
                    # Заголовок с кнопкой удаления (если не поле по умолчанию)
                    header_layout = QHBoxLayout()
                    label = QLabel(label_text)
                    header_layout.addWidget(label)
                    header_layout.addStretch()
                    
                    # Кнопка удаления только для необязательных полей
                    if field_key not in self._default_fields:
                        # Минималистичный стиль, аналогичный кнопке удаления шага
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
                        
                        remove_button = QToolButton()
                        remove_button.setFixedSize(24, 24)
                        remove_button.setAutoRaise(True)
                        remove_button.setCursor(Qt.PointingHandCursor)
                        remove_button.setToolTip("Удалить поле")
                        
                        # Загружаем иконку x.svg (цвет как у текста - серый)
                        remove_icon = self._load_svg_icon("x.svg", size=16, color="#95a5a6")
                        if remove_icon:
                            remove_button.setIcon(remove_icon)
                            remove_button.setIconSize(QSize(16, 16))
                        else:
                            remove_button.setText("×")
                        
                        remove_button.setStyleSheet(action_button_style)
                        
                        # Используем замыкание для правильного захвата переменной
                        def make_remove_handler(key):
                            return lambda checked: self._remove_field(key)
                        remove_button.clicked.connect(make_remove_handler(field_key))
                        header_layout.addWidget(remove_button)
                    
                    field_layout.addLayout(header_layout)
                    field_layout.addWidget(widget)
                    
                    # Добавляем в сетку (2 колонки)
                    row = idx // 2
                    col = idx % 2
                    grid.addWidget(field_container, row, col)
            
            self._fields_layout.addWidget(group)
        
        self._fields_layout.addStretch()
    
    def _load_icon_mapping(self) -> Dict[str, str]:
        """Загрузить маппинг иконок для панели фильтров из JSON файла."""
        mapping_file = get_icons_dir() / "icon_mapping.json"
        
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'filter_panel' in data:
                        return data.get('filter_panel', {})
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка загрузки маппинга иконок: {e}")
        
        # Возвращаем значения по умолчанию
        return {
            "add_field": "plus.svg",
            "apply": "play.svg",
            "reset": "refresh-ccw.svg"
        }
    
    def _load_svg_icon(self, icon_name: str, size: int = 16, color: Optional[str] = None) -> Optional[QIcon]:
        """Загрузить SVG иконку из файла и вернуть QIcon."""
        icon_path = get_icon_path(icon_name)
        
        if not icon_path.exists():
            return None
        
        try:
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            if color:
                svg_content = svg_content.replace('currentColor', color)
                svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{color}"')
                svg_content = svg_content.replace('fill="currentColor"', f'fill="{color}"')
            
            renderer = QSvgRenderer(svg_content.encode('utf-8'))
            if not renderer.isValid():
                return None
            
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            renderer.render(painter)
            painter.end()
            
            return QIcon(pixmap)
        except Exception:
            return None
    
    def _create_list_widget(self) -> CheckboxComboBox:
        """Создать выпадающий список с чекбоксами"""
        combo = CheckboxComboBox()
        return combo
    
    def _populate_all_lists(self):
        """Заполнить все списки значениями из тест-кейсов"""
        # Словарь для хранения значений каждого поля
        field_values: Dict[str, Set[str]] = {key: set() for key in self._all_fields.keys()}
        
        for test_case in self._test_cases:
            # Автор
            if test_case.author:
                field_values["author"].add(test_case.author.strip())
            else:
                field_values["author"].add("пусто")
            
            # Владелец
            if test_case.owner:
                field_values["owner"].add(test_case.owner.strip())
            else:
                field_values["owner"].add("пусто")
            
            # Ревьювер
            if test_case.reviewer:
                field_values["reviewer"].add(test_case.reviewer.strip())
            else:
                field_values["reviewer"].add("пусто")
            
            # Статус
            if test_case.status:
                field_values["status"].add(test_case.status.strip())
            else:
                field_values["status"].add("пусто")
            
            # Test Layer
            if test_case.test_layer:
                field_values["test_layer"].add(test_case.test_layer.strip())
            else:
                field_values["test_layer"].add("пусто")
            
            # Test Type
            if test_case.test_type:
                field_values["test_type"].add(test_case.test_type.strip())
            else:
                field_values["test_type"].add("пусто")
            
            # Severity
            if test_case.severity:
                field_values["severity"].add(test_case.severity.strip())
            else:
                field_values["severity"].add("пусто")
            
            # Priority
            if test_case.priority:
                field_values["priority"].add(test_case.priority.strip())
            else:
                field_values["priority"].add("пусто")
            
            # Environment
            if test_case.environment:
                field_values["environment"].add(test_case.environment.strip())
            else:
                field_values["environment"].add("пусто")
            
            # Browser
            if test_case.browser:
                field_values["browser"].add(test_case.browser.strip())
            else:
                field_values["browser"].add("пусто")
            
            # Test Case ID
            if test_case.test_case_id:
                field_values["test_case_id"].add(test_case.test_case_id.strip())
            else:
                field_values["test_case_id"].add("пусто")
            
            # Issue Links
            if test_case.issue_links:
                field_values["issue_links"].add(test_case.issue_links.strip())
            else:
                field_values["issue_links"].add("пусто")
            
            # Test Case Links
            if test_case.test_case_links:
                field_values["test_case_links"].add(test_case.test_case_links.strip())
            else:
                field_values["test_case_links"].add("пусто")
            
            # Epic
            if test_case.epic:
                field_values["epic"].add(test_case.epic.strip())
            else:
                field_values["epic"].add("пусто")
            
            # Feature
            if test_case.feature:
                field_values["feature"].add(test_case.feature.strip())
            else:
                field_values["feature"].add("пусто")
            
            # Story
            if test_case.story:
                field_values["story"].add(test_case.story.strip())
            else:
                field_values["story"].add("пусто")
            
            # Component
            if test_case.component:
                field_values["component"].add(test_case.component.strip())
            else:
                field_values["component"].add("пусто")
            
            # Tags
            if test_case.tags:
                for tag in test_case.tags:
                    if tag and tag.strip():
                        field_values["tags"].add(tag.strip())
            else:
                field_values["tags"].add("пусто")
            
            # Resolved - собираем из notes
            if test_case.notes:
                for note_data in test_case.notes.values():
                    if isinstance(note_data, dict):
                        resolved = note_data.get("resolved", "new")
                        if resolved:
                            field_values["resolved"].add(resolved.strip())
            else:
                field_values["resolved"].add("пусто")
        
        # Заполняем списки для всех полей
        for field_key, widget in self._field_widgets.items():
            if field_key == "resolved":
                # Для resolved всегда показываем все возможные значения
                resolved_to_show = ["new", "fixed", "closed"]
                if "пусто" in field_values["resolved"]:
                    resolved_to_show.append("пусто")
                self._populate_list(widget, resolved_to_show)
            else:
                self._populate_list(widget, sorted(field_values[field_key]))
    
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
        
        # Собираем фильтры только для видимых полей
        for field_key in self._visible_fields:
            if field_key in self._field_widgets:
                widget = self._field_widgets[field_key]
                selected = self._get_selected_values(widget)
                if selected is not None:
                    filters[field_key] = selected
        
        self._current_filters = filters
        self.filters_applied.emit(filters)
    
    def _on_reset_clicked(self):
        """Обработчик нажатия Сбросить"""
        # Сбрасываем все чекбоксы для всех виджетов
        for widget in self._field_widgets.values():
            widget.clearSelection()
        
        self._current_filters = {}
        self.filters_reset.emit()

