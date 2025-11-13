"""Главное окно приложения"""

import json
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
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont

from ..models.test_case import TestCase
from ..services.test_case_service import TestCaseService
from ..repositories.test_case_repository import TestCaseRepository
from .widgets.placeholder_widget import PlaceholderWidget
from .widgets.tree_widget import TestCaseTreeWidget
from .widgets.form_widget import TestCaseFormWidget
from .widgets.review_panel import ReviewPanel
from .widgets.bulk_actions_panel import BulkActionsPanel
from .styles.telegram_theme import TELEGRAM_DARK_THEME
from ..utils import llm
from ..utils.prompt_builder import build_review_prompt


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
        self.panel_sizes = dict(self.settings.get('panel_sizes', {'left': 350, 'form_area': 900, 'review': 0}))
        self._last_review_width = self.panel_sizes.get('review', 0) or 360
        self.test_cases_dir = Path(self.settings.get('test_cases_dir', 'testcases'))
        if not self.test_cases_dir.exists():
            self.test_cases_dir = self.prompt_select_folder()
        self.default_prompt = self.settings.get('DEFAULT_PROMT', "Опиши задачу для ревью.")
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
        
        self.setup_ui()
        self.apply_theme()
        self.load_all_test_cases()
        self._show_placeholder()
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        self.setWindowTitle("✈️ Test Case Editor v2.0 (SOLID)")
        self._apply_initial_geometry()
        
        # Создаем меню
        self.create_menu()
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
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
    
    def _create_right_panel(self) -> QWidget:
        """Создать правую панель с формой"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.detail_splitter = QSplitter(Qt.Horizontal)
        self.detail_splitter.setChildrenCollapsible(False)
        self.detail_splitter.setCollapsible(1, True)
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

        # Панель ревью
        self.review_panel = ReviewPanel()
        self.review_panel.setVisible(False)
        self.review_panel.prompt_saved.connect(self._on_prompt_saved)
        self.review_panel.enter_clicked.connect(self._on_review_enter_clicked)
        self.review_panel.close_requested.connect(self._hide_review_panel)
        self.detail_splitter.addWidget(self.review_panel)

        layout.addWidget(self.detail_splitter)
        
        return panel
    
    def create_menu(self):
        """Создание меню приложения"""
        menubar = self.menuBar()
        
        # Меню "Файл"
        file_menu = menubar.addMenu('Файл')
        
        # Действие "Выбрать папку"
        select_folder_action = file_menu.addAction('📁 Выбрать папку с тест-кейсами')
        select_folder_action.triggered.connect(self.select_test_cases_folder)
        select_folder_action.setShortcut('Ctrl+O')
        
        # Действие "Конвертировать из Azure DevOps"
        convert_action = file_menu.addAction('Конвертировать')
        convert_action.triggered.connect(self.convert_from_azure)

        file_menu.addSeparator()
        
        # Действие "Выход"
        exit_action = file_menu.addAction('Выход')
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut('Ctrl+Q')

        # Меню "Вид"
        view_menu = menubar.addMenu('Вид')
        width_action = view_menu.addAction('Настроить ширины панелей…')
        width_action.triggered.connect(self._configure_panel_widths)
        statistics_action = view_menu.addAction('Показать статистику')
        statistics_action.triggered.connect(self._show_statistics_panel)

        # Меню "git"
        git_menu = menubar.addMenu('git')
        git_commit_action = git_menu.addAction('Выполнить commit и push…')
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

    def _on_test_case_selected(self, test_case: TestCase):
        """Обработка выбора тест-кейса"""
        self.current_test_case = test_case
        self.detail_stack.setCurrentWidget(self.form_widget)
        self.form_widget.load_test_case(test_case)
        self._hide_review_panel()
        
        # Показываем форму
        
        self.statusBar().showMessage(f"Открыт: {test_case.title}")
    
    def _on_form_unsaved_state(self, has_changes: bool):
        """Обновление статуса при изменениях в форме"""
        if has_changes:
            self.statusBar().showMessage("Есть несохраненные изменения. Нажмите «Сохранить».")
        else:
            if self.current_test_case:
                self.statusBar().showMessage(f"Изменения сохранены. Открыт: {self.current_test_case.title}")
            else:
                self.statusBar().showMessage("Готов к работе")
    
    def _on_tree_updated(self):
        """Обработка обновления дерева"""
        self.load_all_test_cases()
        self.statusBar().showMessage("Дерево тест-кейсов обновлено.")
    
    def _on_test_case_saved(self):
        """Обработка сохранения тест-кейса"""
        self.load_all_test_cases()
        self.statusBar().showMessage("Тест-кейс сохранен")
    
    def _filter_tree(self):
        query = self.search_input.text()
        self.tree_widget.filter_items(query)

    def _on_review_requested(self, data):
        """Показ панели ревью."""
        if self.detail_stack.currentWidget() is not self.form_widget:
            self.detail_stack.setCurrentWidget(self.form_widget)
        self._show_review_panel()
        attachments = self._collect_review_attachments(data)
        self.review_panel.set_attachments(attachments)
        base_prompt = self.settings.get('DEFAULT_PROMT', self.default_prompt)
        self.review_panel.set_prompt_text(base_prompt)
        self.review_panel.clear_response()
        self.statusBar().showMessage("Панель ревью открыта")

    def _on_prompt_saved(self, text: str):
        """Сохранение промта в настройках."""
        self.settings['DEFAULT_PROMT'] = text
        self.save_settings(self.settings)
        self.default_prompt = text
        self.statusBar().showMessage("Промт сохранен")

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

    def _show_statistics_panel(self):
        """Показать дерево и статистику (placeholder)."""
        self.detail_stack.setCurrentWidget(self.placeholder)
        self._hide_review_panel()
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
        prompt = (text or "").strip()
        if not prompt:
            self.review_panel.set_response_text("Введите промт перед отправкой.")
            self.statusBar().showMessage("Пустой промт — запрос не отправлен")
            return

        if self._llm_thread and self._llm_thread.isRunning():
            self.statusBar().showMessage("Ожидайте завершения текущего запроса к LLM")
            return

        attachment_paths = [Path(p) for p in files]
        self.review_panel.set_loading_state(True)
        self.review_panel.set_response_text("Отправляю запрос в LLM…")

        model = self.settings.get('LLM_MODEL') or None
        host = self.settings.get('LLM_HOST') or None

        chtz_path = self._find_chtz_attachment(attachment_paths)
        test_case_path = self._current_test_case_path or self._find_test_case_attachment(attachment_paths)

        try:
            payload = build_review_prompt(
                self.methodic_path,
                prompt,
                test_case_path=test_case_path,
                chtz_path=chtz_path,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.review_panel.set_loading_state(False)
            self.review_panel.set_response_text(f"Не удалось подготовить промт: {exc}")
            self.statusBar().showMessage("Ошибка подготовки промта для LLM")
            return

        self._start_llm_request(payload, model, host, self._handle_llm_success)

        self.statusBar().showMessage(
            f"Отправлен промт длиной {len(prompt)} символов. Прикреплено файлов: {len(files)}"
        )

    def _start_llm_request(self, payload: str, model: Optional[str], host: Optional[str], success_slot):
        worker = _LLMWorker(payload, model, host)
        thread = QThread()
        worker.moveToThread(thread)

        worker.finished.connect(success_slot)
        worker.error.connect(self._handle_llm_error)
        thread.started.connect(worker.run)

        thread.start()

        self._llm_worker = worker
        self._llm_thread = thread

    def _handle_llm_success(self, response: str):
        self.review_panel.set_response_text(response.strip())
        self.review_panel.set_loading_state(False)
        self.statusBar().showMessage("Ответ LLM получен")
        self._cleanup_llm_worker()

    def _handle_llm_error(self, error_message: str):
        self.review_panel.set_response_text(f"Ошибка: {error_message}")
        self.review_panel.set_loading_state(False)
        self.statusBar().showMessage("Ошибка при обращении к LLM")
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
        self._hide_review_panel()

    def _hide_review_panel(self):
        sizes = self.detail_splitter.sizes()
        has_valid_geometry = bool(sizes) and len(sizes) == 2 and any(value > 0 for value in sizes)

        if has_valid_geometry and sizes[1] > 0:
            self._last_review_width = sizes[1]
            self.panel_sizes['review'] = self._last_review_width

        if has_valid_geometry:
            form_area = max(sizes[0] + sizes[1], 200)
        else:
            main_sizes = self.main_splitter.sizes()
            right_width = main_sizes[1] if main_sizes and len(main_sizes) == 2 else self.panel_sizes.get('form_area', 900)
            form_area = max(right_width, 200)

        self.review_panel.setVisible(False)
        self.detail_splitter.setSizes([form_area, 0])

        actual_sizes = self.detail_splitter.sizes()
        if actual_sizes and len(actual_sizes) == 2:
            self.panel_sizes['form_area'] = max(sum(actual_sizes), 200)
            self._save_panel_sizes()

    def _show_review_panel(self):
        main_sizes = self.main_splitter.sizes()
        current_right = main_sizes[1] if main_sizes and len(main_sizes) == 2 else self.panel_sizes.get('form_area', 900)
        current_right = max(current_right, 200)

        review_width = max(self.panel_sizes.get('review', self._last_review_width or 300), 200)
        total_area = max(current_right, review_width + 200)
        form_width = max(total_area - review_width, 200)

        self.review_panel.setVisible(True)
        self.detail_splitter.setSizes([form_width, review_width])

        actual_sizes = self.detail_splitter.sizes()
        if actual_sizes and len(actual_sizes) == 2:
            self.panel_sizes['form_area'] = max(sum(actual_sizes), 200)
            self.panel_sizes['review'] = max(actual_sizes[1], 0)
        else:
            self.panel_sizes['form_area'] = total_area
            self.panel_sizes['review'] = review_width

        self._save_panel_sizes()

    def _apply_initial_panel_sizes(self):
        left_width = max(self.panel_sizes.get('left', 350), 150)
        total_area = max(self.panel_sizes.get('form_area', 900), 200)
        review_width = max(self.panel_sizes.get('review', self._last_review_width or 300), 0)

        self.main_splitter.setSizes([left_width, total_area])

        if review_width > 0:
            self.review_panel.setVisible(True)
            total_area = max(total_area, review_width + 200)
            self.panel_sizes['form_area'] = total_area
            form_width = max(total_area - review_width, 200)
            self.detail_splitter.setSizes([form_width, review_width])
        else:
            self._hide_review_panel()

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
            if sizes[1] > 0:
                self.panel_sizes['review'] = sizes[1]
                self._last_review_width = sizes[1]
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
            0,
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

