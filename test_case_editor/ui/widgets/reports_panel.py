"""Виджет для отображения структуры папки Reports."""

import json
from pathlib import Path
from typing import Optional, Dict

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QScrollArea,
    QPushButton,
    QFrame,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

from ..styles.ui_metrics import UI_METRICS


class ReportsPanel(QWidget):
    """Панель для отображения структуры папки Reports"""
    
    generate_report_requested = pyqtSignal()  # Сигнал для запроса генерации отчета
    generate_summary_report_requested = pyqtSignal()  # Сигнал для запроса генерации суммарного отчета
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reports_dir: Optional[Path] = None
        
        # Загружаем маппинг иконок
        self._icon_mapping = self._load_icon_mapping()
        
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
        
        # Секция суммарного отчета (отдельно сверху)
        summary_section = QFrame()
        summary_section.setStyleSheet("""
            QFrame {
                background-color: rgba(108, 194, 74, 0.1);
                border: 1px solid rgba(108, 194, 74, 0.3);
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 20px;
            }
        """)
        summary_layout = QHBoxLayout(summary_section)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(10)
        
        summary_label = QLabel("📊 Суммарный отчет")
        summary_label.setStyleSheet("font-weight: 600; font-size: 14px; color: #6CC24A;")
        summary_layout.addWidget(summary_label)
        
        summary_layout.addStretch()
        
        # Кнопка генерации суммарного отчета
        self.generate_summary_btn = QPushButton("Сгенерировать")
        self.generate_summary_btn.setToolTip("Сгенерировать суммарный отчет на основе всех отчетов")
        self.generate_summary_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid rgba(108, 194, 74, 0.5);
                border-radius: 4px;
                background-color: rgba(108, 194, 74, 0.2);
                padding: 6px 12px;
                color: #6CC24A;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(108, 194, 74, 0.3);
                border-color: rgba(108, 194, 74, 0.7);
            }
        """)
        self.generate_summary_btn.clicked.connect(self.generate_summary_report_requested.emit)
        summary_layout.addWidget(self.generate_summary_btn)
        
        content_layout.addWidget(summary_section)
        
        # Заголовок с кнопкой генерации отчета
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)
        
        title_label = QLabel("Отчетность")
        title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # Кнопка генерации отчета
        self.generate_report_btn = QPushButton()
        # Загружаем иконку из маппинга
        icon_name = self._get_reports_icon("generate_report")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=20, color="#ffffff")
            if icon:
                self.generate_report_btn.setIcon(icon)
                self.generate_report_btn.setIconSize(QSize(20, 20))
        self.generate_report_btn.setToolTip("Сгенерировать отчет")
        self.generate_report_btn.setFixedSize(32, 32)
        self.generate_report_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.3);
            }
        """)
        self.generate_report_btn.clicked.connect(self.generate_report_requested.emit)
        title_layout.addWidget(self.generate_report_btn)
        
        content_layout.addLayout(title_layout)
        
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
                    if isinstance(data, dict) and any(key in data for key in ['panels', 'context_menu', 'reports']):
                        return data
                    else:
                        # Старый формат - возвращаем с секциями
                        return {
                            'panels': data if isinstance(data, dict) else {},
                            'context_menu': {},
                            'reports': {}
                        }
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка загрузки маппинга иконок: {e}")
        
        # Возвращаем значения по умолчанию, если файл не найден
        return {
            'panels': {},
            'context_menu': {},
            'reports': {
                "generate_report": "printer.svg"
            }
        }

    def _get_reports_icon(self, icon_key: str) -> Optional[str]:
        """Получить имя файла иконки для отчетов по ключу."""
        reports_mapping = self._icon_mapping.get('reports', {})
        return reports_mapping.get(icon_key)

    def _load_svg_icon(self, icon_name: str, size: int = 20, color: Optional[str] = None) -> Optional[QIcon]:
        """Загрузить SVG иконку из файла и вернуть QIcon.
        
        Args:
            icon_name: Имя файла иконки (например, "printer.svg")
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

