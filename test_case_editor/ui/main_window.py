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
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont

from ..models.test_case import TestCase
from ..services.test_case_service import TestCaseService
from ..repositories.test_case_repository import TestCaseRepository
from .widgets.placeholder_widget import PlaceholderWidget
from .widgets.tree_widget import TestCaseTreeWidget
from .widgets.form_widget import TestCaseFormWidget
from .widgets.auxiliary_panel import AuxiliaryPanel
from .widgets.bulk_actions_panel import BulkActionsPanel
from .styles.telegram_theme import TELEGRAM_DARK_THEME
from ..utils import llm
from ..utils.prompt_builder import build_review_prompt, build_creation_prompt
from ..utils.list_models import fetch_models as fetch_llm_models


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
        self.available_llm_models = self._fetch_available_llm_models()
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
        
        self.setup_ui()
        self._apply_model_options()
        self.apply_theme()
        self.load_all_test_cases()
        self._show_placeholder()
        self._apply_mode_state()
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        self.setWindowTitle("✈️ Test Case Editor v2.0 (SOLID)")
        self._apply_initial_geometry()
        self._init_menus()
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = self._create_mode_header()
        main_layout.addWidget(header)
        
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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Заголовок
        header = QFrame()
        header.setMaximumHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        title_label = QLabel("📁 Файлы тест-кейсов")
        title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        header_layout.addWidget(title_label)
        
        self.file_count_label = QLabel("(0)")
        self.file_count_label.setStyleSheet("color: #8B9099;")
        header_layout.addWidget(self.file_count_label)
        header_layout.addStretch()

        layout.addWidget(header)
        
        # Отображение текущей папки
        current_folder_frame = QFrame()
        current_folder_frame.setMaximumHeight(30)
        folder_layout = QHBoxLayout(current_folder_frame)
        folder_layout.setContentsMargins(10, 0, 10, 5)
        
        folder_icon = QLabel("📂")
        folder_icon.setStyleSheet("color: #5288C1; font-size: 10pt;")
        folder_layout.addWidget(folder_icon)
        
        self.current_folder_label = QLabel("testcases")
        self.current_folder_label.setStyleSheet("color: #8B9099; font-size: 9pt;")
        self.current_folder_label.setWordWrap(False)
        folder_layout.addWidget(self.current_folder_label, 1)
        
        layout.addWidget(current_folder_frame)
        
        # Поиск
        search_frame = QFrame()
        search_frame.setMaximumHeight(40)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(10, 0, 10, 5)
        
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

    def _create_mode_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet("background-color: #131A23; border-bottom: 1px solid #1F2A36;")
        header.setMaximumHeight(48)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 8, 16, 8)

        menu_row = QHBoxLayout()
        menu_row.setSpacing(6)
        for menu in (self.file_menu, self.view_menu, self.git_menu):
            btn = QToolButton()
            btn.setText(menu.title())
            btn.setPopupMode(QToolButton.InstantPopup)
            btn.setMenu(menu)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                """
                QToolButton {
                    background-color: #1E2732;
                    border: 1px solid #2B3945;
                    border-radius: 6px;
                    color: #E1E3E6;
                    padding: 4px 12px;
                }
                QToolButton:hover {
                    background-color: #2B3945;
                }
                """
            )
            menu_row.addWidget(btn)

        layout.addLayout(menu_row)

        title = QLabel("✈️ Test Case Editor")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #E1E3E6;")
        layout.addWidget(title, 1, Qt.AlignLeft)

        layout.addStretch(1)

        self.mode_label = QLabel()
        self.mode_label.setStyleSheet("color: #8B9099; font-size: 10pt;")
        layout.addWidget(self.mode_label, alignment=Qt.AlignRight)
        self._update_mode_label()

        return header
    
    def _create_right_panel(self) -> QWidget:
        """Создать правую панель с формой"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
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
        self.detail_splitter.addWidget(self.aux_panel)

        self.detail_splitter.setCollapsible(0, False)
        self.detail_splitter.setCollapsible(1, False)
        layout.addWidget(self.detail_splitter)
        
        return panel
    
    def _init_menus(self):
        self.file_menu = QMenu('Файл', self)
        select_folder_action = self.file_menu.addAction('📁 Выбрать папку с тест-кейсами')
        select_folder_action.triggered.connect(self.select_test_cases_folder)
        select_folder_action.setShortcut('Ctrl+O')

        convert_action = self.file_menu.addAction('Конвертировать')
        convert_action.triggered.connect(self.convert_from_azure)
        self.file_menu.addSeparator()

        exit_action = self.file_menu.addAction('Выход')
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut('Ctrl+Q')

        self.view_menu = QMenu('Вид', self)
        width_action = self.view_menu.addAction('Настроить ширины панелей…')
        width_action.triggered.connect(self._configure_panel_widths)
        statistics_action = self.view_menu.addAction('Показать статистику')
        statistics_action.triggered.connect(self._show_statistics_panel)

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

        self.git_menu = QMenu('git', self)
        git_commit_action = self.git_menu.addAction('Выполнить commit и push…')
        git_commit_action.triggered.connect(self._open_git_commit_dialog)
    
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
    
    def apply_theme(self):
        """Применение темы"""
        self.setStyleSheet(TELEGRAM_DARK_THEME)
    
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
        self.test_cases = self.service.load_all_test_cases(self.test_cases_dir)
        
        # Обновляем дерево
        self.tree_widget.load_tree(self.test_cases_dir, self.test_cases)
        
        # Обновляем счетчики
        self.file_count_label.setText(f"({len(self.test_cases)})")
        self.placeholder.update_count(len(self.test_cases))
        self.current_folder_label.setText(str(self.test_cases_dir))
        
        self.statusBar().showMessage(f"Загружено тест-кейсов: {len(self.test_cases)}")
        self._update_json_preview()
        if hasattr(self, "aux_panel"):
            self.aux_panel.update_statistics(self.test_cases)

    def _on_test_case_selected(self, test_case: TestCase):
        """Обработка выбора тест-кейса"""
        self.current_test_case = test_case
        self.detail_stack.setCurrentWidget(self.form_widget)
        self.form_widget.load_test_case(test_case)
        self._update_json_preview()
        self._update_json_preview()
        
        # Показываем форму
        
        self.statusBar().showMessage(f"Открыт: {test_case.name}")
    
    def _on_form_unsaved_state(self, has_changes: bool):
        """Обновление статуса при изменениях в форме"""
        if has_changes:
            self.statusBar().showMessage("Есть несохраненные изменения. Нажмите «Сохранить».")
        else:
            if self.current_test_case:
                self.statusBar().showMessage(f"Изменения сохранены. Открыт: {self.current_test_case.name}")
            else:
                self.statusBar().showMessage("Готов к работе")
        self._update_mode_label()
    
    def _on_tree_updated(self):
        """Обработка обновления дерева"""
        self.load_all_test_cases()
        self.statusBar().showMessage("Дерево тест-кейсов обновлено.")
    
    def _on_test_case_saved(self):
        """Обработка сохранения тест-кейса"""
        self.load_all_test_cases()
        self._update_json_preview()
        self.statusBar().showMessage("Тест-кейс сохранен")
    
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
        default = self.llm_model or (models[0] if models else "")
        self.aux_panel.set_model_options(models, default)
        if not models:
            warning = (
                "Не удалось получить список моделей LLM. Проверьте настройки LLM_HOST/LLM_MODEL "
                "и повторите попытку."
            )
            self.statusBar().showMessage(warning)

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
            model=self.aux_panel.get_selected_review_model(),
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

        model_used = (self.aux_panel.get_selected_creation_model() or self.llm_model or "").strip()
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
        self._update_mode_label()
        self._apply_mode_state()
        label = "Редактирование" if mode == "edit" else "Запуск тестов"
        self.statusBar().showMessage(f"Режим изменён: {label}")

    def _update_mode_label(self):
        mode_text = "Редактирование" if self._current_mode == "edit" else "Запуск тестов"
        if hasattr(self, "mode_label"):
            self.mode_label.setText(f"Режим: {mode_text}")

    def _apply_mode_state(self):
        is_edit = self._current_mode == "edit"
        if hasattr(self, "form_widget"):
            self.form_widget.set_edit_mode(is_edit)
            self.form_widget.set_run_mode(not is_edit)
        if hasattr(self, "aux_panel"):
            self.aux_panel.set_panels_enabled(is_edit, is_edit)
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
        """Импорт тест-кейсов из JSON Azure DevOps."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите JSON-файлы Azure DevOps",
            str(self.test_cases_dir),
            "JSON файлы (*.json)",
        )

        if not files:
            return

        total_created = 0
        all_errors = []

        for file_path in files:
            created, errors = self.service.import_from_azure(Path(file_path), self.test_cases_dir)
            total_created += created
            all_errors.extend(errors)

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
                f"Создано тест-кейсов: {total_created}",
            )

        self.statusBar().showMessage(f"Импортировано тест-кейсов: {total_created}")


def create_main_window() -> MainWindow:
    """
    Фабричная функция для создания главного окна
    
    Использует паттерн Factory для централизованного создания окна
    """
    return MainWindow()

