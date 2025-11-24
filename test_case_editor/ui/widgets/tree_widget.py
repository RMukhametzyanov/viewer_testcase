"""Простой виджет дерева тест-кейсов."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt5.QtWidgets import (
    QApplication,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QMenu,
    QInputDialog,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData, QByteArray
from PyQt5.QtGui import QFont, QColor

from ...services.test_case_service import TestCaseService
from ...models.test_case import TestCase


class TestCaseTreeWidget(QTreeWidget):
    """Минимальный QTreeWidget для отображения и управления деревом объектов."""

    MIME_TYPE = "application/x-testcase-tree-item"
    _PYTEST_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "utils" / "pytest_tamplete.json"
    _PYTEST_TEMPLATE_CACHE: Optional[str] = None
    _PYTEST_TEMPLATE_FALLBACK = (
        "import os\n"
        "import allure\n"
        "from gpn_qa_utils.api.auth import Auth\n\n"
        "@allure.epic(\"{epic}\")\n"
        "@allure.feature(\"{feature}\")\n"
        "@allure.story(\"{story}\")\n"
        "class Test{class_name}:\n"
        "    client = Auth.get_client(base_url=os.getenv(\"AUTOTEST_BASE_URL\"), timeout=20.0)\n\n"
        "    @allure.testcase(\"{testcase_id}\", \"{testcase_id}\")\n"
        "    @allure.title(\"{title}\")\n"
        "    def test_{method_name}(self):\n"
        "{steps}\n"
    )

    test_case_selected = pyqtSignal(TestCase)
    tree_updated = pyqtSignal()
    review_requested = pyqtSignal(object)

    def __init__(self, service: TestCaseService, parent=None):
        super().__init__(parent)
        self.service = service
        self.test_cases_dir: Optional[Path] = None
        self._edit_mode = True  # По умолчанию режим редактирования
        self._setup_ui()

    def _setup_ui(self):
        self.setHeaderHidden(True)
        self.setIndentation(20)
        self.setAnimated(True)

        self.itemClicked.connect(self._on_item_clicked)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDrop)

    # ------------------------------------------------------------------ load

    def load_tree(self, test_cases_dir: Path, test_cases: list):
        self.test_cases_dir = test_cases_dir
        self.clear()

        if not test_cases_dir.exists():
            return

        self._populate_directory(test_cases_dir, self.invisibleRootItem(), test_cases)
        self.collapseAll()
        # После загрузки обновляем статусы папок на основе актуальных данных дерева
        if not self._edit_mode:
            self._update_folder_statuses(self.invisibleRootItem())
    
    def set_edit_mode(self, enabled: bool):
        """Установить режим редактирования (скрыть/показать иконки статусов)"""
        if self._edit_mode == enabled:
            return
        self._edit_mode = enabled
        # Обновляем все элементы дерева
        self._update_tree_icons(self.invisibleRootItem())
    
    def _update_tree_icons(self, parent_item: QTreeWidgetItem):
        """Обновить иконки во всех элементах дерева"""
        # Сначала обновляем статусы папок (снизу вверх), если не в режиме редактирования
        if not self._edit_mode:
            self._update_folder_statuses(parent_item)
        
        # Затем обновляем отображение всех элементов
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            data = child.data(0, Qt.UserRole)
            if data:
                if data.get('type') == 'file':
                    test_case = data.get('test_case')
                    if test_case:
                        # В режиме редактирования иконки не показываем
                        if not self._edit_mode:
                            icon, color = self._get_test_case_icon_and_color(test_case)
                            item_text = f"{icon} {test_case.name}".strip() if icon else test_case.name
                            child.setText(0, item_text)
                            if color:
                                child.setForeground(0, QColor(color))
                        else:
                            child.setText(0, test_case.name)
                elif data.get('type') == 'folder':
                    # Обновляем отображение папки
                    folder_path = data.get('path')
                    if folder_path:
                        if not self._edit_mode:
                            # Пересчитываем статус папки на основе дерева
                            folder_icon, folder_color = self._calculate_folder_status_from_tree(child)
                            data['icon'] = folder_icon
                            data['color'] = folder_color
                            folder_text = f"{folder_icon} 📁 {folder_path.name}".strip() if folder_icon else f"📁 {folder_path.name}"
                            child.setText(0, folder_text)
                            if folder_color:
                                child.setForeground(0, QColor(folder_color))
                        else:
                            child.setText(0, f"📁 {folder_path.name}")
            # Рекурсивно обновляем дочерние элементы
            self._update_tree_icons(child)
    
    def _update_folder_statuses(self, parent_item: QTreeWidgetItem):
        """Обновить статусы всех папок в дереве (снизу вверх)"""
        # Сначала обновляем дочерние элементы
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            self._update_folder_statuses(child)
        
        # Затем обновляем статус текущей папки, если это папка
        data = parent_item.data(0, Qt.UserRole)
        if data and data.get('type') == 'folder':
            folder_icon, folder_color = self._calculate_folder_status_from_tree(parent_item)
            data['icon'] = folder_icon
            data['color'] = folder_color

    def _populate_directory(self, directory: Path, parent_item: QTreeWidgetItem, test_cases: list):
        for subdir in sorted([d for d in directory.iterdir() if d.is_dir()]):
            # Пропускаем папки _attachment
            if subdir.name == "_attachment":
                continue
            folder_item = QTreeWidgetItem(parent_item)
            
            # Вычисляем статус папки на основе тест-кейсов внутри
            if not self._edit_mode:
                folder_icon, folder_color = self._calculate_folder_status(subdir, test_cases)
            else:
                folder_icon, folder_color = "", ""
            folder_text = f"{folder_icon} 📁 {subdir.name}".strip() if folder_icon else f"📁 {subdir.name}"
            folder_item.setText(0, folder_text)
            folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'path': subdir, 'icon': folder_icon, 'color': folder_color})
            folder_item.setFont(0, QFont("Segoe UI", 10, QFont.Bold))
            if folder_color:
                folder_item.setForeground(0, QColor(folder_color))
            self._populate_directory(subdir, folder_item, test_cases)

        for test_case in test_cases:
            if test_case._filepath and test_case._filepath.parent == directory:
                # В режиме редактирования иконки не показываем
                if not self._edit_mode:
                    icon, color = self._get_test_case_icon_and_color(test_case)
                else:
                    icon, color = "", ""
                
                item = QTreeWidgetItem(parent_item)
                # Добавляем иконку только если она есть
                item_text = f"{icon} {test_case.name}".strip() if icon else test_case.name
                item.setText(0, item_text)
                item.setData(0, Qt.UserRole, {'type': 'file', 'test_case': test_case})
                item.setFont(0, QFont("Segoe UI", 10))
                if color:
                    item.setForeground(0, QColor(color))

    def _get_test_case_icon_and_color(self, test_case) -> Tuple[str, str]:
        """
        Определить иконку и цвет для тест-кейса на основе статусов шагов.
        
        Returns:
            tuple: (icon, color) где icon - символ иконки, color - цвет в формате hex
        """
        if not test_case or not test_case.steps:
            # Если нет шагов, показываем незалитый кружок
            return ('○', '#8B9099')
        
        steps = test_case.steps
        if not steps:
            return ('○', '#8B9099')
        
        # Получаем статусы всех шагов (включая пустые)
        step_statuses = [(step.status or "").strip().lower() for step in steps]
        
        # Проверяем наличие failed (приоритет 1)
        has_failed = any(s == "failed" for s in step_statuses)
        if has_failed:
            return ('●', '#F5555D')  # Красный залитый кружок
        
        # Проверяем наличие skipped (приоритет 2)
        has_skipped = any(s == "skipped" for s in step_statuses)
        if has_skipped:
            return ('●', '#95a5a6')  # Серый залитый кружок
        
        # Проверяем, все ли шаги имеют статус "passed"
        # Все шаги должны иметь непустой статус и все должны быть "passed"
        all_have_status = all(s for s in step_statuses)  # Все статусы непустые
        all_passed = all(s == "passed" for s in step_statuses)  # Все статусы равны "passed"
        
        if all_have_status and all_passed:
            return ('●', '#6CC24A')  # Зеленый залитый кружок
        
        # Не все шаги имеют статус и нет failed/skipped
        return ('○', '#8B9099')  # Незалитый кружок
    
    @staticmethod
    def _status_icon(status: str) -> str:
        """Устаревший метод, оставлен для совместимости"""
        return {
            'Done': '✓',
            'Blocked': '⚠',
            'In Progress': '⟳',
            'Draft': '○',
            'Deprecated': '×',
        }.get(status, '○')

    @staticmethod
    def _status_color(status: str) -> str:
        """Устаревший метод, оставлен для совместимости"""
        return {
            'Done': '#6CC24A',
            'Blocked': '#F5555D',
            'In Progress': '#FFA931',
            'Draft': '#8B9099',
            'Deprecated': '#6B7380',
        }.get(status, '#E1E3E6')
    
    def _calculate_folder_status(self, folder_path: Path, test_cases: list) -> Tuple[str, str]:
        """
        Вычислить статус папки на основе тест-кейсов внутри неё.
        
        Returns:
            tuple: (icon, color) где icon - символ иконки, color - цвет в формате hex
        """
        # Собираем все тест-кейсы в этой папке и подпапках
        folder_test_cases = []
        for test_case in test_cases:
            if test_case._filepath:
                # Проверяем, находится ли тест-кейс в этой папке или её подпапках
                try:
                    relative_path = test_case._filepath.relative_to(folder_path)
                    folder_test_cases.append(test_case)
                except ValueError:
                    # Тест-кейс не в этой папке
                    continue
        
        if not folder_test_cases:
            return ('○', '#8B9099')  # Если нет тест-кейсов, незалитый кружок
        
        # Собираем все статусы шагов из всех тест-кейсов в папке
        all_step_statuses = []
        total_steps_count = 0
        for tc in folder_test_cases:
            if tc.steps:
                for step in tc.steps:
                    total_steps_count += 1
                    status = (step.status or "").strip().lower()
                    all_step_statuses.append(status)  # Включаем пустые статусы
        
        if not all_step_statuses:
            return ('○', '#8B9099')  # Нет шагов
        
        # Проверяем наличие failed (приоритет 1)
        has_failed = any(s == "failed" for s in all_step_statuses)
        if has_failed:
            return ('●', '#F5555D')  # Красный залитый кружок
        
        # Проверяем наличие skipped (приоритет 2)
        has_skipped = any(s == "skipped" for s in all_step_statuses)
        if has_skipped:
            return ('●', '#95a5a6')  # Серый залитый кружок
        
        # Проверяем, все ли шаги имеют статус "passed"
        all_have_status = all(s for s in all_step_statuses)  # Все статусы непустые
        all_passed = all(s == "passed" for s in all_step_statuses)  # Все статусы равны "passed"
        
        if all_have_status and all_passed:
            return ('●', '#6CC24A')  # Зеленый залитый кружок
        
        # Не все шаги имеют статус и нет failed/skipped
        return ('○', '#8B9099')  # Незалитый кружок
    
    def _calculate_folder_status_from_tree(self, folder_item: QTreeWidgetItem) -> Tuple[str, str]:
        """
        Вычислить статус папки на основе элементов дерева внутри неё.
        
        Returns:
            tuple: (icon, color) где icon - символ иконки, color - цвет в формате hex
        """
        all_step_statuses = []
        
        def collect_step_statuses(item: QTreeWidgetItem):
            data = item.data(0, Qt.UserRole)
            if data:
                if data.get('type') == 'file':
                    test_case = data.get('test_case')
                    if test_case and test_case.steps:
                        for step in test_case.steps:
                            status = (step.status or "").strip().lower()
                            all_step_statuses.append(status)  # Включаем пустые статусы
                elif data.get('type') == 'folder':
                    # Рекурсивно собираем статусы из подпапок
                    for i in range(item.childCount()):
                        collect_step_statuses(item.child(i))
        
        # Собираем статусы шагов из всех дочерних элементов
        for i in range(folder_item.childCount()):
            collect_step_statuses(folder_item.child(i))
        
        if not all_step_statuses:
            return ('○', '#8B9099')  # Нет шагов
        
        # Проверяем наличие failed (приоритет 1)
        has_failed = any(s == "failed" for s in all_step_statuses)
        if has_failed:
            return ('●', '#F5555D')  # Красный залитый кружок
        
        # Проверяем наличие skipped (приоритет 2)
        has_skipped = any(s == "skipped" for s in all_step_statuses)
        if has_skipped:
            return ('●', '#95a5a6')  # Серый залитый кружок
        
        # Проверяем, все ли шаги имеют статус "passed"
        all_have_status = all(s for s in all_step_statuses)  # Все статусы непустые
        all_passed = all(s == "passed" for s in all_step_statuses)  # Все статусы равны "passed"
        
        if all_have_status and all_passed:
            return ('●', '#6CC24A')  # Зеленый залитый кружок
        
        # Не все шаги имеют статус и нет failed/skipped
        return ('○', '#8B9099')  # Незалитый кружок

    # ----------------------------------------------------------- interactions

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.UserRole)
        if data and data.get('type') == 'file':
            test_case = data.get('test_case')
            if test_case:
                self.test_case_selected.emit(test_case)

    def _show_context_menu(self, position):
        item = self.itemAt(position)
        if not item:
            self._show_root_menu(position)
            return

        data = item.data(0, Qt.UserRole)
        if not data:
            return

        if data.get('type') == 'folder':
            self._show_folder_menu(position, data)
        elif data.get('type') == 'file':
            self._show_file_menu(position, data)

    # ------------------------------------------------------------ menus

    def _show_root_menu(self, position):
        menu = QMenu(self)

        action_new_tc = menu.addAction("➕ Создать тест-кейс")
        action_new_tc.triggered.connect(lambda: self._create_test_case(self.test_cases_dir))

        menu.addSeparator()

        action_new_folder = menu.addAction("📁 Создать папку")
        action_new_folder.triggered.connect(lambda: self._create_folder(self.test_cases_dir))

        menu.addSeparator()

        action_review = menu.addAction("📝 Ревью")
        action_review.triggered.connect(lambda: self.review_requested.emit({'type': 'root'}))

        menu.exec_(self.mapToGlobal(position))

    def _show_folder_menu(self, position, folder_data):
        menu = QMenu(self)

        folder_path = folder_data['path']

        action_new_tc = menu.addAction("➕ Создать тест-кейс")
        action_new_tc.triggered.connect(lambda: self._create_test_case(folder_path))

        action_new_folder = menu.addAction("📁 Создать подпапку")
        action_new_folder.triggered.connect(lambda: self._create_folder(folder_path))

        menu.addSeparator()

        action_rename = menu.addAction("✎ Переименовать")
        action_rename.triggered.connect(lambda: self._rename_folder(folder_path))

        action_delete = menu.addAction("🗑️ Удалить папку")
        action_delete.triggered.connect(lambda: self._delete_folder(folder_path))

        menu.addSeparator()

        action_open_explorer = menu.addAction("🪟 Открыть в проводнике")
        action_open_explorer.triggered.connect(lambda: self._open_in_explorer(folder_path, select=False))

        menu.exec_(self.mapToGlobal(position))

    def _show_file_menu(self, position, file_data):
        menu = QMenu(self)

        test_case = file_data['test_case']

        action_open = menu.addAction("📂 Открыть")
        action_open.triggered.connect(lambda: self.test_case_selected.emit(test_case))

        action_open_explorer = menu.addAction("🪟 Открыть в проводнике")
        action_open_explorer.triggered.connect(
            lambda: self._open_in_explorer(test_case._filepath, select=True)
        )

        action_copy_info = menu.addAction("📋 Копировать информацию")
        action_copy_info.triggered.connect(lambda: self._copy_test_case_info(test_case))

        action_generate_api = menu.addAction("🧪 Сгенерировать каркас АТ API")
        action_generate_api.triggered.connect(lambda: self._copy_pytest_skeleton(test_case))

        action_rename = menu.addAction("✎ Переименовать файл")
        action_rename.triggered.connect(lambda: self._rename_file(test_case))

        action_duplicate = menu.addAction("📋 Дублировать")
        action_duplicate.triggered.connect(lambda: self._duplicate_test_case(test_case))

        menu.addSeparator()

        action_delete = menu.addAction("🗑️ Удалить")
        action_delete.triggered.connect(lambda: self._delete_test_case(test_case))

        menu.addSeparator()

        action_review = menu.addAction("📝 Ревью")
        action_review.triggered.connect(lambda: self.review_requested.emit(file_data))

        menu.exec_(self.mapToGlobal(position))

    # ------------------------------------------------------- actions

    def _create_test_case(self, target_folder):
        expanded_paths = self._capture_expanded_state()
        test_case = self.service.create_new_test_case(target_folder)
        if test_case:
            self.tree_updated.emit()
            self._restore_expanded_state(expanded_paths)
            self.test_case_selected.emit(test_case)

    def _create_folder(self, parent_dir):
        folder_name, ok = QInputDialog.getText(self, 'Создать папку', 'Имя папки:', text='Новая папка')
        if ok and folder_name:
            new_folder = parent_dir / folder_name
            try:
                new_folder.mkdir(exist_ok=True)
                self.tree_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать папку:\n{e}")

    def _rename_folder(self, folder_path):
        expanded_paths = self._capture_expanded_state()
        old_name = folder_path.name
        new_name, ok = QInputDialog.getText(self, 'Переименовать папку', 'Новое имя:', text=old_name)
        if ok and new_name and new_name != old_name:
            new_path = folder_path.parent / new_name
            try:
                folder_path.rename(new_path)
                self.tree_updated.emit()
                self._restore_expanded_state(expanded_paths)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать:\n{e}")

    def _delete_folder(self, folder_path):
        expanded_paths = self._capture_expanded_state()
        try:
            import shutil
            shutil.rmtree(folder_path)
            self.tree_updated.emit()
            self._restore_expanded_state(expanded_paths)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить папку:\n{e}")

    def _delete_test_case(self, test_case: TestCase):
        if not test_case:
            return

        name = getattr(test_case, "name", None) or getattr(test_case, "title", "тест-кейс")
        reply = QMessageBox.question(
            self,
            "Удаление тест-кейса",
            f"Удалить «{name}»?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        expanded_paths = self._capture_expanded_state()
        try:
            success = self.service.delete_test_case(test_case)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить тест-кейс:\n{exc}")
            return

        if not success:
            QMessageBox.warning(self, "Удаление", "Не удалось удалить тест-кейс.")
            return

        self.tree_updated.emit()
        self._restore_expanded_state(expanded_paths)

    def _rename_file(self, test_case):
        expanded_paths = self._capture_expanded_state()
        old_filename = test_case._filename
        new_filename, ok = QInputDialog.getText(self, 'Переименовать файл', 'Новое имя файла:', text=old_filename)
        if ok and new_filename and new_filename != old_filename:
            if not new_filename.endswith('.json'):
                new_filename += '.json'

            old_path = test_case._filepath
            new_path = old_path.parent / new_filename

            try:
                old_path.rename(new_path)
                self.tree_updated.emit()
                self._restore_expanded_state(expanded_paths)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать:\n{e}")

    def _duplicate_test_case(self, test_case):
        expanded_paths = self._capture_expanded_state()
        new_test_case = self.service.duplicate_test_case(test_case)
        if new_test_case:
            self.tree_updated.emit()
            self._restore_expanded_state(expanded_paths)
            self.focus_on_test_case(new_test_case)

    def _open_in_explorer(self, target_path: Optional[Path], select: bool):
        resolved_path = self._resolve_target_path(target_path)
        if not resolved_path:
            return

        try:
            if sys.platform.startswith("win"):
                self._open_in_windows_explorer(resolved_path, select)
            elif sys.platform == "darwin":
                self._open_in_macos_finder(resolved_path, select)
            else:
                self._open_in_unix_file_manager(resolved_path, select)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Открытие проводника",
                f"Не удалось открыть проводник:\n{exc}",
            )

    def _resolve_target_path(self, target_path: Optional[Path]) -> Optional[Path]:
        if not target_path:
            QMessageBox.warning(self, "Открытие проводника", "Путь к элементу не найден.")
            return None

        try:
            candidate_path = Path(target_path)
        except TypeError:
            QMessageBox.warning(self, "Открытие проводника", "Путь к элементу некорректен.")
            return None

        if not candidate_path.is_absolute():
            base_dir = Path(self.test_cases_dir) if self.test_cases_dir else Path.cwd()
            candidate_path = base_dir / candidate_path

        try:
            resolved_path = candidate_path.resolve(strict=False)
        except Exception:
            QMessageBox.warning(self, "Открытие проводника", "Не удалось определить путь к элементу.")
            return None

        if not resolved_path.exists():
            QMessageBox.warning(self, "Открытие проводника", "Файл или папка не найдены.")
            return None

        return resolved_path

    @staticmethod
    def _open_in_windows_explorer(target_path: Path, select: bool):
        normalized = os.path.normpath(str(target_path))
        if select and target_path.is_file():
            subprocess.run(["explorer", "/select,", normalized], check=False)
        else:
            subprocess.run(["explorer", normalized], check=False)

    @staticmethod
    def _open_in_macos_finder(target_path: Path, select: bool):
        if select and target_path.is_file():
            subprocess.run(["open", "-R", str(target_path)], check=False)
        else:
            subprocess.run(["open", str(target_path)], check=False)

    @staticmethod
    def _open_in_unix_file_manager(target_path: Path, select: bool):
        path_to_open = target_path if not select or target_path.is_dir() else target_path.parent
        subprocess.run(["xdg-open", str(path_to_open)], check=False)

    def _copy_test_case_info(self, test_case: TestCase):
        formatted = self._format_test_case_info(test_case)
        clipboard = QApplication.clipboard()
        clipboard.setText(formatted)
        QMessageBox.information(self, "Скопировано", "Информация по тест-кейсу скопирована в буфер обмена.")

    def _copy_pytest_skeleton(self, test_case: TestCase):
        skeleton = self._build_pytest_skeleton(test_case)
        skeleton = self._normalize_line_endings(skeleton)
        if not skeleton:
            QMessageBox.warning(self, "Каркас автотеста", "Не удалось сформировать каркас автотеста.")
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(skeleton)
        QMessageBox.information(self, "Готово", "Каркас автотеста на pytest скопирован в буфер обмена.")

    @staticmethod
    def _format_test_case_info(test_case: TestCase) -> str:
        tags = ", ".join(getattr(test_case, "tags", []) or []) or "-"
        steps = getattr(test_case, "steps", []) or []
        steps_lines = []
        for idx, step in enumerate(steps, start=1):
            action = getattr(step, "description", getattr(step, "step", "")) or "-"
            expected = getattr(step, "expected_result", getattr(step, "expected_res", "")) or "-"
            steps_lines.append(f"{idx}. {action} → {expected}")
        steps_block = "\n".join(steps_lines) if steps_lines else "-"

        return (
            f"Название: {getattr(test_case, 'name', '') or '-'}\n"
            f"ID: {test_case.id or '-'}\n"
            f"Статус: {test_case.status}\n"
            f"Test Layer: {getattr(test_case, 'test_layer', '-')}\n"
            f"Тип теста: {getattr(test_case, 'test_type', '-')}\n"
            f"Severity/Priority: {getattr(test_case, 'severity', '-')}/{getattr(test_case, 'priority', '-')}\n"
            f"Epic/Feature/Story/Component: "
            f"{getattr(test_case, 'epic', '-')}/"
            f"{getattr(test_case, 'feature', '-')}/"
            f"{getattr(test_case, 'story', '-')}/"
            f"{getattr(test_case, 'component', '-')}\n"
            f"Окружение/Браузер: {getattr(test_case, 'environment', '-')}/"
            f"{getattr(test_case, 'browser', '-')}\n"
            f"Автор/Владелец/Ревьюер: {test_case.author or '-'} / "
            f"{getattr(test_case, 'owner', '-') or '-'} / "
            f"{getattr(test_case, 'reviewer', '-') or '-'}\n"
            f"TestCaseId: {getattr(test_case, 'test_case_id', '-')}\n"
            f"Issue Links: {getattr(test_case, 'issue_links', '-')}\n"
            f"Test Case Links: {getattr(test_case, 'test_case_links', '-')}\n"
            f"Теги: {tags}\n"
            f"Описание:\n{getattr(test_case, 'description', '') or '-'}\n"
            f"Предусловия:\n{test_case.preconditions or '-'}\n"
            f"Ожидаемый результат:\n{getattr(test_case, 'expected_result', '-') or '-'}\n"
            f"Шаги:\n{steps_block}"
        )

    @classmethod
    def _load_pytest_template(cls) -> str:
        if cls._PYTEST_TEMPLATE_CACHE is not None:
            return cls._PYTEST_TEMPLATE_CACHE
        try:
            with open(cls._PYTEST_TEMPLATE_PATH, "r", encoding="utf-8") as handler:
                payload = json.load(handler)
            template = str(payload.get("template", ""))
            if not template.strip():
                template = cls._PYTEST_TEMPLATE_FALLBACK
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            template = cls._PYTEST_TEMPLATE_FALLBACK
        cls._PYTEST_TEMPLATE_CACHE = template
        return template

    def _build_pytest_skeleton(self, test_case: TestCase) -> str:
        template = self._load_pytest_template()

        epic = getattr(test_case, "epic", "") or "Название EPIC"
        feature = getattr(test_case, "feature", "") or "Название FEATURE"
        story = getattr(test_case, "story", "") or "Название STORY"

        class_name = self._sanitize_class_name(test_case.name)
        method_name = self._sanitize_method_name(test_case.name)
        testcase_id = (getattr(test_case, "test_case_id", "") or test_case.id or "tc.id").strip() or "tc.id"
        title = self._escape_quotes(test_case.name or "Без названия")

        steps_fragment = self._render_pytest_steps(test_case)

        try:
            rendered = template.format(
                epic=self._escape_braces(epic),
                feature=self._escape_braces(feature),
                story=self._escape_braces(story),
                class_name=class_name,
                testcase_id=self._escape_braces(testcase_id),
                title=self._escape_braces(title),
                method_name=method_name,
                steps=self._escape_braces(steps_fragment),
            )
        except KeyError:
            rendered = self._PYTEST_TEMPLATE_FALLBACK.format(
                epic=self._escape_braces(epic),
                feature=self._escape_braces(feature),
                story=self._escape_braces(story),
                class_name=class_name,
                testcase_id=self._escape_braces(testcase_id),
                title=self._escape_braces(title),
                method_name=method_name,
                steps=self._escape_braces(steps_fragment),
            )
        return rendered

    @staticmethod
    def _render_pytest_steps(test_case: TestCase) -> str:
        steps = getattr(test_case, "steps", None) or []
        if not steps:
            return (
                '\t\twith allure.step("Шаг1"):\n'
                '\t\t\t"""\n'
                '\t\t\tДействие: -\n'
                '\t\t\tОжидаемый результат: -\n'
                '\t\t\t"""\n'
                '\t\t\tpass'
            )

        blocks: List[str] = []
        for idx, step in enumerate(steps, start=1):
            action_text = TestCaseTreeWidget._prepare_docstring_content(getattr(step, "description", getattr(step, "step", "")))
            expected_text = TestCaseTreeWidget._prepare_docstring_content(getattr(step, "expected_result", getattr(step, "expected_res", "")))

            block = (
                f'\t\twith allure.step("Шаг{idx}"):\n'
                f'\t\t\t"""\n'
                f'\t\t\tДействие: {action_text}\n'
                f'\t\t\tОжидаемый результат: {expected_text}\n'
                f'\t\t\t"""\n'
                f'\t\t\tpass'
            )
            blocks.append(block)

        return "\n\n".join(blocks)

    @staticmethod
    def _prepare_docstring_content(value: Optional[str]) -> str:
        text = (value or "-").strip() or "-"
        text = text.replace('"""', '\\"\\"\\"')
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text.replace("\n", "\n\t\t\t")

    @staticmethod
    def _escape_quotes(value: str) -> str:
        return value.replace("\"", "\\\"")

    @staticmethod
    def _escape_braces(value: str) -> str:
        return value.replace("{", "{{").replace("}", "}}")

    @staticmethod
    def _normalize_line_endings(value: str) -> str:
        normalized = value.replace("\r\n", "\n").replace("\r", "\n")
        return normalized.replace("\n", "\r\n")

    @staticmethod
    def _sanitize_class_name(title: str) -> str:
        source = (title or "Generated").strip()
        parts = re.findall(r"[A-Za-z0-9]+", source.title())
        class_name = "".join(parts)
        if not class_name:
            class_name = "Generated"
        if class_name[0].isdigit():
            class_name = f"Generated{class_name}"
        return class_name

    @staticmethod
    def _sanitize_method_name(title: str) -> str:
        source = (title or "generated").lower()
        slug = re.sub(r"[^0-9a-z]+", "_", source).strip("_")
        if not slug:
            slug = "generated"
        if slug[0].isdigit():
            slug = f"tc_{slug}"
        return slug

    def filter_items(self, query: str):
        pattern = (query or "").strip().lower()
        self._apply_filter(self.invisibleRootItem(), pattern)
        if not pattern:
            self.collapseAll()

    def _apply_filter(self, item: QTreeWidgetItem, pattern: str) -> bool:
        matches = False
        for i in range(item.childCount()):
            child = item.child(i)
            child_match = self._apply_filter(child, pattern)
            matches = matches or child_match

        own_match = False
        if item is not self.invisibleRootItem():
            item_text = item.text(0).lower()
            own_match = not pattern or pattern in item_text
            visible = own_match or matches
            item.setHidden(not visible)
            if pattern:
                item.setExpanded(matches or own_match)
            return visible

        return matches

    # ----------------------------------------------------------- DnD helpers

    def mimeTypes(self):
        return [self.MIME_TYPE]

    def mimeData(self, items):
        if not items:
            return None
        item = items[0]
        data = item.data(0, Qt.UserRole)
        if not data:
            return None

        payload = {"type": data.get("type")}
        if payload["type"] == "file":
            test_case = data.get("test_case")
            if not test_case or not getattr(test_case, "_filepath", None):
                return None
            payload["path"] = str(test_case._filepath)
        elif payload["type"] == "folder":
            folder_path = data.get("path")
            if not folder_path:
                return None
            payload["path"] = str(folder_path)
        else:
            return None

        mime = QMimeData()
        mime.setData(self.MIME_TYPE, QByteArray(json.dumps(payload).encode("utf-8")))
        return mime

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event):
        mime = event.mimeData()
        if not mime.hasFormat(self.MIME_TYPE):
            event.ignore()
            return

        if not self.test_cases_dir:
            event.ignore()
            return

        try:
            payload = json.loads(bytes(mime.data(self.MIME_TYPE)).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            event.ignore()
            return

        source_type = payload.get("type")
        source_path = payload.get("path")
        if not source_type or not source_path:
            event.ignore()
            return

        target_folder = self._resolve_drop_target(event.pos())
        if target_folder is None:
            event.ignore()
            return
        target_folder = Path(target_folder)

        source_path_obj = Path(source_path)
        if source_type == "file":
            if source_path_obj.parent == target_folder:
                event.ignore()
                return
            moved = self.service.move_item(source_path_obj, target_folder)
        elif source_type == "folder":
            if source_path_obj == target_folder or self._is_subpath(target_folder, source_path_obj):
                event.ignore()
                return
            moved = self.service.move_item(source_path_obj, target_folder)
        else:
            event.ignore()
            return

        if moved:
            event.acceptProposedAction()
            expanded_paths = self._capture_expanded_state()
            self.tree_updated.emit()
            self._restore_expanded_state(expanded_paths)
        else:
            event.ignore()

    def _resolve_drop_target(self, position):
        item = self.itemAt(position)
        if not item:
            return self.test_cases_dir

        data = item.data(0, Qt.UserRole)
        if not data:
            return None

        if data.get("type") == "folder":
            return data.get("path")

        if data.get("type") == "file":
            test_case = data.get("test_case")
            if test_case and getattr(test_case, "_filepath", None):
                return test_case._filepath.parent

        return None

    def _capture_expanded_state(self):
        expanded = set()
        stack = [self.invisibleRootItem()]
        while stack:
            node = stack.pop()
            for i in range(node.childCount()):
                child = node.child(i)
                data = child.data(0, Qt.UserRole)
                if child.isExpanded() and data and data.get("type") == "folder":
                    path = data.get("path")
                    if path:
                        expanded.add(Path(path))
                stack.append(child)
        return expanded

    def _restore_expanded_state(self, expanded_paths):
        if not expanded_paths:
            return
        stack = [self.invisibleRootItem()]
        while stack:
            node = stack.pop()
            for i in range(node.childCount()):
                child = node.child(i)
                data = child.data(0, Qt.UserRole)
                if data and data.get("type") == "folder":
                    path = data.get("path")
                    if path and Path(path) in expanded_paths:
                        child.setExpanded(True)
                stack.append(child)

    # Public helpers for external callers

    def capture_expanded_state(self):
        return self._capture_expanded_state()

    def restore_expanded_state(self, expanded_paths):
        self._restore_expanded_state(expanded_paths)

    @staticmethod
    def _is_subpath(path: Path, potential_parent: Path) -> bool:
        try:
            resolved_path = path.resolve()
            resolved_parent = potential_parent.resolve()
        except (OSError, RuntimeError):
            return False

        try:
            resolved_path.relative_to(resolved_parent)
            return True
        except ValueError:
            return False

    # ----------------------------------------------------------- selection --

    def capture_selected_item(self) -> Optional[Path]:
        """Сохранить путь к выбранному тест-кейсу для восстановления после перезагрузки."""
        current = self.currentItem()
        if not current:
            return None
        
        data = current.data(0, Qt.UserRole)
        if data and data.get("type") == "file":
            test_case = data.get("test_case")
            if test_case:
                return getattr(test_case, "_filepath", None)
        return None

    def restore_selected_item(self, filepath: Optional[Path]):
        """Восстановить выбранный элемент по пути к файлу."""
        if not filepath:
            return
        
        item = self._find_item_by_filepath(self.invisibleRootItem(), filepath)
        if item:
            self.setCurrentItem(item)
            self.scrollToItem(item)
            # Не вызываем test_case_selected.emit, чтобы не перезагружать форму

    def _find_item_by_filepath(self, parent: QTreeWidgetItem, filepath: Path) -> Optional[QTreeWidgetItem]:
        """Найти элемент дерева по пути к файлу тест-кейса."""
        for i in range(parent.childCount()):
            child = parent.child(i)
            data = child.data(0, Qt.UserRole)
            if data and data.get("type") == "file":
                test_case = data.get("test_case")
                if test_case and getattr(test_case, "_filepath", None) == filepath:
                    return child

            found = self._find_item_by_filepath(child, filepath)
            if found:
                return found

        return None

    def focus_on_test_case(self, target: TestCase):
        """Выделить тест-кейс в дереве и инициировать открытие."""
        if not target:
            return

        filepath = getattr(target, "_filepath", None)
        item = self._find_item(self.invisibleRootItem(), target, filepath)
        if item:
            self.setCurrentItem(item)
            self.scrollToItem(item)
            self.test_case_selected.emit(target)

    def _find_item(self, parent: QTreeWidgetItem, target: TestCase, filepath: Optional[Path]):
        for i in range(parent.childCount()):
            child = parent.child(i)
            data = child.data(0, Qt.UserRole)
            if data and data.get("type") == "file":
                test_case = data.get("test_case")
                if test_case is target:
                    return child
                if filepath and getattr(test_case, "_filepath", None) == filepath:
                    return child

            found = self._find_item(child, target, filepath)
            if found:
                return found

        return None


