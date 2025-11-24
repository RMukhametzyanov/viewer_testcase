"""Виджет для отображения структуры папки Reports."""

from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

from ..styles.ui_metrics import UI_METRICS


class ReportsPanel(QWidget):
    """Панель для отображения структуры папки Reports"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reports_dir: Optional[Path] = None
        self._setup_ui()
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        content_layout.setSpacing(UI_METRICS.section_spacing)
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Заголовок
        title_label = QLabel("Отчетность")
        title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        content_layout.addWidget(title_label)
        
        # Описание
        desc_label = QLabel("Структура папки Reports с отчетами")
        desc_label.setStyleSheet("color: #888; font-size: 12px; margin-bottom: 10px;")
        content_layout.addWidget(desc_label)
        
        # Дерево отчетов
        self.reports_tree = QTreeWidget()
        self.reports_tree.setHeaderHidden(True)
        self.reports_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.02);
            }
            QTreeWidget::item {
                padding: 5px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
            QTreeWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.05);
            }
            QTreeWidget::item:selected {
                background-color: rgba(108, 194, 74, 0.2);
            }
        """)
        self.reports_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        content_layout.addWidget(self.reports_tree, stretch=1)
        
        # Определяем папку Reports
        self._find_reports_dir()
        
        # Загружаем отчеты
        self.refresh_reports()
    
    def _find_reports_dir(self):
        """Найти папку Reports относительно корня проекта"""
        try:
            # Ищем корень проекта (где находится run_app.py)
            current_file = Path(__file__).resolve()
            # Поднимаемся от widgets/ -> ui/ -> test_case_editor/ -> корень проекта
            app_dir = current_file.parent.parent.parent.parent
            self.reports_dir = app_dir / "Reports"
        except Exception:
            self.reports_dir = None
    
    def refresh_reports(self):
        """Обновить список отчетов"""
        self.reports_tree.clear()
        
        if not self.reports_dir or not self.reports_dir.exists():
            no_reports_item = QTreeWidgetItem(self.reports_tree)
            no_reports_item.setText(0, "Папка Reports не найдена")
            no_reports_item.setFlags(no_reports_item.flags() & ~Qt.ItemIsSelectable)
            return
        
        # Собираем все папки и файлы в Reports
        self._populate_tree(self.reports_dir, self.reports_tree.invisibleRootItem())
        
        # Разворачиваем корневой элемент
        self.reports_tree.expandAll()
    
    def _populate_tree(self, directory: Path, parent_item: QTreeWidgetItem):
        """Рекурсивно заполнить дерево файлами и папками"""
        try:
            # Собираем все элементы
            items = []
            for item_path in directory.iterdir():
                if item_path.is_dir():
                    items.append((item_path, True))  # True = папка
                elif item_path.is_file():
                    items.append((item_path, False))  # False = файл
            
            # Сортируем: папки сначала (по дате изменения, самая свежая сверху), потом файлы (по имени)
            items.sort(key=lambda x: (
                not x[1],  # Папки сначала (True = 0, False = 1)
                -x[0].stat().st_mtime if x[1] else 0,  # Для папок: по дате изменения (отрицательное для обратного порядка)
                x[0].name if not x[1] else ""  # Для файлов: по имени
            ))
            
            for item_path, is_dir in items:
                tree_item = QTreeWidgetItem(parent_item)
                tree_item.setText(0, item_path.name)
                tree_item.setData(0, Qt.UserRole, str(item_path))
                
                # Устанавливаем иконку
                if is_dir:
                    tree_item.setIcon(0, QIcon.fromTheme("folder"))
                else:
                    tree_item.setIcon(0, QIcon.fromTheme("text-x-generic"))
                
                # Если это папка, рекурсивно добавляем содержимое
                if is_dir:
                    self._populate_tree(item_path, tree_item)
        except PermissionError:
            # Игнорируем ошибки доступа
            pass
        except Exception:
            # Игнорируем другие ошибки
            pass
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Обработчик двойного клика по элементу"""
        file_path_str = item.data(0, Qt.UserRole)
        if not file_path_str:
            return
        
        file_path = Path(file_path_str)
        if not file_path.exists():
            return
        
        # Открываем файл/папку в проводнике
        try:
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                if file_path.is_file():
                    # Для файла открываем папку и выделяем файл
                    subprocess.Popen(f'explorer /select,"{file_path}"')
                else:
                    # Для папки просто открываем
                    subprocess.Popen(f'explorer "{file_path}"')
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", str(file_path)])
            else:  # Linux
                subprocess.Popen(["xdg-open", str(file_path)])
        except Exception:
            # Игнорируем ошибки открытия
            pass

