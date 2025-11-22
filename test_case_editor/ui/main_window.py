"""Главное окно приложения"""

import json
import re
import subprocess
from pathlib import Path
from typing import List, Optional

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
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QStringListModel, QSortFilterProxyModel, QRegularExpression, QTimer, QEvent
from PyQt5.QtGui import QFont

from ..models.test_case import TestCase
from ..services.test_case_service import TestCaseService
from ..repositories.test_case_repository import TestCaseRepository
from .widgets.placeholder_widget import PlaceholderWidget
from .widgets.tree_widget import TestCaseTreeWidget
from .widgets.form_widget import TestCaseFormWidget
from .widgets.auxiliary_panel import AuxiliaryPanel
from .widgets.toggle_switch import ToggleSwitch
from ..utils import llm
from ..utils.prompt_builder import build_review_prompt, build_creation_prompt
from ..utils.list_models import fetch_models as fetch_llm_models
from ..utils.allure_generator import generate_allure_report
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
        host_layout.addWidget(self.llm_host_edit)
        host_group.setLayout(host_layout)
        content_layout.addWidget(host_group)
        
        # LLM Model
        model_group = QGroupBox("LLM Model")
        model_layout = QVBoxLayout()
        self.llm_model_edit = QLineEdit()
        self.llm_model_edit.setPlaceholderText("deepseek-v3.1:latest")
        model_layout.addWidget(self.llm_model_edit)
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
        self.test_cases_dir_edit.setText(self.settings.get('test_cases_dir', ''))
        self.methodic_path_edit.setText(self.settings.get('LLM_METHODIC_PATH', ''))
        
        # LLM
        self.llm_host_edit.setText(self.settings.get('LLM_HOST', ''))
        self.llm_model_edit.setText(self.settings.get('LLM_MODEL', ''))
        
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

    def _save_and_accept(self):
        """Сохранить настройки и закрыть диалог"""
        # Общие
        self.settings['test_cases_dir'] = self.test_cases_dir_edit.text().strip()
        self.settings['LLM_METHODIC_PATH'] = self.methodic_path_edit.text().strip()
        
        # LLM
        self.settings['LLM_HOST'] = self.llm_host_edit.text().strip()
        self.settings['LLM_MODEL'] = self.llm_model_edit.text().strip()
        
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

    def get_settings(self) -> dict:
        """Получить сохраненные настройки"""
        return self.settings


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
        self.settings_file = Path("settings.json")
        self.settings = self.load_settings()
        default_sizes = {'left': 350, 'form_area': 900, 'review': 360}
        self.panel_sizes = dict(default_sizes)
        self.panel_sizes.update(self.settings.get('panel_sizes', {}))
        self._last_review_width = self.panel_sizes.get('review', 0) or 360
        self.test_cases_dir = Path(self.settings.get('test_cases_dir', 'testcases'))
        if not self.test_cases_dir.exists():
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
        self.available_llm_models = self._fetch_available_llm_models()
        self.selected_llm_model = self.llm_model
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
        self._current_test_case_path: Optional[Path] = None
        self._current_mode: str = "edit"
        self._geometry_initialized = False
        
        self.setup_ui()
        self._apply_model_options()
        self.load_all_test_cases()
        self._show_placeholder()
        self._apply_mode_state()
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        self.setWindowTitle("Test Case Editor")
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
        
        self.statusBar().showMessage("Готов к работе")
    
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
        search_frame = QFrame()
        search_frame.setMaximumHeight(48)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(
            UI_METRICS.base_spacing,
            0,
            UI_METRICS.base_spacing,
            UI_METRICS.base_spacing // 2,
        )
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Поиск...")
        self.search_input.setMinimumHeight(30)
        self.search_input.textChanged.connect(self._filter_tree)
        search_layout.addWidget(self.search_input)
        
        layout.addWidget(search_frame)
        
        # Дерево
        self.tree_widget = TestCaseTreeWidget(self.service)
        self.tree_widget.test_case_selected.connect(self._on_test_case_selected)
        self.tree_widget.tree_updated.connect(self._on_tree_updated)
        self.tree_widget.review_requested.connect(self._on_review_requested)
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
        self.form_widget.test_case_saved.connect(self._on_test_case_saved)
        self.form_widget.unsaved_changes_state.connect(self._on_form_unsaved_state)
        self.form_widget.before_save.connect(self._on_form_before_save)
        self.detail_stack.addWidget(self.form_widget)
        self.detail_stack.setCurrentWidget(self.placeholder)

        self.detail_splitter.addWidget(self.detail_stack_container)

        # Дополнительная панель
        self.aux_panel = AuxiliaryPanel(
            methodic_path=self.methodic_path,
            default_review_prompt=self.default_prompt,
            default_creation_prompt=self.create_tc_prompt,
        )
        self.aux_panel.review_prompt_saved.connect(self._on_prompt_saved)
        self.aux_panel.review_enter_clicked.connect(self._on_review_enter_clicked)
        self.aux_panel.creation_prompt_saved.connect(self._on_creation_prompt_saved)
        self.aux_panel.creation_enter_clicked.connect(self._on_creation_enter_clicked)
        self.aux_panel.information_data_changed.connect(self._on_information_data_changed)
        self.aux_panel.stats_panel.reset_all_statuses.connect(self._reset_all_step_statuses)
        self.aux_panel.stats_panel.mark_current_passed.connect(self._mark_current_case_passed)
        self.aux_panel.stats_panel.reset_current_case.connect(self._reset_current_case_statuses)
        self.aux_panel.stats_panel.generate_allure.connect(self._generate_allure_report)
        self.detail_splitter.addWidget(self.aux_panel)
        
        # Применяем настройки видимости панели Информация при инициализации
        info_visibility = self.settings.get('information_panel_visibility', {})
        if hasattr(self.aux_panel, 'information_panel'):
            self.aux_panel.information_panel.set_visibility_settings(info_visibility)

        self.detail_splitter.setCollapsible(0, False)
        self.detail_splitter.setCollapsible(1, False)
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

        convert_action = self.file_menu.addAction('Импорт из ALM')
        convert_action.triggered.connect(self.convert_from_azure)
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
        settings_action.setShortcut('Ctrl+,')

        # Меню "Git"
        self.git_menu = menubar.addMenu('Git')
        git_commit_action = self.git_menu.addAction('Выполнить commit и push…')
        git_commit_action.triggered.connect(self._open_git_commit_dialog)
    
    def _create_toolbar(self):
        """Создать панель инструментов с быстрыми действиями"""
        toolbar = QToolBar("Основная панель", self)
        toolbar.setMovable(False)  # Не позволяем перемещать панель
        self.addToolBar(toolbar)
        
        # Селектор модели LLM
        model_label = QLabel("LLM:")
        toolbar.addWidget(model_label)
        
        self.model_selector = QComboBox()
        self.model_selector.setModel(self._model_proxy_model)
        self.model_selector.setEditable(True)
        self.model_selector.setInsertPolicy(QComboBox.NoInsert)
        self.model_selector.setMinimumWidth(200)
        self.model_selector.currentTextChanged.connect(self._on_model_selector_changed)
        line_edit = self.model_selector.lineEdit()
        if line_edit:
            line_edit.setPlaceholderText("Выберите модель…")
            line_edit.textEdited.connect(self._on_model_selector_text_edited)
            line_edit.editingFinished.connect(self._on_model_editing_finished)
        toolbar.addWidget(self.model_selector)
        
        toolbar.addSeparator()
        
        # Переключатель режима
        self.mode_edit_label = QLabel("Редактирование")
        toolbar.addWidget(self.mode_edit_label)
        
        self.mode_switch = ToggleSwitch()
        self.mode_switch.toggled.connect(self._on_mode_switch_changed)
        toolbar.addWidget(self.mode_switch)
        
        self.mode_run_label = QLabel("Запуск тестов")
        toolbar.addWidget(self.mode_run_label)
        
        self._update_mode_indicator()
        
        # Создаем кнопку "Сохранить" в статус-баре
        self._create_statusbar_save_button()
    
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
                self._perform_git_commit_push(comment)

    def _perform_git_commit_push(self, message: str):
        """Выполнить git commit и push в директории тест-кейсов."""
        repo_path = self.test_cases_dir

        if not repo_path.exists():
            QMessageBox.warning(
                self,
                "Git",
                f"Папка с тест-кейсами не найдена:\n{repo_path}",
            )
            return

        try:
            status_proc = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Git",
                "Команда git не найдена. Установите Git и убедитесь, что он доступен в PATH.",
            )
            return
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
                "Нет изменений для коммита.",
            )
            return

        self.statusBar().showMessage("Git: подготовка изменений…")
        commands = [
            ("Git: подготовка файлов…", ["git", "add", "--all"]),
            ("Git: создаю коммит…", ["git", "commit", "-m", message]),
            ("Git: отправляю изменения…", ["git", "push"]),
        ]

        for status_text, cmd in commands:
            self.statusBar().showMessage(status_text)
            try:
                result = subprocess.run(
                    cmd,
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError:
                QMessageBox.critical(
                    self,
                    "Git",
                    "Команда git не найдена. Установите Git и убедитесь, что он доступен в PATH.",
                )
                self.statusBar().showMessage("Git: ошибка выполнения")
                return

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                stdout = (result.stdout or "").strip()
                combined_output = stderr or stdout or "Неизвестная ошибка."
                # Если git commit сообщает об отсутствии изменений
                if "nothing to commit" in combined_output.lower():
                    QMessageBox.information(
                        self,
                        "Git",
                        "Нет изменений для коммита.",
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Git",
                        f"Команда {' '.join(cmd)} завершилась с ошибкой:\n{combined_output}",
                    )
                self.statusBar().showMessage("Git: ошибка выполнения")
                return

        QMessageBox.information(
            self,
            "Git",
            "Изменения успешно отправлены в удалённый репозиторий.",
        )
        self.statusBar().showMessage("Git: изменения отправлены")
    
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
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Выбор папки с тест-кейсами")
        msg_box.setText("Папка с тест-кейсами не найдена.\n\nПожалуйста, выберите папку.")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()
        
        folder = QFileDialog.getExistingDirectory(
            None,
            "Выберите папку с тест-кейсами",
            str(Path.cwd()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder:
            selected_path = Path(folder)
            self.settings['test_cases_dir'] = str(selected_path)
            self.save_settings(self.settings)
            return selected_path
        
        # По умолчанию
        default = Path("testcases")
        default.mkdir(exist_ok=True)
        self.settings['test_cases_dir'] = str(default)
        self.save_settings(self.settings)
        return default
    
    def load_all_test_cases(self):
        """
        Загрузка всех тест-кейсов через сервис
        
        Демонстрирует Dependency Inversion:
        не работаем напрямую с файлами, используем сервис
        """
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
        
        # Обновляем дерево
        self.tree_widget.load_tree(self.test_cases_dir, self.test_cases)
        self.tree_widget.restore_expanded_state(expanded_state)
        # Восстанавливаем выбранный элемент
        if selected_filepath:
            self.tree_widget.restore_selected_item(selected_filepath)
        
        # Восстанавливаем размеры панелей после обновления
        if saved_detail_sizes and hasattr(self, "detail_splitter"):
            self.detail_splitter.setSizes(saved_detail_sizes)
        
        # Обновляем счетчики
        self.placeholder.update_count(len(self.test_cases))
        
        self.statusBar().showMessage(f"Загружено тест-кейсов: {len(self.test_cases)}")
        self._update_json_preview()
        if hasattr(self, "aux_panel"):
            self.aux_panel.update_statistics(self.test_cases)

    def _update_statistics_panel(self):
        if hasattr(self, "aux_panel"):
            self.aux_panel.update_statistics(self.test_cases)

    def _on_test_case_selected(self, test_case: TestCase):
        """Обработка выбора тест-кейса"""
        # Проверяем наличие несохраненных изменений перед переключением
        if hasattr(self, "form_widget") and self.form_widget.has_unsaved_changes:
            # Подсвечиваем кнопку "Сохранить" и показываем предупреждение
            if hasattr(self, "statusbar_save_button"):
                self.statusbar_save_button.setVisible(True)
                self._highlight_save_button()
            self.statusBar().showMessage(
                "Есть несохраненные изменения. Сохраните изменения перед переключением на другой тест-кейс.",
                5000
            )
            # Переключаемся на новый тест-кейс, но предупреждаем пользователя
            # (изменения будут потеряны, но пользователь видит подсвеченную кнопку)
        
        self.current_test_case = test_case
        self.detail_stack.setCurrentWidget(self.form_widget)
        self.form_widget.load_test_case(test_case)
        # Обновляем панель информации
        if hasattr(self, "aux_panel"):
            self.aux_panel.set_information_test_case(test_case)
            self.aux_panel.set_files_test_case(test_case)
            # Подключаем сигнал изменения attachments в панели файлов
            if hasattr(self.aux_panel, "files_panel"):
                try:
                    self.aux_panel.files_panel.attachment_changed.disconnect()
                except TypeError:
                    pass
                self.aux_panel.files_panel.attachment_changed.connect(self._on_files_attachment_changed)
        self._update_json_preview()
        
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
    
    def _on_test_case_saved(self):
        """Обработка сохранения тест-кейса"""
        # Обновляем панель информации после сохранения
        if hasattr(self, "aux_panel") and self.current_test_case:
            self.aux_panel.set_information_test_case(self.current_test_case)
            # Обновляем панель "Файлы" для отображения прикрепленных файлов
            self.aux_panel.set_files_test_case(self.current_test_case)
        self.load_all_test_cases()
        self._update_json_preview()
        self.statusBar().showMessage("Тест-кейс сохранен")
    
    def _on_information_data_changed(self):
        """Обработка изменения данных в панели информации"""
        if not self.current_test_case:
            return
        # Обновляем тест-кейс данными из панели информации
        self.aux_panel.update_information_test_case(self.current_test_case)
        # Помечаем изменения в форме (чтобы появилась кнопка сохранения)
        self.form_widget.has_unsaved_changes = True
        self.form_widget.unsaved_changes_state.emit(True)
    
    def _on_files_attachment_changed(self):
        """Обработка изменения attachments в панели файлов"""
        if not self.current_test_case:
            return
        # Помечаем изменения в форме (чтобы появилась кнопка сохранения)
        self.form_widget.has_unsaved_changes = True
        self.form_widget.unsaved_changes_state.emit(True)
    
    def _on_form_before_save(self, test_case: TestCase):
        """Обновить данные тест-кейса из панели информации перед сохранением"""
        if hasattr(self, "aux_panel") and test_case:
            self.aux_panel.update_information_test_case(test_case)
    
    def _filter_tree(self):
        query = self.search_input.text()
        self.tree_widget.filter_items(query)

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

    def _reset_all_step_statuses(self):
        if not self.test_cases:
            return
        count = 0
        for case in self.test_cases:
            if not case.steps:
                continue
            for step in case.steps:
                step.status = ""
            self.service.save_test_case(case)
            count += 1
        self.load_all_test_cases()
        if self.current_test_case:
            self.form_widget.load_test_case(self.current_test_case)
        self.statusBar().showMessage(f"Статусы шагов сброшены: {count} тест-кейсов")

    def _mark_current_case_passed(self):
        if not self.current_test_case or not self.current_test_case.steps:
            return
        for step in self.current_test_case.steps:
            step.status = "passed"
        self.service.save_test_case(self.current_test_case)
        self.form_widget.load_test_case(self.current_test_case)
        self.load_all_test_cases()
        self.statusBar().showMessage("Все шаги текущего тест-кейса помечены как passed")
        self._update_statistics_panel()

    def _reset_current_case_statuses(self):
        if not self.current_test_case or not self.current_test_case.steps:
            return
        for step in self.current_test_case.steps:
            step.status = ""
        self.service.save_test_case(self.current_test_case)
        self.form_widget.load_test_case(self.current_test_case)
        self.load_all_test_cases()
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
        if hasattr(self, "aux_panel"):
            self.aux_panel.set_panels_enabled(is_edit, is_edit)
            # Устанавливаем режим редактирования для панели информации
            self.aux_panel.set_information_edit_mode(is_edit)
            # Блокируем/разблокируем кнопки в панели управления раннером
            if hasattr(self.aux_panel, "stats_panel"):
                # В режиме редактирования блокируем, в режиме запуска - разблокируем
                self.aux_panel.stats_panel.set_buttons_enabled(not is_edit)
            if is_edit:
                self.aux_panel.restore_last_tab()
            else:
                self.aux_panel.show_stats_tab()

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
        
        # Сохраняем текущие размеры splitter'ов перед обновлением
        current_detail_sizes = self.detail_splitter.sizes()
        current_main_sizes = self.main_splitter.sizes() if hasattr(self, "main_splitter") else None
        
        # Обновляем геометрию формы для корректного пересчета размеров
        self.form_widget.updateGeometry()
        
        # Если есть сохраненные размеры, применяем их пропорционально
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
        if 'LLM_HOST' in new_settings:
            self.llm_host = new_settings['LLM_HOST'].strip()
        if 'LLM_MODEL' in new_settings:
            self.llm_model = new_settings['LLM_MODEL'].strip()
            # Обновляем модель в селекторе
            if hasattr(self, 'model_selector'):
                current_text = self.model_selector.currentText()
                if current_text != self.llm_model:
                    self.model_selector.setCurrentText(self.llm_model)
        
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


def create_main_window() -> MainWindow:
    """
    Фабричная функция для создания главного окна
    
    Использует паттерн Factory для централизованного создания окна
    """
    return MainWindow()

