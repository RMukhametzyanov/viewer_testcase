"""Простой виджет дерева тест-кейсов."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

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

    test_case_selected = pyqtSignal(TestCase)
    tree_updated = pyqtSignal()
    review_requested = pyqtSignal(object)

    def __init__(self, service: TestCaseService, parent=None):
        super().__init__(parent)
        self.service = service
        self.test_cases_dir: Optional[Path] = None
        self._setup_ui()

    def _setup_ui(self):
        self.setHeaderHidden(True)
        self.setIndentation(20)
        self.setAnimated(True)
        self.setStyleSheet(
            """
            QTreeWidget {
                background-color: #17212B;
                border: none;
                border-radius: 8px;
                outline: 0;
                padding: 5px;
            }
            QTreeWidget::item {
                background-color: transparent;
                border: none;
                padding: 6px 8px;
                margin: 2px 0px;
                border-radius: 4px;
                color: #E1E3E6;
            }
            QTreeWidget::item:selected {
                background-color: #2B5278;
                color: #FFFFFF;
            }
            QTreeWidget::item:hover {
                background-color: #1E2732;
            }
            """
        )

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

    def _populate_directory(self, directory: Path, parent_item: QTreeWidgetItem, test_cases: list):
        for subdir in sorted([d for d in directory.iterdir() if d.is_dir()]):
            folder_item = QTreeWidgetItem(parent_item)
            folder_item.setText(0, f"📁 {subdir.name}")
            folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'path': subdir})
            folder_item.setFont(0, QFont("Segoe UI", 10, QFont.Bold))
            self._populate_directory(subdir, folder_item, test_cases)

        for test_case in test_cases:
            if test_case._filepath and test_case._filepath.parent == directory:
                icon = self._status_icon(test_case.status)
                color = self._status_color(test_case.status)

                item = QTreeWidgetItem(parent_item)
                item.setText(0, f"{icon} {test_case.title}")
                item.setData(0, Qt.UserRole, {'type': 'file', 'test_case': test_case})
                item.setFont(0, QFont("Segoe UI", 10))
                item.setForeground(0, QColor(color))

    @staticmethod
    def _status_icon(status: str) -> str:
        return {
            'Done': '✓',
            'Blocked': '⚠',
            'In Progress': '⟳',
            'Draft': '○',
            'Deprecated': '×',
        }.get(status, '○')

    @staticmethod
    def _status_color(status: str) -> str:
        return {
            'Done': '#6CC24A',
            'Blocked': '#F5555D',
            'In Progress': '#FFA931',
            'Draft': '#8B9099',
            'Deprecated': '#6B7380',
        }.get(status, '#E1E3E6')

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
        menu.setStyleSheet(self._menu_style())

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
        menu.setStyleSheet(self._menu_style())

        folder_path = folder_data['path']

        action_new_tc = menu.addAction("➕ Создать тест-кейс")
        action_new_tc.triggered.connect(lambda: self._create_test_case(folder_path))

        action_new_folder = menu.addAction("📁 Создать подпапку")
        action_new_folder.triggered.connect(lambda: self._create_folder(folder_path))

        menu.addSeparator()

        action_rename = menu.addAction("✏️ Переименовать")
        action_rename.triggered.connect(lambda: self._rename_folder(folder_path))

        action_delete = menu.addAction("🗑️ Удалить папку")
        action_delete.triggered.connect(lambda: self._delete_folder(folder_path))

        menu.addSeparator()

        action_open_explorer = menu.addAction("🪟 Открыть в проводнике")
        action_open_explorer.triggered.connect(lambda: self._open_in_explorer(folder_path, select=False))

        action_review = menu.addAction("📝 Ревью")
        action_review.triggered.connect(lambda: self.review_requested.emit(folder_data))

        menu.exec_(self.mapToGlobal(position))

    def _show_file_menu(self, position, file_data):
        menu = QMenu(self)
        menu.setStyleSheet(self._menu_style())

        test_case = file_data['test_case']

        action_open = menu.addAction("📂 Открыть")
        action_open.triggered.connect(lambda: self.test_case_selected.emit(test_case))

        action_open_explorer = menu.addAction("🪟 Открыть в проводнике")
        action_open_explorer.triggered.connect(
            lambda: self._open_in_explorer(test_case._filepath, select=True)
        )

        action_copy_info = menu.addAction("📋 Копировать информацию")
        action_copy_info.triggered.connect(lambda: self._copy_test_case_info(test_case))

        action_rename = menu.addAction("✏️ Переименовать файл")
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
        if not target_path:
            QMessageBox.warning(self, "Открытие проводника", "Путь к элементу не найден.")
            return

        if not target_path.exists():
            QMessageBox.warning(self, "Открытие проводника", "Файл или папка не найдены.")
            return

        try:
            if sys.platform.startswith("win"):
                if select and target_path.is_file():
                    subprocess.run(["explorer", f"/select,{str(target_path)}"], check=False)
                else:
                    subprocess.run(["explorer", str(target_path)], check=False)
            elif sys.platform == "darwin":
                if select and target_path.is_file():
                    subprocess.run(["open", "-R", str(target_path)], check=False)
                else:
                    subprocess.run(["open", str(target_path)], check=False)
            else:
                path_to_open = target_path if not select or target_path.is_dir() else target_path.parent
                subprocess.run(["xdg-open", str(path_to_open)], check=False)
        except Exception as exc:
            QMessageBox.critical(self, "Открытие проводника", f"Не удалось открыть проводник:\n{exc}")

    def _copy_test_case_info(self, test_case: TestCase):
        formatted = self._format_test_case_info(test_case)
        clipboard = QApplication.clipboard()
        clipboard.setText(formatted)
        QMessageBox.information(self, "Скопировано", "Информация по тест-кейсу скопирована в буфер обмена.")

    @staticmethod
    def _format_test_case_info(test_case: TestCase) -> str:
        tags = ", ".join(test_case.tags) if test_case.tags else "-"
        steps_lines = []
        for idx, step in enumerate(test_case.steps, start=1):
            action = step.step.strip() or "-"
            expected = step.expected_res.strip() or "-"
            steps_lines.append(f"{idx}. Действие:\n    {action}\n   Ожидаемый результат:\n    {expected}")
        steps_text = "\n\n".join(steps_lines) if steps_lines else "Шаги не заданы."

        labels_lines = []
        for label in test_case.labels:
            labels_lines.append(f"- {label.name}: {label.value}")
        labels_text = "\n".join(labels_lines) if labels_lines else "-"

        description = test_case.description.strip() or "-"
        precondition = test_case.precondition.strip() or "-"
        created = test_case.created_at or "-"
        updated = test_case.updated_at or "-"

        return (
            f"Тест-кейс: {test_case.title}\n"
            f"ID: {test_case.id or '-'}\n"
            f"Статус: {test_case.status}\n"
            f"Уровень: {test_case.level}\n"
            f"Автор: {test_case.author or '-'}\n"
            f"Теги: {tags}\n"
            f"Создан: {created}\n"
            f"Обновлён: {updated}\n"
            f"Предусловия:\n{precondition}\n\n"
            f"Описание:\n{description}\n\n"
            f"Метки:\n{labels_text}\n\n"
            f"Шаги:\n{steps_text}\n"
        )

    def _delete_test_case(self, test_case):
        expanded_paths = self._capture_expanded_state()
        if self.service.delete_test_case(test_case):
            self.tree_updated.emit()
            self._restore_expanded_state(expanded_paths)

    # ---------------------------------------------------------------- style --

    @staticmethod
    def _menu_style() -> str:
        return (
            """
            QMenu {
                background-color: #1E2732;
                border: 1px solid #2B3945;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 30px 8px 20px;
                border-radius: 4px;
                color: #E1E3E6;
                transition: background 120ms ease;
            }
            QMenu::item:hover {
                background-color: #3D6A98;
                color: #FFFFFF;
            }
            QMenu::item:selected {
                background-color: #2B5278;
                color: #FFFFFF;
                border: 1px solid #5E9BE3;
                padding-left: 24px;
            }
            QMenu::item:pressed {
                background-color: #1D3F5F;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2B3945;
                margin: 5px 10px;
            }
            """
        )

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


