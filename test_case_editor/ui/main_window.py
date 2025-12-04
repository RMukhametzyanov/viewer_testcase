"""Главное окно приложения"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Dict

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QFileDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedLayout,
    QInputDialog,
    QDialog,
    QTextEdit,
    QDialogButtonBox,
    QAction,
    QActionGroup,
    QMenu,
    QToolButton,
    QToolBar,
    QComboBox,
    QSpinBox,
    QGroupBox,
    QScrollArea,
    QTabWidget,
    QFontComboBox,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QCheckBox,
    QButtonGroup,
    QSizePolicy,
    QShortcut,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QStringListModel, QSortFilterProxyModel, QRegularExpression, QTimer, QEvent, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QKeySequence
from PyQt5.QtSvg import QSvgRenderer

from ..models.test_case import TestCase
from ..services.test_case_service import TestCaseService
from ..repositories.test_case_repository import TestCaseRepository
from .widgets.placeholder_widget import PlaceholderWidget
from .widgets.tree_widget import TestCaseTreeWidget
from .widgets.form_widget import TestCaseFormWidget
from .widgets.auxiliary_panel import AuxiliaryPanel
from .widgets.toggle_switch import ToggleSwitch
from .widgets.filter_panel import FilterPanel
from ..utils import llm
from ..utils.prompt_builder import build_review_prompt, build_creation_prompt
from ..utils.list_models import fetch_models as fetch_llm_models
from ..utils.settings_path import get_settings_path
from ..utils.allure_generator import generate_allure_report
from ..utils.html_report_generator import generate_html_report
from ..utils.resource_path import get_icon_path, get_icons_dir
from .styles.ui_metrics import UI_METRICS
from .styles.app_theme import build_app_style_sheet
from .styles.theme_provider import THEME_PROVIDER, ThemeProvider


class GitCommitDialog(QDialog):
    """Диалог для ввода комментария git-коммита."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Git commit")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        label = QLabel("Введите комментарий к коммиту:")
        label.setWordWrap(True)
        layout.addWidget(label)

        self.comment_edit = QTextEdit(self)
        self.comment_edit.setPlaceholderText("Комментарий обязателен…")
        self.comment_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.comment_edit)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        self.ok_button = self.button_box.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _on_text_changed(self):
        text = self.get_comment().strip()
        self.ok_button.setEnabled(bool(text))

    def get_comment(self) -> str:
        return self.comment_edit.toPlainText()


