"""Простой виджет дерева тест-кейсов."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Dict

from PyQt5.QtWidgets import (
    QApplication,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QMenu,
    QInputDialog,
    QAbstractItemView,
    QDialog,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QDialogButtonBox,
    QWidget,
    QStyle,
)
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData, QByteArray, QSize, QPoint, QTimer
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QPen, QMouseEvent, QBrush
from PyQt5.QtSvg import QSvgRenderer

from ...services.test_case_service import TestCaseService
from ...models.test_case import TestCase


class ContextMenu(QMenu):
    """Кастомное контекстное меню, которое срабатывает только по ЛКМ"""
    
    def mousePressEvent(self, event: QMouseEvent):
        """Переопределяем обработку нажатия мыши - только ЛКМ активирует действия"""
        if event.button() == Qt.LeftButton:
            super().mousePressEvent(event)
        elif event.button() == Qt.RightButton:
            # ПКМ просто закрывает меню без активации действия
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Переопределяем обработку отпускания мыши - только ЛКМ активирует действия"""
        if event.button() == Qt.LeftButton:
            super().mouseReleaseEvent(event)
        elif event.button() == Qt.RightButton:
            # ПКМ просто закрывает меню без активации действия
            event.accept()
        else:
            super().mouseReleaseEvent(event)


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
    test_cases_updated = pyqtSignal()  # Сигнал для обновления тест-кейсов после изменения статусов
    add_to_review_requested = pyqtSignal(TestCase)  # Сигнал для добавления файла в панель ревью

    def __init__(self, service: TestCaseService, parent=None):
        super().__init__(parent)
        self.service = service
        self.test_cases_dir: Optional[Path] = None
        self._edit_mode = True  # По умолчанию режим редактирования
        self._skip_reasons: List[str] = ['Автотесты', 'Нагрузочное тестирование', 'Другое']  # Значения по умолчанию
        self._show_folder_counters = False  # По умолчанию счетчики выключены
        
        # Загружаем маппинг иконок
        self._icon_mapping = self._load_icon_mapping()
        
        self._setup_ui()
    
    def set_skip_reasons(self, reasons: List[str]):
        """Установить список причин пропуска из настроек"""
        if reasons and isinstance(reasons, list):
            self._skip_reasons = reasons
    
    def set_show_folder_counters(self, show: bool):
        """Установить отображение счетчиков JSON файлов в папках"""
        if self._show_folder_counters != show:
            self._show_folder_counters = show
            # Обновляем дерево, чтобы применить изменения
            if self.test_cases_dir:
                # Сохраняем состояние развернутых папок
                expanded_paths = self._capture_expanded_state()
                # Перезагружаем дерево
                test_cases = self.service.load_all_test_cases(self.test_cases_dir)
                self.load_tree(self.test_cases_dir, test_cases)
                # Восстанавливаем состояние
                self._restore_expanded_state(expanded_paths)

    def _setup_ui(self):
        self.setHeaderHidden(True)
        self.setIndentation(20)
        self.setAnimated(True)
        
        # Включаем множественный выбор (Ctrl на Windows/Linux, Cmd на macOS)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.itemClicked.connect(self._on_item_clicked)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        
        # Кэш для цветных иконок кружков
        self._icon_cache = {}
        
        # Для визуальной подсветки при drag & drop
        self._drag_over_item: Optional[QTreeWidgetItem] = None
        self._original_background: Optional[QBrush] = None
        
        # Таймер для автоматического разворачивания папок при drag & drop
        self._expand_timer = QTimer(self)
        self._expand_timer.setSingleShot(True)
        self._expand_timer.timeout.connect(self._auto_expand_folder)
        self._expand_target_item: Optional[QTreeWidgetItem] = None
        
        # Таймер для плавной автоскролли при drag & drop
        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._perform_smooth_scroll)
        self._scroll_direction = 0  # -1 для вверх, 1 для вниз, 0 для остановки
    
    def drawRow(self, painter: QPainter, option, index):
        """Переопределяем отрисовку строки для добавления подсветки при drag & drop"""
        # Получаем элемент
        item = self.itemFromIndex(index)
        
        # Если это элемент с подсветкой drag & drop, рисуем фон ПЕРЕД стандартной отрисовкой
        if item == self._drag_over_item:
            # Сохраняем состояние painter
            painter.save()
            
            # Используем более яркий и заметный цвет для подсветки
            highlight_color = QColor(100, 150, 255, 180)  # Полупрозрачный синий
            highlight_brush = QBrush(highlight_color)
            
            # Рисуем фон на всю ширину строки
            rect = option.rect
            # Расширяем прямоугольник на всю ширину виджета для лучшей видимости
            full_rect = rect
            full_rect.setLeft(0)
            full_rect.setRight(self.viewport().width())
            
            painter.fillRect(full_rect, highlight_brush)
            
            # Восстанавливаем состояние painter
            painter.restore()
        
        # Вызываем стандартную отрисовку поверх фона
        super().drawRow(painter, option, index)

    def _load_icon_mapping(self) -> Dict[str, Dict[str, str]]:
        """Загрузить маппинг иконок из JSON файла."""
        # Определяем путь к файлу маппинга относительно корня проекта
        project_root = Path(__file__).parent.parent.parent.parent
        mapping_file = project_root / "icons" / "icon_mapping.json"
        
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Поддерживаем как старый формат (плоский), так и новый (с секциями)
                    if isinstance(data, dict) and any(key in data for key in ['panels', 'context_menu', 'status_icons']):
                        return data
                    else:
                        # Старый формат - возвращаем с секциями
                        return {
                            'panels': data,
                            'context_menu': {},
                            'status_icons': {}
                        }
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка загрузки маппинга иконок: {e}")
        
        # Возвращаем значения по умолчанию, если файл не найден
        return {
            'panels': {
                "information": "info.svg",
                "review": "eye.svg",
                "creation": "file-plus.svg",
                "json": "code.svg",
                "files": "file.svg",
                "reports": "book.svg"
            },
            'context_menu': {
                "open_explorer": "external-link.svg",
                "copy_info": "clipboard.svg",
                "generate_api": "code.svg",
                "rename": "edit.svg",
                "duplicate": "copy.svg",
                "delete": "x.svg",
                "create_test_case": "file-plus.svg",
                "create_folder": "folder-plus.svg"
            },
            'status_icons': {
                "passed": "check-circle.svg",
                "failed": "x-circle.svg",
                "skipped": "skip-forward.svg"
            }
        }

    def _get_context_menu_icon(self, icon_key: str) -> Optional[str]:
        """Получить имя файла иконки для контекстного меню по ключу."""
        context_menu_mapping = self._icon_mapping.get('context_menu', {})
        return context_menu_mapping.get(icon_key)

    def _get_status_icon(self, status: str) -> Optional[str]:
        """Получить имя файла иконки для статуса по ключу."""
        status_icons_mapping = self._icon_mapping.get('status_icons', {})
        return status_icons_mapping.get(status)

    def _load_svg_icon(self, icon_name: str, size: int = 16, color: Optional[str] = None) -> Optional[QIcon]:
        """Загрузить SVG иконку из файла и вернуть QIcon.
        
        Args:
            icon_name: Имя файла иконки (например, "info.svg")
            size: Размер иконки в пикселях
            color: Цвет иконки в формате "#RRGGBB" или None для использования цвета по умолчанию
        """
        # Определяем путь к папке с иконками относительно корня проекта
        project_root = Path(__file__).parent.parent.parent.parent
        icon_path = project_root / "icons" / icon_name
        
        if not icon_path.exists():
            print(f"Иконка не найдена: {icon_path}")
            return None
        
        try:
            # Читаем содержимое SVG файла
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # Если указан цвет, заменяем currentColor на конкретный цвет
            if color:
                svg_content = svg_content.replace('currentColor', color)
                svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{color}"')
                svg_content = svg_content.replace('fill="currentColor"', f'fill="{color}"')
            
            # Создаем рендерер SVG из модифицированного содержимого
            renderer = QSvgRenderer(svg_content.encode('utf-8'))
            if not renderer.isValid():
                print(f"Невалидный SVG файл: {icon_path}")
                return None
            
            # Создаем пиксмап нужного размера
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            # Рендерим SVG на пиксмап
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            renderer.render(painter)
            painter.end()
            
            # Создаем иконку из пиксмапа
            icon = QIcon(pixmap)
            return icon
        except Exception as e:
            print(f"Ошибка загрузки иконки {icon_name}: {e}")
            return None

    # ------------------------------------------------------------------ load

    def load_tree(self, test_cases_dir: Path, test_cases: list):
        self.test_cases_dir = test_cases_dir
        self.clear()

        # Если путь пустой или не существует, оставляем дерево пустым
        if not test_cases_dir or str(test_cases_dir).strip() == "" or not test_cases_dir.exists():
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
                        if not self._edit_mode:
                            # В режиме запуска тестов показываем цветные кружки
                            icon, color = self._get_test_case_icon_and_color(test_case)
                            child.setText(0, test_case.name)
                            if icon:
                                child.setIcon(0, icon)
                            else:
                                child.setIcon(0, QIcon())  # Пустая иконка
                        else:
                            # В режиме редактирования показываем пустые кружки для элементов с неполными статусами
                            child.setText(0, test_case.name)
                            icon = self._get_edit_mode_icon(test_case)
                            child.setIcon(0, icon)
                elif data.get('type') == 'folder':
                    # Обновляем отображение папки
                    folder_path = data.get('path')
                    if folder_path:
                        # Формируем текст папки с учетом счетчика
                        folder_name = folder_path.name
                        if self._show_folder_counters:
                            json_count = self._count_json_files_in_folder(folder_path)
                            # Показываем счетчик только если количество больше 0
                            if json_count > 0:
                                folder_name = f"{folder_path.name} ({json_count})"
                        
                        child.setText(0, f"📁 {folder_name}")
                        if not self._edit_mode:
                            # Пересчитываем статус папки на основе дерева
                            folder_icon, folder_color = self._calculate_folder_status_from_tree(child)
                            data['icon'] = folder_icon
                            data['color'] = folder_color
                            if folder_icon:
                                child.setIcon(0, folder_icon)
                            else:
                                child.setIcon(0, QIcon())  # Пустая иконка
                        else:
                            child.setIcon(0, QIcon())  # Пустая иконка в режиме редактирования
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

    def _count_json_files_in_folder(self, folder_path: Path) -> int:
        """Подсчитать количество JSON файлов непосредственно в папке (без подпапок).
        
        Args:
            folder_path: Путь к папке
            
        Returns:
            int: Количество JSON файлов в папке
        """
        if not folder_path.exists() or not folder_path.is_dir():
            return 0
        
        count = 0
        for item in folder_path.iterdir():
            if item.is_file() and item.suffix.lower() == '.json':
                count += 1
        
        return count
    
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
                folder_icon, folder_color = None, ""
            
            # Формируем текст папки с учетом счетчика
            folder_name = subdir.name
            if self._show_folder_counters:
                json_count = self._count_json_files_in_folder(subdir)
                # Показываем счетчик только если количество больше 0
                if json_count > 0:
                    folder_name = f"{subdir.name} ({json_count})"
            
            # Устанавливаем текст и иконку
            folder_item.setText(0, f"📁 {folder_name}")
            if folder_icon:
                folder_item.setIcon(0, folder_icon)
            else:
                folder_item.setIcon(0, QIcon())  # Пустая иконка
            folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'path': subdir, 'icon': folder_icon, 'color': folder_color})
            folder_item.setFont(0, QFont("Segoe UI", 10, QFont.Bold))
            self._populate_directory(subdir, folder_item, test_cases)

        for test_case in test_cases:
            if test_case._filepath and test_case._filepath.parent == directory:
                # В режиме редактирования иконки не показываем
                if not self._edit_mode:
                    icon, color = self._get_test_case_icon_and_color(test_case)
                else:
                    # В режиме редактирования показываем пустые кружки для элементов с неполными статусами
                    icon = self._get_edit_mode_icon(test_case)
                    color = ""
                
                item = QTreeWidgetItem(parent_item)
                # Устанавливаем текст и иконку
                item.setText(0, test_case.name)
                if icon:
                    item.setIcon(0, icon)
                else:
                    item.setIcon(0, QIcon())  # Пустая иконка
                item.setData(0, Qt.UserRole, {'type': 'file', 'test_case': test_case})
                item.setFont(0, QFont("Segoe UI", 10))

    def _create_colored_circle_icon(self, color: str, size: int = 12) -> QIcon:
        """
        Создать иконку с цветным кружком.
        
        Args:
            color: Цвет в формате hex (например, '#6CC24A')
            size: Размер иконки в пикселях
            
        Returns:
            QIcon с цветным кружком
        """
        # Используем кэш для оптимизации
        cache_key = f"{color}_{size}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        # Рисуем кружок с небольшими отступами для лучшего вида
        margin = 2
        painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
        painter.end()
        
        icon = QIcon(pixmap)
        self._icon_cache[cache_key] = icon
        return icon
    
    def _get_test_case_icon_and_color(self, test_case) -> Tuple[Optional[QIcon], str]:
        """
        Определить иконку и цвет для тест-кейса на основе статусов шагов.
        
        Returns:
            tuple: (icon, color) где icon - QIcon или None, color - цвет в формате hex
        """
        if not test_case or not test_case.steps:
            # Если нет шагов, возвращаем None (без иконки)
            return (None, '#8B9099')
        
        steps = test_case.steps
        if not steps:
            return (None, '#8B9099')
        
        # Получаем статусы всех шагов (включая пустые)
        step_statuses = [(step.status or "").strip().lower() for step in steps]
        
        # Проверяем наличие failed (приоритет 1)
        has_failed = any(s == "failed" for s in step_statuses)
        if has_failed:
            return (self._create_colored_circle_icon('#F5555D'), '#F5555D')  # Красный залитый кружок
        
        # Проверяем наличие skipped (приоритет 2)
        has_skipped = any(s == "skipped" for s in step_statuses)
        if has_skipped:
            return (self._create_colored_circle_icon('#95a5a6'), '#95a5a6')  # Серый залитый кружок
        
        # Проверяем, все ли шаги имеют статус "passed"
        # Все шаги должны иметь непустой статус и все должны быть "passed"
        all_have_status = all(s for s in step_statuses)  # Все статусы непустые
        all_passed = all(s == "passed" for s in step_statuses)  # Все статусы равны "passed"
        
        if all_have_status and all_passed:
            return (self._create_colored_circle_icon('#6CC24A'), '#6CC24A')  # Зеленый залитый кружок
        
        # Не все шаги имеют статус и нет failed/skipped - пустой кружок с серой обводкой
        return (self._create_empty_circle_with_gray_border(), '#8B9099')
    
    def _create_empty_circle_with_gray_border(self, size: int = 12) -> QIcon:
        """
        Создать иконку пустого кружка без заливки с серой обводкой.
        Используется для тест-кейсов, где не все шаги имеют статус.
        
        Args:
            size: Размер иконки в пикселях
        
        Returns:
            QIcon: Иконка пустого кружка с серой обводкой
        """
        try:
            # Используем кэш для оптимизации
            cache_key = f"empty_gray_border_{size}"
            if cache_key in self._icon_cache:
                return self._icon_cache[cache_key]
            
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Рисуем только серую обводку (без заливки)
            margin = 2
            pen = QPen(QColor('#8B9099'))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)  # Без заливки
            painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
            
            painter.end()
            
            icon = QIcon(pixmap)
            self._icon_cache[cache_key] = icon
            return icon
        except Exception as e:
            print(f"Ошибка создания пустого кружка с серой обводкой: {e}")
            return QIcon()
    
    def _create_empty_circle_icon(self, color: str = "#8B9099", size: int = 12) -> QIcon:
        """
        Создать иконку пустого (незаполненного) кружка.
        
        Args:
            color: Цвет обводки кружка в формате hex
            size: Размер иконки в пикселях
        
        Returns:
            QIcon: Иконка пустого кружка
        """
        try:
            # Используем кэш для оптимизации
            cache_key = f"empty_{color}_{size}"
            if cache_key in self._icon_cache:
                return self._icon_cache[cache_key]
            
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Рисуем только обводку (пустой кружок)
            pen = QPen(QColor(color))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)  # Без заливки
            
            # Отступ для обводки
            margin = 2
            painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
            
            painter.end()
            
            icon = QIcon(pixmap)
            self._icon_cache[cache_key] = icon
            return icon
        except Exception as e:
            print(f"Ошибка создания пустого кружка: {e}")
            return QIcon()
    
    def _get_edit_mode_icon(self, test_case) -> QIcon:
        """
        Получить иконку для тест-кейса в режиме редактирования.
        Показывает пустой кружок, если не все шаги имеют статусы.
        
        Returns:
            QIcon: Иконка пустого кружка или пустая иконка
        """
        if not test_case or not test_case.steps:
            # Если нет шагов, возвращаем пустую иконку
            return QIcon()
        
        steps = test_case.steps
        if not steps:
            return QIcon()
        
        # Получаем статусы всех шагов (включая пустые)
        step_statuses = [(step.status or "").strip().lower() for step in steps]
        
        # Проверяем, все ли шаги имеют статус
        all_have_status = all(s for s in step_statuses)  # Все статусы непустые
        
        if not all_have_status:
            # Не все шаги имеют статус - показываем пустой кружок
            return self._create_empty_circle_icon("#8B9099", 12)
        
        # Все шаги имеют статус - не показываем иконку
        return QIcon()
    
    @staticmethod
    def _status_icon(status: str) -> str:
        """Устаревший метод, оставлен для совместимости"""
        return {
            'Done': '✓',
            'Review': '👁',
            'Design': '⟳',
            'Draft': '○',
        }.get(status, '○')

    @staticmethod
    def _status_color(status: str) -> str:
        """Устаревший метод, оставлен для совместимости"""
        return {
            'Done': '#6CC24A',
            'Review': '#4A90E2',
            'Design': '#FFA931',
            'Draft': '#8B9099',
        }.get(status, '#E1E3E6')
    
    def _calculate_folder_status(self, folder_path: Path, test_cases: list) -> Tuple[Optional[QIcon], str]:
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
            return (None, '#8B9099')  # Если нет тест-кейсов, без иконки
        
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
            return (None, '#8B9099')  # Нет шагов
        
        # Проверяем наличие failed (приоритет 1)
        has_failed = any(s == "failed" for s in all_step_statuses)
        if has_failed:
            return (self._create_colored_circle_icon('#F5555D'), '#F5555D')  # Красный залитый кружок
        
        # Проверяем наличие skipped (приоритет 2)
        has_skipped = any(s == "skipped" for s in all_step_statuses)
        if has_skipped:
            return (self._create_colored_circle_icon('#95a5a6'), '#95a5a6')  # Серый залитый кружок
        
        # Проверяем, все ли шаги имеют статус "passed"
        all_have_status = all(s for s in all_step_statuses)  # Все статусы непустые
        all_passed = all(s == "passed" for s in all_step_statuses)  # Все статусы равны "passed"
        
        if all_have_status and all_passed:
            return (self._create_colored_circle_icon('#6CC24A'), '#6CC24A')  # Зеленый залитый кружок
        
        # Не все шаги имеют статус и нет failed/skipped - пустой кружок с серой обводкой
        return (self._create_empty_circle_with_gray_border(), '#8B9099')
    
    def _calculate_folder_status_from_tree(self, folder_item: QTreeWidgetItem) -> Tuple[Optional[QIcon], str]:
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
            return (None, '#8B9099')  # Нет шагов
        
        # Проверяем наличие failed (приоритет 1)
        has_failed = any(s == "failed" for s in all_step_statuses)
        if has_failed:
            return (self._create_colored_circle_icon('#F5555D'), '#F5555D')  # Красный залитый кружок
        
        # Проверяем наличие skipped (приоритет 2)
        has_skipped = any(s == "skipped" for s in all_step_statuses)
        if has_skipped:
            return (self._create_colored_circle_icon('#95a5a6'), '#95a5a6')  # Серый залитый кружок
        
        # Проверяем, все ли шаги имеют статус "passed"
        all_have_status = all(s for s in all_step_statuses)  # Все статусы непустые
        all_passed = all(s == "passed" for s in all_step_statuses)  # Все статусы равны "passed"
        
        if all_have_status and all_passed:
            return (self._create_colored_circle_icon('#6CC24A'), '#6CC24A')  # Зеленый залитый кружок
        
        # Не все шаги имеют статус и нет failed/skipped - пустой кружок с серой обводкой
        return (self._create_empty_circle_with_gray_border(), '#8B9099')

    # ----------------------------------------------------------- interactions

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        # При множественном выборе не открываем тест-кейс
        selected_items = self.selectedItems()
        if len(selected_items) > 1:
            return
        
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

        # Получаем все выделенные элементы
        selected_items = self.selectedItems()
        
        # Проверяем, есть ли множественный выбор файлов
        selected_files = []
        selected_folders = []
        for selected_item in selected_items:
            data = selected_item.data(0, Qt.UserRole)
            if not data:
                continue
            if data.get('type') == 'file':
                test_case = data.get('test_case')
                if test_case:
                    selected_files.append(test_case)
            elif data.get('type') == 'folder':
                selected_folders.append(data)
        
        # Если выделено несколько файлов, показываем меню для множественного выбора
        if len(selected_files) > 1:
            self._show_multiple_files_menu(position, selected_files)
            return
        
        # Если выделена папка и файлы, или только папка
        if selected_folders:
            # Показываем меню для первой папки (или можно сделать общее меню)
            self._show_folder_menu(position, selected_folders[0])
            return
        
        # Одиночный выбор - используем старую логику
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        if data.get('type') == 'folder':
            self._show_folder_menu(position, data)
        elif data.get('type') == 'file':
            self._show_file_menu(position, data)

    # ------------------------------------------------------------ menus

    def _show_root_menu(self, position):
        menu = ContextMenu(self)

        icon_name = self._get_context_menu_icon("create_test_case")
        if icon_name:
            icon_create = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            action_new_tc = menu.addAction(icon_create, "Создать тест-кейс")
        else:
            action_new_tc = menu.addAction("Создать тест-кейс")
        action_new_tc.triggered.connect(lambda: self._create_test_case(self.test_cases_dir))

        menu.addSeparator()

        icon_name = self._get_context_menu_icon("create_folder")
        if icon_name:
            icon_create = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            action_new_folder = menu.addAction(icon_create, "Создать папку")
        else:
            action_new_folder = menu.addAction("Создать папку")
        action_new_folder.triggered.connect(lambda: self._create_folder(self.test_cases_dir))

        menu.exec_(self.mapToGlobal(position))

    def _show_folder_menu(self, position, folder_data):
        menu = ContextMenu(self)

        folder_path = folder_data['path']
        
        # В режиме запуска тестов показываем упрощенное меню
        if not self._edit_mode:
            icon_name = self._get_status_icon("passed")
            if icon_name:
                icon_passed = self._load_svg_icon(icon_name, size=16, color="#2ecc71")
                action_mark_passed = menu.addAction(icon_passed, "Пометить как passed")
            else:
                action_mark_passed = menu.addAction("Пометить как passed")
            action_mark_passed.triggered.connect(lambda: self._mark_folder_passed(folder_path))
            
            icon_name = self._get_status_icon("skipped")
            if icon_name:
                icon_skipped = self._load_svg_icon(icon_name, size=16, color="#95a5a6")
                action_mark_skipped = menu.addAction(icon_skipped, "Пометить как skipped")
            else:
                action_mark_skipped = menu.addAction("Пометить как skipped")
            action_mark_skipped.triggered.connect(lambda: self._mark_folder_skipped(folder_path))
        else:
            # В режиме редактирования показываем полное меню
            icon_name = self._get_context_menu_icon("create_test_case")
            if icon_name:
                icon_create = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                action_new_tc = menu.addAction(icon_create, "Создать тест-кейс")
            else:
                action_new_tc = menu.addAction("Создать тест-кейс")
            action_new_tc.triggered.connect(lambda: self._create_test_case(folder_path))

            icon_name = self._get_context_menu_icon("create_folder")
            if icon_name:
                icon_create = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                action_new_folder = menu.addAction(icon_create, "Создать папку")
            else:
                action_new_folder = menu.addAction("Создать папку")
            action_new_folder.triggered.connect(lambda: self._create_folder(folder_path))

            menu.addSeparator()

            icon_name = self._get_context_menu_icon("rename")
            if icon_name:
                icon_edit = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                action_rename = menu.addAction(icon_edit, "Переименовать")
            else:
                action_rename = menu.addAction("Переименовать")
            action_rename.triggered.connect(lambda: self._rename_folder(folder_path))

            icon_name = self._get_context_menu_icon("delete")
            if icon_name:
                icon_x = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                action_delete = menu.addAction(icon_x, "Удалить папку")
            else:
                action_delete = menu.addAction("Удалить папку")
            action_delete.triggered.connect(lambda: self._delete_folder(folder_path))

            menu.addSeparator()

            icon_name = self._get_context_menu_icon("open_explorer")
            if icon_name:
                icon_explorer = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                action_open_explorer = menu.addAction(icon_explorer, "Открыть в проводнике")
            else:
                action_open_explorer = menu.addAction("Открыть в проводнике")
            action_open_explorer.triggered.connect(lambda: self._open_in_explorer(folder_path, select=False))

        menu.exec_(self.mapToGlobal(position))

    def _show_multiple_files_menu(self, position, test_cases: List[TestCase]):
        """Показать контекстное меню для множественного выбора файлов"""
        try:
            menu = ContextMenu(self)
            
            # Добавить в панель ревью
            icon_name = self._get_context_menu_icon("add_to_review")
            if icon_name:
                icon_add = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                action_add_to_review = menu.addAction(icon_add, f"Добавить в панель ревью ({len(test_cases)})")
            else:
                action_add_to_review = menu.addAction(f"Добавить в панель ревью ({len(test_cases)})")
            action_add_to_review.triggered.connect(lambda: self._add_multiple_to_review(test_cases))
            
            menu.addSeparator()
            
            # Удалить
            icon_name = self._get_context_menu_icon("delete")
            if icon_name:
                icon_x = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                action_delete = menu.addAction(icon_x, f"Удалить ({len(test_cases)})")
            else:
                action_delete = menu.addAction(f"Удалить ({len(test_cases)})")
            action_delete.triggered.connect(lambda: self._delete_multiple_test_cases(test_cases))
            
            menu.exec_(self.mapToGlobal(position))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при отображении контекстного меню: {str(e)}")
    
    def _show_file_menu(self, position, file_data):
        try:
            menu = ContextMenu(self)

            test_case = file_data.get('test_case')
            if not test_case:
                return
            
            # В режиме запуска тестов показываем упрощенное меню
            if not self._edit_mode:
                icon_name = self._get_context_menu_icon("copy_info")
                if icon_name:
                    icon_clipboard = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                    action_copy_info = menu.addAction(icon_clipboard, "Копировать информацию")
                else:
                    action_copy_info = menu.addAction("Копировать информацию")
                action_copy_info.triggered.connect(lambda: self._copy_test_case_info(test_case))
                
                menu.addSeparator()
                
                icon_name = self._get_status_icon("passed")
                if icon_name:
                    icon_passed = self._load_svg_icon(icon_name, size=16, color="#2ecc71")
                    action_mark_passed = menu.addAction(icon_passed, "Пометить как passed")
                else:
                    action_mark_passed = menu.addAction("Пометить как passed")
                action_mark_passed.triggered.connect(lambda: self._mark_test_case_passed(test_case))
                
                icon_name = self._get_status_icon("skipped")
                if icon_name:
                    icon_skipped = self._load_svg_icon(icon_name, size=16, color="#95a5a6")
                    action_mark_skipped = menu.addAction(icon_skipped, "Пометить как skipped")
                else:
                    action_mark_skipped = menu.addAction("Пометить как skipped")
                action_mark_skipped.triggered.connect(lambda: self._mark_test_case_skipped(test_case))
            else:
                # В режиме редактирования показываем полное меню
                icon_name = self._get_context_menu_icon("open_explorer")
                if icon_name:
                    icon_explorer = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                    action_open_explorer = menu.addAction(icon_explorer, "Открыть в проводнике")
                else:
                    action_open_explorer = menu.addAction("Открыть в проводнике")
                action_open_explorer.triggered.connect(
                    lambda: self._open_in_explorer(test_case._filepath, select=True)
                )

                icon_name = self._get_context_menu_icon("copy_info")
                if icon_name:
                    icon_clipboard = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                    action_copy_info = menu.addAction(icon_clipboard, "Копировать информацию")
                else:
                    action_copy_info = menu.addAction("Копировать информацию")
                action_copy_info.triggered.connect(lambda: self._copy_test_case_info(test_case))

                icon_name = self._get_context_menu_icon("generate_api")
                if icon_name:
                    icon_code = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                    action_generate_api = menu.addAction(icon_code, "Сгенерировать каркас АТ API")
                else:
                    action_generate_api = menu.addAction("Сгенерировать каркас АТ API")
                action_generate_api.triggered.connect(lambda: self._copy_pytest_skeleton(test_case))

                icon_name = self._get_context_menu_icon("rename")
                if icon_name:
                    icon_edit = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                    action_rename = menu.addAction(icon_edit, "Переименовать файл")
                else:
                    action_rename = menu.addAction("Переименовать файл")
                action_rename.triggered.connect(lambda: self._rename_file(test_case))

                icon_name = self._get_context_menu_icon("duplicate")
                if icon_name:
                    icon_copy = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                    action_duplicate = menu.addAction(icon_copy, "Дублировать")
                else:
                    action_duplicate = menu.addAction("Дублировать")
                action_duplicate.triggered.connect(lambda: self._duplicate_test_case(test_case))

                menu.addSeparator()

                icon_name = self._get_context_menu_icon("delete")
                if icon_name:
                    icon_x = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                    action_delete = menu.addAction(icon_x, "Удалить")
                else:
                    action_delete = menu.addAction("Удалить")
                action_delete.triggered.connect(lambda: self._delete_test_case(test_case))

                menu.addSeparator()

                # Добавить в панель ревью
                icon_name = self._get_context_menu_icon("add_to_review")
                if icon_name:
                    icon_add = self._load_svg_icon(icon_name, size=16, color="#ffffff")
                    action_add_to_review = menu.addAction(icon_add, "Добавить в панель ревью")
                else:
                    action_add_to_review = menu.addAction("Добавить в панель ревью")
                action_add_to_review.triggered.connect(lambda: self.add_to_review_requested.emit(test_case))

            menu.exec_(self.mapToGlobal(position))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при отображении контекстного меню: {str(e)}")

    # ------------------------------------------------------- actions

    class FolderNameDialog(QDialog):
        """Диалог для ввода имени папки с валидацией"""
        
        def __init__(self, parent=None, title: str = "Имя папки", initial_text: str = ""):
            super().__init__(parent)
            self.setWindowTitle(title)
            self.setMinimumWidth(500)
            self.setMinimumHeight(150)
            self._setup_ui(initial_text)
        
        def _setup_ui(self, initial_text: str):
            layout = QVBoxLayout(self)
            
            # Метка с подсказкой
            hint_label = QLabel("Имя файла не должно содержать следующих знаков: \\ / : * ? \" < > |")
            hint_label.setWordWrap(True)
            hint_label.setStyleSheet("color: #666; font-size: 10pt;")
            layout.addWidget(hint_label)
            
            # Поле ввода
            label = QLabel("Введите имя папки:")
            layout.addWidget(label)
            
            self.name_edit = QLineEdit(initial_text)
            self.name_edit.selectAll()  # Выделяем весь текст для удобства редактирования
            self.name_edit.textChanged.connect(self._on_text_changed)
            layout.addWidget(self.name_edit)
            
            # Метка для отображения ошибки валидации
            self.error_label = QLabel()
            self.error_label.setWordWrap(True)
            self.error_label.setStyleSheet("color: #d32f2f; font-size: 9pt;")
            self.error_label.setVisible(False)
            layout.addWidget(self.error_label)
            
            # Кнопки
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(self._on_accept)
            button_box.rejected.connect(self.reject)
            self.ok_button = button_box.button(QDialogButtonBox.Ok)
            layout.addWidget(button_box)
            
            # Устанавливаем фокус на поле ввода
            self.name_edit.setFocus()
        
        def _on_text_changed(self, text: str):
            """Обработчик изменения текста - скрываем ошибку при вводе"""
            self.error_label.setVisible(False)
        
        def _on_accept(self):
            """Обработчик нажатия кнопки OK - проверяем валидность"""
            name = self.name_edit.text().strip()
            if not name:
                self.error_label.setText("Имя папки не может быть пустым")
                self.error_label.setVisible(True)
                return
            
            # Проверяем на запрещенные символы
            is_valid, found_chars = TestCaseTreeWidget._validate_folder_name(name)
            if not is_valid:
                self.error_label.setText("Имя файла не должно содержать следующих знаков: \\ / : * ? \" < > |")
                self.error_label.setVisible(True)
                return
            
            # Если все в порядке, принимаем диалог
            self.accept()
        
        def get_name(self) -> str:
            """Получить введенное имя папки"""
            return self.name_edit.text().strip()

    class FileNameDialog(QDialog):
        """Диалог для ввода имени файла с валидацией"""
        
        def __init__(self, parent=None, title: str = "Имя файла", initial_text: str = ""):
            super().__init__(parent)
            self.setWindowTitle(title)
            self.setMinimumWidth(500)
            self.setMinimumHeight(150)
            self._setup_ui(initial_text)
        
        def _setup_ui(self, initial_text: str):
            layout = QVBoxLayout(self)
            
            # Метка с подсказкой
            hint_label = QLabel("Имя файла не должно содержать следующих знаков: \\ / : * ? \" < > |")
            hint_label.setWordWrap(True)
            hint_label.setStyleSheet("color: #666; font-size: 10pt;")
            layout.addWidget(hint_label)
            
            # Поле ввода
            label = QLabel("Введите имя файла:")
            layout.addWidget(label)
            
            self.name_edit = QLineEdit(initial_text)
            self.name_edit.selectAll()  # Выделяем весь текст для удобства редактирования
            self.name_edit.textChanged.connect(self._on_text_changed)
            layout.addWidget(self.name_edit)
            
            # Метка для отображения ошибки валидации
            self.error_label = QLabel()
            self.error_label.setWordWrap(True)
            self.error_label.setStyleSheet("color: #d32f2f; font-size: 9pt;")
            self.error_label.setVisible(False)
            layout.addWidget(self.error_label)
            
            # Кнопки
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(self._on_accept)
            button_box.rejected.connect(self.reject)
            self.ok_button = button_box.button(QDialogButtonBox.Ok)
            layout.addWidget(button_box)
            
            # Устанавливаем фокус на поле ввода
            self.name_edit.setFocus()
        
        def _on_text_changed(self, text: str):
            """Обработчик изменения текста - скрываем ошибку при вводе"""
            self.error_label.setVisible(False)
        
        def _on_accept(self):
            """Обработчик нажатия кнопки OK - проверяем валидность"""
            name = self.name_edit.text().strip()
            if not name:
                self.error_label.setText("Имя файла не может быть пустым")
                self.error_label.setVisible(True)
                return
            
            # Убираем расширение .json для валидации (если есть)
            name_without_ext = name
            if name_without_ext.endswith('.json'):
                name_without_ext = name_without_ext[:-5]
            
            # Проверяем на запрещенные символы (без расширения)
            is_valid, found_chars = TestCaseTreeWidget._validate_folder_name(name_without_ext)
            if not is_valid:
                self.error_label.setText("Имя файла не должно содержать следующих знаков: \\ / : * ? \" < > |")
                self.error_label.setVisible(True)
                return
            
            # Если все в порядке, принимаем диалог
            self.accept()
        
        def get_name(self) -> str:
            """Получить введенное имя файла"""
            return self.name_edit.text().strip()

    @staticmethod
    def _validate_folder_name(name: str) -> Tuple[bool, Optional[str]]:
        """Проверить имя папки на наличие запрещенных символов.
        
        Args:
            name: Имя папки для проверки
            
        Returns:
            Tuple[bool, Optional[str]]: (валидно, список запрещенных символов)
        """
        if not name:
            return False, None
        
        # Запрещенные символы для имен файлов/папок в Windows
        forbidden_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        found_chars = [char for char in forbidden_chars if char in name]
        
        if found_chars:
            return False, ' '.join(found_chars)
        return True, None

    def _create_test_case(self, target_folder):
        expanded_paths = self._capture_expanded_state()
        test_case = self.service.create_new_test_case(target_folder)
        if test_case:
            self.tree_updated.emit()
            self._restore_expanded_state(expanded_paths)
            self.test_case_selected.emit(test_case)

    def _create_folder(self, parent_dir):
        dialog = self.FolderNameDialog(self, 'Создать папку', 'Новая папка')
        if dialog.exec_() == QDialog.Accepted:
            folder_name = dialog.get_name()
            if folder_name:
                new_folder = parent_dir / folder_name
                try:
                    new_folder.mkdir(exist_ok=True)
                    self.tree_updated.emit()
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось создать папку:\n{e}")

    def _rename_folder(self, folder_path):
        expanded_paths = self._capture_expanded_state()
        old_name = folder_path.name
        dialog = self.FolderNameDialog(self, 'Переименовать папку', old_name)
        if dialog.exec_() == QDialog.Accepted:
            new_name = dialog.get_name()
            if new_name and new_name != old_name:
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
    
    def _delete_multiple_test_cases(self, test_cases: List[TestCase]):
        """Удалить несколько тест-кейсов"""
        if not test_cases:
            return
        
        names = [getattr(tc, "name", None) or getattr(tc, "title", "тест-кейс") for tc in test_cases[:5]]
        if len(test_cases) > 5:
            names_text = ", ".join(names) + f" и еще {len(test_cases) - 5}"
        else:
            names_text = ", ".join(names)
        
        reply = QMessageBox.question(
            self,
            "Удаление тест-кейсов",
            f"Удалить {len(test_cases)} тест-кейсов?\n\n{names_text}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        
        expanded_paths = self._capture_expanded_state()
        deleted_count = 0
        failed_count = 0
        
        for test_case in test_cases:
            try:
                success = self.service.delete_test_case(test_case)
                if success:
                    deleted_count += 1
                else:
                    failed_count += 1
            except Exception as exc:
                failed_count += 1
                print(f"Ошибка при удалении тест-кейса: {exc}")
        
        self.tree_updated.emit()
        self._restore_expanded_state(expanded_paths)
        
        if failed_count > 0:
            QMessageBox.warning(
                self,
                "Удаление",
                f"Удалено: {deleted_count}\nНе удалось удалить: {failed_count}"
            )
        else:
            QMessageBox.information(
                self,
                "Удаление",
                f"Успешно удалено {deleted_count} тест-кейсов"
            )
    
    def _add_multiple_to_review(self, test_cases: List[TestCase]):
        """Добавить несколько тест-кейсов в панель ревью"""
        for test_case in test_cases:
            self.add_to_review_requested.emit(test_case)

    def _rename_file(self, test_case):
        expanded_paths = self._capture_expanded_state()
        old_filename = test_case._filename
        
        dialog = self.FileNameDialog(self, 'Переименовать файл', old_filename)
        if dialog.exec_() == QDialog.Accepted:
            new_filename = dialog.get_name()
            if new_filename and new_filename != old_filename:
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

    def filter_items(self, query: str, filters: Optional[Dict] = None):
        """Фильтровать элементы дерева по текстовому запросу и дополнительным фильтрам.
        
        Args:
            query: Текстовый запрос для поиска
            filters: Словарь с фильтрами (author, owner, status, tags)
        """
        pattern = (query or "").strip().lower()
        filters = filters or {}
        self._apply_filter(self.invisibleRootItem(), pattern, filters)
        if not pattern and not filters:
            self.collapseAll()
    
    def count_visible_test_cases(self) -> int:
        """Подсчитать количество видимых тест-кейсов в дереве после фильтрации.
        
        Returns:
            int: Количество видимых тест-кейсов
        """
        count = 0
        
        def count_items(item: QTreeWidgetItem):
            nonlocal count
            for i in range(item.childCount()):
                child = item.child(i)
                # Проверяем, видим ли элемент
                if not child.isHidden():
                    data = child.data(0, Qt.UserRole)
                    if data and isinstance(data, dict) and data.get('type') == 'file':
                        count += 1
                # Рекурсивно проверяем дочерние элементы
                count_items(child)
        
        count_items(self.invisibleRootItem())
        return count

    def _apply_filter(self, item: QTreeWidgetItem, pattern: str, filters: Dict) -> bool:
        """Применить фильтры к элементу дерева и его детям.
        
        Returns:
            True если элемент или его дети соответствуют фильтрам
        """
        # Сначала обрабатываем всех детей
        matches = False
        for i in range(item.childCount()):
            child = item.child(i)
            child_match = self._apply_filter(child, pattern, filters)
            matches = matches or child_match

        own_match = False
        if item is not self.invisibleRootItem():
            item_data = item.data(0, Qt.UserRole)
            
            # Проверяем текстовый поиск
            item_text = item.text(0).lower()
            text_match = not pattern or pattern in item_text
            
            # Для файлов также проверяем test_case_id
            if item_data and isinstance(item_data, dict) and item_data.get('type') == 'file':
                test_case = item_data.get('test_case')
                if test_case and isinstance(test_case, TestCase) and pattern:
                    # Если есть паттерн поиска, проверяем также test_case_id
                    test_case_id = (getattr(test_case, 'test_case_id', '') or "").strip().lower()
                    if test_case_id and pattern in test_case_id:
                        text_match = True
            
            # Проверяем фильтры для тест-кейсов
            filter_match = True
            if item_data and isinstance(item_data, dict) and item_data.get('type') == 'file':
                test_case = item_data.get('test_case')
                if test_case and isinstance(test_case, TestCase):
                    # Фильтр по автору (поддержка множественного выбора)
                    if 'author' in filters and filters['author']:
                        author_filter = filters['author']
                        if isinstance(author_filter, list):
                            # Множественный выбор - проверяем, что автор тест-кейса в списке
                            test_case_author = (test_case.author or "").strip()
                            if not any(author.strip() == test_case_author for author in author_filter):
                                filter_match = False
                        else:
                            # Одиночный выбор (для обратной совместимости)
                            if filters['author'].lower() not in (test_case.author or "").lower():
                                filter_match = False
                    
                    # Фильтр по владельцу (поддержка множественного выбора)
                    if 'owner' in filters and filters['owner']:
                        owner_filter = filters['owner']
                        if isinstance(owner_filter, list):
                            # Множественный выбор - проверяем, что владелец тест-кейса в списке
                            test_case_owner = (test_case.owner or "").strip()
                            if not any(owner.strip() == test_case_owner for owner in owner_filter):
                                filter_match = False
                        else:
                            # Одиночный выбор (для обратной совместимости)
                            if filters['owner'].lower() not in (test_case.owner or "").lower():
                                filter_match = False
                    
                    # Фильтр по статусу (поддержка множественного выбора)
                    if 'status' in filters and filters['status']:
                        status_filter = filters['status']
                        if isinstance(status_filter, list):
                            test_case_status = (test_case.status or "").strip()
                            if not any(status.strip() == test_case_status for status in status_filter):
                                filter_match = False
                        else:
                            if status_filter.lower() != (test_case.status or "").lower():
                                filter_match = False
                    
                    # Фильтр по reviewer
                    if 'reviewer' in filters and filters['reviewer']:
                        reviewer_filter = filters['reviewer']
                        if isinstance(reviewer_filter, list):
                            test_case_reviewer = (getattr(test_case, 'reviewer', '') or "").strip()
                            if not any(reviewer.strip() == test_case_reviewer for reviewer in reviewer_filter):
                                filter_match = False
                        else:
                            if reviewer_filter.lower() not in (getattr(test_case, 'reviewer', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по test_layer
                    if 'test_layer' in filters and filters['test_layer']:
                        test_layer_filter = filters['test_layer']
                        if isinstance(test_layer_filter, list):
                            test_case_layer = (getattr(test_case, 'test_layer', '') or "").strip()
                            if not any(layer.strip() == test_case_layer for layer in test_layer_filter):
                                filter_match = False
                        else:
                            if test_layer_filter.lower() not in (getattr(test_case, 'test_layer', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по test_type
                    if 'test_type' in filters and filters['test_type']:
                        test_type_filter = filters['test_type']
                        if isinstance(test_type_filter, list):
                            test_case_type = (getattr(test_case, 'test_type', '') or "").strip()
                            if not any(t_type.strip() == test_case_type for t_type in test_type_filter):
                                filter_match = False
                        else:
                            if test_type_filter.lower() not in (getattr(test_case, 'test_type', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по severity
                    if 'severity' in filters and filters['severity']:
                        severity_filter = filters['severity']
                        if isinstance(severity_filter, list):
                            test_case_severity = (getattr(test_case, 'severity', '') or "").strip()
                            if not any(severity.strip() == test_case_severity for severity in severity_filter):
                                filter_match = False
                        else:
                            if severity_filter.lower() not in (getattr(test_case, 'severity', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по priority
                    if 'priority' in filters and filters['priority']:
                        priority_filter = filters['priority']
                        if isinstance(priority_filter, list):
                            test_case_priority = (getattr(test_case, 'priority', '') or "").strip()
                            if not any(priority.strip() == test_case_priority for priority in priority_filter):
                                filter_match = False
                        else:
                            if priority_filter.lower() not in (getattr(test_case, 'priority', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по environment
                    if 'environment' in filters and filters['environment']:
                        env_filter = filters['environment']
                        if isinstance(env_filter, list):
                            test_case_env = (getattr(test_case, 'environment', '') or "").strip()
                            if not any(env.strip() == test_case_env for env in env_filter):
                                filter_match = False
                        else:
                            if env_filter.lower() not in (getattr(test_case, 'environment', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по browser
                    if 'browser' in filters and filters['browser']:
                        browser_filter = filters['browser']
                        if isinstance(browser_filter, list):
                            test_case_browser = (getattr(test_case, 'browser', '') or "").strip()
                            if not any(browser.strip() == test_case_browser for browser in browser_filter):
                                filter_match = False
                        else:
                            if browser_filter.lower() not in (getattr(test_case, 'browser', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по test_case_id
                    if 'test_case_id' in filters and filters['test_case_id']:
                        tc_id_filter = filters['test_case_id']
                        if isinstance(tc_id_filter, list):
                            test_case_id = (getattr(test_case, 'test_case_id', '') or "").strip()
                            if not any(tc_id.strip() == test_case_id for tc_id in tc_id_filter):
                                filter_match = False
                        else:
                            if tc_id_filter.lower() not in (getattr(test_case, 'test_case_id', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по issue_links
                    if 'issue_links' in filters and filters['issue_links']:
                        issue_links_filter = filters['issue_links']
                        if isinstance(issue_links_filter, list):
                            test_case_issue_links = (getattr(test_case, 'issue_links', '') or "").strip()
                            if not any(links.strip() == test_case_issue_links for links in issue_links_filter):
                                filter_match = False
                        else:
                            if issue_links_filter.lower() not in (getattr(test_case, 'issue_links', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по test_case_links
                    if 'test_case_links' in filters and filters['test_case_links']:
                        tc_links_filter = filters['test_case_links']
                        if isinstance(tc_links_filter, list):
                            test_case_tc_links = (getattr(test_case, 'test_case_links', '') or "").strip()
                            if not any(links.strip() == test_case_tc_links for links in tc_links_filter):
                                filter_match = False
                        else:
                            if tc_links_filter.lower() not in (getattr(test_case, 'test_case_links', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по epic
                    if 'epic' in filters and filters['epic']:
                        epic_filter = filters['epic']
                        if isinstance(epic_filter, list):
                            test_case_epic = (getattr(test_case, 'epic', '') or "").strip()
                            if not any(epic.strip() == test_case_epic for epic in epic_filter):
                                filter_match = False
                        else:
                            if epic_filter.lower() not in (getattr(test_case, 'epic', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по feature
                    if 'feature' in filters and filters['feature']:
                        feature_filter = filters['feature']
                        if isinstance(feature_filter, list):
                            test_case_feature = (getattr(test_case, 'feature', '') or "").strip()
                            if not any(feature.strip() == test_case_feature for feature in feature_filter):
                                filter_match = False
                        else:
                            if feature_filter.lower() not in (getattr(test_case, 'feature', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по story
                    if 'story' in filters and filters['story']:
                        story_filter = filters['story']
                        if isinstance(story_filter, list):
                            test_case_story = (getattr(test_case, 'story', '') or "").strip()
                            if not any(story.strip() == test_case_story for story in story_filter):
                                filter_match = False
                        else:
                            if story_filter.lower() not in (getattr(test_case, 'story', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по component
                    if 'component' in filters and filters['component']:
                        component_filter = filters['component']
                        if isinstance(component_filter, list):
                            test_case_component = (getattr(test_case, 'component', '') or "").strip()
                            if not any(component.strip() == test_case_component for component in component_filter):
                                filter_match = False
                        else:
                            if component_filter.lower() not in (getattr(test_case, 'component', '') or "").lower():
                                filter_match = False
                    
                    # Фильтр по description (текстовый поиск)
                    if 'description' in filters and filters['description']:
                        description_text = filters['description'].lower()
                        test_case_description = (getattr(test_case, 'description', '') or "").lower()
                        if description_text not in test_case_description:
                            filter_match = False
                    
                    # Фильтр по тегам (поддержка множественного выбора)
                    if 'tags' in filters and filters['tags']:
                        test_case_tags = [tag.lower().strip() for tag in (test_case.tags or [])]
                        filter_tags = filters['tags']
                        if isinstance(filter_tags, list):
                            # Множественный выбор - проверяем, что хотя бы один тег из фильтра присутствует в тест-кейсе
                            filter_tags_lower = [tag.lower().strip() for tag in filter_tags]
                            if not any(tag in test_case_tags for tag in filter_tags_lower):
                                filter_match = False
                        else:
                            # Одиночный выбор (для обратной совместимости)
                            filter_tag_lower = filter_tags.lower().strip()
                            if filter_tag_lower not in test_case_tags:
                                filter_match = False
                    
                    # Фильтр по resolved (проверяем notes)
                    if 'resolved' in filters and filters['resolved']:
                        resolved_filter = filters['resolved']
                        # Получаем все статусы resolved из notes тест-кейса
                        test_case_resolved_statuses = set()
                        if hasattr(test_case, 'notes') and test_case.notes:
                            for note_data in test_case.notes.values():
                                if isinstance(note_data, dict):
                                    resolved = note_data.get("resolved", "new")
                                    if resolved:
                                        test_case_resolved_statuses.add(resolved.strip())
                        
                        # Если у тест-кейса нет notes с resolved, считаем, что у него нет resolved статусов
                        if not test_case_resolved_statuses:
                            test_case_resolved_statuses.add("пусто")
                        
                        # Проверяем, есть ли пересечение между фильтром и статусами тест-кейса
                        if isinstance(resolved_filter, list):
                            # Множественный выбор - проверяем пересечение
                            filter_set = set(r.strip() for r in resolved_filter)
                            if not filter_set.intersection(test_case_resolved_statuses):
                                filter_match = False
                        else:
                            # Одиночный выбор
                            if resolved_filter.strip() not in test_case_resolved_statuses:
                                filter_match = False
            
            # Для файлов: проверяем текстовый поиск и фильтры
            # Для папок: проверяем текстовый поиск и наличие видимых дочерних элементов
            if item_data and isinstance(item_data, dict) and item_data.get('type') == 'folder':
                # Для папок: видима только если имя соответствует поиску И есть видимые дочерние элементы
                own_match = text_match and matches
            else:
                # Для файлов: видима если соответствует текстовому поиску и фильтрам
                own_match = text_match and filter_match
            
            visible = own_match or matches
            item.setHidden(not visible)
            if pattern or filters:
                item.setExpanded(matches or own_match)
            return visible

        return matches

    # ----------------------------------------------------------- DnD helpers

    def mimeTypes(self):
        return [self.MIME_TYPE]

    def mimeData(self, items):
        if not items:
            return None
        
        # Поддержка множественного выбора
        paths = []
        types = set()
        
        for item in items:
            data = item.data(0, Qt.UserRole)
            if not data:
                continue
            
            item_type = data.get("type")
            types.add(item_type)
            
            if item_type == "file":
                test_case = data.get("test_case")
                if test_case and getattr(test_case, "_filepath", None):
                    paths.append({"type": "file", "path": str(test_case._filepath)})
            elif item_type == "folder":
                folder_path = data.get("path")
                if folder_path:
                    paths.append({"type": "folder", "path": str(folder_path)})
        
        if not paths:
            return None
        
        # Если все элементы одного типа, используем старый формат для обратной совместимости
        if len(types) == 1 and len(paths) == 1:
            payload = paths[0]
        else:
            # Множественный выбор - используем массив
            payload = {"multiple": True, "items": paths}
        
        mime = QMimeData()
        mime.setData(self.MIME_TYPE, QByteArray(json.dumps(payload).encode("utf-8")))
        return mime

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
            self._update_drag_over_item(event.pos())
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
            self._update_drag_over_item(event.pos())
            # Автоскролл при приближении к краям виджета
            self._auto_scroll_on_drag(event.pos())
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        """Обработка выхода drag & drop"""
        # Останавливаем таймер разворачивания
        self._expand_timer.stop()
        self._expand_target_item = None
        # Останавливаем таймер автоскролла
        self._scroll_timer.stop()
        self._scroll_direction = 0
        self._clear_drag_over_item()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()
        if not mime.hasFormat(self.MIME_TYPE):
            event.ignore()
            self._clear_drag_over_item()
            return

        if not self.test_cases_dir:
            event.ignore()
            self._clear_drag_over_item()
            return

        try:
            payload = json.loads(bytes(mime.data(self.MIME_TYPE)).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            event.ignore()
            self._clear_drag_over_item()
            return

        target_folder = self._resolve_drop_target(event.pos())
        if target_folder is None:
            event.ignore()
            self._clear_drag_over_item()
            return
        target_folder = Path(target_folder)

        # Поддержка множественного выбора
        if payload.get("multiple"):
            items = payload.get("items", [])
            moved_count = 0
            for item_data in items:
                source_type = item_data.get("type")
                source_path = item_data.get("path")
                if not source_type or not source_path:
                    continue
                
                source_path_obj = Path(source_path)
                if source_type == "file":
                    if source_path_obj.parent == target_folder:
                        continue
                    if self.service.move_item(source_path_obj, target_folder):
                        moved_count += 1
                elif source_type == "folder":
                    if source_path_obj == target_folder or self._is_subpath(target_folder, source_path_obj):
                        continue
                    if self.service.move_item(source_path_obj, target_folder):
                        moved_count += 1
            
            if moved_count > 0:
                event.acceptProposedAction()
                # Очищаем подсветку ДО перестроения дерева, чтобы избежать обращения к невалидным элементам
                self._clear_drag_over_item()
                expanded_paths = self._capture_expanded_state()
                self.tree_updated.emit()
                self._restore_expanded_state(expanded_paths)
            else:
                event.ignore()
                # Очищаем подсветку если операция не удалась
                self._clear_drag_over_item()
        else:
            # Одиночный выбор (старый формат для обратной совместимости)
            source_type = payload.get("type")
            source_path = payload.get("path")
            if not source_type or not source_path:
                event.ignore()
                self._clear_drag_over_item()
                return

            source_path_obj = Path(source_path)
            if source_type == "file":
                if source_path_obj.parent == target_folder:
                    event.ignore()
                    self._clear_drag_over_item()
                    return
                moved = self.service.move_item(source_path_obj, target_folder)
            elif source_type == "folder":
                if source_path_obj == target_folder or self._is_subpath(target_folder, source_path_obj):
                    event.ignore()
                    self._clear_drag_over_item()
                    return
                moved = self.service.move_item(source_path_obj, target_folder)
            else:
                event.ignore()
                self._clear_drag_over_item()
                return

            if moved:
                event.acceptProposedAction()
                # Очищаем подсветку ДО перестроения дерева, чтобы избежать обращения к невалидным элементам
                self._clear_drag_over_item()
                expanded_paths = self._capture_expanded_state()
                self.tree_updated.emit()
                self._restore_expanded_state(expanded_paths)
            else:
                event.ignore()
                # Очищаем подсветку если операция не удалась
                self._clear_drag_over_item()

    def _update_drag_over_item(self, position):
        """Обновить визуальное выделение элемента при drag & drop"""
        item = self.itemAt(position)
        
        # Если элемент не изменился, проверяем только состояние таймера
        if item == self._drag_over_item:
            # Если элемент не изменился, но папка уже развернута, останавливаем таймер
            if item:
                data = item.data(0, Qt.UserRole)
                if data and isinstance(data, dict):
                    if data.get("type") == "folder" and item.isExpanded():
                        self._expand_timer.stop()
                        self._expand_target_item = None
            return
        
        # Убираем выделение с предыдущего элемента
        self._clear_drag_over_item()
        
        # Добавляем выделение новому элементу
        if item:
            self._drag_over_item = item
            data = item.data(0, Qt.UserRole)
            
            # Подсвечиваем только папки и файлы (не корневой элемент)
            if data and isinstance(data, dict):
                # Фон теперь рисуется в drawRow, просто обновляем виджет
                self.viewport().update()
                self.update()
                
                # Запускаем таймер для автоматического разворачивания папок
                if data.get("type") == "folder" and not item.isExpanded() and item.childCount() > 0:
                    self._expand_target_item = item
                    self._expand_timer.start(2000)  # 2 секунды
                else:
                    # Останавливаем таймер, если элемент не папка или уже развернут
                    self._expand_timer.stop()
                    self._expand_target_item = None
    
    def _clear_drag_over_item(self):
        """Убрать визуальное выделение элемента"""
        # Останавливаем таймер разворачивания
        self._expand_timer.stop()
        self._expand_target_item = None
        # Останавливаем таймер автоскролла
        self._scroll_timer.stop()
        self._scroll_direction = 0
        
        if self._drag_over_item:
            # Очищаем ссылку на элемент
            self._drag_over_item = None
            self._original_background = None
            
            # Принудительно обновляем виджет для перерисовки без подсветки
            # Используем update() для безопасной перерисовки (repaint() может быть небезопасным)
            self.viewport().update()
            self.update()
    
    def _auto_scroll_on_drag(self, position):
        """Автоматическая прокрутка дерева при drag & drop, если курсор близко к краю"""
        viewport = self.viewport()
        viewport_rect = viewport.rect()
        
        # Порог для начала автоскролла (в пикселях от края)
        scroll_threshold = 30
        
        # Проверяем верхний край
        if position.y() < scroll_threshold:
            scrollbar = self.verticalScrollBar()
            if scrollbar and scrollbar.value() > scrollbar.minimum():
                # Запускаем плавную прокрутку вверх
                if self._scroll_direction != -1:
                    self._scroll_direction = -1
                    if not self._scroll_timer.isActive():
                        self._scroll_timer.start(16)  # ~60 FPS для плавности
            else:
                # Достигли верха, останавливаем прокрутку
                self._scroll_timer.stop()
                self._scroll_direction = 0
        
        # Проверяем нижний край
        elif position.y() > viewport_rect.height() - scroll_threshold:
            scrollbar = self.verticalScrollBar()
            if scrollbar and scrollbar.value() < scrollbar.maximum():
                # Запускаем плавную прокрутку вниз
                if self._scroll_direction != 1:
                    self._scroll_direction = 1
                    if not self._scroll_timer.isActive():
                        self._scroll_timer.start(16)  # ~60 FPS для плавности
            else:
                # Достигли низа, останавливаем прокрутку
                self._scroll_timer.stop()
                self._scroll_direction = 0
        else:
            # Курсор вне зоны автоскролла, останавливаем прокрутку
            self._scroll_timer.stop()
            self._scroll_direction = 0
    
    def _perform_smooth_scroll(self):
        """Выполнить один шаг плавной прокрутки"""
        if self._scroll_direction == 0:
            self._scroll_timer.stop()
            return
        
        scrollbar = self.verticalScrollBar()
        if not scrollbar:
            self._scroll_timer.stop()
            self._scroll_direction = 0
            return
        
        # Попиксельная прокрутка для максимальной плавности
        scroll_speed = 1  # 1 пиксель за тик
        current_value = scrollbar.value()
        
        if self._scroll_direction == -1:  # Прокрутка вверх
            if current_value > scrollbar.minimum():
                new_value = max(scrollbar.minimum(), current_value - scroll_speed)
                scrollbar.setValue(new_value)
            else:
                # Достигли верха, останавливаем
                self._scroll_timer.stop()
                self._scroll_direction = 0
        elif self._scroll_direction == 1:  # Прокрутка вниз
            if current_value < scrollbar.maximum():
                new_value = min(scrollbar.maximum(), current_value + scroll_speed)
                scrollbar.setValue(new_value)
            else:
                # Достигли низа, останавливаем
                self._scroll_timer.stop()
                self._scroll_direction = 0
    
    def _auto_expand_folder(self):
        """Автоматически развернуть папку после задержки при drag & drop"""
        if self._expand_target_item and not self._expand_target_item.isExpanded():
            # Проверяем, что элемент все еще является папкой
            data = self._expand_target_item.data(0, Qt.UserRole)
            if data and data.get("type") == "folder":
                self._expand_target_item.setExpanded(True)
                # Обновляем позицию drag over item, так как дерево изменилось
                if self._drag_over_item == self._expand_target_item:
                    self.viewport().update()
                    self.update()
    
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
    
    # ----------------------------------------------------------- skip dialog
    
    class SkipReasonDialog(QDialog):
        """Диалог для выбора причины пропуска тест-кейса"""
        
        def __init__(self, parent=None, skip_reasons: Optional[List[str]] = None):
            super().__init__(parent)
            self.setWindowTitle("Причина пропуска")
            self.setMinimumWidth(400)
            self.skip_reasons = skip_reasons or ['Автотесты', 'Нагрузочное тестирование', 'Другое']
            self._setup_ui()
        
        def _setup_ui(self):
            layout = QVBoxLayout(self)
            
            # Инструкция
            label = QLabel("Выберите причину пропуска:")
            layout.addWidget(label)
            
            # Дропдаун с причинами (пустой пункт по умолчанию)
            self.reason_combo = QComboBox()
            self.reason_combo.addItem("")  # Пустой пункт по умолчанию
            # Добавляем причины из настроек
            if self.skip_reasons:
                self.reason_combo.addItems(self.skip_reasons)
            else:
                # Fallback на значения по умолчанию
                self.reason_combo.addItems(["Автотесты", "Нагрузочное тестирование", "Другое"])
            self.reason_combo.setCurrentIndex(0)  # Выбираем пустой пункт
            self.reason_combo.currentTextChanged.connect(self._on_reason_changed)
            layout.addWidget(self.reason_combo)
            
            # Поле для комментария (видно только при выборе "Другое")
            self.comment_label = QLabel("Комментарий:")
            self.comment_label.setVisible(False)
            layout.addWidget(self.comment_label)
            
            self.comment_edit = QLineEdit()
            self.comment_edit.setPlaceholderText("Введите причину пропуска...")
            self.comment_edit.setVisible(False)
            self.comment_edit.textChanged.connect(self._on_comment_changed)
            layout.addWidget(self.comment_edit)
            
            # Кнопки
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(self.accept)
            button_box.rejected.connect(self.reject)
            self.ok_button = button_box.button(QDialogButtonBox.Ok)
            self.ok_button.setEnabled(False)  # По умолчанию заблокирована
            layout.addWidget(button_box)
        
        def _on_reason_changed(self, text):
            # Показываем поле комментария только для "Другое"
            is_other = text == "Другое"
            self.comment_label.setVisible(is_other)
            self.comment_edit.setVisible(is_other)
            # Обновляем состояние кнопки ОК
            self._update_ok_button()
        
        def _on_comment_changed(self):
            self._update_ok_button()
        
        def _update_ok_button(self):
            # Кнопка ОК активна, если выбрана причина (не пустая) или введен комментарий
            reason = self.reason_combo.currentText().strip()
            if not reason:
                # Если не выбрана причина, проверяем комментарий
                comment = self.comment_edit.text().strip()
                self.ok_button.setEnabled(bool(comment))
            elif reason == "Другое":
                # Если выбрано "Другое", нужен комментарий
                comment = self.comment_edit.text().strip()
                self.ok_button.setEnabled(bool(comment))
            else:
                # Если выбрана любая другая причина, кнопка активна
                self.ok_button.setEnabled(True)
        
        def get_skip_reason(self) -> str:
            """Получить причину пропуска"""
            reason = self.reason_combo.currentText().strip()
            if not reason:
                # Если не выбрана причина, возвращаем комментарий
                return self.comment_edit.text().strip()
            elif reason == "Другое":
                # Если выбрано "Другое", возвращаем комментарий
                return self.comment_edit.text().strip()
            else:
                # Если выбрана другая причина, возвращаем её значение
                return reason
    
    # ----------------------------------------------------------- mark as passed/skipped
    
    def _mark_test_case_passed(self, test_case: TestCase):
        """Пометить все шаги тест-кейса как passed"""
        try:
            if not test_case:
                QMessageBox.warning(self, "Ошибка", "Тест-кейс не выбран")
                return
            
            if not test_case.steps:
                QMessageBox.information(self, "Информация", "В тест-кейсе нет шагов")
                return
            
            # Проверяем наличие filepath для сохранения
            if not hasattr(test_case, "_filepath") or not test_case._filepath:
                QMessageBox.warning(self, "Ошибка", "Не удалось определить путь к файлу тест-кейса")
                return
            
            for step in test_case.steps:
                step.status = "passed"
                step.skip_reason = ""  # Очищаем skipReason при пометке как passed
            
            if not self.service.save_test_case(test_case):
                QMessageBox.warning(self, "Ошибка", "Не удалось сохранить тест-кейс")
                return
            
            self.test_cases_updated.emit()
            test_case_name = getattr(test_case, "name", "тест-кейс")
            QMessageBox.information(self, "Готово", f"Все шаги тест-кейса «{test_case_name}» помечены как passed")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при пометке тест-кейса: {str(e)}")
    
    def _mark_test_case_skipped(self, test_case: TestCase):
        """Пометить все шаги тест-кейса как skipped с выбором причины"""
        try:
            if not test_case:
                QMessageBox.warning(self, "Ошибка", "Тест-кейс не выбран")
                return
            
            if not test_case.steps:
                QMessageBox.information(self, "Информация", "В тест-кейсе нет шагов")
                return
            
            # Проверяем наличие filepath для сохранения
            if not hasattr(test_case, "_filepath") or not test_case._filepath:
                QMessageBox.warning(self, "Ошибка", "Не удалось определить путь к файлу тест-кейса")
                return
            
            # Показываем диалог выбора причины
            dialog = self.SkipReasonDialog(self, self._skip_reasons)
            if dialog.exec_() != QDialog.Accepted:
                return
            
            skip_reason = dialog.get_skip_reason()
            
            # Помечаем все шаги как skipped с причиной
            for step in test_case.steps:
                step.status = "skipped"
                step.skip_reason = skip_reason
            
            if not self.service.save_test_case(test_case):
                QMessageBox.warning(self, "Ошибка", "Не удалось сохранить тест-кейс")
                return
            
            self.test_cases_updated.emit()
            test_case_name = getattr(test_case, "name", "тест-кейс")
            QMessageBox.information(self, "Готово", f"Все шаги тест-кейса «{test_case_name}» помечены как skipped")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при пометке тест-кейса: {str(e)}")
    
    def _mark_folder_passed(self, folder_path: Path):
        """Пометить все шаги всех тест-кейсов в папке и подпапках как passed"""
        if not self.test_cases_dir or not folder_path.exists():
            return
        
        # Собираем все тест-кейсы в папке и подпапках
        test_cases_to_update = []
        for test_case in self.service.load_all_test_cases(self.test_cases_dir):
            if test_case._filepath:
                try:
                    test_case._filepath.relative_to(folder_path)
                    test_cases_to_update.append(test_case)
                except ValueError:
                    continue
        
        if not test_cases_to_update:
            QMessageBox.information(self, "Информация", "В выбранной папке нет тест-кейсов")
            return
        
        # Помечаем все шаги как passed
        count = 0
        for test_case in test_cases_to_update:
            if test_case.steps:
                for step in test_case.steps:
                    step.status = "passed"
                    step.skip_reason = ""  # Очищаем skipReason при пометке как passed
                self.service.save_test_case(test_case)
                count += 1
        
        self.test_cases_updated.emit()
        QMessageBox.information(self, "Готово", f"Все шаги {count} тест-кейсов в папке помечены как passed")
    
    def _mark_folder_skipped(self, folder_path: Path):
        """Пометить все шаги всех тест-кейсов в папке и подпапках как skipped"""
        if not self.test_cases_dir or not folder_path.exists():
            return
        
        # Показываем диалог выбора причины
        dialog = self.SkipReasonDialog(self, self._skip_reasons)
        if dialog.exec_() != QDialog.Accepted:
            return
        
        skip_reason = dialog.get_skip_reason()
        
        # Собираем все тест-кейсы в папке и подпапках
        test_cases_to_update = []
        for test_case in self.service.load_all_test_cases(self.test_cases_dir):
            if test_case._filepath:
                try:
                    test_case._filepath.relative_to(folder_path)
                    test_cases_to_update.append(test_case)
                except ValueError:
                    continue
        
        if not test_cases_to_update:
            QMessageBox.information(self, "Информация", "В выбранной папке нет тест-кейсов")
            return
        
        # Помечаем все шаги как skipped с причиной
        count = 0
        for test_case in test_cases_to_update:
            if test_case.steps:
                for step in test_case.steps:
                    step.status = "skipped"
                    step.skip_reason = skip_reason
                self.service.save_test_case(test_case)
                count += 1
        
        self.test_cases_updated.emit()
        QMessageBox.information(self, "Готово", f"Все шаги {count} тест-кейсов в папке помечены как skipped")