class SettingsDialog(QDialog):
    """Диалог настроек приложения."""

    def __init__(self, settings: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setMinimumSize(700, 600)
        self.parent_window = parent  # Сохраняем ссылку на главное окно для доступа к методам загрузки моделей
        
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Настройка UI с горизонтальной навигацией (список слева, контент справа)"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(UI_METRICS.base_spacing)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Горизонтальный layout: список слева, контент справа
        content_layout = QHBoxLayout()
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Список навигации слева
        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(200)
        self.nav_list.setMinimumWidth(180)
        self.nav_list.setSpacing(4)
        
        # StackedWidget для контента справа
        self.content_stack = QStackedWidget()
        
        # Добавляем разделы
        sections = [
            ("Общие", "general"),
            ("LLM", "llm"),
            ("Промпты", "prompts"),
            ("Панели", "panels"),
            ("Внешний вид", "appearance"),
            ("Панель Информация", "information_panel"),
            ("Импорт", "import"),
        ]
        
        self.section_widgets = {}
        for name, key in sections:
            # Добавляем в список навигации
            item = QListWidgetItem(name)
            self.nav_list.addItem(item)
            
            # Создаем и добавляем контент
            if key == "general":
                widget = self._create_general_tab()
            elif key == "llm":
                widget = self._create_llm_tab()
            elif key == "prompts":
                widget = self._create_prompts_tab()
            elif key == "panels":
                widget = self._create_panels_tab()
            elif key == "appearance":
                widget = self._create_appearance_tab()
            elif key == "information_panel":
                widget = self._create_information_panel_tab()
            elif key == "import":
                widget = self._create_import_tab()
            else:
                widget = QWidget()
            
            index = self.content_stack.addWidget(widget)
            self.section_widgets[key] = index
        
        # Подключаем переключение
        self.nav_list.currentRowChanged.connect(self.content_stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)
        
        content_layout.addWidget(self.nav_list)
        content_layout.addWidget(self.content_stack, 1)  # Контент растягивается
        
        main_layout.addLayout(content_layout)

        # Кнопки внизу
        button_layout = QHBoxLayout()
        
        # Кнопка для открытия settings.json в проводнике
        open_settings_btn = QPushButton("Открыть settings.json")
        open_settings_btn.clicked.connect(self._open_settings_file_in_explorer)
        button_layout.addWidget(open_settings_btn)
        
        button_layout.addStretch()
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        button_box.accepted.connect(self._save_and_accept)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)
        main_layout.addLayout(button_layout)

    def _create_general_tab(self) -> QWidget:
        """Создать вкладку общих настроек"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(UI_METRICS.base_spacing)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(UI_METRICS.section_spacing)
        
        # Название проекта
        project_group = QGroupBox("Название проекта")
        project_layout = QVBoxLayout()
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("Введите название проекта")
        project_layout.addWidget(self.project_name_edit)
        project_group.setLayout(project_layout)
        content_layout.addWidget(project_group)
        
        # Список тестировщиков
        testers_group = QGroupBox("Тестировщики")
        testers_layout = QVBoxLayout()
        testers_label = QLabel("Введите список тестировщиков (каждый с новой строки):")
        self.testers_edit = QTextEdit()
        self.testers_edit.setPlaceholderText("Тестировщик 1\nТестировщик 2\nТестировщик 3")
        self.testers_edit.setMaximumHeight(150)
        testers_layout.addWidget(testers_label)
        testers_layout.addWidget(self.testers_edit)
        testers_group.setLayout(testers_layout)
        content_layout.addWidget(testers_group)
        
        # Папка с тест-кейсами
        test_cases_group = QGroupBox("Папка с тест-кейсами")
        test_cases_layout = QHBoxLayout()
        self.test_cases_dir_edit = QLineEdit()
        self.test_cases_dir_edit.setPlaceholderText("Путь к папке с тест-кейсами")
        test_cases_dir_btn = QPushButton("Обзор...")
        test_cases_dir_btn.clicked.connect(self._browse_test_cases_dir)
        test_cases_layout.addWidget(self.test_cases_dir_edit)
        test_cases_layout.addWidget(test_cases_dir_btn)
        test_cases_group.setLayout(test_cases_layout)
        content_layout.addWidget(test_cases_group)
        
        # Путь к методике
        methodic_group = QGroupBox("Путь к методике")
        methodic_layout = QHBoxLayout()
        self.methodic_path_edit = QLineEdit()
        self.methodic_path_edit.setPlaceholderText("Путь к файлу методики")
        methodic_path_btn = QPushButton("Обзор...")
        methodic_path_btn.clicked.connect(self._browse_methodic_path)
        methodic_layout.addWidget(self.methodic_path_edit)
        methodic_layout.addWidget(methodic_path_btn)
        methodic_group.setLayout(methodic_layout)
        content_layout.addWidget(methodic_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget

    def _create_llm_tab(self) -> QWidget:
        """Создать вкладку настроек LLM"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(UI_METRICS.base_spacing)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(UI_METRICS.section_spacing)
        
        # LLM Host
        host_group = QGroupBox("LLM Host")
        host_layout = QVBoxLayout()
        self.llm_host_edit = QLineEdit()
        self.llm_host_edit.setPlaceholderText("http://localhost:11434")
        self.llm_host_edit.textChanged.connect(self._on_llm_host_changed)
        host_layout.addWidget(self.llm_host_edit)
        host_group.setLayout(host_layout)
        content_layout.addWidget(host_group)
        
        # LLM Model - комбобокс для выбора модели
        model_group = QGroupBox("LLM Model")
        model_layout = QVBoxLayout()
        
        # Создаем модель для комбобокса
        self.llm_model_list_model = QStringListModel(self)
        self.llm_model_proxy_model = QSortFilterProxyModel(self)
        self.llm_model_proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.llm_model_proxy_model.setFilterKeyColumn(0)
        self.llm_model_proxy_model.setSourceModel(self.llm_model_list_model)
        
        self.llm_model_edit = QComboBox()
        self.llm_model_edit.setModel(self.llm_model_proxy_model)
        self.llm_model_edit.setEditable(True)
        self.llm_model_edit.setInsertPolicy(QComboBox.NoInsert)
        self.llm_model_edit.setMinimumWidth(200)
        self.llm_model_edit.currentTextChanged.connect(self._on_llm_model_changed)
        line_edit = self.llm_model_edit.lineEdit()
        if line_edit:
            line_edit.setPlaceholderText("Выберите модель…")
            line_edit.textEdited.connect(self._on_llm_model_text_edited)
            line_edit.editingFinished.connect(self._on_llm_model_editing_finished)
        
        # Кнопка обновления списка моделей
        refresh_btn = QPushButton("Обновить список")
        refresh_btn.clicked.connect(self._refresh_llm_models)
        
        model_btn_layout = QHBoxLayout()
        model_btn_layout.addWidget(self.llm_model_edit)
        model_btn_layout.addWidget(refresh_btn)
        
        model_layout.addLayout(model_btn_layout)
        model_group.setLayout(model_layout)
        content_layout.addWidget(model_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget

    def _create_prompts_tab(self) -> QWidget:
        """Создать вкладку настроек промптов"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(UI_METRICS.base_spacing)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(UI_METRICS.section_spacing)
        
        # Промпт для ревью
        review_group = QGroupBox("Промпт для ревью")
        review_layout = QVBoxLayout()
        self.review_prompt_edit = QTextEdit()
        self.review_prompt_edit.setPlaceholderText("Опиши, на что обратить внимание при ревью тест-кейсов.")
        self.review_prompt_edit.setMinimumHeight(100)
        review_layout.addWidget(self.review_prompt_edit)
        review_group.setLayout(review_layout)
        content_layout.addWidget(review_group)
        
        # Промпт для создания ТК
        create_group = QGroupBox("Промпт для создания тест-кейсов")
        create_layout = QVBoxLayout()
        self.create_prompt_edit = QTextEdit()
        self.create_prompt_edit.setPlaceholderText("Создай тест-кейсы...")
        self.create_prompt_edit.setMinimumHeight(100)
        create_layout.addWidget(self.create_prompt_edit)
        create_group.setLayout(create_layout)
        content_layout.addWidget(create_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget

    def _create_panels_tab(self) -> QWidget:
        """Создать вкладку настроек панелей"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(UI_METRICS.base_spacing)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(UI_METRICS.section_spacing)
        
        # Размеры панелей
        panels_group = QGroupBox("Размеры панелей (в пикселях)")
        panels_layout = QVBoxLayout()
        panels_layout.setSpacing(UI_METRICS.base_spacing)
        
        # Левая панель
        left_layout = QHBoxLayout()
        left_layout.addWidget(QLabel("Левая панель (дерево):"))
        self.left_panel_spin = QSpinBox()
        self.left_panel_spin.setMinimum(150)
        self.left_panel_spin.setMaximum(2000)
        self.left_panel_spin.setSuffix(" px")
        left_layout.addWidget(self.left_panel_spin)
        left_layout.addStretch()
        panels_layout.addLayout(left_layout)
        
        # Панель редактирования
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Панель редактирования:"))
        self.form_area_spin = QSpinBox()
        self.form_area_spin.setMinimum(300)
        self.form_area_spin.setMaximum(5000)
        self.form_area_spin.setSuffix(" px")
        form_layout.addWidget(self.form_area_spin)
        form_layout.addStretch()
        panels_layout.addLayout(form_layout)
        
        # Панель ревью
        review_layout = QHBoxLayout()
        review_layout.addWidget(QLabel("Панель ревью:"))
        self.review_panel_spin = QSpinBox()
        self.review_panel_spin.setMinimum(200)
        self.review_panel_spin.setMaximum(2000)
        self.review_panel_spin.setSuffix(" px")
        review_layout.addWidget(self.review_panel_spin)
        review_layout.addStretch()
        panels_layout.addLayout(review_layout)
        
        panels_group.setLayout(panels_layout)
        content_layout.addWidget(panels_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget

    def _create_appearance_tab(self) -> QWidget:
        """Создать вкладку настроек внешнего вида"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(UI_METRICS.base_spacing)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(UI_METRICS.section_spacing)
        
        # Тема
        theme_group = QGroupBox("Тема")
        theme_layout = QVBoxLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.setEditable(True)
        self.theme_combo.addItems(["light", "dark"])
        theme_layout.addWidget(self.theme_combo)
        theme_group.setLayout(theme_layout)
        content_layout.addWidget(theme_group)
        
        # Шрифт
        font_group = QGroupBox("Шрифт")
        font_layout = QVBoxLayout()
        font_layout.setSpacing(UI_METRICS.base_spacing)
        
        font_family_layout = QHBoxLayout()
        font_family_layout.addWidget(QLabel("Семейство шрифтов:"))
        self.font_family_combo = QFontComboBox()
        self.font_family_combo.setEditable(False)
        self.font_family_combo.setFontFilters(QFontComboBox.AllFonts)
        font_family_layout.addWidget(self.font_family_combo)
        font_layout.addLayout(font_family_layout)
        
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("Размер шрифта:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setMinimum(8)
        self.font_size_spin.setMaximum(24)
        self.font_size_spin.setSuffix(" pt")
        font_size_layout.addWidget(self.font_size_spin)
        font_size_layout.addStretch()
        font_layout.addLayout(font_size_layout)
        
        font_group.setLayout(font_layout)
        content_layout.addWidget(font_group)
        
        # Отступы
        padding_group = QGroupBox("Отступы и пробелы")
        padding_layout = QVBoxLayout()
        padding_layout.setSpacing(UI_METRICS.base_spacing)
        
        # Базовый отступ между элементами
        base_spacing_layout = QHBoxLayout()
        base_spacing_layout.addWidget(QLabel("Базовый отступ между элементами:"))
        self.base_spacing_spin = QSpinBox()
        self.base_spacing_spin.setMinimum(4)
        self.base_spacing_spin.setMaximum(32)
        self.base_spacing_spin.setSuffix(" px")
        self.base_spacing_spin.setToolTip("Стандартный промежуток между элементами интерфейса")
        base_spacing_layout.addWidget(self.base_spacing_spin)
        base_spacing_layout.addStretch()
        padding_layout.addLayout(base_spacing_layout)
        
        # Отступ между секциями
        section_spacing_layout = QHBoxLayout()
        section_spacing_layout.addWidget(QLabel("Отступ между секциями:"))
        self.section_spacing_spin = QSpinBox()
        self.section_spacing_spin.setMinimum(4)
        self.section_spacing_spin.setMaximum(32)
        self.section_spacing_spin.setSuffix(" px")
        self.section_spacing_spin.setToolTip("Вертикальные интервалы между большими секциями")
        section_spacing_layout.addWidget(self.section_spacing_spin)
        section_spacing_layout.addStretch()
        padding_layout.addLayout(section_spacing_layout)
        
        # Отступ контейнеров
        container_padding_layout = QHBoxLayout()
        container_padding_layout.addWidget(QLabel("Отступ контейнеров (панелей, групп):"))
        self.container_padding_spin = QSpinBox()
        self.container_padding_spin.setMinimum(4)
        self.container_padding_spin.setMaximum(32)
        self.container_padding_spin.setSuffix(" px")
        self.container_padding_spin.setToolTip("Внутренние отступы контейнеров (панелей, групп)")
        container_padding_layout.addWidget(self.container_padding_spin)
        container_padding_layout.addStretch()
        padding_layout.addLayout(container_padding_layout)
        
        # Отступы текстовых полей
        padding_text_layout = QHBoxLayout()
        padding_text_layout.addWidget(QLabel("Вертикальные отступы текстовых полей:"))
        self.text_padding_spin = QSpinBox()
        self.text_padding_spin.setMinimum(0)
        self.text_padding_spin.setMaximum(20)
        self.text_padding_spin.setSuffix(" px")
        self.text_padding_spin.setToolTip("Отступы сверху и снизу до текста в редактируемых полях (QLineEdit, QTextEdit)")
        padding_text_layout.addWidget(self.text_padding_spin)
        padding_text_layout.addStretch()
        padding_layout.addLayout(padding_text_layout)
        
        # Отступ заголовка QGroupBox
        group_title_spacing_layout = QHBoxLayout()
        group_title_spacing_layout.addWidget(QLabel("Отступ заголовка QGroupBox до содержимого:"))
        self.group_title_spacing_spin = QSpinBox()
        self.group_title_spacing_spin.setMinimum(0)
        self.group_title_spacing_spin.setMaximum(20)
        self.group_title_spacing_spin.setSuffix(" px")
        self.group_title_spacing_spin.setToolTip("Отступ от заголовка группы до внутренних элементов")
        group_title_spacing_layout.addWidget(self.group_title_spacing_spin)
        group_title_spacing_layout.addStretch()
        padding_layout.addLayout(group_title_spacing_layout)
        
        padding_group.setLayout(padding_layout)
        content_layout.addWidget(padding_group)
        
        # Счетчики в дереве
        tree_group = QGroupBox("Дерево элементов")
        tree_layout = QVBoxLayout()
        self.show_folder_counters_check = QCheckBox("Показывать счетчики JSON файлов в папках")
        self.show_folder_counters_check.setToolTip("Отображать количество JSON файлов в каждой папке дерева (например: Кандидаты (6))")
        tree_layout.addWidget(self.show_folder_counters_check)
        tree_group.setLayout(tree_layout)
        content_layout.addWidget(tree_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget

    def _create_information_panel_tab(self) -> QWidget:
        """Создать вкладку настроек панели Информация"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(UI_METRICS.base_spacing)
        layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(UI_METRICS.section_spacing)
        
        # Описание
        info_label = QLabel("Управление видимостью элементов в боковой панели 'Информация'")
        info_label.setWordWrap(True)
        content_layout.addWidget(info_label)
        
        # Основная информация
        main_info_group = QGroupBox("Основная информация")
        main_info_layout = QVBoxLayout()
        main_info_layout.setSpacing(UI_METRICS.base_spacing)
        
        # Метаданные - отдельные элементы
        self.info_id_check = QCheckBox("ID")
        main_info_layout.addWidget(self.info_id_check)
        self.info_created_check = QCheckBox("Создан")
        main_info_layout.addWidget(self.info_created_check)
        self.info_updated_check = QCheckBox("Обновлён")
        main_info_layout.addWidget(self.info_updated_check)
        
        main_info_layout.addSpacing(UI_METRICS.base_spacing // 2)
        
        # Люди - отдельные элементы
        self.info_author_check = QCheckBox("Автор")
        main_info_layout.addWidget(self.info_author_check)
        self.info_owner_check = QCheckBox("Владелец")
        main_info_layout.addWidget(self.info_owner_check)
        self.info_reviewer_check = QCheckBox("Ревьюер")
        main_info_layout.addWidget(self.info_reviewer_check)
        
        main_info_layout.addSpacing(UI_METRICS.base_spacing // 2)
        
        # Статус и тип - отдельные элементы
        self.info_status_check = QCheckBox("Статус")
        main_info_layout.addWidget(self.info_status_check)
        self.info_test_layer_check = QCheckBox("Test Layer")
        main_info_layout.addWidget(self.info_test_layer_check)
        self.info_test_type_check = QCheckBox("Тип теста")
        main_info_layout.addWidget(self.info_test_type_check)
        
        main_info_layout.addSpacing(UI_METRICS.base_spacing // 2)
        
        # Severity и Priority - отдельные элементы
        self.info_severity_check = QCheckBox("Severity")
        main_info_layout.addWidget(self.info_severity_check)
        self.info_priority_check = QCheckBox("Priority")
        main_info_layout.addWidget(self.info_priority_check)
        
        main_info_layout.addSpacing(UI_METRICS.base_spacing // 2)
        
        # Окружение и Браузер - отдельные элементы
        self.info_environment_check = QCheckBox("Окружение")
        main_info_layout.addWidget(self.info_environment_check)
        self.info_browser_check = QCheckBox("Браузер")
        main_info_layout.addWidget(self.info_browser_check)
        
        main_info_layout.addSpacing(UI_METRICS.base_spacing // 2)
        
        # Ссылки - отдельные элементы
        self.info_test_case_id_check = QCheckBox("Test Case ID")
        main_info_layout.addWidget(self.info_test_case_id_check)
        self.info_issue_links_check = QCheckBox("Issue Links")
        main_info_layout.addWidget(self.info_issue_links_check)
        self.info_test_case_links_check = QCheckBox("TC Links")
        main_info_layout.addWidget(self.info_test_case_links_check)
        
        main_info_group.setLayout(main_info_layout)
        content_layout.addWidget(main_info_group)
        
        # Теги
        self.info_tags_check = QCheckBox("Теги")
        content_layout.addWidget(self.info_tags_check)
        
        # Контекст - отдельные элементы
        context_group = QGroupBox("Контекст")
        context_layout = QVBoxLayout()
        self.info_epic_check = QCheckBox("Epic")
        context_layout.addWidget(self.info_epic_check)
        self.info_feature_check = QCheckBox("Feature")
        context_layout.addWidget(self.info_feature_check)
        self.info_story_check = QCheckBox("Story")
        context_layout.addWidget(self.info_story_check)
        self.info_component_check = QCheckBox("Component")
        context_layout.addWidget(self.info_component_check)
        context_group.setLayout(context_layout)
        content_layout.addWidget(context_group)
        
        # Описание
        self.info_description_check = QCheckBox("Описание")
        content_layout.addWidget(self.info_description_check)
        
        # Общий ожидаемый результат
        self.info_expected_result_check = QCheckBox("Общий ожидаемый результат")
        content_layout.addWidget(self.info_expected_result_check)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget

    def _browse_test_cases_dir(self):
        """Выбрать папку с тест-кейсами"""
        current_path = self.test_cases_dir_edit.text() or str(Path.cwd())
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку с тест-кейсами",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.test_cases_dir_edit.setText(folder)

    def _browse_methodic_path(self):
        """Выбрать файл методики"""
        current_path = self.methodic_path_edit.text() or str(Path.cwd())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл методики",
            current_path,
            "Markdown файлы (*.md);;Текстовые файлы (*.txt);;Все файлы (*.*)"
        )
        if file_path:
            self.methodic_path_edit.setText(file_path)

    def _load_settings(self):
        """Загрузить настройки в поля формы"""
        # Общие
        self.project_name_edit.setText(self.settings.get('project_name', ''))
        # Список тестировщиков
        testers_list = self.settings.get('testers', [])
        if isinstance(testers_list, list):
            self.testers_edit.setPlainText('\n'.join(testers_list))
        elif isinstance(testers_list, str):
            self.testers_edit.setPlainText(testers_list)
        self.test_cases_dir_edit.setText(self.settings.get('test_cases_dir', ''))
        self.methodic_path_edit.setText(self.settings.get('LLM_METHODIC_PATH', ''))
        
        # LLM
        self.llm_host_edit.setText(self.settings.get('LLM_HOST', ''))
        # Загружаем модели для комбобокса (используем кэш, чтобы не блокировать UI)
        self._load_llm_models(use_cached=True)
        # Устанавливаем текущую модель
        current_model = self.settings.get('LLM_MODEL', '')
        if current_model:
            self.llm_model_edit.setEditText(current_model)
        
        # Промпты
        self.review_prompt_edit.setPlainText(self.settings.get('DEFAULT_PROMT', ''))
        self.create_prompt_edit.setPlainText(self.settings.get('DEFAULT_PROMT_CREATE_TC', ''))
        
        # Панели
        panel_sizes = self.settings.get('panel_sizes', {})
        self.left_panel_spin.setValue(panel_sizes.get('left', 350))
        self.form_area_spin.setValue(panel_sizes.get('form_area', 900))
        self.review_panel_spin.setValue(panel_sizes.get('review', 360))
        
        # Внешний вид
        self.theme_combo.setCurrentText(self.settings.get('theme', 'dark'))
        font_family = self.settings.get('font_family', 'Segoe UI')
        # Устанавливаем шрифт в QFontComboBox
        font_index = self.font_family_combo.findText(font_family, Qt.MatchFixedString)
        if font_index >= 0:
            self.font_family_combo.setCurrentIndex(font_index)
        else:
            # Если шрифт не найден, используем первый доступный или Segoe UI
            segoe_index = self.font_family_combo.findText('Segoe UI', Qt.MatchFixedString)
            if segoe_index >= 0:
                self.font_family_combo.setCurrentIndex(segoe_index)
            elif self.font_family_combo.count() > 0:
                self.font_family_combo.setCurrentIndex(0)
        self.font_size_spin.setValue(self.settings.get('font_size', 13))
        self.base_spacing_spin.setValue(self.settings.get('base_spacing', 12))
        self.section_spacing_spin.setValue(self.settings.get('section_spacing', 8))
        self.container_padding_spin.setValue(self.settings.get('container_padding', 12))
        self.text_padding_spin.setValue(self.settings.get('text_input_vertical_padding', 2))
        self.group_title_spacing_spin.setValue(self.settings.get('group_title_spacing', 1))
        # Счетчики в дереве
        if hasattr(self, 'show_folder_counters_check'):
            self.show_folder_counters_check.setChecked(self.settings.get('show_folder_counters', False))
        
        # Панель Информация - видимость элементов (отдельно для каждого элемента)
        info_visibility = self.settings.get('information_panel_visibility', {})
        # Значения по умолчанию: все элементы видимы (True)
        # Метаданные
        if hasattr(self, 'info_id_check'):
            self.info_id_check.setChecked(info_visibility.get('id', True))
        if hasattr(self, 'info_created_check'):
            self.info_created_check.setChecked(info_visibility.get('created', True))
        if hasattr(self, 'info_updated_check'):
            self.info_updated_check.setChecked(info_visibility.get('updated', True))
        # Люди
        if hasattr(self, 'info_author_check'):
            self.info_author_check.setChecked(info_visibility.get('author', True))
        if hasattr(self, 'info_owner_check'):
            self.info_owner_check.setChecked(info_visibility.get('owner', True))
        if hasattr(self, 'info_reviewer_check'):
            self.info_reviewer_check.setChecked(info_visibility.get('reviewer', True))
        # Статус и тип
        if hasattr(self, 'info_status_check'):
            self.info_status_check.setChecked(info_visibility.get('status', True))
        if hasattr(self, 'info_test_layer_check'):
            self.info_test_layer_check.setChecked(info_visibility.get('test_layer', True))
        if hasattr(self, 'info_test_type_check'):
            self.info_test_type_check.setChecked(info_visibility.get('test_type', True))
        # Severity и Priority
        if hasattr(self, 'info_severity_check'):
            self.info_severity_check.setChecked(info_visibility.get('severity', True))
        if hasattr(self, 'info_priority_check'):
            self.info_priority_check.setChecked(info_visibility.get('priority', True))
        # Окружение и Браузер
        if hasattr(self, 'info_environment_check'):
            self.info_environment_check.setChecked(info_visibility.get('environment', True))
        if hasattr(self, 'info_browser_check'):
            self.info_browser_check.setChecked(info_visibility.get('browser', True))
        # Ссылки
        if hasattr(self, 'info_test_case_id_check'):
            self.info_test_case_id_check.setChecked(info_visibility.get('test_case_id', True))
        if hasattr(self, 'info_issue_links_check'):
            self.info_issue_links_check.setChecked(info_visibility.get('issue_links', True))
        if hasattr(self, 'info_test_case_links_check'):
            self.info_test_case_links_check.setChecked(info_visibility.get('test_case_links', True))
        # Группы
        if hasattr(self, 'info_tags_check'):
            self.info_tags_check.setChecked(info_visibility.get('tags', True))
        # Контекст
        if hasattr(self, 'info_epic_check'):
            self.info_epic_check.setChecked(info_visibility.get('epic', True))
        if hasattr(self, 'info_feature_check'):
            self.info_feature_check.setChecked(info_visibility.get('feature', True))
        if hasattr(self, 'info_story_check'):
            self.info_story_check.setChecked(info_visibility.get('story', True))
        if hasattr(self, 'info_component_check'):
            self.info_component_check.setChecked(info_visibility.get('component', True))
        if hasattr(self, 'info_description_check'):
            self.info_description_check.setChecked(info_visibility.get('description', True))
        if hasattr(self, 'info_expected_result_check'):
            self.info_expected_result_check.setChecked(info_visibility.get('expected_result', True))

    def _create_import_tab(self) -> QWidget:
        """Создать вкладку настроек импорта"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(UI_METRICS.base_spacing)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(UI_METRICS.section_spacing)
        
        # Импорт из ALM
        import_group = QGroupBox("Импорт из ALM")
        import_layout = QVBoxLayout()
        
        import_label = QLabel(
            "Импорт тест-кейсов из ALM с созданием структуры папок согласно иерархии."
        )
        import_label.setWordWrap(True)
        import_layout.addWidget(import_label)
        
        import_btn = QPushButton("Импорт из ALM")
        import_btn.clicked.connect(self._on_import_from_alm_clicked)
        import_layout.addWidget(import_btn)
        
        import_group.setLayout(import_layout)
        content_layout.addWidget(import_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget
    
    def _on_import_from_alm_clicked(self):
        """Обработчик нажатия кнопки импорта из ALM в настройках"""
        if self.parent_window and hasattr(self.parent_window, 'convert_from_azure'):
            # Закрываем диалог настроек перед импортом
            self.accept()
            # Вызываем метод импорта из главного окна
            self.parent_window.convert_from_azure()

    def _save_and_accept(self):
        """Сохранить настройки и закрыть диалог"""
        # Общие
        self.settings['project_name'] = self.project_name_edit.text().strip()
        # Список тестировщиков - сохраняем как список
        testers_text = self.testers_edit.toPlainText().strip()
        testers_list = [t.strip() for t in testers_text.split('\n') if t.strip()]
        self.settings['testers'] = testers_list
        self.settings['test_cases_dir'] = self.test_cases_dir_edit.text().strip()
        self.settings['LLM_METHODIC_PATH'] = self.methodic_path_edit.text().strip()
        
        # LLM
        self.settings['LLM_HOST'] = self.llm_host_edit.text().strip()
        self.settings['LLM_MODEL'] = self.llm_model_edit.currentText().strip()
        
        # Промпты
        self.settings['DEFAULT_PROMT'] = self.review_prompt_edit.toPlainText().strip()
        self.settings['DEFAULT_PROMT_CREATE_TC'] = self.create_prompt_edit.toPlainText().strip()
        
        # Панели
        if 'panel_sizes' not in self.settings:
            self.settings['panel_sizes'] = {}
        self.settings['panel_sizes']['left'] = self.left_panel_spin.value()
        self.settings['panel_sizes']['form_area'] = self.form_area_spin.value()
        self.settings['panel_sizes']['review'] = self.review_panel_spin.value()
        
        # Внешний вид
        self.settings['theme'] = self.theme_combo.currentText().strip()
        self.settings['font_family'] = self.font_family_combo.currentText()
        self.settings['font_size'] = self.font_size_spin.value()
        self.settings['base_spacing'] = self.base_spacing_spin.value()
        self.settings['section_spacing'] = self.section_spacing_spin.value()
        self.settings['container_padding'] = self.container_padding_spin.value()
        self.settings['text_input_vertical_padding'] = self.text_padding_spin.value()
        self.settings['group_title_spacing'] = self.group_title_spacing_spin.value()
        # Счетчики в дереве
        if hasattr(self, 'show_folder_counters_check'):
            self.settings['show_folder_counters'] = self.show_folder_counters_check.isChecked()
        
        # Панель Информация - видимость элементов (отдельно для каждого элемента)
        if 'information_panel_visibility' not in self.settings:
            self.settings['information_panel_visibility'] = {}
        info_visibility = self.settings['information_panel_visibility']
        # Метаданные
        if hasattr(self, 'info_id_check'):
            info_visibility['id'] = self.info_id_check.isChecked()
        if hasattr(self, 'info_created_check'):
            info_visibility['created'] = self.info_created_check.isChecked()
        if hasattr(self, 'info_updated_check'):
            info_visibility['updated'] = self.info_updated_check.isChecked()
        # Люди
        if hasattr(self, 'info_author_check'):
            info_visibility['author'] = self.info_author_check.isChecked()
        if hasattr(self, 'info_owner_check'):
            info_visibility['owner'] = self.info_owner_check.isChecked()
        if hasattr(self, 'info_reviewer_check'):
            info_visibility['reviewer'] = self.info_reviewer_check.isChecked()
        # Статус и тип
        if hasattr(self, 'info_status_check'):
            info_visibility['status'] = self.info_status_check.isChecked()
        if hasattr(self, 'info_test_layer_check'):
            info_visibility['test_layer'] = self.info_test_layer_check.isChecked()
        if hasattr(self, 'info_test_type_check'):
            info_visibility['test_type'] = self.info_test_type_check.isChecked()
        # Severity и Priority
        if hasattr(self, 'info_severity_check'):
            info_visibility['severity'] = self.info_severity_check.isChecked()
        if hasattr(self, 'info_priority_check'):
            info_visibility['priority'] = self.info_priority_check.isChecked()
        # Окружение и Браузер
        if hasattr(self, 'info_environment_check'):
            info_visibility['environment'] = self.info_environment_check.isChecked()
        if hasattr(self, 'info_browser_check'):
            info_visibility['browser'] = self.info_browser_check.isChecked()
        # Ссылки
        if hasattr(self, 'info_test_case_id_check'):
            info_visibility['test_case_id'] = self.info_test_case_id_check.isChecked()
        if hasattr(self, 'info_issue_links_check'):
            info_visibility['issue_links'] = self.info_issue_links_check.isChecked()
        if hasattr(self, 'info_test_case_links_check'):
            info_visibility['test_case_links'] = self.info_test_case_links_check.isChecked()
        # Группы
        if hasattr(self, 'info_tags_check'):
            info_visibility['tags'] = self.info_tags_check.isChecked()
        # Контекст
        if hasattr(self, 'info_epic_check'):
            info_visibility['epic'] = self.info_epic_check.isChecked()
        if hasattr(self, 'info_feature_check'):
            info_visibility['feature'] = self.info_feature_check.isChecked()
        if hasattr(self, 'info_story_check'):
            info_visibility['story'] = self.info_story_check.isChecked()
        if hasattr(self, 'info_component_check'):
            info_visibility['component'] = self.info_component_check.isChecked()
        if hasattr(self, 'info_description_check'):
            info_visibility['description'] = self.info_description_check.isChecked()
        if hasattr(self, 'info_expected_result_check'):
            info_visibility['expected_result'] = self.info_expected_result_check.isChecked()
        self.settings['information_panel_visibility'] = info_visibility
        
        self.accept()

    def _open_settings_file_in_explorer(self):
        """Открыть файл settings.json в проводнике"""
        try:
            settings_file = get_settings_path()
            
            # Создаем файл, если его нет
            if not settings_file.exists():
                settings_file.parent.mkdir(parents=True, exist_ok=True)
                # Создаем пустой файл с минимальными настройками
                with open(settings_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=4)
            
            # Открываем файл в проводнике с выделением
            if sys.platform == "win32":
                # Windows: открываем папку и выделяем файл
                normalized = os.path.normpath(str(settings_file))
                subprocess.run(["explorer", "/select,", normalized], check=False)
            elif sys.platform == "darwin":
                # macOS: открываем Finder и выделяем файл
                subprocess.run(["open", "-R", str(settings_file)], check=False)
            else:
                # Linux: открываем файловый менеджер
                subprocess.run(["xdg-open", str(settings_file.parent)], check=False)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Ошибка",
                f"Не удалось открыть файл настроек в проводнике:\n{str(e)}"
            )

    def get_settings(self) -> dict:
        """Получить сохраненные настройки"""
        return self.settings
    
    def _load_llm_models(self, use_cached: bool = True):
        """Загрузить список доступных LLM моделей
        
        Args:
            use_cached: Если True, использует кэшированные модели из главного окна вместо запроса к серверу
        """
        if not self.parent_window:
            return
        
        # Получаем список моделей из главного окна
        host = self.llm_host_edit.text().strip() or self.settings.get('LLM_HOST', '')
        if not host:
            # Если host не указан, используем модели из главного окна
            if hasattr(self.parent_window, 'available_llm_models'):
                models = self.parent_window.available_llm_models
            else:
                models = []
        else:
            # Если use_cached=True, используем кэшированные модели из главного окна (если есть)
            # чтобы не блокировать UI при открытии диалога
            if use_cached:
                # Пытаемся использовать кэш из главного окна, если хост совпадает
                if (hasattr(self.parent_window, 'llm_host') and 
                    self.parent_window.llm_host == host and
                    hasattr(self.parent_window, 'available_llm_models')):
                    models = self.parent_window.available_llm_models
                else:
                    # Если хост другой или кэша нет, используем пустой список
                    # (текущая модель будет добавлена ниже)
                    models = []
            else:
                # Синхронная загрузка только при явном запросе (кнопка "Обновить")
                try:
                    from ..utils.list_models import fetch_models as fetch_llm_models
                    models = fetch_llm_models(host)
                    models = [str(m).strip() for m in (models or []) if str(m or "").strip()]
                except Exception:
                    models = []
        
        # Добавляем текущую модель, если её нет в списке
        current_model = self.settings.get('LLM_MODEL', '')
        if current_model and current_model not in models:
            models.insert(0, current_model)
        
        # Обновляем модель комбобокса
        self.llm_model_list_model.setStringList(models)
        self._reset_llm_model_filter()
    
    def _refresh_llm_models(self):
        """Обновить список LLM моделей (с запросом к серверу)"""
        # При обновлении делаем реальный запрос к серверу
        self._load_llm_models(use_cached=False)
        QMessageBox.information(self, "Обновление", "Список моделей обновлен")
    
    def _on_llm_host_changed(self, text: str):
        """Обработчик изменения LLM Host"""
        # При изменении хоста обновляем список моделей (используем кэш, чтобы не блокировать UI)
        if text.strip():
            QTimer.singleShot(500, lambda: self._load_llm_models(use_cached=True))  # Задержка для завершения ввода
    
    def _on_llm_model_changed(self, text: str):
        """Обработчик изменения выбранной модели"""
        pass  # Модель сохранится при нажатии OK
    
    def _on_llm_model_text_edited(self, text: str):
        """Обработчик редактирования текста в комбобоксе модели"""
        if text:
            pattern = f".*{QRegularExpression.escape(text)}.*"
            regex = QRegularExpression(pattern, QRegularExpression.CaseInsensitiveOption)
        else:
            regex = QRegularExpression(".*", QRegularExpression.CaseInsensitiveOption)
        self.llm_model_proxy_model.setFilterRegularExpression(regex)
        self.llm_model_edit.showPopup()
        line_edit = self.llm_model_edit.lineEdit()
        if line_edit:
            line_edit.setFocus()
            line_edit.setCursorPosition(len(text))
    
    def _on_llm_model_editing_finished(self):
        """Обработчик завершения редактирования модели"""
        line_edit = self.llm_model_edit.lineEdit()
        if not line_edit:
            return
        value = line_edit.text().strip()
        if not value:
            self._reset_llm_model_filter()
            return
        
        # Добавляем модель в список, если её нет
        current_models = self.llm_model_list_model.stringList()
        if value not in current_models:
            current_models.append(value)
            self.llm_model_list_model.setStringList(current_models)
        
        self._reset_llm_model_filter()
        # Устанавливаем выбранную модель
        source_index = self.llm_model_list_model.index(current_models.index(value), 0)
        proxy_index = self.llm_model_proxy_model.mapFromSource(source_index)
        if proxy_index.isValid():
            self.llm_model_edit.setCurrentIndex(proxy_index.row())
        else:
            self.llm_model_edit.setCurrentIndex(-1)
        self.llm_model_edit.setEditText(value)
    
    def _reset_llm_model_filter(self):
        """Сбросить фильтр комбобокса моделей"""
        self.llm_model_proxy_model.setFilterRegularExpression(
            QRegularExpression(".*", QRegularExpression.CaseInsensitiveOption)
        )


class _LLMWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, message: str, model: Optional[str], host: Optional[str]):
        super().__init__()
        self.message = message
        self.model = model
        self.host = host

    def run(self):
        try:
            response = llm.send_prompt(
                self.message,
                model=self.model,
                host=self.host,
            )
        except Exception as exc:
            self.error.emit(str(exc))
        else:
            self.finished.emit(response)


class _LLMAvailabilityWorker(QObject):
    """Воркер для проверки доступности LLM в фоновом потоке"""
    availability_checked = pyqtSignal(bool)  # True если доступен, False если нет

    def __init__(self, host: Optional[str]):
        super().__init__()
        self.host = host

    def run(self):
        """Проверить доступность LLM"""
        try:
            if not self.host or not str(self.host).strip():
                self.availability_checked.emit(False)
                return
            
            # Используем короткий timeout для проверки доступности
            try:
                models = fetch_llm_models(str(self.host).strip(), timeout=5.0)
                # Если получили список моделей (даже пустой), значит LLM доступен
                is_available = True
            except Exception:
                # Любая ошибка означает, что LLM недоступен
                is_available = False
            
            # Отправляем сигнал в любом случае
            self.availability_checked.emit(is_available)
        except Exception:
            # На всякий случай, если произошла ошибка на верхнем уровне
            try:
                self.availability_checked.emit(False)
            except Exception:
                # Игнорируем ошибки при отправке сигнала
                pass


class MainWindow(QMainWindow):
    """
    Главное окно редактора тест-кейсов
    
    Соответствует принципам SOLID:
    - Single Responsibility: отвечает только за координацию UI
    - Dependency Inversion: использует абстракции (сервисы)
    - Open/Closed: легко расширяется новыми функциями через сервисы
    
    ВАЖНО: Это упрощенная версия для демонстрации принципов SOLID.
    Полная версия из test_case_editor_v1.py может быть постепенно портирована
    по тому же принципу - разделение на отдельные виджеты и сервисы.
    """
    
    def __init__(self):
        super().__init__()
        
        # Внедрение зависимостей (Dependency Injection)
        repository = TestCaseRepository()
        self.service = TestCaseService(repository)
        
        # Настройки
        self.settings_file = get_settings_path()
        self.settings = self.load_settings()
        default_sizes = {'left': 350, 'form_area': 900, 'review': 360}
        self.panel_sizes = dict(default_sizes)
        self.panel_sizes.update(self.settings.get('panel_sizes', {}))
        self._last_review_width = self.panel_sizes.get('review', 0) or 360
        test_cases_dir_str = self.settings.get('test_cases_dir', '').strip()
        if not test_cases_dir_str:
            # Если test_cases_dir пустое, запрашиваем выбор папки
            self.test_cases_dir = self.prompt_select_folder()
        else:
            self.test_cases_dir = Path(test_cases_dir_str)
            if not self.test_cases_dir.exists():
                # Если путь указан, но папка не существует, запрашиваем выбор папки
                self.test_cases_dir = self.prompt_select_folder()
        self.default_prompt = self.settings.get('DEFAULT_PROMT', "Опиши задачу для ревью.")
        self.create_tc_prompt = self.settings.get('DEFAULT_PROMT_CREATE_TC', "Создай ТТ")
        self.llm_model = self.settings.get('LLM_MODEL', "").strip()
        self.llm_host = self.settings.get('LLM_HOST', "").strip()
        
        # Применяем настройки шрифта и темы к UI_METRICS и THEME_PROVIDER
        self._apply_font_settings()
        # Применяем тему из настроек
        theme_name = self.settings.get('theme', 'dark').strip().lower()
        if theme_name not in ['dark', 'light']:
            theme_name = 'dark'  # По умолчанию темная тема
        try:
            THEME_PROVIDER.set_theme(theme_name)
        except (ValueError, AttributeError):
            # Если что-то пошло не так, используем темную тему
            THEME_PROVIDER.set_theme('dark')
        self._model_list_model = QStringListModel(self)
        self._model_proxy_model = QSortFilterProxyModel(self)
        self._model_proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._model_proxy_model.setFilterKeyColumn(0)
        self._model_proxy_model.setSourceModel(self._model_list_model)
        self._model_options: List[str] = []
        self._suppress_model_change = False
        # Инициализируем списком с текущей моделью, если она есть (неблокирующий запуск)
        self.available_llm_models = [self.llm_model] if self.llm_model else []
        self.selected_llm_model = self.llm_model
        # Статус доступности LLM: None - неизвестен, True - доступен, False - недоступен
        self._llm_available: Optional[bool] = None
        # Таймер для периодической проверки LLM (каждые 5 минут)
        self._llm_check_timer = QTimer(self)
        self._llm_check_timer.timeout.connect(self._check_llm_availability)
        methodic_setting = self.settings.get('LLM_METHODIC_PATH')
        if methodic_setting:
            self.methodic_path = Path(methodic_setting).expanduser()
        else:
            self.methodic_path = self._default_methodic_path()
        if not self.methodic_path.exists():
            self.methodic_path = self._default_methodic_path()
        
        # Состояние
        self.current_test_case: Optional[TestCase] = None
        self.test_cases = []
        self._llm_thread: Optional[QThread] = None
        self._llm_worker: Optional[_LLMWorker] = None
        self._llm_availability_thread: Optional[QThread] = None
        self._llm_availability_worker: Optional[_LLMAvailabilityWorker] = None
        self._current_test_case_path: Optional[Path] = None
        self._current_filters: Dict = {}
        self._current_mode: str = "edit"
        self._geometry_initialized = False
        self._preserve_panel_sizes = False  # Флаг для предотвращения автоматического изменения размеров панелей
        
        self.setup_ui()
        self._apply_model_options()
        self.load_all_test_cases()
        self._show_placeholder()
        self._apply_mode_state()
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        self.setWindowTitle("Test Case Editor")
        
        # Устанавливаем иконку окна
        logo_path = get_icon_path("logo.png")
        if logo_path and logo_path.exists():
            window_icon = QIcon(str(logo_path))
            self.setWindowIcon(window_icon)
        if not self._geometry_initialized:
            self._apply_initial_geometry()
            self._geometry_initialized = True
        
        # Инициализируем меню и добавляем в стандартный menuBar
        self._init_menus()
        
        # Создаем панель инструментов
        self._create_toolbar()
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(
            UI_METRICS.window_margin,
            UI_METRICS.window_margin,
            UI_METRICS.window_margin,
            UI_METRICS.window_margin,
        )
        main_layout.setSpacing(UI_METRICS.base_spacing)
        
        # Splitter для разделения
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.splitterMoved.connect(self._on_main_splitter_moved)
        
        # Левая панель
        left_panel = self._create_left_panel()
        self.main_splitter.addWidget(left_panel)
        
        # Правая панель
        right_panel = self._create_right_panel()
        self.main_splitter.addWidget(right_panel)
        
        # Пропорции
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(self.main_splitter)
        
        self._apply_initial_panel_sizes()
        
        # Статусбар будет обновлен в _apply_mode_state()
    
    def _create_left_panel(self) -> QWidget:
        """Создать левую панель с деревом"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        layout.setSpacing(UI_METRICS.section_spacing)
        
        # Поиск
        self.search_frame = QFrame()  # Сохраняем как атрибут класса
        search_layout = QHBoxLayout(self.search_frame)
        search_layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        search_layout.setSpacing(UI_METRICS.base_spacing // 2)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Название или идентификатор")
        self.search_input.textChanged.connect(self._filter_tree)
        search_layout.addWidget(self.search_input, 1)
        
        # Иконка фильтра
        self.filter_button = QToolButton()
        # Загружаем иконку фильтра из icon_mapping.json
        mapping_file = get_icons_dir() / "icon_mapping.json"
        filter_icon_name = "filter.svg"
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    filter_icon_name = data.get("search", {}).get("filter", "filter.svg")
            except:
                pass
        
        filter_icon = self._load_svg_icon(filter_icon_name, size=28, color="#ffffff")
        if filter_icon:
            self.filter_button.setIcon(filter_icon)
            self.filter_button.setIconSize(QSize(28, 28))
        self.filter_button.setToolTip("Фильтры")
        self.filter_button.setCursor(Qt.PointingHandCursor)
        self.filter_button.setAutoRaise(True)
        self.filter_button.setFixedSize(36, 36)
        self.filter_button.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.filter_button.clicked.connect(self._on_filter_button_clicked)
        search_layout.addWidget(self.filter_button)
        
        layout.addWidget(self.search_frame)
        
        # Панель фильтров будет добавлена в detail_stack
        
        # Дерево
        self.tree_widget = TestCaseTreeWidget(self.service)
        # Передаем настройки для списка причин пропуска
        skip_reasons = self.settings.get('skip_reasons', ['Автотесты', 'Нагрузочное тестирование', 'Другое'])
        self.tree_widget.set_skip_reasons(skip_reasons)
        # Передаем настройку для отображения счетчиков
        show_counters = self.settings.get('show_folder_counters', False)
        self.tree_widget.set_show_folder_counters(show_counters)
        self.tree_widget.test_case_selected.connect(self._on_test_case_selected)
        self.tree_widget.tree_updated.connect(self._on_tree_updated)
        self.tree_widget.review_requested.connect(self._on_review_requested)
        self.tree_widget.test_cases_updated.connect(self._on_test_cases_updated)
        self.tree_widget.add_to_review_requested.connect(self._on_add_to_review_requested)
        layout.addWidget(self.tree_widget, 1)
        
        return panel

    def _create_right_panel(self) -> QWidget:
        """Создать правую панель с формой"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(UI_METRICS.base_spacing)
        
        self.detail_splitter = QSplitter(Qt.Horizontal)
        self.detail_splitter.setChildrenCollapsible(False)
        self.detail_splitter.splitterMoved.connect(self._on_detail_splitter_moved)

        # Контейнер для placeholder / формы
        self.detail_stack_container = QWidget()
        self.detail_stack = QStackedLayout(self.detail_stack_container)
        self.detail_stack.setContentsMargins(0, 0, 0, 0)

        self.placeholder = PlaceholderWidget()
        self.detail_stack.addWidget(self.placeholder)
        
        self.form_widget = TestCaseFormWidget(self.service)
        # Передаем настройки для списка причин пропуска
        skip_reasons = self.settings.get('skip_reasons', ['Автотесты', 'Нагрузочное тестирование', 'Другое'])
        self.form_widget.set_skip_reasons(skip_reasons)
        self.form_widget.test_case_saved.connect(self._on_test_case_saved)
        self.form_widget.status_changed.connect(self._on_status_changed)
        self.form_widget.unsaved_changes_state.connect(self._on_form_unsaved_state)
        self.form_widget.before_save.connect(self._on_form_before_save)
        self.form_widget.file_attached_to_step.connect(self._on_file_attached_to_step)
        self.detail_stack.addWidget(self.form_widget)
        
        # Панель фильтров
        self.filter_panel = FilterPanel(test_cases=[])
        self.filter_panel.filters_applied.connect(self._on_filters_applied)
        self.filter_panel.filters_reset.connect(self._on_filters_reset)
        self.detail_stack.addWidget(self.filter_panel)
        
        self.detail_stack.setCurrentWidget(self.placeholder)

        self.detail_splitter.addWidget(self.detail_stack_container)

        # Дополнительная панель
        self.aux_panel = AuxiliaryPanel(
            methodic_path=self.methodic_path,
            default_review_prompt=self.default_prompt,
            default_creation_prompt=self.create_tc_prompt,
        )
        # Устанавливаем список тестировщиков из настроек
        testers_list = self.settings.get('testers', [])
        if isinstance(testers_list, list):
            self.aux_panel.set_information_testers(testers_list)
        elif isinstance(testers_list, str):
            # Если сохранено как строка, разбиваем по переносам строк
            testers_list = [t.strip() for t in testers_list.split('\n') if t.strip()]
            self.aux_panel.set_information_testers(testers_list)
        # Устанавливаем минимальную и максимальную ширину для aux_panel
        # чтобы предотвратить автоматическое расширение
        self.aux_panel.setMinimumWidth(220)
        self.aux_panel.setMaximumWidth(2000)
        self.aux_panel.review_prompt_saved.connect(self._on_prompt_saved)
        self.aux_panel.review_enter_clicked.connect(self._on_review_enter_clicked)
        self.aux_panel.creation_prompt_saved.connect(self._on_creation_prompt_saved)
        self.aux_panel.creation_enter_clicked.connect(self._on_creation_enter_clicked)
        self.aux_panel.information_data_changed.connect(self._on_information_data_changed)
        self.aux_panel.generate_report_requested.connect(self._generate_html_report)
        self.aux_panel.generate_summary_report_requested.connect(self._generate_summary_report)
        self.aux_panel.tab_changed.connect(self._on_aux_panel_tab_changed)
        self.aux_panel.manual_review_notes_changed.connect(self._on_manual_review_notes_changed)
        self.detail_splitter.addWidget(self.aux_panel)
        
        # Создаем кнопки панелей в toolbar после создания aux_panel
        self._create_panel_buttons()
        
        # Применяем настройки видимости панели Информация при инициализации
        info_visibility = self.settings.get('information_panel_visibility', {})
        if hasattr(self.aux_panel, 'information_panel'):
            self.aux_panel.information_panel.set_visibility_settings(info_visibility)

        self.detail_splitter.setCollapsible(0, False)
        self.detail_splitter.setCollapsible(1, True)  # Разрешаем скрывать aux_panel
        layout.addWidget(self.detail_splitter)
        
        return panel
    
    def _init_menus(self):
        """Инициализация меню и добавление в стандартный menuBar"""
        menubar = self.menuBar()
        menubar.clear()
        
        # Меню "Файл"
        self.file_menu = menubar.addMenu('Файл')
        select_folder_action = self.file_menu.addAction('📁 Выбрать папку с тест-кейсами')
        select_folder_action.triggered.connect(self.select_test_cases_folder)
        select_folder_action.setShortcut('Ctrl+O')

        self.file_menu.addSeparator()

        exit_action = self.file_menu.addAction('Выход')
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut('Ctrl+Q')

        # Меню "Вид"
        self.view_menu = menubar.addMenu('Вид')
        width_action = self.view_menu.addAction('Настроить ширины панелей…')
        width_action.triggered.connect(self._configure_panel_widths)
        statistics_action = self.view_menu.addAction('Показать статистику')
        statistics_action.triggered.connect(self._show_statistics_panel)
        
        # Подменю "Режим" в меню "Вид"
        mode_menu = self.view_menu.addMenu('Режим')
        self._mode_action_group = QActionGroup(self)
        self._mode_action_group.setExclusive(True)
        self._mode_actions = {}
        edit_action = QAction("Редактирование", self, checkable=True)
        run_action = QAction("Запуск", self, checkable=True)
        self._mode_actions["edit"] = edit_action
        self._mode_actions["run"] = run_action
        self._mode_action_group.addAction(edit_action)
        self._mode_action_group.addAction(run_action)
        mode_menu.addAction(edit_action)
        mode_menu.addAction(run_action)
        edit_action.triggered.connect(lambda checked: checked and self._set_mode("edit"))
        run_action.triggered.connect(lambda checked: checked and self._set_mode("run"))
        edit_action.setChecked(True)
        
        # Кнопка настроек в меню "Вид"
        settings_action = self.view_menu.addAction('Настройки…')
        settings_action.triggered.connect(self._open_settings_dialog)
        
        # Меню "Runner"
        self.runner_menu = menubar.addMenu('Runner')
        reset_all_statuses_action = self.runner_menu.addAction('Сброс статусов тест-кейсов')
        reset_all_statuses_action.triggered.connect(self._confirm_and_reset_all_statuses)
        
        generate_allure_action = self.runner_menu.addAction('Сгенерировать отчет Allure')
        generate_allure_action.triggered.connect(self._generate_allure_report)
        
        generate_report_action = self.runner_menu.addAction('Сгенерировать отчет')
        generate_report_action.triggered.connect(self._generate_html_report)
        settings_action.setShortcut('Ctrl+,')

        # Меню "Git" - создаем через QAction чтобы иконка отображалась рядом с текстом
        self.git_menu_action = QAction('Git', self)
        self.git_menu = QMenu(self)
        self.git_menu_action.setMenu(self.git_menu)
        menubar.addAction(self.git_menu_action)
        self.git_commit_action = self.git_menu.addAction('Commit…')
        self.git_commit_action.triggered.connect(self._open_git_commit_dialog)
        self.git_push_action = self.git_menu.addAction('Push')
        self.git_push_action.triggered.connect(self._perform_git_push)
        
        # Обновляем индикаторы статуса Git
        self._update_git_status_indicators()
    
    def _create_toolbar(self):
        """Создать панель инструментов с быстрыми действиями"""
        self.toolbar = QToolBar("Основная панель", self)
        self.toolbar.setMovable(False)  # Не позволяем перемещать панель
        self.addToolBar(self.toolbar)
        
        # Переключатель режима
        self.mode_edit_label = QLabel("Редактирование")
        self.toolbar.addWidget(self.mode_edit_label)
        
        self.mode_switch = ToggleSwitch()
        self.mode_switch.toggled.connect(self._on_mode_switch_changed)
        self.toolbar.addWidget(self.mode_switch)
        
        self.mode_run_label = QLabel("Запуск тестов")
        self.toolbar.addWidget(self.mode_run_label)
        
        # Добавляем растягивающийся разделитель, чтобы кнопки панелей были справа
        self.toolbar.addSeparator()
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)
        
        # Кнопки панелей (будут добавлены после создания aux_panel)
        self._panel_buttons: dict[str, QToolButton] = {}
        self._panel_button_group = QButtonGroup(self)
        self._panel_button_group.setExclusive(True)
        self._current_active_panel: Optional[str] = None  # Текущая активная панель
        
        self._update_mode_indicator()
        
        # Создаем label для статистики в статус-баре (включая статус LLM)
        self._create_statusbar_statistics_label()
        
        # Создаем кнопку "Сохранить" в статус-баре
        self._create_statusbar_save_button()
        
        # Создаем горячую клавишу Ctrl+S для сохранения
        self._create_save_shortcut()
        
        # Отображаем статус LLM сразу (серый, пока проверка не завершена)
        self._update_statusbar_statistics()
        
        # Запускаем проверку LLM в фоне после инициализации UI (с небольшой задержкой)
        QTimer.singleShot(500, self._start_llm_availability_check)
    
    def _load_icon_mapping(self) -> dict:
        """Загрузить маппинг панелей на иконки из JSON файла."""
        mapping_file = get_icons_dir() / "icon_mapping.json"
        
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'panels' in data:
                        return data.get('panels', {})
                    else:
                        return data
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка загрузки маппинга иконок: {e}")
        
        return {
            "information": "info.svg",
            "review": "eye.svg",
            "creation": "file-plus.svg",
            "json": "code.svg",
            "files": "file.svg",
            "reports": "book.svg"
        }
    
    def _load_svg_icon(self, icon_name: str, size: int = 24, color: Optional[str] = None) -> Optional[QIcon]:
        """Загрузить SVG иконку из файла и вернуть QIcon."""
        icon_path = get_icon_path(icon_name)
        
        if not icon_path.exists():
            print(f"Иконка не найдена: {icon_path}")
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
                print(f"Невалидный SVG файл: {icon_path}")
                return None
            
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            renderer.render(painter)
            painter.end()
            
            icon = QIcon(pixmap)
            return icon
        except Exception as e:
            print(f"Ошибка загрузки иконки {icon_name}: {e}")
            return None
    
    def _create_panel_buttons(self):
        """Создать кнопки панелей в toolbar."""
        # Проверяем, что toolbar существует
        if not hasattr(self, 'toolbar') or not self.toolbar:
            return
        
        # Загружаем маппинг иконок
        icon_mapping = self._load_icon_mapping()
        
        # Порядок панелей
        tabs_order = ["information", "review", "creation", "json", "files", "reports", "manual_review"]
        
        # Маппинг панелей на подсказки
        tooltips = {
            "information": "Информация",
            "review": "Ревью",
            "creation": "Создать ТК",
            "json": "JSON превью",
            "files": "Файлы",
            "reports": "Отчетность",
            "manual_review": "Ручное ревью",
        }
        
        for index, tab_id in enumerate(tabs_order):
            button = QToolButton()
            
            # Загружаем иконку из SVG файла
            icon_name = icon_mapping.get(tab_id)
            if icon_name:
                icon = self._load_svg_icon(icon_name, size=20, color="#ffffff")
                if icon and not icon.isNull():
                    button.setIcon(icon)
                    button.setIconSize(QSize(20, 20))
                else:
                    print(f"Предупреждение: не удалось загрузить иконку {icon_name} для панели {tab_id}")
                    button.setText("?")
            else:
                print(f"Предупреждение: иконка не найдена в маппинге для панели {tab_id}")
                button.setText("?")
            
            button.setToolTip(tooltips.get(tab_id, tab_id))
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setAutoRaise(True)
            button.setFixedSize(32, 32)
            button.setProperty("tab_id", tab_id)
            
            # Стиль кнопки
            button.setStyleSheet(self._get_panel_button_style(False))
            
            self._panel_button_group.addButton(button, index)
            
            # Подключаем обработчик клика
            button.clicked.connect(
                lambda checked, tab=tab_id: 
                self._on_panel_button_clicked(tab, checked) if hasattr(self, 'aux_panel') else None
            )
            
            # Обновляем стиль при изменении состояния
            button.toggled.connect(
                lambda checked, btn=button: 
                self._update_panel_button_style(btn, checked)
            )
            
            self.toolbar.addWidget(button)
            self._panel_buttons[tab_id] = button
        
        # Устанавливаем первую кнопку как активную
        if "information" in self._panel_buttons:
            self._current_active_panel = "information"
            self._panel_buttons["information"].setChecked(True)
            self._update_panel_button_style(self._panel_buttons["information"], True)
            if hasattr(self, 'aux_panel'):
                self.aux_panel.setVisible(True)
                self.aux_panel.select_tab("information")
    
    def _on_panel_button_clicked(self, tab_id: str, checked: bool):
        """Обработчик клика на кнопку панели."""
        if not hasattr(self, 'aux_panel'):
            return
        
        # Если нажата уже активная панель - скрываем её
        if checked and self._current_active_panel == tab_id:
            # Скрываем панель
            self.aux_panel.setVisible(False)
            # Снимаем выделение с кнопки
            button = self._panel_buttons.get(tab_id)
            if button:
                button.setChecked(False)
                self._update_panel_button_style(button, False)
            self._current_active_panel = None
        elif checked:
            # Показываем панель и переключаемся на выбранную вкладку
            self.aux_panel.setVisible(True)
            self.aux_panel.select_tab(tab_id)
            self._current_active_panel = tab_id
        else:
            # Если кнопка была отжата (не должно происходить при обычном клике)
            # но на всякий случай обрабатываем
            if self._current_active_panel == tab_id:
                self.aux_panel.setVisible(False)
                self._current_active_panel = None
    
    @staticmethod
    def _get_panel_button_style(is_active: bool) -> str:
        """Получить стиль для кнопки панели в toolbar."""
        if is_active:
            return """
                QToolButton {
                    background-color: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.4);
                    border-radius: 4px;
                    padding: 0px;
                    min-width: 32px;
                    max-width: 32px;
                    min-height: 32px;
                    max-height: 32px;
                }
                QToolButton:hover {
                    background-color: rgba(255, 255, 255, 0.15);
                    border-color: rgba(255, 255, 255, 0.5);
                }
            """
        else:
            return """
                QToolButton {
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    padding: 0px;
                    min-width: 32px;
                    max-width: 32px;
                    min-height: 32px;
                    max-height: 32px;
                }
                QToolButton:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                    border-color: rgba(255, 255, 255, 0.15);
                }
            """
    
    @staticmethod
    def _update_panel_button_style(button: QToolButton, is_active: bool):
        """Обновить стиль кнопки панели в зависимости от состояния."""
        button.setStyleSheet(MainWindow._get_panel_button_style(is_active))
    
    def _on_aux_panel_tab_changed(self, tab_id: str):
        """Обработчик изменения активной вкладки в aux_panel."""
        # Обновляем состояние всех кнопок в toolbar
        # Только если панель видима
        if hasattr(self, 'aux_panel') and self.aux_panel.isVisible():
            self._current_active_panel = tab_id
            for btn_tab_id, button in self._panel_buttons.items():
                if btn_tab_id == tab_id:
                    button.setChecked(True)
                    self._update_panel_button_style(button, True)
                else:
                    button.setChecked(False)
                    self._update_panel_button_style(button, False)
    
    def _set_panels_visible(self, review_visible: bool, creation_visible: bool):
        """Установить видимость кнопок панелей Ревью и Создать ТК в toolbar.
        
        Args:
            review_visible: True для показа кнопки Ревью, False для скрытия
            creation_visible: True для показа кнопки Создать ТК, False для скрытия
        """
        if button := self._panel_buttons.get("review"):
            button.setVisible(review_visible)
        if button := self._panel_buttons.get("creation"):
            button.setVisible(creation_visible)
        
        # Если скрываем панели и текущая активная панель - одна из скрываемых, переключаемся на information
        if hasattr(self, 'aux_panel'):
            current_index = self.aux_panel._stack.currentIndex()
            tabs_order = self.aux_panel._tabs_order
            if not review_visible and current_index == tabs_order.index("review"):
                self.aux_panel.select_tab("information")
            if not creation_visible and current_index == tabs_order.index("creation"):
                self.aux_panel.select_tab("information")
    
    def _create_statusbar_statistics_label(self):
        """Создать QLabel для отображения статистики в statusbar"""
        self.statusbar_stats_label = QLabel("")
        self.statusbar_stats_label.setVisible(False)
        self.statusBar().addPermanentWidget(self.statusbar_stats_label)
    
    def _create_statusbar_save_button(self):
        """Создать кнопку 'Сохранить' в статус-баре"""
        statusbar = self.statusBar()
        
        # Создаем кнопку
        self.statusbar_save_button = QPushButton("Сохранить")
        self.statusbar_save_button.setMinimumHeight(28)
        self.statusbar_save_button.setMinimumWidth(100)
        self.statusbar_save_button.setCursor(Qt.PointingHandCursor)
        self.statusbar_save_button.setVisible(False)  # Скрыта по умолчанию
        self.statusbar_save_button.clicked.connect(self._on_save_button_clicked)
        
        # Добавляем кнопку в статус-бар (справа)
        statusbar.addPermanentWidget(self.statusbar_save_button)
    
    def _highlight_save_button(self):
        """Подсветить кнопку 'Сохранить' для привлечения внимания"""
        if hasattr(self, "statusbar_save_button"):
            # Получаем цвета из текущей темы
            theme = THEME_PROVIDER.colors
            success_color = theme.success  # Зеленый цвет для успеха
            
            # Применяем стиль с подсветкой (яркий зеленый фон для привлечения внимания)
            self.statusbar_save_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {success_color};
                    color: white;
                    border: 2px solid {success_color};
                    border-radius: 6px;
                    padding: 6px 16px;
                    font-weight: bold;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {success_color};
                    border-color: {success_color};
                    opacity: 0.9;
                }}
                QPushButton:pressed {{
                    background-color: {success_color};
                    border-color: {success_color};
                    opacity: 0.8;
                }}
            """)
    
    def _create_save_shortcut(self):
        """Создать горячую клавишу для сохранения (Ctrl+S на Windows/Linux, Cmd+S на macOS)"""
        # Используем QKeySequence.Save, который автоматически использует правильную комбинацию для каждой платформы
        # На Windows/Linux это Ctrl+S, на macOS это Cmd+S
        save_shortcut = QShortcut(QKeySequence.Save, self)
        save_shortcut.activated.connect(self._on_save_button_clicked)
        self.save_shortcut = save_shortcut  # Сохраняем ссылку, чтобы не удалился
    
    def _unhighlight_save_button(self):
        """Убрать подсветку с кнопки 'Сохранить'"""
        if hasattr(self, "statusbar_save_button"):
            # Получаем цвета из текущей темы
            theme = THEME_PROVIDER.colors
            button_bg = theme.button_background
            button_hover = theme.button_hover
            button_pressed = theme.button_pressed
            text_color = theme.text_primary
            border_color = theme.border_primary
            
            # Возвращаем обычный стиль (кнопка будет скрыта, но стиль нужен для плавного перехода)
            self.statusbar_save_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {button_bg};
                    color: {text_color};
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    padding: 6px 16px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {button_hover};
                    border-color: {theme.border_hover};
                }}
                QPushButton:pressed {{
                    background-color: {button_pressed};
                }}
            """)
    
    def _open_git_commit_dialog(self):
        """Открыть диалог с комментарием git-коммита."""
        dialog = GitCommitDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            comment = dialog.get_comment().strip()
            if comment:
                self._perform_git_commit(comment)

    def _get_git_repo_info(self):
        """Получить информацию о git репозитории (корень и относительный путь)."""
        test_cases_dir = self.test_cases_dir

        if not test_cases_dir or not test_cases_dir.exists():
            QMessageBox.warning(
                self,
                "Git",
                f"Папка с тест-кейсами не найдена:\n{test_cases_dir}",
            )
            return None, None

        # Находим корень git репозитория
        try:
            repo_root_proc = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(test_cases_dir),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True,
            )
            repo_root = Path(repo_root_proc.stdout.strip())
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Git",
                "Команда git не найдена. Установите Git и убедитесь, что он доступен в PATH.",
            )
            return None, None
        except subprocess.CalledProcessError as exc:
            error_message = exc.stderr or exc.stdout or str(exc)
            QMessageBox.critical(
                self,
                "Git",
                f"Папка с тест-кейсами не является частью git репозитория:\n{error_message}",
            )
            return None, None

        # Вычисляем относительный путь от корня репозитория до test_cases_dir
        try:
            test_cases_dir_abs = test_cases_dir.resolve()
            repo_root_abs = repo_root.resolve()
            relative_path = test_cases_dir_abs.relative_to(repo_root_abs)
            # Преобразуем в строку с использованием слешей (для git)
            git_path = str(relative_path).replace("\\", "/")
        except ValueError:
            # Если test_cases_dir не находится внутри repo_root, используем весь репозиторий
            git_path = "."

        return repo_root, git_path

    def _perform_git_commit(self, message: str):
        """Выполнить git commit только файлов из директории тест-кейсов."""
        repo_root, git_path = self._get_git_repo_info()
        if repo_root is None or git_path is None:
            return

        # Проверяем статус только файлов из test_cases_dir
        try:
            status_proc = subprocess.run(
                ["git", "status", "--porcelain", git_path],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            error_message = exc.stderr or exc.stdout or str(exc)
            QMessageBox.critical(
                self,
                "Git",
                f"Не удалось получить статус репозитория:\n{error_message}",
            )
            return

        if not status_proc.stdout.strip():
            QMessageBox.information(
                self,
                "Git",
                "Нет изменений для коммита в папке с тест-кейсами.",
            )
            return

        self.statusBar().showMessage("Git: подготовка изменений…")
        
        # Шаг 1: Добавление файлов
        try:
            self.statusBar().showMessage("Git: подготовка файлов…")
            add_result = subprocess.run(
                ["git", "add", git_path],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            if add_result.returncode != 0:
                stderr = (add_result.stderr or "").strip()
                stdout = (add_result.stdout or "").strip()
                combined_output = stderr or stdout or "Неизвестная ошибка."
                QMessageBox.critical(
                    self,
                    "Git",
                    f"Не удалось добавить файлы в индекс:\n{combined_output}",
                )
                self.statusBar().showMessage("Git: ошибка при добавлении файлов")
                return
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Git",
                "Команда git не найдена. Установите Git и убедитесь, что он доступен в PATH.",
            )
            self.statusBar().showMessage("Git: ошибка выполнения")
            return

        # Шаг 2: Создание коммита
        try:
            self.statusBar().showMessage("Git: создаю коммит…")
            commit_result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            
            if commit_result.returncode != 0:
                stderr = (commit_result.stderr or "").strip()
                stdout = (commit_result.stdout or "").strip()
                combined_output = stderr or stdout or "Неизвестная ошибка."
                
                # Если git commit сообщает об отсутствии изменений
                if "nothing to commit" in combined_output.lower() or "no changes" in combined_output.lower():
                    QMessageBox.information(
                        self,
                        "Git",
                        "Нет изменений для коммита.",
                    )
                    self.statusBar().showMessage("Git: нет изменений для коммита")
                    return
                
                # Проверяем, не исправил ли pre-commit хук файлы автоматически
                if "files were modified by this hook" in combined_output.lower() or "fixing" in combined_output.lower():
                    # Pre-commit хук исправил файлы, нужно добавить их и повторить коммит
                    self.statusBar().showMessage("Git: pre-commit хук исправил файлы, добавляю изменения…")
                    
                    # Добавляем исправленные файлы
                    try:
                        add_result = subprocess.run(
                            ["git", "add", git_path],
                            cwd=str(repo_root),
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                        )
                        
                        if add_result.returncode == 0:
                            # Повторяем коммит
                            self.statusBar().showMessage("Git: повторяю коммит после исправлений…")
                            retry_commit_result = subprocess.run(
                                ["git", "commit", "-m", message],
                                cwd=str(repo_root),
                                capture_output=True,
                                text=True,
                                encoding='utf-8',
                                errors='replace',
                            )
                            
                            if retry_commit_result.returncode == 0:
                                # Коммит успешно создан после исправлений
                                QMessageBox.information(
                                    self,
                                    "Git",
                                    "Коммит успешно создан.\n\n"
                                    "Pre-commit хук автоматически исправил некоторые файлы (например, добавил символ новой строки в конец файла).",
                                )
                                self.statusBar().showMessage("Git: коммит успешно создан")
                                # Обновляем индикаторы статуса Git
                                self._update_git_status_indicators()
                                return
                            else:
                                # Повторный коммит тоже не удался
                                retry_stderr = (retry_commit_result.stderr or "").strip()
                                retry_stdout = (retry_commit_result.stdout or "").strip()
                                retry_output = retry_stderr or retry_stdout or "Неизвестная ошибка."
                                QMessageBox.critical(
                                    self,
                                    "Git",
                                    f"Не удалось создать коммит после исправлений:\n{retry_output}",
                                )
                                self.statusBar().showMessage("Git: ошибка при создании коммита")
                                return
                        else:
                            # Не удалось добавить исправленные файлы
                            QMessageBox.critical(
                                self,
                                "Git",
                                f"Не удалось добавить исправленные файлы:\n{add_result.stderr or add_result.stdout}",
                            )
                            self.statusBar().showMessage("Git: ошибка при добавлении файлов")
                            return
                    except FileNotFoundError:
                        QMessageBox.critical(
                            self,
                            "Git",
                            "Команда git не найдена. Установите Git и убедитесь, что он доступен в PATH.",
                        )
                        self.statusBar().showMessage("Git: ошибка выполнения")
                        return
                else:
                    # Другая ошибка коммита
                    QMessageBox.critical(
                        self,
                        "Git",
                        f"Не удалось создать коммит:\n{combined_output}",
                    )
                    self.statusBar().showMessage("Git: ошибка при создании коммита")
                return
            else:
                # Коммит успешно создан
                QMessageBox.information(
                    self,
                    "Git",
                    "Коммит успешно создан.",
                )
                self.statusBar().showMessage("Git: коммит успешно создан")
                # Обновляем индикаторы статуса Git
                self._update_git_status_indicators()
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Git",
                "Команда git не найдена. Установите Git и убедитесь, что он доступен в PATH.",
            )
            self.statusBar().showMessage("Git: ошибка выполнения")
            return

    def _perform_git_push(self):
        """Выполнить git push только файлов из директории тест-кейсов."""
        repo_root, git_path = self._get_git_repo_info()
        if repo_root is None or git_path is None:
            return

        # Проверяем, есть ли коммиты для отправки
        try:
            status_proc = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True,
            )
            
            # Проверяем, есть ли локальные коммиты, которые не отправлены
            ahead_proc = subprocess.run(
                ["git", "rev-list", "--count", "@{u}..HEAD"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            
            # Если команда не удалась, возможно нет upstream ветки
            if ahead_proc.returncode != 0:
                # Проверяем наличие коммитов другим способом
                log_proc = subprocess.run(
                    ["git", "log", "--oneline", "-1"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                )
                if not log_proc.stdout.strip():
                    QMessageBox.information(
                        self,
                        "Git",
                        "Нет коммитов для отправки.",
                    )
                    return
        except subprocess.CalledProcessError as exc:
            error_message = exc.stderr or exc.stdout or str(exc)
            QMessageBox.critical(
                self,
                "Git",
                f"Не удалось проверить статус репозитория:\n{error_message}",
            )
            return

        # Отправка изменений (push)
        try:
            self.statusBar().showMessage("Git: отправляю изменения…")
            push_result = subprocess.run(
                ["git", "push"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60,  # Таймаут 60 секунд для push
            )
            
            if push_result.returncode != 0:
                stderr = (push_result.stderr or "").strip()
                stdout = (push_result.stdout or "").strip()
                combined_output = stderr or stdout or "Неизвестная ошибка."
                
                # Определяем тип ошибки для более понятного сообщения
                error_lower = combined_output.lower()
                if any(keyword in error_lower for keyword in ["could not resolve", "failed to connect", "connection refused", "network", "unreachable", "timeout"]):
                    error_message = (
                        "Не удалось отправить изменения в удалённый репозиторий.\n\n"
                        "Возможные причины:\n"
                        "• GitLab недоступен или перегружен\n"
                        "• Проблемы с сетевым подключением\n"
                        "• Неверный URL удалённого репозитория\n\n"
                        f"Детали ошибки:\n{combined_output}"
                    )
                elif "authentication" in error_lower or "permission" in error_lower or "denied" in error_lower:
                    error_message = (
                        "Не удалось отправить изменения: проблема с аутентификацией.\n\n"
                        "Проверьте:\n"
                        "• Настройки доступа к репозиторию\n"
                        "• Учётные данные Git\n\n"
                        f"Детали ошибки:\n{combined_output}"
                    )
                elif "rejected" in error_lower or "non-fast-forward" in error_lower:
                    error_message = (
                        "Не удалось отправить изменения: удалённый репозиторий содержит новые коммиты.\n\n"
                        "Выполните 'git pull' перед push или используйте 'git push --force' (осторожно!).\n\n"
                        f"Детали ошибки:\n{combined_output}"
                    )
                elif "no upstream" in error_lower or "no tracking" in error_lower or "has no upstream branch" in error_lower:
                    # Автоматически настраиваем upstream ветку
                    self.statusBar().showMessage("Git: настраиваю upstream ветку…")
                    
                    # Получаем имя текущей ветки
                    try:
                        branch_proc = subprocess.run(
                            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                            cwd=str(repo_root),
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            check=True,
                        )
                        branch_name = branch_proc.stdout.strip()
                    except subprocess.CalledProcessError:
                        QMessageBox.warning(
                            self,
                            "Git Push - Ошибка",
                            "Не удалось определить имя текущей ветки.",
                        )
                        self.statusBar().showMessage("Git: ошибка определения ветки")
                        return
                    
                    # Получаем имя удалённого репозитория (по умолчанию "origin")
                    try:
                        remote_proc = subprocess.run(
                            ["git", "remote"],
                            cwd=str(repo_root),
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            check=True,
                        )
                        remotes = remote_proc.stdout.strip().split('\n')
                        remote_name = remotes[0] if remotes and remotes[0] else "origin"
                    except subprocess.CalledProcessError:
                        # Если не удалось получить список удалённых репозиториев, используем "origin"
                        remote_name = "origin"
                    
                    # Выполняем push с настройкой upstream
                    try:
                        self.statusBar().showMessage(f"Git: отправляю изменения в {remote_name}/{branch_name}…")
                        push_setup_result = subprocess.run(
                            ["git", "push", "-u", remote_name, branch_name],
                            cwd=str(repo_root),
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            timeout=60,
                        )
                        
                        if push_setup_result.returncode != 0:
                            stderr = (push_setup_result.stderr or "").strip()
                            stdout = (push_setup_result.stdout or "").strip()
                            combined_output = stderr or stdout or "Неизвестная ошибка."
                            
                            # Определяем тип ошибки
                            error_lower_setup = combined_output.lower()
                            if any(keyword in error_lower_setup for keyword in ["could not resolve", "failed to connect", "connection refused", "network", "unreachable", "timeout"]):
                                error_message = (
                                    "Не удалось отправить изменения в удалённый репозиторий.\n\n"
                                    "Возможные причины:\n"
                                    "• GitLab недоступен или перегружен\n"
                                    "• Проблемы с сетевым подключением\n"
                                    "• Неверный URL удалённого репозитория\n\n"
                                    f"Детали ошибки:\n{combined_output}"
                                )
                            elif "authentication" in error_lower_setup or "permission" in error_lower_setup or "denied" in error_lower_setup:
                                error_message = (
                                    "Не удалось отправить изменения: проблема с аутентификацией.\n\n"
                                    "Проверьте:\n"
                                    "• Настройки доступа к репозиторию\n"
                                    "• Учётные данные Git\n\n"
                                    f"Детали ошибки:\n{combined_output}"
                                )
                            else:
                                error_message = (
                                    "Не удалось отправить изменения в удалённый репозиторий.\n\n"
                                    f"Детали ошибки:\n{combined_output}"
                                )
                            
                            QMessageBox.warning(
                                self,
                                "Git Push - Ошибка",
                                error_message,
                            )
                            self.statusBar().showMessage("Git: не удалось отправить изменения")
                            return
                        else:
                            # Push успешно выполнен с настройкой upstream
                            QMessageBox.information(
                                self,
                                "Git",
                                f"Изменения успешно отправлены в {remote_name}/{branch_name}.\n\n"
                                "Upstream ветка настроена автоматически.",
                            )
                            self.statusBar().showMessage("Git: изменения успешно отправлены")
                            # Обновляем индикаторы статуса Git
                            self._update_git_status_indicators()
                            return
                            
                    except subprocess.TimeoutExpired:
                        QMessageBox.warning(
                            self,
                            "Git Push - Таймаут",
                            (
                                "Превышено время ожидания при отправке изменений.\n\n"
                                "Возможные причины:\n"
                                "• GitLab недоступен или перегружен\n"
                                "• Медленное сетевое подключение\n"
                                "• Слишком большой объём данных для отправки\n\n"
                                "Попробуйте выполнить push позже или проверьте подключение к сети."
                            ),
                        )
                        self.statusBar().showMessage("Git: таймаут при отправке изменений")
                        return
                    except FileNotFoundError:
                        QMessageBox.critical(
                            self,
                            "Git",
                            "Команда git не найдена. Установите Git и убедитесь, что он доступен в PATH.",
                        )
                        self.statusBar().showMessage("Git: ошибка выполнения")
                        return
                else:
                    error_message = (
                        "Не удалось отправить изменения в удалённый репозиторий.\n\n"
                        f"Детали ошибки:\n{combined_output}"
                    )
                
                QMessageBox.warning(
                    self,
                    "Git Push - Ошибка",
                    error_message,
                )
                self.statusBar().showMessage("Git: не удалось отправить изменения")
                return
            else:
                # Push успешно выполнен
                QMessageBox.information(
                    self,
                    "Git",
                    "Изменения успешно отправлены в удалённый репозиторий.",
                )
                self.statusBar().showMessage("Git: изменения успешно отправлены")
                # Обновляем индикаторы статуса Git
                self._update_git_status_indicators()
                
        except subprocess.TimeoutExpired:
            QMessageBox.warning(
                self,
                "Git Push - Таймаут",
                (
                    "Превышено время ожидания при отправке изменений.\n\n"
                    "Возможные причины:\n"
                    "• GitLab недоступен или перегружен\n"
                    "• Медленное сетевое подключение\n"
                    "• Слишком большой объём данных для отправки\n\n"
                    "Попробуйте выполнить push позже или проверьте подключение к сети."
                ),
            )
            self.statusBar().showMessage("Git: таймаут при отправке изменений")
            return
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Git",
                "Команда git не найдена. Установите Git и убедитесь, что он доступен в PATH.",
            )
            self.statusBar().showMessage("Git: ошибка выполнения")
            return
    
    def _check_git_status(self):
        """Проверить статус Git: есть ли незакоммиченные изменения и незапушенные коммиты."""
        repo_root, git_path = self._get_git_repo_info()
        if repo_root is None or git_path is None:
            return False, False
        
        has_uncommitted = False
        has_unpushed = False
        
        try:
            # Проверяем наличие незакоммиченных изменений
            status_proc = subprocess.run(
                ["git", "status", "--porcelain", git_path],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True,
            )
            has_uncommitted = bool(status_proc.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Если не удалось проверить, считаем что изменений нет
            pass
        
        try:
            # Проверяем наличие незапушенных коммитов
            # Сначала проверяем, есть ли upstream ветка
            ahead_proc = subprocess.run(
                ["git", "rev-list", "--count", "@{u}..HEAD"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            
            if ahead_proc.returncode == 0:
                ahead_count = ahead_proc.stdout.strip()
                has_unpushed = bool(ahead_count and int(ahead_count) > 0)
            else:
                # Если нет upstream, проверяем наличие локальных коммитов
                # и наличие удалённого репозитория
                remote_check = subprocess.run(
                    ["git", "remote"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                )
                if remote_check.returncode == 0 and remote_check.stdout.strip():
                    # Есть удалённый репозиторий, но нет upstream - возможно есть коммиты для push
                    log_proc = subprocess.run(
                        ["git", "log", "--oneline", "-1"],
                        cwd=str(repo_root),
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                    )
                    has_unpushed = bool(log_proc.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            # Если не удалось проверить, считаем что коммитов для push нет
            pass
        
        return has_uncommitted, has_unpushed
    
    def _update_git_status_indicators(self):
        """Обновить визуальные индикаторы статуса Git в меню."""
        if not hasattr(self, 'git_commit_action') or not hasattr(self, 'git_push_action'):
            return
        
        has_uncommitted, has_unpushed = self._check_git_status()
        
        # Обновляем индикатор для Commit
        if has_uncommitted:
            # Есть незакоммиченные изменения - добавляем индикатор
            self.git_commit_action.setText('● Commit…')
        else:
            # Нет незакоммиченных изменений - обычный текст
            self.git_commit_action.setText('Commit…')
        
        # Обновляем индикатор для Push
        if has_unpushed:
            # Есть незапушенные коммиты - добавляем индикатор
            self.git_push_action.setText('● Push')
        else:
            # Нет незапушенных коммитов - обычный текст
            self.git_push_action.setText('Push')
        
        # Обновляем иконку меню Git (используем git_menu_action чтобы иконка отображалась рядом с текстом)
        if hasattr(self, 'git_menu_action'):
            if has_uncommitted:
                # Приоритет: незакоммиченные изменения - желтая иконка
                icon = self._load_svg_icon('arrow-up-right.svg', size=16, color='#f39c12')
                if icon:
                    self.git_menu_action.setIcon(icon)
                else:
                    self.git_menu_action.setIcon(QIcon())
            elif has_unpushed:
                # Есть незапушенные коммиты - синяя иконка
                icon = self._load_svg_icon('arrow-up-right.svg', size=16, color='#3498db')
                if icon:
                    self.git_menu_action.setIcon(icon)
                else:
                    self.git_menu_action.setIcon(QIcon())
            else:
                # Нет изменений - убираем иконку
                self.git_menu_action.setIcon(QIcon())
    
    def select_test_cases_folder(self):
        """Обработчик выбора папки с тест-кейсами"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку с тест-кейсами",
            str(self.test_cases_dir),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            self.test_cases_dir = Path(folder)
            self.settings['test_cases_dir'] = str(self.test_cases_dir)
            self.save_settings(self.settings)
            self.load_all_test_cases()
            self.statusBar().showMessage(f"Выбрана папка: {self.test_cases_dir}")
    
    
    def load_settings(self) -> dict:
        """Загрузка настроек"""
        defaults = {
            'test_cases_dir': 'testcases',
            'DEFAULT_PROMT': "Опиши, на что обратить внимание при ревью тест-кейсов.",
            'DEFAULT_PROMT_CREATE_TC': "Создай ТТ",
            'LLM_MODEL': llm.DEFAULT_MODEL,
            'LLM_HOST': llm.DEFAULT_HOST,
            'LLM_METHODIC_PATH': str(self._default_methodic_path()),
            'panel_sizes': {'left': 350, 'form_area': 900, 'review': 0},
            'skip_reasons': ['Автотесты', 'Нагрузочное тестирование', 'Другое'],
            'show_folder_counters': False,
        }
        
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    for key, value in defaults.items():
                        settings.setdefault(key, value)
                    if isinstance(settings.get('panel_sizes'), dict):
                        panel_defaults = defaults['panel_sizes']
                        for key, value in panel_defaults.items():
                            settings['panel_sizes'].setdefault(key, value)
                    else:
                        settings['panel_sizes'] = defaults['panel_sizes']
                    self.save_settings(settings)
                    return settings
            except Exception as e:
                print(f"Ошибка загрузки настроек: {e}")
        
        self.save_settings(defaults)
        return defaults
    
    def save_settings(self, data: dict):
        """Сохранение настроек"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
    
    def prompt_select_folder(self) -> Path:
        """Диалог выбора папки"""
        folder = QFileDialog.getExistingDirectory(
            None,
            "Выберите папку с тест-кейсами вашего репозитория",
            str(Path.cwd()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            selected_path = Path(folder)
            self.settings['test_cases_dir'] = str(selected_path)
            self.save_settings(self.settings)
            return selected_path
        
        # Если пользователь отменил выбор, сохраняем пустое значение
        # Это приведет к пустому дереву и диалог будет показан при следующем запуске
        self.settings['test_cases_dir'] = ""
        self.save_settings(self.settings)
        return Path("")
    
    def load_all_test_cases(self):
        """
        Загрузка всех тест-кейсов через сервис
        
        Демонстрирует Dependency Inversion:
        не работаем напрямую с файлами, используем сервис
        """
        # Если test_cases_dir пустое, не загружаем тест-кейсы и оставляем дерево пустым
        test_cases_dir_str = str(self.test_cases_dir).strip() if self.test_cases_dir else ""
        if not self.test_cases_dir or test_cases_dir_str == "":
            self.test_cases = []
            if hasattr(self, "tree_widget"):
                self.tree_widget.load_tree(Path(""), [])
            if hasattr(self, 'filter_panel'):
                self.filter_panel.update_test_cases([])
            if hasattr(self, "placeholder"):
                self.placeholder.update_statistics([])
            if hasattr(self, "aux_panel"):
                self.aux_panel.update_reports_panel()
            return
        
        expanded_state = set()
        selected_filepath = None
        # Сохраняем размеры панелей перед обновлением
        saved_detail_sizes = None
        if hasattr(self, "detail_splitter"):
            saved_detail_sizes = self.detail_splitter.sizes()
        
        if hasattr(self, "tree_widget"):
            expanded_state = self.tree_widget.capture_expanded_state()
            # Сохраняем путь к выбранному элементу для восстановления фокуса
            selected_filepath = self.tree_widget.capture_selected_item()

        self.test_cases = self.service.load_all_test_cases(self.test_cases_dir)
        
        # Обновляем панель фильтров с новыми тест-кейсами
        if hasattr(self, 'filter_panel'):
            self.filter_panel.update_test_cases(self.test_cases)
        
        # Обновляем дерево
        self.tree_widget.load_tree(self.test_cases_dir, self.test_cases)
        self.tree_widget.restore_expanded_state(expanded_state)
        # Восстанавливаем выбранный элемент
        if selected_filepath:
            self.tree_widget.restore_selected_item(selected_filepath)
        # Обновляем индикаторы статусов в дереве (в режиме запуска тестов)
        if not self.tree_widget._edit_mode:
            self.tree_widget._update_tree_icons(self.tree_widget.invisibleRootItem())
        
        # Восстанавливаем размеры панелей после обновления
        if saved_detail_sizes and hasattr(self, "detail_splitter"):
            self.detail_splitter.setSizes(saved_detail_sizes)
        
        # Обновляем статистику
        self.placeholder.update_statistics(self.test_cases)
        
        self._update_json_preview()
        # Обновляем статусбар (покажет статистику в режиме запуска или обычное сообщение в режиме редактирования)
        self._update_statusbar_statistics()
        # Обновляем панель отчетности
        if hasattr(self, "aux_panel"):
            self.aux_panel.update_reports_panel()

    def _update_statistics_panel(self):
        # Панель статистики удалена, метод оставлен для совместимости
        # Обновляем только статусбар
        self._update_statusbar_statistics()

    def _on_test_case_selected(self, test_case: TestCase):
        """Обработка выбора тест-кейса"""
        # Проверяем наличие несохраненных изменений перед переключением
        if hasattr(self, "form_widget") and self.form_widget.has_unsaved_changes:
            # Сохраняем предыдущий выбранный элемент для возможности отмены
            # Находим элемент по текущему тест-кейсу, так как currentItem() уже указывает на новый
            previous_test_case = self.current_test_case
            previous_item = None
            if previous_test_case and hasattr(previous_test_case, "_filepath"):
                previous_item = self.tree_widget._find_item_by_filepath(
                    self.tree_widget.invisibleRootItem(), 
                    previous_test_case._filepath
                )
            
            # Показываем диалог с вопросом о сохранении
            reply = QMessageBox.question(
                self,
                "Несохраненные изменения",
                "Есть несохраненные изменения. Сохранить?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Cancel:
                # Отменяем переключение - возвращаем выделение на предыдущий элемент
                if previous_item:
                    # Временно блокируем сигнал, чтобы не вызвать рекурсию
                    self.tree_widget.itemClicked.disconnect()
                    self.tree_widget.setCurrentItem(previous_item)
                    self.tree_widget.itemClicked.connect(self.tree_widget._on_item_clicked)
                return
            elif reply == QMessageBox.Yes:
                # Сохраняем изменения перед переключением
                if hasattr(self, "form_widget"):
                    self.form_widget.save()
                    # После сохранения проверяем, не было ли ошибки сохранения
                    if self.form_widget.has_unsaved_changes:
                        # Если сохранение не удалось, отменяем переключение
                        if previous_item:
                            self.tree_widget.itemClicked.disconnect()
                            self.tree_widget.setCurrentItem(previous_item)
                            self.tree_widget.itemClicked.connect(self.tree_widget._on_item_clicked)
                        return
        
        # Устанавливаем флаг для предотвращения автоматического изменения размеров панелей
        self._preserve_panel_sizes = True
        
        self.current_test_case = test_case
        self.detail_stack.setCurrentWidget(self.form_widget)
        self.form_widget.load_test_case(test_case)
        # Обновляем панель информации
        if hasattr(self, "aux_panel"):
            self.aux_panel.set_information_test_case(test_case)
            self.aux_panel.set_files_test_case(test_case)
            self.aux_panel.set_manual_review_test_case(test_case)
            # Подключаем сигнал изменения attachments в панели файлов
            if hasattr(self.aux_panel, "files_panel"):
                try:
                    self.aux_panel.files_panel.attachment_changed.disconnect()
                except TypeError:
                    pass
                self.aux_panel.files_panel.attachment_changed.connect(self._on_files_attachment_changed)
        self._update_json_preview()
        
        # Сбрасываем флаг после завершения операции
        QTimer.singleShot(200, lambda: setattr(self, '_preserve_panel_sizes', False))
        
        # Обновляем статусбар (покажет статистику в режиме запуска или сообщение в режиме редактирования)
        if self._current_mode == "run":
            self._update_statusbar_statistics()
        else:
            self.statusBar().showMessage(f"Открыт: {test_case.name}")
    
    def _on_form_unsaved_state(self, has_changes: bool):
        """Обновление статуса при изменениях в форме"""
        # Управляем видимостью и подсветкой кнопки сохранения в статус-баре
        if hasattr(self, "statusbar_save_button"):
            self.statusbar_save_button.setVisible(has_changes)
            if has_changes:
                self._highlight_save_button()
            else:
                self._unhighlight_save_button()
        if has_changes:
            self.statusBar().showMessage("Есть несохраненные изменения. Нажмите «Сохранить».")
        else:
            if self.current_test_case:
                self.statusBar().showMessage(f"Изменения сохранены. Открыт: {self.current_test_case.name}")
            else:
                self.statusBar().showMessage("Готов к работе")
        self._update_mode_indicator()
    
    def _on_save_button_clicked(self):
        """Обработка нажатия кнопки сохранения"""
        if hasattr(self, "form_widget"):
            self.form_widget.save()
    
    def _on_tree_updated(self):
        """Обработка обновления дерева"""
        self.load_all_test_cases()
        self.statusBar().showMessage("Дерево тест-кейсов обновлено.")
    
    def _on_test_cases_updated(self):
        """Обработка обновления тест-кейсов после изменения статусов"""
        try:
            # Сохраняем состояние дерева
            expanded_state = self.tree_widget.capture_expanded_state()
            selected_filepath = self.tree_widget.capture_selected_item()
            
            # Перезагружаем тест-кейсы
            self.load_all_test_cases()
            
            # Восстанавливаем состояние дерева
            self.tree_widget.restore_expanded_state(expanded_state)
            if selected_filepath:
                self.tree_widget.restore_selected_item(selected_filepath)
            
            # Обновляем индикаторы статусов в дереве (в режиме запуска тестов)
            if not self.tree_widget._edit_mode:
                self.tree_widget._update_tree_icons(self.tree_widget.invisibleRootItem())
            
            # Обновляем статистику в statusbar
            self._update_statusbar_statistics()
            
            # Обновляем панель отчетности
            if hasattr(self, "aux_panel"):
                self.aux_panel.update_reports_panel()
            
            # Обновляем форму, если открыт текущий тест-кейс
            if self.current_test_case:
                # Находим обновленный тест-кейс
                current_filepath = getattr(self.current_test_case, "_filepath", None)
                if current_filepath:
                    updated_case = next(
                        (tc for tc in self.test_cases if getattr(tc, "_filepath", None) == current_filepath),
                        None
                    )
                    if updated_case:
                        self.current_test_case = updated_case
                        self.form_widget.load_test_case(updated_case)
        except Exception as e:
            # Логируем ошибку, но не показываем пользователю, чтобы не прерывать работу
            print(f"Ошибка при обновлении тест-кейсов: {e}")
    
    def _on_status_changed(self):
        """Обработка изменения статуса шага"""
        # Обновляем статистику в statusbar при изменении статуса
        self._update_statusbar_statistics()
        # Обновляем панель отчетности
        if hasattr(self, "aux_panel"):
            self.aux_panel.update_reports_panel()
        # Обновляем индикаторы статусов в дереве (в режиме запуска тестов)
        if hasattr(self, "tree_widget") and not self.tree_widget._edit_mode:
            self.tree_widget._update_tree_icons(self.tree_widget.invisibleRootItem())
        # Обновляем статистику при изменении статуса
        if hasattr(self, "placeholder") and hasattr(self, "test_cases"):
            self.placeholder.update_statistics(self.test_cases)
    
    def _on_test_case_saved(self):
        """Обработка сохранения тест-кейса"""
        # Обновляем панель информации после сохранения
        if hasattr(self, "aux_panel") and self.current_test_case:
            self.aux_panel.set_information_test_case(self.current_test_case)
            # Обновляем панель "Файлы" для отображения прикрепленных файлов
            self.aux_panel.set_files_test_case(self.current_test_case)
            self.aux_panel.set_manual_review_test_case(self.current_test_case)
        self.load_all_test_cases()
        # Обновляем индикаторы статусов в дереве (в режиме запуска тестов)
        if hasattr(self, "tree_widget") and not self.tree_widget._edit_mode:
            self.tree_widget._update_tree_icons(self.tree_widget.invisibleRootItem())
        # Обновляем индикаторы статуса Git после сохранения
        self._update_git_status_indicators()
        self._update_json_preview()
        # Обновляем статистику в statusbar (всегда)
        self._update_statusbar_statistics()
    
    def _on_information_data_changed(self):
        """Обработка изменения данных в панели информации"""
        if not self.current_test_case:
            return
        # Обновляем тест-кейс данными из панели информации
        self.aux_panel.update_information_test_case(self.current_test_case)
        # Помечаем изменения в форме (чтобы появилась кнопка сохранения)
        self.form_widget.has_unsaved_changes = True
        self.form_widget.unsaved_changes_state.emit(True)
        # Обновляем статистику при изменении данных
        if hasattr(self, "placeholder") and hasattr(self, "test_cases"):
            self.placeholder.update_statistics(self.test_cases)
    
    def _on_files_attachment_changed(self):
        """Обработка изменения attachments в панели файлов"""
        if not self.current_test_case:
            return
        # Помечаем изменения в форме (чтобы появилась кнопка сохранения)
        self.form_widget.has_unsaved_changes = True
        self.form_widget.unsaved_changes_state.emit(True)
    
    def _on_file_attached_to_step(self):
        """Обработка прикрепления файла к шагу из формы"""
        if not self.current_test_case:
            return
        # Обновляем панель "Файлы" для отображения нового файла
        if hasattr(self, "aux_panel"):
            self.aux_panel.set_files_test_case(self.current_test_case)
        # Помечаем изменения в форме (чтобы появилась кнопка сохранения)
        self.form_widget.has_unsaved_changes = True
        self.form_widget.unsaved_changes_state.emit(True)
    
    def _on_manual_review_notes_changed(self):
        """Обработка изменения notes в панели ручного ревью"""
        if not self.current_test_case:
            return
        
        # Notes уже обновлены в current_test_case в момент вызова сигнала
        # Автоматически сохраняем тест-кейс после изменения notes
        if hasattr(self, "form_widget") and self.current_test_case:
            # Убеждаемся, что form_widget использует тот же объект тест-кейса
            if self.form_widget.current_test_case != self.current_test_case:
                self.form_widget.current_test_case = self.current_test_case
            # Сохраняем тест-кейс (notes уже обновлены в current_test_case)
            self.form_widget.save()
        
        # Обновляем JSON preview, чтобы показать изменения
        self._update_json_preview()
    
    def _on_form_before_save(self, test_case: TestCase):
        """Обновить данные тест-кейса из панели информации перед сохранением"""
        if hasattr(self, "aux_panel") and test_case:
            self.aux_panel.update_information_test_case(test_case)
    
    def _filter_tree(self):
        query = self.search_input.text()
        # Получаем текущие фильтры
        filters = getattr(self, '_current_filters', {})
        self.tree_widget.filter_items(query, filters)
    
    def _on_filter_button_clicked(self):
        """Обработчик клика на кнопку фильтра."""
        if not hasattr(self, 'filter_panel'):
            return
        
        # Переключаемся на панель фильтров
        if self.detail_stack.currentWidget() == self.filter_panel:
            # Если уже открыта панель фильтров, возвращаемся к форме
            if self._current_test_case_path:
                self.detail_stack.setCurrentWidget(self.form_widget)
            else:
                self.detail_stack.setCurrentWidget(self.placeholder)
        else:
            # Показываем панель фильтров
            self.detail_stack.setCurrentWidget(self.filter_panel)
    
    def _on_filters_applied(self, filters: dict):
        """Обработчик применения фильтров."""
        # Обновляем цвет иконки фильтра на зеленый
        if hasattr(self, 'filter_button'):
            filter_icon_name = "filter.svg"
            mapping_file = get_icons_dir() / "icon_mapping.json"
            if mapping_file.exists():
                try:
                    with open(mapping_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        filter_icon_name = data.get("search", {}).get("filter", "filter.svg")
                except:
                    pass
            
            filter_icon = self._load_svg_icon(filter_icon_name, size=20, color="#4CAF50")  # Зеленый цвет
            if filter_icon:
                self.filter_button.setIcon(filter_icon)
        
        # Применяем фильтры к дереву
        query = self.search_input.text() if hasattr(self, 'search_input') else ""
        if hasattr(self, 'tree_widget'):
            self.tree_widget.filter_items(query, filters)
            # Подсчитываем количество найденных тест-кейсов
            count = self.tree_widget.count_visible_test_cases()
            self.statusBar().showMessage(f"Найдено тест-кейсов: {count}")
    
    def _on_filters_reset(self):
        """Обработчик сброса фильтров."""
        # Возвращаем белый цвет иконки фильтра
        if hasattr(self, 'filter_button'):
            filter_icon_name = "filter.svg"
            mapping_file = get_icons_dir() / "icon_mapping.json"
            if mapping_file.exists():
                try:
                    with open(mapping_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        filter_icon_name = data.get("search", {}).get("filter", "filter.svg")
                except:
                    pass
            
            filter_icon = self._load_svg_icon(filter_icon_name, size=20, color="#ffffff")  # Белый цвет
            if filter_icon:
                self.filter_button.setIcon(filter_icon)
        
        # Сбрасываем фильтры
        self._current_filters = {}
        
        # Сбрасываем фильтры в дереве
        query = self.search_input.text() if hasattr(self, 'search_input') else ""
        if hasattr(self, 'tree_widget'):
            self.tree_widget.filter_items(query, {})

    def _on_review_requested(self, data):
        """Показ панели ревью."""
        if self.detail_stack.currentWidget() is not self.form_widget:
            self.detail_stack.setCurrentWidget(self.form_widget)
        self.aux_panel.select_tab("review")
        attachments = self._collect_review_attachments(data)
        self.aux_panel.set_review_attachments(attachments)
        base_prompt = self.settings.get('DEFAULT_PROMT', self.default_prompt)
        self.aux_panel.set_review_prompt_text(base_prompt)
        self.aux_panel.clear_review_response()
        self.statusBar().showMessage("Панель ревью открыта")
    
    def _on_add_to_review_requested(self, test_case: TestCase):
        """Добавить файл тест-кейса в панель ревью."""
        if hasattr(self, "aux_panel") and hasattr(self.aux_panel, "review_panel"):
            if hasattr(test_case, "_filepath") and test_case._filepath:
                self.aux_panel.review_panel.add_attachments([test_case._filepath])
                # Переключаемся на панель ревью, если она не активна
                if self.aux_panel._stack.currentIndex() != self.aux_panel._tabs_order.index("review"):
                    self.aux_panel.select_tab("review")
                self.statusBar().showMessage(f"Файл {test_case._filepath.name} добавлен в панель ревью")

    def _on_prompt_saved(self, text: str):
        """Сохранение промта в настройках."""
        self.settings['DEFAULT_PROMT'] = text
        self.save_settings(self.settings)
        self.default_prompt = text
        self.statusBar().showMessage("Промт сохранен")

    def _on_creation_prompt_saved(self, text: str):
        """Сохранение промта для создания ТК."""
        self.settings['DEFAULT_PROMT_CREATE_TC'] = text
        self.save_settings(self.settings)
        self.create_tc_prompt = text
        self.aux_panel.set_creation_default_prompt(text)
        self.statusBar().showMessage("Промт создания ТК сохранен")

    def _collect_review_attachments(self, data) -> List[Path]:
        attachments: List[Path] = []
        self._current_test_case_path = None

        if self.methodic_path and self.methodic_path not in attachments:
            attachments.append(self.methodic_path)

        if isinstance(data, dict) and data.get('type') == 'file':
            test_case = data.get('test_case')
            file_path = getattr(test_case, '_filepath', None)
            if file_path:
                path_obj = Path(file_path)
                self._current_test_case_path = path_obj
                if path_obj not in attachments:
                    attachments.append(path_obj)

        return attachments

    def _fetch_available_llm_models(self) -> List[str]:
        fallback = [self.llm_model] if self.llm_model else []
        host = self.llm_host
        if not host:
            return fallback
        try:
            models = fetch_llm_models(host)
        except Exception as exc:  # noqa: BLE001
            print(f"[LLM] Не удалось получить список моделей с {host}: {exc}")
            return fallback

        cleaned = [str(model).strip() for model in (models or []) if str(model or "").strip()]
        if self.llm_model and self.llm_model not in cleaned:
            cleaned.insert(0, self.llm_model)
        return cleaned or fallback

    def _start_llm_availability_check(self):
        """Запустить первую проверку доступности LLM и настроить периодическую проверку"""
        # Запускаем первую проверку сразу (с небольшой задержкой, чтобы UI успел инициализироваться)
        QTimer.singleShot(100, self._check_llm_availability)
        # Настраиваем таймер для периодической проверки каждые 5 минут (300000 мс)
        self._llm_check_timer.start(300000)  # 5 минут

    def _check_llm_availability(self):
        """Проверить доступность LLM в фоновом потоке"""
        # Если предыдущая проверка еще выполняется, не запускаем новую
        if self._llm_availability_thread and self._llm_availability_thread.isRunning():
            return
        
        # Если host не задан, просто устанавливаем статус как недоступный
        if not self.llm_host or not self.llm_host.strip():
            self._llm_available = False
            self._update_statusbar_statistics()
            return
        
        # Создаем воркер и поток для проверки доступности
        worker = _LLMAvailabilityWorker(self.llm_host)
        thread = QThread()
        worker.moveToThread(thread)

        # Подключаем сигналы
        worker.availability_checked.connect(self._on_llm_availability_checked)
        thread.started.connect(worker.run)

        thread.start()

        self._llm_availability_worker = worker
        self._llm_availability_thread = thread

    def _on_llm_availability_checked(self, is_available: bool):
        """Обработчик результата проверки доступности LLM"""
        self._llm_available = is_available
        # Обновляем статистику, так как она теперь включает статус LLM
        self._update_statusbar_statistics()
        # Очищаем воркер и поток после обновления статуса
        QTimer.singleShot(0, self._cleanup_llm_availability_worker)

    def _cleanup_llm_availability_worker(self):
        """Очистка воркера и потока проверки доступности LLM"""
        if self._llm_availability_thread:
            if self._llm_availability_thread.isRunning():
                self._llm_availability_thread.quit()
                self._llm_availability_thread.wait()
            self._llm_availability_thread.deleteLater()
            self._llm_availability_thread = None
        if self._llm_availability_worker:
            self._llm_availability_worker.deleteLater()
            self._llm_availability_worker = None

    def _apply_model_options(self):
        models = self.available_llm_models or ([self.llm_model] if self.llm_model else [])
        default = self.selected_llm_model or self.llm_model or (models[0] if models else "")
        self._configure_model_selector(models, default)
        if not models:
            warning = (
                "Не удалось получить список моделей LLM. Проверьте настройки LLM_HOST/LLM_MODEL "
                "и повторите попытку."
            )
            self.statusBar().showMessage(warning)

    def _configure_model_selector(self, models: List[str], default: str):
        if not hasattr(self, "model_selector"):
            return
        combo = self.model_selector
        cleaned = [str(m).strip() for m in models if str(m or "").strip()]
        self._model_options = cleaned
        self._model_list_model.setStringList(cleaned)
        target = (default or (cleaned[0] if cleaned else "")).strip()
        self._reset_model_filter()
        self._suppress_model_change = True
        if target and target in cleaned:
            source_index = self._model_list_model.index(cleaned.index(target), 0)
            proxy_index = self._model_proxy_model.mapFromSource(source_index)
            if proxy_index.isValid():
                combo.setCurrentIndex(proxy_index.row())
        else:
            combo.setCurrentIndex(-1)
        combo.setEditText(target)
        self._suppress_model_change = False
        line_edit = combo.lineEdit()
        if line_edit:
            line_edit.setPlaceholderText("Выберите модель…")
        self.selected_llm_model = target
        if target:
            self.llm_model = target

    def _on_model_selector_changed(self, text: str):
        if self._suppress_model_change:
            return
        value = (text or "").strip()
        self.selected_llm_model = value
        if value:
            self._apply_model_selection(value)

    def _apply_model_selection(self, value: str):
        value = (value or "").strip()
        if not value:
            return
        self.selected_llm_model = value
        self.llm_model = value
        self.settings['LLM_MODEL'] = value
        self.save_settings(self.settings)

    def _current_llm_model(self) -> str:
        value = (self.selected_llm_model or "").strip()
        if value:
            return value
        if hasattr(self, "model_selector"):
            return self.model_selector.currentText().strip()
        return self.llm_model or ""

    def _on_model_selector_text_edited(self, text: str):
        if not hasattr(self, "_model_proxy_model"):
            return
        if text:
            pattern = f".*{QRegularExpression.escape(text)}.*"
            regex = QRegularExpression(pattern, QRegularExpression.CaseInsensitiveOption)
        else:
            regex = QRegularExpression(".*", QRegularExpression.CaseInsensitiveOption)
        self._model_proxy_model.setFilterRegularExpression(regex)
        self.model_selector.showPopup()
        line_edit = self.model_selector.lineEdit()
        if line_edit:
            line_edit.setFocus()
            line_edit.setCursorPosition(len(text))

    def _on_model_editing_finished(self):
        if not hasattr(self, "model_selector"):
            return
        line_edit = self.model_selector.lineEdit()
        if not line_edit:
            return
        value = line_edit.text().strip()
        if not value:
            self._reset_model_filter()
            return
        if value not in self._model_options:
            self._model_options.append(value)
            self._model_list_model.setStringList(self._model_options)
        self._reset_model_filter()
        source_index = self._model_list_model.index(self._model_options.index(value), 0)
        proxy_index = self._model_proxy_model.mapFromSource(source_index)
        self._suppress_model_change = True
        if proxy_index.isValid():
            self.model_selector.setCurrentIndex(proxy_index.row())
        else:
            self.model_selector.setCurrentIndex(-1)
        self.model_selector.setEditText(value)
        self._suppress_model_change = False
        self._apply_model_selection(value)

    def _reset_model_filter(self):
        if hasattr(self, "_model_proxy_model"):
            self._model_proxy_model.setFilterRegularExpression(
                QRegularExpression(".*", QRegularExpression.CaseInsensitiveOption)
            )
    

    def _confirm_and_reset_all_statuses(self):
        """Показать диалог подтверждения и сбросить статусы всех тест-кейсов"""
        reply = QMessageBox.question(
            self,
            "Подтверждение действия",
            "Вы уверены, что хотите сбросить статусы всех шагов во всех тест-кейсах?\n\n"
            "Это действие нельзя отменить.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._reset_all_step_statuses()
    
    def _reset_all_step_statuses(self):
        if not self.test_cases:
            return
        count = 0
        for case in self.test_cases:
            if not case.steps:
                continue
            for step in case.steps:
                step.status = ""
                step.skip_reason = ""  # Очищаем skipReason при сбросе статуса
            self.service.save_test_case(case)
            count += 1
        self.load_all_test_cases()
        if self.current_test_case:
            self.form_widget.load_test_case(self.current_test_case)
        # Обновляем индикаторы статусов в дереве (в режиме запуска тестов)
        if hasattr(self, "tree_widget") and not self.tree_widget._edit_mode:
            self.tree_widget._update_tree_icons(self.tree_widget.invisibleRootItem())
        # Обновляем статистику в statusbar (всегда)
        self._update_statusbar_statistics()
        QMessageBox.information(self, "Готово", f"Статусы сброшены для {count} тест-кейсов")

    def _mark_current_case_passed(self):
        if not self.current_test_case or not self.current_test_case.steps:
            return
        for step in self.current_test_case.steps:
            step.status = "passed"
            step.skip_reason = ""  # Очищаем skipReason при пометке как passed
        self.service.save_test_case(self.current_test_case)
        self.form_widget.load_test_case(self.current_test_case)
        self.load_all_test_cases()
        # Обновляем индикаторы статусов в дереве (в режиме запуска тестов)
        if hasattr(self, "tree_widget") and not self.tree_widget._edit_mode:
            self.tree_widget._update_tree_icons(self.tree_widget.invisibleRootItem())
        # Обновляем статистику в statusbar (всегда)
        self._update_statusbar_statistics()
        self._update_statistics_panel()

    def _reset_current_case_statuses(self):
        if not self.current_test_case or not self.current_test_case.steps:
            return
        for step in self.current_test_case.steps:
            step.status = ""
        self.service.save_test_case(self.current_test_case)
        self.form_widget.load_test_case(self.current_test_case)
        self.load_all_test_cases()
        # Обновляем индикаторы статусов в дереве (в режиме запуска тестов)
        if hasattr(self, "tree_widget") and not self.tree_widget._edit_mode:
            self.tree_widget._update_tree_icons(self.tree_widget.invisibleRootItem())
        # Обновляем статусбар (покажет статистику в режиме запуска или сообщение в режиме редактирования)
        if self._current_mode == "run":
            self._update_statusbar_statistics()
        else:
            self.statusBar().showMessage("Статусы текущего тест-кейса сброшены")
        self._update_statistics_panel()

    def _show_statistics_panel(self):
        """Показать дерево и статистику (placeholder)."""
        self.detail_stack.setCurrentWidget(self.placeholder)
        self.statusBar().showMessage("Показана статистика тест-кейсов")

    def _find_chtz_attachment(self, attachments: List[Path]) -> Optional[Path]:
        for path in attachments:
            if self.methodic_path and path == self.methodic_path:
                continue
            name_lower = path.name.lower()
            if "chtz" in name_lower or "чтз" in name_lower or ("тз" in name_lower and path.suffix.lower() in {".txt", ".md", ".docx", ".doc"}):
                return path
        return None

    @staticmethod
    def _default_methodic_path() -> Path:
        return Path(__file__).resolve().parent.parent / "docs" / "test-cases-guidelines.md"

    @staticmethod
    def _find_test_case_attachment(attachments: List[Path]) -> Optional[Path]:
        for path in attachments:
            if path.suffix.lower() in {".json", ".txt", ".md"}:
                return path
        return None


    def _on_review_enter_clicked(self, text: str, files: list):
        """Обработка нажатия кнопки Enter на панели ревью."""
        self.aux_panel.select_tab("review")
        self._submit_prompt(
            prompt_text=text,
            model=self._current_llm_model(),
            files=files,
            status_context="Ревью",
            default_test_case_path=self._current_test_case_path,
            set_loading=self.aux_panel.set_review_loading_state,
            set_response=self.aux_panel.set_review_response_text,
            success_handler=self._handle_review_success,
            error_handler=self._handle_review_error,
        )

    def _on_creation_enter_clicked(self, text: str, files: list):
        """Обработка Enter в панели создания ТК."""
        self.aux_panel.select_tab("creation")
        self._submit_creation_prompt(text=text, files=files)

    def _submit_prompt(
        self,
        *,
        prompt_text: str,
        model: str,
        files: list,
        status_context: str,
        default_test_case_path: Optional[Path],
        set_loading,
        set_response,
        success_handler,
        error_handler,
    ):
        prompt = (prompt_text or "").strip()
        if not prompt:
            set_response("Введите промт перед отправкой.")
            self.statusBar().showMessage(f"{status_context}: пустой промт — запрос не отправлен")
            return

        if self._llm_thread and self._llm_thread.isRunning():
            self.statusBar().showMessage(f"{status_context}: ожидайте завершения текущего запроса к LLM")
            return

        attachment_paths = [Path(p) for p in files]
        set_loading(True)
        set_response("Отправляю запрос в LLM…")

        model_used = (model or self.llm_model or "").strip()
        host = self.llm_host or None
        if not model_used and self.available_llm_models:
            model_used = self.available_llm_models[0]

        chtz_path = self._find_chtz_attachment(attachment_paths)
        test_case_path = default_test_case_path or self._find_test_case_attachment(attachment_paths)

        try:
            payload = build_review_prompt(
                self.methodic_path,
                prompt,
                test_case_path=test_case_path,
                chtz_path=chtz_path,
            )
        except Exception as exc:  # pylint: disable=broad-except
            set_loading(False)
            set_response(f"Не удалось подготовить промт: {exc}")
            self.statusBar().showMessage(f"{status_context}: ошибка подготовки промта для LLM")
            return

        self._start_llm_request(payload, model_used or None, host, success_handler, error_handler)
        self.statusBar().showMessage(
            f"{status_context}: отправлен промт (модель {model_used or 'не указана'}) длиной {len(prompt)} символов. "
            f"Прикреплено файлов: {len(files)}"
        )

    def _submit_creation_prompt(self, *, text: str, files: list):
        set_loading = self.aux_panel.set_creation_loading_state
        set_response = self.aux_panel.set_creation_response_text

        if self._llm_thread and self._llm_thread.isRunning():
            self.statusBar().showMessage("Создание ТК: ожидайте завершения текущего запроса к LLM")
            return

        task_text = (text or "").strip() or (self.create_tc_prompt or "Создай ТТ")

        set_loading(True)
        set_response("Отправляю запрос в LLM…")

        methodic_path = self.methodic_path

        attachment_paths: list[Path] = []
        for raw_path in files:
            try:
                attachment_paths.append(Path(raw_path))
            except (TypeError, ValueError):
                continue

        methodic_resolved = None
        if methodic_path:
            try:
                methodic_resolved = methodic_path.resolve()
            except OSError:
                methodic_resolved = methodic_path

        tech_task_paths: list[Path] = []
        seen = set()
        for path in attachment_paths:
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if methodic_resolved and resolved == methodic_resolved:
                continue
            if not path.exists():
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            tech_task_paths.append(path)

        try:
            payload = build_creation_prompt(methodic_path, tech_task_paths, task_text)
        except Exception as exc:  # noqa: BLE001
            set_loading(False)
            set_response(f"Не удалось подготовить промт: {exc}")
            self.statusBar().showMessage("Создание ТК: ошибка подготовки промта для LLM")
            return

        model_used = self._current_llm_model() or self.llm_model
        if not model_used and self.available_llm_models:
            model_used = self.available_llm_models[0]
        host = self.llm_host or None

        self._start_llm_request(
            payload,
            model_used or None,
            host,
            self._handle_creation_success,
            self._handle_creation_error,
        )
        self.statusBar().showMessage(
            f"Создание ТК: отправлен промт (модель {model_used or 'не указана'}) длиной {len(payload)} символов. "
            f"Прикреплено файлов: {len(files)}"
        )

    @staticmethod
    def _extract_json_from_llm(raw_text: str):
        """Попытаться извлечь JSON из произвольного текста LLM."""
        candidates = []
        code_blocks = re.findall(r"```(?:json)?\s*(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
        candidates.extend(code_blocks)
        candidates.append(raw_text)

        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        decoder = json.JSONDecoder()
        for match in re.finditer(r"[\[{]", raw_text):
            start_index = match.start()
            try:
                obj, _ = decoder.raw_decode(raw_text[start_index:].strip())
            except json.JSONDecodeError:
                continue
            else:
                return obj

        return None

    def _materialize_generated_test_cases(self, raw_response: str):
        """Создать файлы тест-кейсов на основе ответа LLM."""
        parsed = self._extract_json_from_llm(raw_response)
        if parsed is None:
            self.statusBar().showMessage("Создание ТК: не удалось распознать JSON в ответе LLM")
            return

        if isinstance(parsed, dict):
            if isinstance(parsed.get("test_cases"), list):
                payloads = parsed.get("test_cases") or []
            elif isinstance(parsed.get("cases"), list):
                payloads = parsed.get("cases") or []
            else:
                payloads = [parsed]
        elif isinstance(parsed, list):
            payloads = parsed
        else:
            self.statusBar().showMessage("Создание ТК: ответ LLM имеет неподдерживаемый формат")
            return

        if not payloads:
            self.statusBar().showMessage("Создание ТК: JSON не содержит тест-кейсов")
            return

        target_folder = self.test_cases_dir / "from LLM"
        target_folder.mkdir(parents=True, exist_ok=True)

        created_cases: List[TestCase] = []
        errors: List[str] = []

        for idx, payload in enumerate(payloads, start=1):
            if not isinstance(payload, dict):
                errors.append(f"{idx}: ожидался объект тест-кейса.")
                continue
            try:
                test_case = self.service.create_test_case_from_dict(payload, target_folder)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{idx}: не удалось построить тест-кейс ({exc})")
                continue

            if self.service.save_test_case(test_case):
                created_cases.append(test_case)
                try:
                    self.service._repository.save(test_case, test_case._filepath)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{idx}: не удалось записать файл «{test_case.name}»: {exc}")
                else:
                    errors.append(f"{idx}: не удалось сохранить файл тест-кейса «{test_case.name}».")

        summary_lines: List[str] = []
        if created_cases:
            summary_lines.append(f"Создано тест-кейсов: {len(created_cases)}.")
        if errors:
            summary_lines.append("Ошибки:\n" + "\n".join(errors))

        if summary_lines:
            combined = raw_response.strip()
            combined += "\n\n" + "\n".join(summary_lines)
            self.aux_panel.set_creation_response_text(combined)

        highlight_path = created_cases[0]._filepath if created_cases else None
        if created_cases:
            self.load_all_test_cases()
            if highlight_path:
                refreshed = next(
                    (tc for tc in self.test_cases if getattr(tc, "_filepath", None) == highlight_path),
                    None,
                )
                if refreshed:
                    self.tree_widget.focus_on_test_case(refreshed)

        if errors:
            self.statusBar().showMessage(
                f"Создание ТК: создано {len(created_cases)}, ошибок {len(errors)}."
            )
        elif created_cases:
            self.statusBar().showMessage(
                f"Создание ТК: создано тест-кейсов — {len(created_cases)}."
            )

    def _start_llm_request(
        self,
        payload: str,
        model: Optional[str],
        host: Optional[str],
        success_slot,
        error_slot,
    ):
        worker = _LLMWorker(payload, model, host)
        thread = QThread()
        worker.moveToThread(thread)

        worker.finished.connect(success_slot)
        worker.error.connect(error_slot)
        thread.started.connect(worker.run)

        thread.start()

        self._llm_worker = worker
        self._llm_thread = thread

    def _handle_review_success(self, response: str):
        self.aux_panel.set_review_response_text(response.strip())
        self.aux_panel.set_review_loading_state(False)
        self.statusBar().showMessage("Ревью: ответ LLM получен")
        self._cleanup_llm_worker()

    def _handle_review_error(self, error_message: str):
        self.aux_panel.set_review_response_text(f"Ошибка: {error_message}")
        self.aux_panel.set_review_loading_state(False)
        self.statusBar().showMessage("Ревью: ошибка при обращении к LLM")
        self._cleanup_llm_worker()

    def _handle_creation_success(self, response: str):
        cleaned = response.strip()
        self.aux_panel.set_creation_response_text(cleaned)
        self.aux_panel.set_creation_loading_state(False)
        self.statusBar().showMessage("Создание ТК: ответ LLM получен")
        self._cleanup_llm_worker()
        self._materialize_generated_test_cases(cleaned)

    def _handle_creation_error(self, error_message: str):
        self.aux_panel.set_creation_response_text(f"Ошибка: {error_message}")
        self.aux_panel.set_creation_loading_state(False)
        self.statusBar().showMessage("Создание ТК: ошибка при обращении к LLM")
        self._cleanup_llm_worker()

    def _cleanup_llm_worker(self):
        if self._llm_thread:
            self._llm_thread.quit()
            self._llm_thread.wait()
            self._llm_thread.deleteLater()
            self._llm_thread = None
        if self._llm_worker:
            self._llm_worker.deleteLater()
            self._llm_worker = None

    # --- Работа с панелями и размерами -----------------------------------

    def _show_placeholder(self):
        self.detail_stack.setCurrentWidget(self.placeholder)

    def _update_json_preview(self):
        if not hasattr(self, "aux_panel"):
            return
        self.aux_panel.set_json_test_case(self.current_test_case)

    def _set_mode(self, mode: str):
        if mode not in ("edit", "run"):
            return
        if self._current_mode == mode:
            return
        self._current_mode = mode
        action = self._mode_actions.get(mode)
        if action and not action.isChecked():
            action.setChecked(True)
        self._update_mode_indicator()
        self._apply_mode_state()
        label = "Редактирование" if mode == "edit" else "Запуск тестов"
        self.statusBar().showMessage(f"Режим изменён: {label}")

    def _update_mode_indicator(self):
        is_run = self._current_mode == "run"
        if hasattr(self, "mode_switch"):
            self.mode_switch.blockSignals(True)
            self.mode_switch.setChecked(is_run)
            self.mode_switch.blockSignals(False)
        if hasattr(self, "mode_edit_label"):
            self.mode_edit_label.setStyleSheet(
                "color: #ffffff;" if not is_run else "color: #777777;"
            )
        if hasattr(self, "mode_run_label"):
            self.mode_run_label.setStyleSheet(
                "color: #ffffff;" if is_run else "color: #777777;"
            )

    def _apply_mode_state(self):
        is_edit = self._current_mode == "edit"
        if hasattr(self, "form_widget"):
            self.form_widget.set_edit_mode(is_edit)
            self.form_widget.set_run_mode(not is_edit)
        if hasattr(self, "tree_widget"):
            # Устанавливаем режим редактирования для дерева (скрыть/показать иконки)
            self.tree_widget.set_edit_mode(is_edit)
        if hasattr(self, "aux_panel"):
            self.aux_panel.set_panels_enabled(is_edit, is_edit)
            # В режиме редактирования показываем кнопки панелей Ревью и Создать ТК в toolbar
            # В режиме запуска тестов скрываем их
            # is_edit = True (режим редактирования) -> показать кнопки (True)
            # is_edit = False (режим запуска) -> скрыть кнопки (False)
            self._set_panels_visible(is_edit, is_edit)
            # Устанавливаем режим редактирования для панели информации
            self.aux_panel.set_information_edit_mode(is_edit)
        
        # Обновляем статистику в statusbar
        self._update_statusbar_statistics()

    def _update_statusbar_statistics(self):
        """Обновить статистику в statusbar (всегда видна, включает статус LLM)"""
        if not hasattr(self, "statusbar_stats_label"):
            return
        
        # Определяем цвет и текст для статуса LLM (всегда отображается)
        if self._llm_available is None:
            llm_status_color = "#95a5a6"  # Серый - статус неизвестен
        elif self._llm_available:
            llm_status_color = "#6CC24A"  # Зеленый - доступен
        else:
            llm_status_color = "#F5555D"  # Красный - недоступен
        
        # Используем название модели вместо "LLM", если модель выбрана
        llm_model_name = self.llm_model if self.llm_model else "LLM"
        llm_status_html = f"<span style='color: {llm_status_color};'>{llm_model_name}</span>"
        
        if not self.test_cases:
            # Показываем только статус LLM, если нет тест-кейсов
            stats_text = llm_status_html
            self.statusbar_stats_label.setText(stats_text)
            self.statusbar_stats_label.setVisible(True)
            self.statusBar().showMessage("")
            return
        
        cases = list(self.test_cases or [])
        total = len(cases)
        if not total:
            # Показываем только статус LLM, если список пуст
            stats_text = llm_status_html
            self.statusbar_stats_label.setText(stats_text)
            self.statusbar_stats_label.setVisible(True)
            self.statusBar().showMessage("")
            return
        
        pending_cases = 0
        passed_cases = 0
        failed_cases = 0
        skipped_cases = 0
        
        for case in cases:
            steps = case.steps or []
            statuses = [s.status or "" for s in steps]
            if not statuses:
                pending_cases += 1
                continue
            
            normalized = [status.strip().lower() for status in statuses]
            if all(status in ("", "pending") for status in normalized):
                pending_cases += 1
                continue
            if all(status == "passed" for status in normalized):
                passed_cases += 1
                continue
            if any(status == "failed" for status in normalized):
                failed_cases += 1
            if any(status == "skipped" for status in normalized):
                skipped_cases += 1
        
        # Вычисляем проценты
        passed_percent = (passed_cases / total * 100) if total > 0 else 0
        pending_percent = (pending_cases / total * 100) if total > 0 else 0
        
        # Формируем текст статистики с HTML-форматированием и цветами
        # Статус LLM добавляется в начало с разделителем |
        stats_text = (
            f"{llm_status_html} | "
            f"Всего тест-кейсов: {total} | "
            f"Успешно: <span style='color: #6CC24A;'>{passed_cases}</span> "
            f"(<span style='color: #6CC24A;'>{passed_percent:.1f}%</span>) | "
            f"Осталось: <span style='color: #FFA931;'>{pending_cases}</span> "
            f"(<span style='color: #FFA931;'>{pending_percent:.1f}%</span>) | "
            f"Есть failed: <span style='color: #F5555D;'>{failed_cases}</span> | "
            f"Есть skipped: <span style='color: #95a5a6;'>{skipped_cases}</span>"
        )
        
        # Используем QLabel с HTML вместо showMessage для поддержки цветов
        if hasattr(self, "statusbar_stats_label"):
            self.statusbar_stats_label.setText(stats_text)
            self.statusbar_stats_label.setVisible(True)
            # Очищаем обычное сообщение, чтобы показывалась только статистика
            self.statusBar().showMessage("")
        else:
            # Fallback на обычный текст, если label не создан
            self.statusBar().showMessage(stats_text.replace("<span style='color: #6CC24A;'>", "").replace("</span>", "").replace("<span style='color: #FFA931;'>", "").replace("<span style='color: #F5555D;'>", "").replace("<span style='color: #95a5a6;'>", ""))

    def _apply_initial_panel_sizes(self):
        left_width = max(self.panel_sizes.get('left', 350), 150)
        total_area = max(self.panel_sizes.get('form_area', 900), 400)
        aux_width = max(self.panel_sizes.get('review', self._last_review_width or 300), 220)
        aux_width = min(aux_width, total_area - 300) if total_area > 300 else aux_width
        aux_width = max(aux_width, 220)
        form_width = max(total_area - aux_width, 300)
        total_area = form_width + aux_width
        self.panel_sizes['form_area'] = total_area
        self.panel_sizes['review'] = aux_width

        self.main_splitter.setSizes([left_width, total_area])
        self.detail_splitter.setSizes([form_width, aux_width])
        self._last_review_width = aux_width

    def _on_main_splitter_moved(self, _pos: int, _index: int):
        sizes = self.main_splitter.sizes()
        if sizes and len(sizes) >= 2:
            self.panel_sizes['left'] = sizes[0]
            self.panel_sizes['form_area'] = sizes[1]
            self._save_panel_sizes()

    def _on_detail_splitter_moved(self, _pos: int, _index: int):
        sizes = self.detail_splitter.sizes()
        if sizes and len(sizes) >= 2:
            self.panel_sizes['form_area'] = sizes[0] + sizes[1]
            self.panel_sizes['review'] = max(sizes[1], 200)
            self._last_review_width = self.panel_sizes['review']
        self._save_panel_sizes()

    def _save_panel_sizes(self):
        self.settings['panel_sizes'] = {
            'left': self.panel_sizes.get('left', 350),
            'form_area': self.panel_sizes.get('form_area', 900),
            'review': self.panel_sizes.get('review', self._last_review_width),
        }
        self.save_settings(self.settings)

    def _configure_panel_widths(self):
        left_width, ok = QInputDialog.getInt(
            self,
            "Ширина панели",
            "Панель дерева (px):",
            int(self.panel_sizes.get('left', 350)),
            150,
            1200,
        )
        if not ok:
            return

        form_area, ok = QInputDialog.getInt(
            self,
            "Ширина панели",
            "Панель редактирования (px):",
            int(self.panel_sizes.get('form_area', 900)),
            300,
            2000,
        )
        if not ok:
            return

        review_width, ok = QInputDialog.getInt(
            self,
            "Ширина панели",
            "Панель ревью (px):",
            int(self.panel_sizes.get('review', max(self._last_review_width, 300))),
            200,
            1200,
        )
        if not ok:
            return

        self.panel_sizes['left'] = left_width
        self.panel_sizes['form_area'] = max(form_area, 300)
        self.panel_sizes['review'] = max(review_width, 0)
        if review_width > 0:
            self._last_review_width = review_width

        self._save_panel_sizes()
        self._apply_initial_panel_sizes()

    def _apply_initial_geometry(self):
        geometry = self.settings.get('window_geometry')
        screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry() if screen else None
        default_width = min(1600, screen_rect.width() if screen_rect else 1920)
        default_height = min(900, screen_rect.height() if screen_rect else 1080)
        default_x = (screen_rect.width() - default_width) // 2 if screen_rect else 100
        default_y = (screen_rect.height() - default_height) // 2 if screen_rect else 100

        if geometry and isinstance(geometry, dict):
            x = geometry.get('x', default_x)
            y = geometry.get('y', default_y)
            width = geometry.get('width', default_width)
            height = geometry.get('height', default_height)
            self.setGeometry(x, y, width, height)
            if geometry.get('is_fullscreen'):
                self.showMaximized()
        else:
            self.setGeometry(default_x, default_y, default_width, default_height)

    def changeEvent(self, event):
        """Обработка изменения состояния окна (maximize/restore и т.д.)"""
        if event.type() == QEvent.WindowStateChange:
            # При изменении состояния окна (maximize/restore) обновляем панели
            QTimer.singleShot(100, self._update_panels_after_resize)
        super().changeEvent(event)
    
    def resizeEvent(self, event):
        """Обработка изменения размера окна"""
        # При изменении размера окна обновляем панели
        QTimer.singleShot(100, self._update_panels_after_resize)
        super().resizeEvent(event)
    
    def _update_panels_after_resize(self):
        """Обновить панели после изменения размера окна"""
        if not hasattr(self, "detail_splitter") or not hasattr(self, "form_widget"):
            return
        
        # Если флаг установлен, не изменяем размеры панелей
        # (это предотвращает автоматическое изменение при выборе тест-кейса)
        if hasattr(self, "_preserve_panel_sizes") and self._preserve_panel_sizes:
            return
        
        # Сохраняем текущие размеры splitter'ов перед обновлением
        current_detail_sizes = self.detail_splitter.sizes()
        current_main_sizes = self.main_splitter.sizes() if hasattr(self, "main_splitter") else None
        
        # Обновляем геометрию формы для корректного пересчета размеров
        self.form_widget.updateGeometry()
        
        # Если есть сохраненные размеры, применяем их пропорционально
        # ТОЛЬКО если размер окна действительно изменился (не при выборе тест-кейса)
        if hasattr(self, "panel_sizes") and current_main_sizes and len(current_main_sizes) > 1:
            # Вычисляем пропорции на основе сохраненных размеров
            total_saved = self.panel_sizes.get('form_area', 900)
            if total_saved > 0:
                # Текущая доступная ширина для правой панели
                current_total = current_main_sizes[1]
                
                # Вычисляем пропорции для detail_splitter
                saved_review = self.panel_sizes.get('review', 360)
                saved_form = total_saved - saved_review
                
                if saved_form > 0 and saved_review > 0:
                    # Сохраняем пропорции
                    form_ratio = saved_form / total_saved
                    review_ratio = saved_review / total_saved
                    
                    # Применяем пропорции к текущему размеру
                    new_form_width = int(current_total * form_ratio)
                    new_review_width = int(current_total * review_ratio)
                    
                    # Убеждаемся, что размеры не слишком малы
                    new_form_width = max(new_form_width, 300)
                    new_review_width = max(new_review_width, 220)
                    
                    # Если сумма превышает доступное пространство, корректируем
                    if new_form_width + new_review_width > current_total:
                        total_needed = new_form_width + new_review_width
                        new_form_width = int(new_form_width * current_total / total_needed)
                        new_review_width = current_total - new_form_width
                    
                    # Применяем новые размеры только если они отличаются от текущих
                    # (это предотвращает ненужные изменения)
                    current_form = current_detail_sizes[0] if len(current_detail_sizes) > 0 else 0
                    current_review = current_detail_sizes[1] if len(current_detail_sizes) > 1 else 0
                    
                    # Если разница больше 5 пикселей, применяем новые размеры
                    if abs(current_form - new_form_width) > 5 or abs(current_review - new_review_width) > 5:
                        self.detail_splitter.setSizes([new_form_width, new_review_width])
                else:
                    # Если пропорции не определены, используем текущие размеры
                    if len(current_detail_sizes) >= 2:
                        self.detail_splitter.setSizes(current_detail_sizes)
            else:
                # Если сохраненных размеров нет, используем текущие
                if len(current_detail_sizes) >= 2:
                    self.detail_splitter.setSizes(current_detail_sizes)
        else:
            # Если нет сохраненных размеров, используем текущие
            if len(current_detail_sizes) >= 2:
                self.detail_splitter.setSizes(current_detail_sizes)
        
        # Принудительно обновляем форму для пересчета размеров шагов
        QTimer.singleShot(50, self._refresh_form_layout)
    
    def _refresh_form_layout(self):
        """Обновить layout формы для корректного отображения после изменения размера"""
        if not hasattr(self, "form_widget"):
            return
        
        # Обновляем геометрию формы
        self.form_widget.updateGeometry()
        
        # Обновляем размеры шагов, если они есть
        if hasattr(self.form_widget, "steps_list"):
            # Обновляем размеры всех шагов для корректного переноса текста
            for row in range(self.form_widget.steps_list.count()):
                widget = self.form_widget._get_step_widget(row)
                if widget:
                    # Обновляем ширину текста в документах для правильного переноса
                    if hasattr(widget, "action_edit"):
                        viewport_width = widget.action_edit.viewport().width()
                        if viewport_width > 0:
                            widget.action_edit.document().setTextWidth(viewport_width)
                    if hasattr(widget, "expected_edit"):
                        viewport_width = widget.expected_edit.viewport().width()
                        if viewport_width > 0:
                            widget.expected_edit.document().setTextWidth(viewport_width)
                    # Синхронизируем высоту полей после обновления ширины
                    widget._sync_text_edits_height()
            
            # Обновляем общую высоту списка шагов
            self.form_widget._update_steps_list_height()
    
    def _open_settings_dialog(self):
        """Открыть диалог настроек"""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            
            # Сохраняем существующие настройки, которые не редактируются в диалоге
            # (например, window_geometry)
            for key, value in self.settings.items():
                if key not in new_settings:
                    new_settings[key] = value
            
            # Сохраняем настройки
            self.save_settings(new_settings)
            self.settings = new_settings
            
            # Применяем изменения
            self._apply_settings_changes(new_settings)
            
            QMessageBox.information(
                self,
                "Настройки сохранены",
                "Настройки успешно сохранены. Некоторые изменения могут потребовать перезапуска приложения."
            )
    
    def _apply_settings_changes(self, new_settings: dict):
        """Применить изменения настроек к приложению"""
        # Обновляем пути
        if 'test_cases_dir' in new_settings:
            old_dir = self.test_cases_dir
            self.test_cases_dir = Path(new_settings['test_cases_dir'])
            if old_dir != self.test_cases_dir:
                # Перезагружаем дерево тест-кейсов, если изменилась папка
                self.load_all_test_cases()
        
        # Обновляем LLM настройки
        llm_host_changed = False
        if 'LLM_HOST' in new_settings:
            old_host = self.llm_host
            self.llm_host = new_settings['LLM_HOST'].strip()
            if old_host != self.llm_host:
                llm_host_changed = True
                # Сбрасываем статус доступности при изменении хоста
                self._llm_available = None
        if 'LLM_MODEL' in new_settings:
            self.llm_model = new_settings['LLM_MODEL'].strip()
            # Обновляем модель в селекторе
            if hasattr(self, 'model_selector'):
                current_text = self.model_selector.currentText()
                if current_text != self.llm_model:
                    self.model_selector.setCurrentText(self.llm_model)
        
        # Если изменился LLM_HOST, запускаем новую проверку доступности
        if llm_host_changed:
            self._check_llm_availability()
            # Обновляем статистику, чтобы отобразить обновленный статус
            self._update_statusbar_statistics()
        
        # Обновляем список тестировщиков
        if 'testers' in new_settings:
            testers_list = new_settings['testers']
            if isinstance(testers_list, list):
                if hasattr(self, 'aux_panel'):
                    self.aux_panel.set_information_testers(testers_list)
            elif isinstance(testers_list, str):
                # Если сохранено как строка, разбиваем по переносам строк
                testers_list = [t.strip() for t in testers_list.split('\n') if t.strip()]
                if hasattr(self, 'aux_panel'):
                    self.aux_panel.set_information_testers(testers_list)
        
        # Обновляем настройку счетчиков в дереве
        if 'show_folder_counters' in new_settings:
            show_counters = new_settings.get('show_folder_counters', False)
            if hasattr(self, 'tree_widget'):
                self.tree_widget.set_show_folder_counters(show_counters)
        
        # Обновляем промпты
        if 'DEFAULT_PROMT' in new_settings:
            self.default_prompt = new_settings['DEFAULT_PROMT']
        if 'DEFAULT_PROMT_CREATE_TC' in new_settings:
            self.create_tc_prompt = new_settings['DEFAULT_PROMT_CREATE_TC']
        
        # Обновляем размеры панелей
        if 'panel_sizes' in new_settings:
            self.panel_sizes.update(new_settings['panel_sizes'])
            # Применяем новые размеры
            if hasattr(self, 'main_splitter') and hasattr(self, 'detail_splitter'):
                self._apply_initial_panel_sizes()
        
        # Обновляем путь к методике
        if 'LLM_METHODIC_PATH' in new_settings:
            methodic_path = new_settings['LLM_METHODIC_PATH']
            if methodic_path:
                self.settings['LLM_METHODIC_PATH'] = methodic_path
        
        # Внешний вид (тема, шрифт, отступы) - применяем сразу
        needs_style_refresh = (
            'theme' in new_settings or 
            'font_family' in new_settings or 
            'font_size' in new_settings or 
            'base_spacing' in new_settings or
            'section_spacing' in new_settings or
            'container_padding' in new_settings or
            'text_input_vertical_padding' in new_settings or
            'group_title_spacing' in new_settings
        )
        
        if needs_style_refresh:
            self._apply_font_settings()
            # Применяем настройки отступов
            if 'base_spacing' in new_settings:
                UI_METRICS.base_spacing = new_settings['base_spacing']
            if 'section_spacing' in new_settings:
                UI_METRICS.section_spacing = new_settings['section_spacing']
            if 'container_padding' in new_settings:
                UI_METRICS.container_padding = new_settings['container_padding']
            if 'text_input_vertical_padding' in new_settings:
                UI_METRICS.text_input_vertical_padding = new_settings['text_input_vertical_padding']
            if 'group_title_spacing' in new_settings:
                UI_METRICS.group_title_spacing = new_settings['group_title_spacing']
                # Обновляем отступы в существующих QGroupBox
                if hasattr(self, 'form_widget'):
                    self._update_group_title_spacings(self.form_widget)
                if hasattr(self, 'aux_panel') and hasattr(self.aux_panel, 'information_panel'):
                    self._update_group_title_spacings(self.aux_panel.information_panel)
            
            # Применяем тему
            if 'theme' in new_settings:
                theme_name = new_settings['theme'].strip().lower()
                if theme_name in ['dark', 'light']:
                    THEME_PROVIDER.set_theme(theme_name)
            
            # Переприменяем стили к приложению
            app = QApplication.instance()
            if app:
                new_style_sheet = build_app_style_sheet(UI_METRICS)
                app.setStyleSheet(new_style_sheet)
        
        # Панель Информация - видимость элементов
        if 'information_panel_visibility' in new_settings:
            visibility_settings = new_settings['information_panel_visibility']
            if hasattr(self, 'aux_panel') and hasattr(self.aux_panel, 'information_panel'):
                self.aux_panel.information_panel.set_visibility_settings(visibility_settings)
    
    @staticmethod
    def _update_group_title_spacings(widget: QWidget):
        """Обновить отступы заголовков во всех QGroupBox внутри виджета"""
        for group_box in widget.findChildren(QGroupBox):
            layout = group_box.layout()
            if layout:
                margins = layout.getContentsMargins()
                # Обновляем только верхний отступ
                layout.setContentsMargins(margins[0], UI_METRICS.group_title_spacing, margins[2], margins[3])
    
    def closeEvent(self, event):
        # Останавливаем таймер проверки LLM
        if hasattr(self, '_llm_check_timer'):
            self._llm_check_timer.stop()
        
        # Очищаем потоки проверки LLM
        if hasattr(self, '_cleanup_llm_availability_worker'):
            self._cleanup_llm_availability_worker()
        
        # Очищаем потоки LLM запросов
        if hasattr(self, '_cleanup_llm_worker'):
            self._cleanup_llm_worker()
        
        if self.isMaximized():
            geom = self.normalGeometry()
            geometry_data = {
                'x': geom.x(),
                'y': geom.y(),
                'width': geom.width(),
                'height': geom.height(),
                'is_fullscreen': True,
            }
        else:
            geom = self.geometry()
            geometry_data = {
                'x': geom.x(),
                'y': geom.y(),
                'width': geom.width(),
                'height': geom.height(),
                'is_fullscreen': False,
            }
        self.settings['window_geometry'] = geometry_data
        self.save_settings(self.settings)
        super().closeEvent(event)

    def convert_from_azure(self):
        """Импорт тест-кейсов из ALM с созданием структуры папок согласно иерархии."""
        # Определяем пути к папкам - сначала пробуем относительно корня проекта
        # (где находится run_app.py), затем относительно test_cases_dir
        app_dir = Path(__file__).resolve().parent.parent.parent
        test_suites_dir = None
        from_alm_dir = None
        hierarchy_map_path = None

        # Пробуем найти относительно корня проекта
        candidate_dir = app_dir / "test_suites"
        if candidate_dir.exists():
            test_suites_dir = candidate_dir
        else:
            # Пробуем относительно test_cases_dir
            candidate_dir = self.test_cases_dir / "test_suites"
            if candidate_dir.exists():
                test_suites_dir = candidate_dir

        if test_suites_dir:
            from_alm_dir = test_suites_dir / "from_alm"
            hierarchy_map_path = test_suites_dir / "suite_hierarchy_map.json"
        else:
            # Если не нашли test_suites, пробуем прямо в test_cases_dir
            from_alm_dir = self.test_cases_dir / "test_suites" / "from_alm"
            hierarchy_map_path = self.test_cases_dir / "test_suites" / "suite_hierarchy_map.json"

        # Проверяем наличие необходимых папок и файлов
        if not from_alm_dir.exists():
            QMessageBox.warning(
                self,
                "Папка не найдена",
                f"Папка с suite файлами не найдена:\n{from_alm_dir}\n\n"
                "Убедитесь, что папка test_suites/from_alm существует и содержит JSON файлы.\n\n"
                f"Искали в:\n- {app_dir / 'test_suites'}\n- {self.test_cases_dir / 'test_suites'}",
            )
            return

        if not hierarchy_map_path.exists():
            QMessageBox.warning(
                self,
                "Файл не найден",
                f"Файл карты иерархии не найден:\n{hierarchy_map_path}\n\n"
                "Убедитесь, что файл test_suites/suite_hierarchy_map.json существует.\n\n"
                f"Искали в:\n- {app_dir / 'test_suites' / 'suite_hierarchy_map.json'}\n"
                f"- {self.test_cases_dir / 'test_suites' / 'suite_hierarchy_map.json'}",
            )
            return

        # Подтверждение импорта
        reply = QMessageBox.question(
            self,
            "Импорт из ALM",
            f"Будет обработано всех suite из папки:\n{from_alm_dir}\n\n"
            f"Структура папок будет создана согласно:\n{hierarchy_map_path}\n\n"
            "Продолжить?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply != QMessageBox.Yes:
            return

        # Выполняем импорт
        self.statusBar().showMessage("Импорт из ALM: обработка файлов...")
        QApplication.processEvents()  # Обновляем UI

        total_created, all_errors = self.service.import_from_alm_with_hierarchy(
            from_alm_dir=from_alm_dir,
            hierarchy_map_path=hierarchy_map_path,
            target_root=self.test_cases_dir,
        )

        self.load_all_test_cases()

        if all_errors:
            message = "\n".join(all_errors[:10])
            if len(all_errors) > 10:
                message += f"\n... и еще {len(all_errors) - 10} ошибок."
            QMessageBox.warning(
                self,
                "Импорт завершен с ошибками",
                f"Создано тест-кейсов: {total_created}\n\nОшибки:\n{message}",
            )
        else:
            QMessageBox.information(
                self,
                "Импорт завершен",
                f"Создано тест-кейсов: {total_created}\n\n"
                f"Структура папок создана согласно иерархии из:\n{hierarchy_map_path.name}",
            )

        self.statusBar().showMessage(f"Импортировано тест-кейсов: {total_created}")

    # ----------------------- UI Metrics ---------------------------------

    def _apply_font_settings(self):
        """Применить настройки шрифта и отступов из settings к UI_METRICS"""
        if 'font_family' in self.settings:
            UI_METRICS.font_family = self.settings['font_family']
        if 'font_size' in self.settings:
            UI_METRICS.base_font_size = self.settings['font_size']
        if 'base_spacing' in self.settings:
            UI_METRICS.base_spacing = self.settings['base_spacing']
        if 'section_spacing' in self.settings:
            UI_METRICS.section_spacing = self.settings['section_spacing']
        if 'container_padding' in self.settings:
            UI_METRICS.container_padding = self.settings['container_padding']
        if 'text_input_vertical_padding' in self.settings:
            UI_METRICS.text_input_vertical_padding = self.settings['text_input_vertical_padding']
        if 'group_title_spacing' in self.settings:
            UI_METRICS.group_title_spacing = self.settings['group_title_spacing']

    def _on_mode_switch_changed(self, checked: bool):
        self._set_mode("run" if checked else "edit")

    def _generate_allure_report(self):
        """Генерация Allure отчета из JSON файлов тест-кейсов"""
        try:
            # Определяем папку приложения (где находится run_app_v2.py)
            # main_window.py находится в ui/, поднимаемся на 2 уровня вверх
            app_dir = Path(__file__).resolve().parent.parent.parent
            
            # Генерируем отчет
            report_dir = generate_allure_report(
                test_cases_dir=self.test_cases_dir,
                app_dir=app_dir,
            )
            
            if report_dir:
                self.statusBar().showMessage(
                    f"Allure отчет сгенерирован: {report_dir.name}. "
                    f"Папка открыта в проводнике."
                )
            else:
                self.statusBar().showMessage("Ошибка при генерации Allure отчета")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка генерации Allure отчета",
                f"Не удалось сгенерировать Allure отчет:\n{e}",
            )
            self.statusBar().showMessage(f"Ошибка: {e}")
    
    def _generate_html_report(self):
        """Генерация HTML отчета с статистикой по тест-кейсам"""
        try:
            # Определяем папку приложения
            app_dir = Path(__file__).resolve().parent.parent.parent
            
            # Проверяем и создаем папку Reports, если её нет
            reports_dir = app_dir / "Reports"
            if not reports_dir.exists():
                try:
                    reports_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "Ошибка создания папки",
                        f"Не удалось создать папку Reports:\n{e}"
                    )
                    self.statusBar().showMessage(f"Ошибка создания папки Reports: {e}")
                    return
            
            # Получаем название проекта из настроек
            project_name = self.settings.get('project_name', '').strip()
            
            # Генерируем отчет
            report_dir = generate_html_report(
                test_cases_dir=self.test_cases_dir,
                app_dir=app_dir,
                project_name=project_name if project_name else None,
            )
            
            if report_dir:
                # Открываем проводник с отчетом
                from ..utils.allure_generator import _open_explorer
                _open_explorer(report_dir)
                
                # Обновляем панель отчетности
                if hasattr(self, "aux_panel"):
                    self.aux_panel.update_reports_panel()
                
                self.statusBar().showMessage(
                    f"HTML отчет сгенерирован: {report_dir.name}. "
                    f"Проводник открыт."
                )
            else:
                self.statusBar().showMessage("Ошибка при генерации HTML отчета")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка генерации HTML отчета",
                f"Не удалось сгенерировать HTML отчет:\n{e}",
            )
            self.statusBar().showMessage(f"Ошибка: {e}")

    def _generate_summary_report(self):
        """Генерация суммарного HTML отчета на основе всех отчетов в папке Reports"""
        try:
            # Определяем папку приложения
            current_file = Path(__file__).resolve()
            app_dir = current_file.parent.parent.parent
            
            # Определяем папку Reports
            reports_dir = app_dir / "Reports"
            
            if not reports_dir.exists():
                QMessageBox.warning(
                    self,
                    "Папка Reports не найдена",
                    f"Папка Reports не существует:\n{reports_dir}",
                )
                self.statusBar().showMessage("Папка Reports не найдена")
                return
            
            # Генерируем суммарный отчет
            from ..utils.summary_report_generator import generate_summary_report
            
            # Получаем название проекта из настроек
            project_name = self.settings.get('project_name', '').strip()
            
            summary_file = generate_summary_report(
                reports_dir, 
                app_dir,
                project_name=project_name if project_name else None,
            )
            
            if summary_file:
                # Открываем проводник с отчетом
                from ..utils.allure_generator import _open_explorer
                _open_explorer(summary_file.parent)
                
                # Обновляем панель отчетности
                if hasattr(self, "aux_panel"):
                    self.aux_panel.update_reports_panel()
                
                self.statusBar().showMessage(
                    f"Суммарный отчет сгенерирован: {summary_file.name}. "
                    f"Проводник открыт."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Ошибка генерации суммарного отчета",
                    "Не удалось сгенерировать суммарный отчет.\n"
                    "Убедитесь, что в папке Reports есть HTML отчеты.",
                )
                self.statusBar().showMessage("Ошибка при генерации суммарного отчета")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка генерации суммарного отчета",
                f"Не удалось сгенерировать суммарный отчет:\n{e}",
            )
            self.statusBar().showMessage(f"Ошибка: {e}")


def create_main_window() -> MainWindow:
    """
    Фабричная функция для создания главного окна
    
    Использует паттерн Factory для централизованного создания окна
    """
    return MainWindow()


