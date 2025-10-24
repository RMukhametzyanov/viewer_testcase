"""
Редактор тест-кейсов в стиле Telegram Dark
"""
import json
import os
import sys
import uuid
import copy
from pathlib import Path
from typing import Dict, List, Optional
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLineEdit, QTextEdit,
    QLabel, QComboBox, QSplitter, QScrollArea, QFrame, QMessageBox,
    QFileDialog, QGroupBox, QInputDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QTableView, QStyledItemDelegate, QStyle, QStyleOptionViewItem,
    QAbstractItemView, QCheckBox, QListWidget, QListWidgetItem, QMenu, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal, QAbstractTableModel, QModelIndex, QVariant, QRect, QSize, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPainter, QPen, QBrush


class CollapsibleBox(QWidget):
    """Сворачиваемая секция (аккордеон) в стиле Telegram"""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        
        self.toggle_button = QPushButton(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 10px;
                background-color: #1E2732;
                border: none;
                border-radius: 6px;
                color: #5288C1;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #2B3945;
            }
            QPushButton:checked {
                color: #5288C1;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle)
        
        self.content_area = QWidget()
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_area)
        
    def set_content_layout(self, content_layout):
        """Установить layout содержимого"""
        old_layout = self.content_area.layout()
        if old_layout:
            QWidget().setLayout(old_layout)
        self.content_area.setLayout(content_layout)
        
    def toggle(self):
        """Переключить состояние (свернуто/развернуто)"""
        self.is_collapsed = not self.is_collapsed
        self.content_area.setVisible(not self.is_collapsed)
        
        # Обновляем текст кнопки (стрелка вниз/вправо)
        if self.is_collapsed:
            arrow = "▶"
        else:
            arrow = "▼"
        
        current_text = self.toggle_button.text()
        # Удаляем старую стрелку, если есть
        if current_text.startswith("▶") or current_text.startswith("▼"):
            current_text = current_text[2:]
        
        self.toggle_button.setText(f"{arrow} {current_text}")


class CustomTreeWidget(QTreeWidget):
    """Кастомное дерево с поддержкой drag & drop"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_editor = None
    
    def dropEvent(self, event):
        """Обработка события drop для перемещения файлов и папок"""
        source_item = self.currentItem()
        if not source_item:
            event.ignore()
            return
        
        # Получаем данные перетаскиваемого элемента
        source_data = source_item.data(0, Qt.UserRole)
        if not source_data:
            event.ignore()
            return
        
        source_type = source_data.get('type')
        if source_type not in ['file', 'folder']:
            event.ignore()
            return
        
        # Получаем целевой элемент (куда перетаскиваем)
        target_item = self.itemAt(event.pos())
        if not target_item:
            event.ignore()
            return
        
        target_data = target_item.data(0, Qt.UserRole)
        if not target_data:
            event.ignore()
            return
        
        # Определяем целевую папку
        if target_data.get('type') == 'folder':
            target_folder = target_data['path']
        elif target_data.get('type') == 'file':
            # Если перетаскиваем на файл, берем его родительскую папку
            parent = target_item.parent()
            if parent:
                parent_data = parent.data(0, Qt.UserRole)
                if parent_data and parent_data.get('type') == 'folder':
                    target_folder = parent_data['path']
                else:
                    event.ignore()
                    return
            else:
                # Корневая директория
                target_folder = self.parent_editor.test_cases_dir
        else:
            event.ignore()
            return
        
        # Перемещаем файл или папку
        import shutil
        
        if source_type == 'file':
            # Перемещение файла
            test_case = source_data['test_case']
            if '_filepath' in test_case:
                old_path = Path(test_case['_filepath'])
                new_path = target_folder / old_path.name
                
                # Проверяем, не перемещаем ли в ту же папку
                if old_path.parent == new_path.parent:
                    event.ignore()
                    return
                
                try:
                    shutil.move(str(old_path), str(new_path))
                    if self.parent_editor:
                        self.parent_editor.load_test_cases()
                        self.parent_editor.statusBar().showMessage(f"Файл перемещен в {target_folder.name}")
                    event.accept()
                except Exception as e:
                    if self.parent_editor:
                        QMessageBox.critical(self.parent_editor, "Ошибка", f"Не удалось переместить файл:\n{e}")
                    event.ignore()
            else:
                event.ignore()
        
        elif source_type == 'folder':
            # Перемещение папки
            old_folder_path = source_data['path']
            new_folder_path = target_folder / old_folder_path.name
            
            # Проверяем, не перемещаем ли в ту же родительскую папку
            if old_folder_path.parent == target_folder:
                event.ignore()
                return
            
            # Проверяем, не перемещаем ли папку саму в себя или в свою подпапку
            if target_folder == old_folder_path or str(target_folder).startswith(str(old_folder_path) + os.sep):
                if self.parent_editor:
                    self.parent_editor.statusBar().showMessage("Нельзя переместить папку в саму себя")
                event.ignore()
                return
            
            # Проверяем, не существует ли уже папка с таким именем
            if new_folder_path.exists():
                if self.parent_editor:
                    self.parent_editor.statusBar().showMessage(f"Папка {old_folder_path.name} уже существует в целевой директории")
                event.ignore()
                return
            
            try:
                shutil.move(str(old_folder_path), str(new_folder_path))
                if self.parent_editor:
                    self.parent_editor.load_test_cases()
                    self.parent_editor.statusBar().showMessage(f"Папка '{old_folder_path.name}' перемещена в '{target_folder.name}'")
                event.accept()
            except Exception as e:
                if self.parent_editor:
                    QMessageBox.critical(self.parent_editor, "Ошибка", f"Не удалось переместить папку:\n{e}")
                event.ignore()
        else:
            event.ignore()


class TestCaseListItemWidget(QWidget):
    """Виджет элемента списка в стиле Azure DevOps"""
    
    clicked = pyqtSignal(dict)
    
    def __init__(self, test_case: Dict, parent=None):
        super().__init__(parent)
        self.test_case = test_case
        self.is_selected = False
        self.init_ui()
        
    def init_ui(self):
        """Инициализация интерфейса - только статус и название"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        
        # Статус (иконка)
        status = self.test_case.get('status', 'Draft')
        status_icon = self.get_status_icon(status)
        status_color = self.get_status_color(status)
        
        status_label = QLabel(status_icon)
        status_label.setFixedSize(20, 20)
        status_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        status_label.setStyleSheet(f"color: {status_color}; background: transparent;")
        status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_label)
        
        # Название (растягивается)
        title = self.test_case.get('title', 'Без названия')
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 10))
        title_label.setStyleSheet("color: #E1E3E6; background: transparent;")
        title_label.setWordWrap(False)
        
        # Укорачиваем длинный текст с многоточием
        metrics = title_label.fontMetrics()
        elided_text = metrics.elidedText(title, Qt.ElideRight, 350)
        title_label.setText(elided_text)
        title_label.setToolTip(title)
        
        layout.addWidget(title_label, 1)
        
        self.setStyleSheet("""
            TestCaseListItemWidget {
                background-color: transparent;
                border-radius: 4px;
            }
        """)
        
    def get_status_color(self, status: str) -> str:
        """Получить цвет для статуса"""
        colors = {
            'Done': '#6CC24A',
            'Blocked': '#F5555D',
            'In Progress': '#FFA931',
            'Draft': '#8B9099',
            'Deprecated': '#6B7380'
        }
        return colors.get(status, '#8B9099')
    
    def get_status_icon(self, status: str) -> str:
        """Получить иконку для статуса"""
        icons = {
            'Done': '✓',
            'Blocked': '⚠',
            'In Progress': '⟳',
            'Draft': '○',
            'Deprecated': '×'
        }
        return icons.get(status, '○')
    
    def set_selected(self, selected: bool):
        """Установить состояние выбора"""
        self.is_selected = selected
        if selected:
            self.setStyleSheet("""
                TestCaseListItemWidget {
                    background-color: #2B5278;
                    border-radius: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                TestCaseListItemWidget {
                    background-color: transparent;
                    border-radius: 4px;
                }
            """)
    
    def enterEvent(self, event):
        """Hover эффект"""
        if not self.is_selected:
            self.setStyleSheet("""
                TestCaseListItemWidget {
                    background-color: #1E2732;
                    border-radius: 4px;
                }
            """)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Убрать hover"""
        if not self.is_selected:
            self.setStyleSheet("""
                TestCaseListItemWidget {
                    background-color: transparent;
                    border-radius: 4px;
                }
            """)
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """Обработка клика"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.test_case)
        super().mousePressEvent(event)


class TestCaseTableModel(QAbstractTableModel):
    """Модель данных для таблицы тест-кейсов"""
    
    def __init__(self, test_cases: List[Dict] = None, parent=None):
        super().__init__(parent)
        self.test_cases = test_cases or []
        self.headers = ["Статус", "Название", "Автор", "Уровень", "Файл"]
        
    def rowCount(self, parent=QModelIndex()):
        return len(self.test_cases)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)
    
    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.test_cases)):
            return QVariant()
        
        test_case = self.test_cases[index.row()]
        column = index.column()
        
        if role == Qt.DisplayRole:
            if column == 0:  # Статус
                return test_case.get('status', 'Draft')
            elif column == 1:  # Название
                return test_case.get('title', 'Без названия')
            elif column == 2:  # Автор
                return test_case.get('author', '-')
            elif column == 3:  # Уровень
                return test_case.get('level', 'minor')
            elif column == 4:  # Файл
                return test_case.get('_filename', 'Unknown')
        
        elif role == Qt.UserRole:
            # Возвращаем весь объект тест-кейса
            return test_case
        
        elif role == Qt.TextAlignmentRole:
            if column == 0 or column == 3:  # Статус и Уровень - по центру
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        
        elif role == Qt.FontRole:
            font = QFont("Segoe UI", 10)
            if column == 1:  # Название жирным
                font.setBold(False)
            return font
        
        elif role == Qt.ToolTipRole:
            # Подсказка с полной информацией
            tooltip = f"📄 {test_case.get('_filename', 'Unknown')}\n"
            tooltip += f"━━━━━━━━━━━━━━━━\n"
            tooltip += f"📝 {test_case.get('title', 'Без названия')}\n"
            tooltip += f"📊 {test_case.get('status', 'Draft')}\n"
            tooltip += f"👤 {test_case.get('author', '-')}\n"
            tooltip += f"⚡ {test_case.get('level', '-').upper()}\n"
            tooltip += f"🔖 {', '.join(test_case.get('tags', []))}"
            return tooltip
        
        return QVariant()
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headers[section]
        return QVariant()
    
    def set_test_cases(self, test_cases: List[Dict]):
        """Обновить список тест-кейсов"""
        self.beginResetModel()
        self.test_cases = test_cases
        self.endResetModel()
    
    def get_test_case(self, row: int) -> Optional[Dict]:
        """Получить тест-кейс по индексу строки"""
        if 0 <= row < len(self.test_cases):
            return self.test_cases[row]
        return None


class StatusDelegate(QStyledItemDelegate):
    """Делегат для красивого отображения статуса"""
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        status = index.data(Qt.DisplayRole)
        
        # Цвета статусов
        colors = {
            'Done': QColor("#6CC24A"),
            'Blocked': QColor("#F5555D"),
            'In Progress': QColor("#FFA931"),
            'Draft': QColor("#8B9099"),
            'Deprecated': QColor("#6B7380")
        }
        
        # Иконки статусов
        icons = {
            'Done': '✓',
            'Blocked': '⚠',
            'In Progress': '⟳',
            'Draft': '○',
            'Deprecated': '×'
        }
        
        painter.save()
        
        # Фон при наведении/выделении
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#2B5278"))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#1E2732"))
        
        # Получаем цвет и иконку
        color = colors.get(status, QColor("#8B9099"))
        icon = icons.get(status, '○')
        
        # Рисуем текст с иконкой и цветом
        painter.setPen(color)
        font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font)
        
        text = f"{icon} {status}"
        painter.drawText(option.rect, Qt.AlignCenter, text)
        
        painter.restore()
    
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        return QSize(120, 45)


class LevelDelegate(QStyledItemDelegate):
    """Делегат для красивого отображения уровня в виде бейджа"""
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        level = index.data(Qt.DisplayRole)
        
        # Цвета уровней
        colors = {
            'smoke': ('#F5555D', '#FFFFFF'),      # Красный
            'critical': ('#FFA931', '#FFFFFF'),   # Оранжевый
            'major': ('#5288C1', '#FFFFFF'),      # Синий
            'minor': ('#8B9099', '#FFFFFF'),      # Серый
            'trivial': ('#2B3945', '#E1E3E6')     # Темно-серый
        }
        
        painter.save()
        
        # Фон при наведении/выделении
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#2B5278"))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#1E2732"))
        
        # Получаем цвета
        bg_color, text_color = colors.get(level.lower(), ('#2B3945', '#E1E3E6'))
        
        # Рисуем бейдж
        badge_rect = QRect(
            option.rect.x() + (option.rect.width() - 80) // 2,
            option.rect.y() + (option.rect.height() - 24) // 2,
            80, 24
        )
        
        painter.setBrush(QBrush(QColor(bg_color)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, 10, 10)
        
        # Рисуем текст
        painter.setPen(QColor(text_color))
        font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font)
        painter.drawText(badge_rect, Qt.AlignCenter, level.upper())
        
        painter.restore()
    
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        return QSize(100, 45)


class TestCaseEditor(QMainWindow):
    """Главное окно редактора тест-кейсов"""
    
    def __init__(self):
        super().__init__()
        self.test_cases: List[Dict] = []
        self.current_test_case: Optional[Dict] = None
        self.test_cases_dir = Path("test_cases")
        self.has_unsaved_changes = False
        self.init_ui()
        self.apply_telegram_theme()
        self.load_test_cases()
        
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        self.setWindowTitle("✈️ Test Case Editor")
        self.setGeometry(100, 100, 1400, 900)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter для разделения дерева и формы
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - дерево тест-кейсов
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - форма редактирования
        self.form_widget = self.create_form_widget()
        splitter.addWidget(self.form_widget)
        
        # Установка пропорций
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([350, 1050])
        
        main_layout.addWidget(splitter)
        
        # Строка состояния
        self.statusBar().showMessage("Готов к работе")
    
    def create_left_panel(self) -> QWidget:
        """Создание левой панели с деревом и поиском"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Заголовок панели
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
        
        # Поле поиска
        search_frame = QFrame()
        search_frame.setMaximumHeight(40)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(10, 0, 10, 5)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Поиск...")
        self.search_input.textChanged.connect(self.filter_tree)
        self.search_input.setMinimumHeight(30)
        search_layout.addWidget(self.search_input)
        
        layout.addWidget(search_frame)
        
        # Дерево тест-кейсов с папками
        self.test_cases_tree = self.create_test_cases_tree()
        layout.addWidget(self.test_cases_tree)
        
        return panel
        
    def create_test_cases_tree(self) -> CustomTreeWidget:
        """Создание дерева тест-кейсов с папками"""
        tree = CustomTreeWidget()
        tree.parent_editor = self  # Передаем ссылку на главное окно
        tree.setHeaderHidden(True)
        tree.setMinimumWidth(400)
        tree.setIndentation(20)
        tree.setAnimated(True)
        
        # Включаем drag & drop
        tree.setDragEnabled(True)
        tree.setAcceptDrops(True)
        tree.setDropIndicatorShown(True)
        tree.setDragDropMode(QTreeWidget.InternalMove)
        
        # Стиль дерева
        tree.setStyleSheet("""
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
            
            QTreeWidget::branch {
                background-color: transparent;
            }
            
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                image: none;
                border-image: none;
            }
            
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                image: none;
                border-image: none;
            }
            
            QScrollBar:vertical {
                background-color: transparent;
                width: 8px;
                border-radius: 4px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #2B3945;
                border-radius: 4px;
                min-height: 30px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #3D6A98;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        # Обработка кликов
        tree.itemClicked.connect(self.on_tree_item_clicked)
        
        # Контекстное меню
        tree.setContextMenuPolicy(Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        
        return tree
    
    def create_test_cases_list(self) -> QListWidget:
        """Создание списка тест-кейсов в стиле Azure DevOps"""
        list_widget = QListWidget()
        list_widget.setMinimumWidth(400)
        list_widget.setSpacing(2)
        list_widget.setUniformItemSizes(False)
        
        # Стиль Azure DevOps
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: #17212B;
                border: none;
                border-radius: 8px;
                outline: 0;
                padding: 5px;
            }
            
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                border-radius: 4px;
            }
            
            QListWidget::item:selected {
                background-color: transparent;
            }
            
            QListWidget::item:hover {
                background-color: transparent;
            }
            
            QScrollBar:vertical {
                background-color: transparent;
                width: 8px;
                border-radius: 4px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #2B3945;
                border-radius: 4px;
                min-height: 30px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #3D6A98;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        # Контекстное меню
        list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        list_widget.customContextMenuRequested.connect(self.show_context_menu_list)
        
        return list_widget
    
    def create_table_view(self) -> QTableView:
        """Создание таблицы тест-кейсов"""
        table = QTableView()
        
        # Создаем модель данных
        self.table_model = TestCaseTableModel()
        table.setModel(self.table_model)
        
        # Устанавливаем кастомные делегаты
        self.status_delegate = StatusDelegate(table)
        self.level_delegate = LevelDelegate(table)
        table.setItemDelegateForColumn(0, self.status_delegate)  # Статус
        table.setItemDelegateForColumn(3, self.level_delegate)   # Уровень
        
        # Настройка внешнего вида
        table.setFont(QFont("Segoe UI", 10))
        table.setMinimumWidth(350)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)  # Выбор целой строки
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setShowGrid(False)
        table.setAlternatingRowColors(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(False)
        
        # Включение сортировки
        table.setSortingEnabled(True)
        table.sortByColumn(1, Qt.AscendingOrder)
        
        # Высота строк
        table.verticalHeader().setDefaultSectionSize(45)
        
        # Ширина колонок
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Статус
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Название
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Автор
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # Уровень
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Файл
        
        table.setColumnWidth(0, 130)  # Статус
        table.setColumnWidth(2, 150)  # Автор
        table.setColumnWidth(3, 110)  # Уровень
        table.setColumnWidth(4, 120)  # Файл
        
        # Скрываем колонки "Уровень" и "Файл" по умолчанию
        table.setColumnHidden(3, True)  # Уровень
        table.setColumnHidden(4, True)  # Файл
        
        # Обработка кликов
        table.clicked.connect(self.on_table_item_clicked)
        
        # Контекстное меню
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self.show_context_menu)
        
        # Hover эффект на всю строку
        table.setMouseTracking(True)
        
        # Стиль таблицы
        table.setStyleSheet("""
            QTableView {
                background-color: #17212B;
                border: none;
                border-radius: 12px;
                outline: 0;
                gridline-color: #2B3945;
            }
            
            QTableView::item {
                padding: 10px;
                border: none;
                border-bottom: 1px solid #2B3945;
                color: #E1E3E6;
            }
            
            QTableView::item:selected {
                background-color: #2B5278;
                color: #FFFFFF;
            }
            
            QTableView::item:hover {
                background-color: #1E2732;
            }
            
            QHeaderView::section {
                background-color: #17212B;
                color: #8B9099;
                padding: 12px 10px;
                border: none;
                border-bottom: 2px solid #2B3945;
                font-weight: 600;
                font-size: 9pt;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            QHeaderView::section:hover {
                background-color: #1E2732;
            }
            
            QScrollBar:vertical {
                background-color: transparent;
                width: 8px;
                border-radius: 4px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #2B3945;
                border-radius: 4px;
                min-height: 30px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #3D6A98;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        return table
        
    def create_form_widget(self) -> QWidget:
        """Создание формы редактирования"""
        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(0)
        
        # Фиксированный заголовок с названием тест-кейса (не скроллится)
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #1E2732; border-bottom: 2px solid #2B3945;")
        header_frame.setMaximumHeight(80)
        header_main_layout = QHBoxLayout(header_frame)
        header_main_layout.setContentsMargins(15, 10, 15, 10)
        
        # Левая часть - заголовки
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(5)
        
        static_title = QLabel("Редактирование тест-кейса")
        static_title.setFont(QFont("Segoe UI", 11, QFont.Normal))
        static_title.setStyleSheet("color: #8B9099; border: none;")
        header_text_layout.addWidget(static_title)
        
        self.testcase_title_label = QLabel("Не выбран тест-кейс")
        self.testcase_title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.testcase_title_label.setStyleSheet("color: #5288C1; border: none;")
        self.testcase_title_label.setWordWrap(True)
        header_text_layout.addWidget(self.testcase_title_label)
        
        header_main_layout.addLayout(header_text_layout, 1)
        
        # Правая часть - кнопка сохранить
        self.save_button = QPushButton("💾 Сохранить")
        self.save_button.setMinimumHeight(40)
        self.save_button.setMinimumWidth(140)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #2B5278;
                border: 1px solid #3D6A98;
                border-radius: 8px;
                padding: 10px 20px;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #3D6A98;
                border: 1px solid #5288C1;
            }
            QPushButton:pressed {
                background-color: #1D3F5F;
            }
        """)
        self.save_button.clicked.connect(self.save_current_test_case)
        self.save_button.setVisible(False)  # Скрыта по умолчанию
        header_main_layout.addWidget(self.save_button)
        
        form_layout.addWidget(header_frame)
        
        # Scroll area для формы
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        form_widget = QWidget()
        layout = QVBoxLayout(form_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Группа: Основная информация (2 колонки)
        main_group = QGroupBox("Основная информация")
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        
        # === Строка 1: ID и Название ===
        row1 = QHBoxLayout()
        row1.setSpacing(15)
        
        # ID (компактный, только для чтения)
        id_container = QVBoxLayout()
        id_container.setSpacing(5)
        id_label = QLabel("ID:")
        id_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        id_label.setStyleSheet("color: #8B9099;")
        id_container.addWidget(id_label)
        
        self.id_input = QLineEdit()
        self.id_input.setReadOnly(True)
        self.id_input.setPlaceholderText("Генерируется автоматически")
        self.id_input.setMinimumHeight(32)
        self.id_input.setMaximumWidth(280)
        self.id_input.setStyleSheet("""
            QLineEdit {
                background-color: #17212B;
                color: #6B7380;
                font-size: 9pt;
            }
        """)
        id_container.addWidget(self.id_input)
        row1.addLayout(id_container)
        
        # Название (растягивается)
        title_container = QVBoxLayout()
        title_container.setSpacing(5)
        title_label = QLabel("Название:")
        title_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        title_container.addWidget(title_label)
        
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Введите название тест-кейса")
        self.title_input.setMinimumHeight(32)
        self.title_input.textChanged.connect(self.update_title_label)
        self.title_input.textChanged.connect(self.mark_as_changed)
        title_container.addWidget(self.title_input)
        row1.addLayout(title_container, 1)
        
        main_layout.addLayout(row1)
        
        # === Строка 2: Автор и Статус ===
        row2 = QHBoxLayout()
        row2.setSpacing(15)
        
        # Автор
        author_container = QVBoxLayout()
        author_container.setSpacing(5)
        author_label = QLabel("Автор:")
        author_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        author_container.addWidget(author_label)
        
        self.author_input = QLineEdit()
        self.author_input.setPlaceholderText("Имя автора")
        self.author_input.setMinimumHeight(32)
        self.author_input.textChanged.connect(self.mark_as_changed)
        author_container.addWidget(self.author_input)
        row2.addLayout(author_container, 1)
        
        # Статус
        status_container = QVBoxLayout()
        status_container.setSpacing(5)
        status_label = QLabel("Статус:")
        status_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        status_container.addWidget(status_label)
        
        self.status_input = QComboBox()
        self.status_input.addItems(["Draft", "In Progress", "Done", "Blocked", "Deprecated"])
        self.status_input.setMinimumHeight(32)
        self.status_input.currentTextChanged.connect(self.mark_as_changed)
        status_container.addWidget(self.status_input)
        row2.addLayout(status_container, 1)
        
        main_layout.addLayout(row2)
        
        # === Строка 3: Детали (inline, компактно) ===
        details_frame = QFrame()
        details_frame.setStyleSheet("""
            QFrame {
                background-color: #1E2732;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        details_layout = QHBoxLayout(details_frame)
        details_layout.setContentsMargins(10, 8, 10, 8)
        details_layout.setSpacing(15)
        
        # Уровень (компактный)
        level_label = QLabel("Уровень:")
        level_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        level_label.setStyleSheet("color: #8B9099;")
        details_layout.addWidget(level_label)
        
        self.level_input = QComboBox()
        self.level_input.addItems(["smoke", "critical", "major", "minor", "trivial"])
        self.level_input.setMinimumHeight(28)
        self.level_input.setMaximumWidth(120)
        self.level_input.currentTextChanged.connect(self.mark_as_changed)
        details_layout.addWidget(self.level_input)
        
        details_layout.addSpacing(10)
        
        # Use Case ID (компактный)
        usecase_label = QLabel("Use Case ID:")
        usecase_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        usecase_label.setStyleSheet("color: #8B9099;")
        details_layout.addWidget(usecase_label)
        
        self.use_case_id_input = QLineEdit()
        self.use_case_id_input.setReadOnly(True)
        self.use_case_id_input.setPlaceholderText("ID связанного use case")
        self.use_case_id_input.setMinimumHeight(28)
        self.use_case_id_input.setStyleSheet("""
            QLineEdit {
                background-color: #17212B;
                color: #6B7380;
                font-size: 9pt;
            }
        """)
        details_layout.addWidget(self.use_case_id_input, 1)
        
        main_layout.addWidget(details_frame)
        
        main_group.setLayout(main_layout)
        layout.addWidget(main_group)
        
        # Группа: Теги
        tags_group = QGroupBox("Теги")
        tags_layout = QVBoxLayout()
        
        self.tags_input = QTextEdit()
        self.tags_input.setPlaceholderText("Введите теги, каждый с новой строки")
        self.tags_input.setMaximumHeight(100)
        self.tags_input.textChanged.connect(self.mark_as_changed)
        tags_layout.addWidget(self.tags_input)
        
        tags_group.setLayout(tags_layout)
        layout.addWidget(tags_group)
        
        # Сворачиваемая секция: Предусловия
        precondition_box = CollapsibleBox("▼ Предусловия")
        precondition_layout = QVBoxLayout()
        precondition_layout.setContentsMargins(0, 5, 0, 0)
        
        self.precondition_input = QTextEdit()
        self.precondition_input.setPlaceholderText("Введите предусловия для выполнения тест-кейса")
        self.precondition_input.setMinimumHeight(80)
        self.precondition_input.setMaximumHeight(120)
        self.precondition_input.textChanged.connect(self.mark_as_changed)
        precondition_layout.addWidget(self.precondition_input)
        
        precondition_box.set_content_layout(precondition_layout)
        layout.addWidget(precondition_box)
        
        # Сворачиваемая секция: Шаги тестирования
        actions_box = CollapsibleBox("▼ Шаги тестирования")
        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(0, 5, 0, 0)
        actions_layout.setSpacing(10)
        
        # Таблица для шагов
        self.actions_table = QTableWidget()
        self.actions_table.setColumnCount(2)
        self.actions_table.setHorizontalHeaderLabels(["Действие", "Ожидаемый результат"])
        self.actions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.actions_table.verticalHeader().setVisible(True)
        self.actions_table.setMinimumHeight(250)
        self.actions_table.setAlternatingRowColors(True)
        self.actions_table.itemChanged.connect(self.mark_as_changed)
        
        # Настройка внешнего вида таблицы
        self.actions_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #2B3945;
                background-color: #17212B;
                border: 1px solid #2B3945;
                border-radius: 8px;
                outline: 0;
            }
            QTableWidget::item {
                padding: 10px;
                color: #E1E3E6;
                background-color: #17212B;
                border: none;
                outline: 0;
            }
            QTableWidget::item:selected {
                background-color: #2B5278;
                color: #FFFFFF;
                border: none;
                outline: 0;
            }
            QTableWidget::item:focus {
                background-color: #2B5278;
                color: #FFFFFF;
                border: none;
                outline: 0;
            }
            QTableWidget::item:hover {
                background-color: #1E2732;
            }
            QHeaderView::section {
                background-color: #17212B;
                color: #E1E3E6;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #2B3945;
                font-weight: bold;
            }
        """)
        
        actions_layout.addWidget(self.actions_table)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        btn_add_action = QPushButton("➕ Добавить шаг")
        btn_add_action.clicked.connect(self.add_action_row)
        btn_add_action.setMinimumHeight(35)
        buttons_layout.addWidget(btn_add_action)
        
        btn_remove_action = QPushButton("➖ Удалить выбранный")
        btn_remove_action.clicked.connect(self.remove_action_row)
        btn_remove_action.setMinimumHeight(35)
        buttons_layout.addWidget(btn_remove_action)
        
        btn_move_up = QPushButton("⬆️ Вверх")
        btn_move_up.clicked.connect(self.move_action_up)
        btn_move_up.setMinimumHeight(35)
        buttons_layout.addWidget(btn_move_up)
        
        btn_move_down = QPushButton("⬇️ Вниз")
        btn_move_down.clicked.connect(self.move_action_down)
        btn_move_down.setMinimumHeight(35)
        buttons_layout.addWidget(btn_move_down)
        
        actions_layout.addLayout(buttons_layout)
        
        actions_box.set_content_layout(actions_layout)
        layout.addWidget(actions_box)
        
        layout.addStretch()
        
        scroll.setWidget(form_widget)
        form_layout.addWidget(scroll)
        
        return form_container
        
    def create_field(self, parent_layout: QVBoxLayout, label_text: str, widget: QWidget) -> QWidget:
        """Создание поля формы с подписью"""
        label = QLabel(label_text)
        label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        parent_layout.addWidget(label)
        parent_layout.addWidget(widget)
        return widget
        
    def add_action_row(self, step_text: str = "", expected_res: str = ""):
        """Добавление строки в таблицу шагов"""
        row_position = self.actions_table.rowCount()
        self.actions_table.insertRow(row_position)
        
        # Создаем ячейки с текстом
        step_item = QTableWidgetItem(step_text)
        expected_item = QTableWidgetItem(expected_res)
        
        # Настройка переноса текста
        step_item.setFlags(step_item.flags() | Qt.ItemIsEditable)
        expected_item.setFlags(expected_item.flags() | Qt.ItemIsEditable)
        
        self.actions_table.setItem(row_position, 0, step_item)
        self.actions_table.setItem(row_position, 1, expected_item)
        
        # Устанавливаем высоту строки
        self.actions_table.setRowHeight(row_position, 80)
        
    def remove_action_row(self):
        """Удаление выбранной строки из таблицы"""
        current_row = self.actions_table.currentRow()
        if current_row >= 0:
                self.actions_table.removeRow(current_row)
    
    def move_action_up(self):
        """Переместить шаг вверх"""
        current_row = self.actions_table.currentRow()
        if current_row > 0:
            self.swap_table_rows(current_row, current_row - 1)
            self.actions_table.setCurrentCell(current_row - 1, 0)
    
    def move_action_down(self):
        """Переместить шаг вниз"""
        current_row = self.actions_table.currentRow()
        if current_row >= 0 and current_row < self.actions_table.rowCount() - 1:
            self.swap_table_rows(current_row, current_row + 1)
            self.actions_table.setCurrentCell(current_row + 1, 0)
    
    def swap_table_rows(self, row1: int, row2: int):
        """Поменять местами две строки в таблице"""
        for col in range(self.actions_table.columnCount()):
            item1 = self.actions_table.takeItem(row1, col)
            item2 = self.actions_table.takeItem(row2, col)
            self.actions_table.setItem(row1, col, item2)
            self.actions_table.setItem(row2, col, item1)
                    
    def load_test_cases(self):
        """Загрузка всех тест-кейсов из директории с поддержкой папок"""
        self.test_cases = []
        self.test_cases_tree.clear()
        
        if not self.test_cases_dir.exists():
            self.statusBar().showMessage("Директория test_cases не найдена")
            return
            
        # Загружаем папки и файлы рекурсивно
        self.load_directory_recursive(self.test_cases_dir, self.test_cases_tree)
        
        # Развернуть все папки
        self.test_cases_tree.expandAll()
        
        # Обновление счетчика файлов
        self.file_count_label.setText(f"({len(self.test_cases)})")
        self.statusBar().showMessage(f"Загружено тест-кейсов: {len(self.test_cases)}")
    
    def load_directory_recursive(self, directory: Path, parent_item):
        """Рекурсивная загрузка директории"""
        # Загружаем папки
        subdirs = sorted([d for d in directory.iterdir() if d.is_dir()])
        for subdir in subdirs:
            folder_item = QTreeWidgetItem(parent_item)
            folder_item.setText(0, f"📁 {subdir.name}")
            folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'path': subdir})
            folder_item.setFont(0, QFont("Segoe UI", 10, QFont.Bold))
            
            # Рекурсивно загружаем содержимое папки
            self.load_directory_recursive(subdir, folder_item)
        
        # Загружаем файлы
        json_files = sorted(list(directory.glob("*.json")))
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    test_case = json.load(f)
                    test_case['_filename'] = json_file.name
                    test_case['_filepath'] = json_file
                    self.test_cases.append(test_case)
                    
                    # Создаем элемент дерева
                    status = test_case.get('status', 'Draft')
                    status_icon = self.get_status_icon_text(status)
                    status_color = self.get_status_color_text(status)
                    title = test_case.get('title', 'Без названия')
                    
                    item = QTreeWidgetItem(parent_item)
                    item.setText(0, f"{status_icon} {title}")
                    item.setData(0, Qt.UserRole, {'type': 'file', 'test_case': test_case})
                    item.setFont(0, QFont("Segoe UI", 10))
                    item.setForeground(0, QColor(status_color))
                        
            except Exception as e:
                print(f"Ошибка загрузки {json_file}: {e}")
                # Добавляем элемент с ошибкой
                error_item = QTreeWidgetItem(parent_item)
                error_item.setText(0, f"⚠️ {json_file.name} (ошибка)")
                error_item.setForeground(0, QColor("#F5555D"))
    
    def get_status_icon_text(self, status: str) -> str:
        """Получить иконку статуса для дерева"""
        icons = {
            'Done': '✓',
            'Blocked': '⚠',
            'In Progress': '⟳',
            'Draft': '○',
            'Deprecated': '×'
        }
        return icons.get(status, '○')
    
    def get_status_color_text(self, status: str) -> str:
        """Получить цвет статуса"""
        colors = {
            'Done': '#6CC24A',
            'Blocked': '#F5555D',
            'In Progress': '#FFA931',
            'Draft': '#8B9099',
            'Deprecated': '#6B7380'
        }
        return colors.get(status, '#E1E3E6')
        
    def on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Обработка клика по элементу дерева"""
        data = item.data(0, Qt.UserRole)
        if data and data.get('type') == 'file':
            test_case = data.get('test_case')
            if test_case:
                self.current_test_case = test_case
                self.load_test_case_to_form(test_case)
    
    def on_test_case_clicked(self, test_case: Dict):
        """Обработка клика по тест-кейсу (для старого списка)"""
        self.current_test_case = test_case
        self.load_test_case_to_form(test_case)
    
    def mark_as_changed(self):
        """Пометить форму как измененную"""
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            self.save_button.setVisible(True)
    
    def mark_as_saved(self):
        """Пометить форму как сохраненную"""
        self.has_unsaved_changes = False
        self.save_button.setVisible(False)
    
    def update_title_label(self):
        """Обновление заголовка с названием тест-кейса при изменении"""
        title = self.title_input.text().strip()
        if not title:
            title = "Без названия"
        self.testcase_title_label.setText(title)
    
    def load_test_case_to_form(self, test_case: Dict):
        """Загрузка тест-кейса в форму редактирования"""
        # Отключаем отслеживание изменений при загрузке
        self.has_unsaved_changes = False
        self.save_button.setVisible(False)
        
        # Обновление заголовка с названием тест-кейса
        title = test_case.get('title', 'Без названия')
        self.testcase_title_label.setText(title)
        
        # Основные поля
        self.id_input.setText(test_case.get('id', ''))
        self.title_input.setText(test_case.get('title', ''))
        self.author_input.setText(test_case.get('author', ''))
        
        # Status
        status = test_case.get('status', 'Draft')
        index = self.status_input.findText(status)
        if index >= 0:
            self.status_input.setCurrentIndex(index)
            
        # Level
        level = test_case.get('level', 'minor')
        index = self.level_input.findText(level)
        if index >= 0:
            self.level_input.setCurrentIndex(index)
            
        self.use_case_id_input.setText(test_case.get('useCaseId', ''))
        
        # Теги
        tags = test_case.get('tags', [])
        self.tags_input.setText('\n'.join(tags))
        
        # Предусловия
        self.precondition_input.setText(test_case.get('precondition', ''))
        
        # Очистка и загрузка шагов
        self.actions_table.setRowCount(0)
        
        for action in test_case.get('actions', []):
            self.add_action_row(
                action.get('step', ''),
                action.get('expected_res', '')
            )
            
        self.statusBar().showMessage(f"Открыт: {test_case.get('title', '')}")
        
    def get_form_data(self) -> Dict:
        """Получение данных из формы"""
        # Сбор шагов из таблицы
        actions = []
        for row in range(self.actions_table.rowCount()):
            step_item = self.actions_table.item(row, 0)
            expected_item = self.actions_table.item(row, 1)
            
            step_text = step_item.text() if step_item else ""
            expected_text = expected_item.text() if expected_item else ""
            
            actions.append({
                'step': step_text,
                'expected_res': expected_text
            })
                
        # Сбор тегов
        tags_text = self.tags_input.toPlainText().strip()
        tags = [tag.strip() for tag in tags_text.split('\n') if tag.strip()]
        
        return {
            'id': self.id_input.text(),
            'title': self.title_input.text(),
            'author': self.author_input.text(),
            'tags': tags,
            'status': self.status_input.currentText(),
            'useCaseId': self.use_case_id_input.text(),
            'level': self.level_input.currentText(),
            'precondition': self.precondition_input.toPlainText(),
            'actions': actions
        }
        
    def save_current_test_case(self):
        """Сохранение текущего тест-кейса"""
        if not self.current_test_case:
            QMessageBox.warning(self, "Предупреждение", "Не выбран тест-кейс для сохранения")
            return
            
        data = self.get_form_data()
        
        if not data['title']:
            QMessageBox.warning(self, "Ошибка", "Название тест-кейса обязательно")
            return
            
        # Сохранение в файл - используем _filepath если есть
        if '_filepath' in self.current_test_case:
            filepath = self.current_test_case['_filepath']
        else:
            filename = self.current_test_case.get('_filename', f"tc_{data['id'][:8]}.json")
            filepath = self.test_cases_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            self.mark_as_saved()  # Скрываем кнопку после успешного сохранения
            self.load_test_cases()
            filename = Path(filepath).name
            self.statusBar().showMessage(f"Сохранено: {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл:\n{e}")
            
    def create_new_test_case(self, target_folder=None):
        """Создание нового тест-кейса"""
        if target_folder is None:
            target_folder = self.test_cases_dir
        
        new_id = str(uuid.uuid4())
        filename = f'tc_new_{uuid.uuid4().hex[:8]}.json'
        
        new_test_case = {
            'id': new_id,
            'title': 'Новый тест-кейс',
            'author': '',
            'tags': [],
            'status': 'Draft',
            'useCaseId': '',
            'level': 'minor',
            'precondition': '',
            'actions': [],
            '_filename': filename,
            '_filepath': target_folder / filename
        }
        
        # Сохраняем пустой тест-кейс
        try:
            filepath = target_folder / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({k: v for k, v in new_test_case.items() if not k.startswith('_')}, 
                         f, ensure_ascii=False, indent=4)
            
            self.load_test_cases()
            self.current_test_case = new_test_case
            self.load_test_case_to_form(new_test_case)
            self.statusBar().showMessage(f"Создан новый тест-кейс: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать тест-кейс:\n{e}")
        
    def delete_test_case(self):
        """Удаление текущего тест-кейса"""
        if not self.current_test_case:
            return
            
        # Используем _filepath если есть
        if '_filepath' in self.current_test_case:
            filepath = self.current_test_case['_filepath']
        else:
            filename = self.current_test_case.get('_filename')
            filepath = self.test_cases_dir / filename if filename else None
        
        if filepath:
            try:
                Path(filepath).unlink()
                self.current_test_case = None
                self.load_test_cases()
                self.statusBar().showMessage("Тест-кейс удален")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить файл:\n{e}")
    
    def show_context_menu_list(self, position):
        """Показать контекстное меню для выбранного тест-кейса"""
        item = self.test_cases_list.itemAt(position)
        if not item:
            return
        
        test_case = item.data(Qt.UserRole)
        if not test_case:
            return
        
        self.show_context_menu(position, test_case)
    
    def show_context_menu(self, position, test_case: Dict):
        """Показать контекстное меню для файла"""
        menu = QMenu(self)
        menu.setStyleSheet("""
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
            }
            QMenu::item:selected {
                background-color: #2B5278;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2B3945;
                margin: 5px 10px;
            }
        """)
        
        # Пункты меню
        action_open = QAction("📂 Открыть", self)
        action_open.triggered.connect(lambda: self.on_test_case_clicked(test_case))
        menu.addAction(action_open)
        
        action_rename = QAction("✏️ Переименовать файл", self)
        action_rename.triggered.connect(lambda: self.rename_file(test_case))
        menu.addAction(action_rename)
        
        action_duplicate = QAction("📋 Дублировать", self)
        action_duplicate.triggered.connect(lambda: self.duplicate_test_case(test_case))
        menu.addAction(action_duplicate)
        
        menu.addSeparator()
        
        action_delete = QAction("🗑️ Удалить", self)
        action_delete.triggered.connect(lambda: self.delete_specific_test_case(test_case))
        menu.addAction(action_delete)
        
        # Показать меню
        menu.exec_(self.test_cases_tree.mapToGlobal(position))
        
    def rename_file(self, test_case: Dict):
        """Переименование файла тест-кейса"""
        old_filename = test_case.get('_filename', '')
        if not old_filename:
            return
        
        new_filename, ok = QInputDialog.getText(
            self, 
            'Переименовать файл',
            'Новое имя файла:',
            text=old_filename
        )
        
        if ok and new_filename and new_filename != old_filename:
            # Проверка расширения
            if not new_filename.endswith('.json'):
                new_filename += '.json'
            
            # Используем _filepath если есть
            if '_filepath' in test_case:
                old_path = Path(test_case['_filepath'])
                new_path = old_path.parent / new_filename
            else:
                old_path = self.test_cases_dir / old_filename
                new_path = self.test_cases_dir / new_filename
            
            if new_path.exists():
                self.statusBar().showMessage(f"Файл {new_filename} уже существует")
                return
            
            try:
                old_path.rename(new_path)
                test_case['_filename'] = new_filename
                self.load_test_cases()
                self.statusBar().showMessage(f"Файл переименован: {new_filename}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать файл:\n{e}")
    
    def duplicate_test_case(self, test_case: Dict):
        """Дублирование тест-кейса"""
        # Создаем копию
        new_test_case = copy.deepcopy(test_case)
        new_test_case['id'] = str(uuid.uuid4())
        new_test_case['title'] = f"{new_test_case.get('title', 'Тест-кейс')} (копия)"
        
        # Генерируем новое имя файла
        original_filename = test_case.get('_filename', 'tc.json')
        base_name = original_filename.replace('.json', '')
        new_filename = f"{base_name}_copy_{uuid.uuid4().hex[:8]}.json"
        new_test_case['_filename'] = new_filename
        
        # Определяем путь сохранения (в той же папке, что и оригинал)
        if '_filepath' in test_case:
            original_path = Path(test_case['_filepath'])
            filepath = original_path.parent / new_filename
        else:
            filepath = self.test_cases_dir / new_filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({k: v for k, v in new_test_case.items() if not k.startswith('_')}, 
                         f, ensure_ascii=False, indent=4)
            
            self.load_test_cases()
            self.statusBar().showMessage(f"Создана копия: {new_filename}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось дублировать:\n{e}")
    
    def delete_specific_test_case(self, test_case: Dict):
        """Удаление конкретного тест-кейса"""
        self.current_test_case = test_case
        self.delete_test_case()
    
    def create_folder(self, parent_dir=None):
        """Создание новой папки"""
        if parent_dir is None:
            current_item = self.test_cases_tree.currentItem()
            
            # Определяем родительскую директорию
            if current_item:
                data = current_item.data(0, Qt.UserRole)
                if data and data.get('type') == 'folder':
                    parent_dir = data['path']
                else:
                    parent_dir = self.test_cases_dir
            else:
                parent_dir = self.test_cases_dir
        
        # Запрашиваем имя папки
        folder_name, ok = QInputDialog.getText(
            self, 
            'Создать папку',
            'Имя папки:',
            text='Новая папка'
        )
        
        if ok and folder_name:
            new_folder = parent_dir / folder_name
            try:
                new_folder.mkdir(exist_ok=True)
                self.load_test_cases()
                self.statusBar().showMessage(f"Создана папка: {folder_name}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать папку:\n{e}")
    
    def rename_folder(self):
        """Переименование папки или файла"""
        current_item = self.test_cases_tree.currentItem()
        if not current_item:
            return
        
        data = current_item.data(0, Qt.UserRole)
        if not data:
            return
        
        if data.get('type') == 'folder':
            old_path = data['path']
            old_name = old_path.name
            
            new_name, ok = QInputDialog.getText(
                self, 
                'Переименовать папку',
                'Новое имя:',
                text=old_name
            )
            
            if ok and new_name and new_name != old_name:
                new_path = old_path.parent / new_name
                try:
                    old_path.rename(new_path)
                    self.load_test_cases()
                    self.statusBar().showMessage(f"Папка переименована: {new_name}")
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать папку:\n{e}")
        
        elif data.get('type') == 'file':
            test_case = data['test_case']
            self.rename_file(test_case)
    
    def delete_folder(self):
        """Удаление папки"""
        current_item = self.test_cases_tree.currentItem()
        if not current_item:
            return
        
        data = current_item.data(0, Qt.UserRole)
        if not data or data.get('type') != 'folder':
            return
        
        folder_path = data['path']
        folder_name = folder_path.name
        
        try:
            import shutil
            shutil.rmtree(folder_path)
            self.load_test_cases()
            self.statusBar().showMessage(f"Папка удалена: {folder_name}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить папку:\n{e}")
    
    def show_tree_context_menu(self, position):
        """Показать контекстное меню для дерева"""
        item = self.test_cases_tree.itemAt(position)
        
        if not item:
            # Клик на пустом месте - показываем меню создания папки в корне
            self.show_root_context_menu(position)
            return
        
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        
        if data.get('type') == 'folder':
            self.show_folder_context_menu(position, data)
        elif data.get('type') == 'file':
            test_case = data.get('test_case')
            if test_case:
                self.show_context_menu(position, test_case)
    
    def show_root_context_menu(self, position):
        """Показать контекстное меню для корня (пустого места)"""
        menu = QMenu(self)
        menu.setStyleSheet("""
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
            }
            QMenu::item:selected {
                background-color: #2B5278;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2B3945;
                margin: 5px 10px;
            }
        """)
        
        # Создать тест-кейс в корне
        action_new_testcase = QAction("➕ Создать тест-кейс", self)
        action_new_testcase.triggered.connect(lambda: self.create_new_test_case(self.test_cases_dir))
        menu.addAction(action_new_testcase)
        
        menu.addSeparator()
        
        # Создать папку в корне
        action_new_folder = QAction("📁 Создать папку", self)
        action_new_folder.triggered.connect(lambda: self.create_folder(self.test_cases_dir))
        menu.addAction(action_new_folder)
        
        # Показать меню
        menu.exec_(self.test_cases_tree.mapToGlobal(position))
    
    def show_folder_context_menu(self, position, folder_data):
        """Показать контекстное меню для папки"""
        menu = QMenu(self)
        menu.setStyleSheet("""
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
            }
            QMenu::item:selected {
                background-color: #2B5278;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2B3945;
                margin: 5px 10px;
            }
        """)
        
        folder_path = folder_data.get('path')
        
        # Создать тест-кейс в этой папке
        action_new_testcase = QAction("➕ Создать тест-кейс", self)
        action_new_testcase.triggered.connect(lambda: self.create_new_test_case(folder_path))
        menu.addAction(action_new_testcase)
        
        # Создать подпапку
        action_new_folder = QAction("📁 Создать подпапку", self)
        action_new_folder.triggered.connect(lambda: self.create_folder())
        menu.addAction(action_new_folder)
        
        menu.addSeparator()
        
        # Переименовать
        action_rename = QAction("✏️ Переименовать", self)
        action_rename.triggered.connect(lambda: self.rename_folder())
        menu.addAction(action_rename)
        
        # Удалить папку
        action_delete = QAction("🗑️ Удалить папку", self)
        action_delete.triggered.connect(lambda: self.delete_folder())
        menu.addAction(action_delete)
        
        # Показать меню
        menu.exec_(self.test_cases_tree.mapToGlobal(position))
    
    def filter_tree(self):
        """Фильтрация дерева тест-кейсов по поисковому запросу"""
        search_text = self.search_input.text().lower()
        
        if not search_text:
            # Показываем все элементы
            self.show_all_tree_items(self.test_cases_tree.invisibleRootItem())
            self.file_count_label.setText(f"({len(self.test_cases)})")
            self.statusBar().showMessage(f"Загружено тест-кейсов: {len(self.test_cases)}")
            return
        
        # Фильтруем элементы
        visible_count = self.filter_tree_recursive(self.test_cases_tree.invisibleRootItem(), search_text)
        
        # Обновляем счетчик
        self.file_count_label.setText(f"({visible_count}/{len(self.test_cases)})")
        self.statusBar().showMessage(f"Найдено: {visible_count} из {len(self.test_cases)}")
    
    def show_all_tree_items(self, parent_item):
        """Показать все элементы дерева"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setHidden(False)
            self.show_all_tree_items(child)
    
    def filter_tree_recursive(self, parent_item, search_text) -> int:
        """Рекурсивная фильтрация дерева, возвращает количество видимых элементов"""
        visible_count = 0
        
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            data = child.data(0, Qt.UserRole)
            
            if data and data.get('type') == 'file':
                # Проверяем файл
                test_case = data['test_case']
                title = test_case.get('title', '').lower()
                status = test_case.get('status', '').lower()
                filename = test_case.get('_filename', '').lower()
                tags = ' '.join(test_case.get('tags', [])).lower()
                
                match = (search_text in title or 
                    search_text in status or 
                        search_text in filename or
                        search_text in tags)
                
                child.setHidden(not match)
                if match:
                    visible_count += 1
            
            elif data and data.get('type') == 'folder':
                # Рекурсивно проверяем папку
                child_visible = self.filter_tree_recursive(child, search_text)
                # Папка видима, если есть видимые дочерние элементы
                child.setHidden(child_visible == 0)
                visible_count += child_visible
        
        return visible_count
                    
    def apply_telegram_theme(self):
        """Применение темы Telegram Dark"""
        telegram_stylesheet = """
        QMainWindow {
            background-color: #0E1621;
        }
        
        QWidget {
            background-color: #17212B;
            color: #E1E3E6;
            font-family: 'Segoe UI', 'Arial', sans-serif;
            font-size: 10pt;
        }
        
        QTableView {
            background-color: #17212B;
            border: none;
            border-radius: 12px;
            color: #E1E3E6;
            outline: 0;
        }
        
        QTableView::item {
            padding: 10px;
            border-bottom: 1px solid #2B3945;
            color: #E1E3E6;
        }
        
        QTableView::item:selected {
            background-color: #2B5278;
            color: #FFFFFF;
        }
        
        QTableView::item:hover {
            background-color: #1E2732;
        }
        
        QHeaderView::section {
            background-color: #17212B;
            color: #8B9099;
            padding: 12px 10px;
            border: none;
            border-bottom: 2px solid #2B3945;
            font-weight: 600;
            font-size: 9pt;
        }
        
        QLineEdit, QTextEdit, QComboBox {
            background-color: #1E2732;
            border: 1px solid #2B3945;
            border-radius: 6px;
            padding: 8px;
            color: #E1E3E6;
            selection-background-color: #2B5278;
        }
        
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border: 2px solid #5288C1;
            background-color: #1E2732;
        }
        
        QLineEdit:read-only {
            background-color: #17212B;
            color: #8B9099;
            border: 1px solid #2B3945;
        }
        
        QPushButton {
            background-color: #2B5278;
            border: 1px solid #3D6A98;
            border-radius: 8px;
            padding: 10px 18px;
            color: #FFFFFF;
            font-weight: 600;
        }
        
        QPushButton:hover {
            background-color: #3D6A98;
            border: 1px solid #5288C1;
        }
        
        QPushButton:pressed {
            background-color: #1D3F5F;
        }
        
        QGroupBox {
            border: 1px solid #2B3945;
            border-radius: 10px;
            margin-top: 12px;
            padding-top: 12px;
            font-weight: bold;
            color: #5288C1;
            background-color: #17212B;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 5px 12px;
            color: #5288C1;
            background-color: transparent;
        }
        
        QLabel {
            background-color: transparent;
            color: #E1E3E6;
        }
        
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        
        QScrollBar:vertical {
            background-color: #17212B;
            width: 12px;
            border-radius: 6px;
            border: none;
        }
        
        QScrollBar::handle:vertical {
            background-color: #2B3945;
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #3D6A98;
        }
        
        QScrollBar:horizontal {
            background-color: #17212B;
            height: 12px;
            border-radius: 6px;
            border: none;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #2B3945;
            border-radius: 6px;
            min-width: 20px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #3D6A98;
        }
        
        QScrollBar::add-line, QScrollBar::sub-line {
            border: none;
            background: none;
        }
        
        QFrame[frameShape="4"], QFrame[frameShape="5"] {
            border: 1px solid #2B3945;
        }
        
        QStatusBar {
            background-color: #17212B;
            color: #E1E3E6;
            border-top: 1px solid #2B3945;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #5288C1;
            margin-right: 5px;
        }
        
        QComboBox QAbstractItemView {
            background-color: #1E2732;
            border: 1px solid #2B3945;
            border-radius: 6px;
            selection-background-color: #2B5278;
            color: #E1E3E6;
        }
        
        QTableWidget {
            background-color: #17212B;
            gridline-color: #2B3945;
            border: 1px solid #2B3945;
            border-radius: 8px;
            outline: 0;
        }
        
        QTableWidget::item {
            padding: 10px;
            color: #E1E3E6;
            background-color: #17212B;
            border: none;
            outline: 0;
        }
        
        QTableWidget::item:selected {
            background-color: #2B5278;
            color: #FFFFFF;
            border: none;
            outline: 0;
        }
        
        QTableWidget::item:focus {
            background-color: #2B5278;
            color: #FFFFFF;
            border: none;
            outline: 0;
        }
        
        QTableWidget::item:hover {
            background-color: #1E2732;
        }
        """
        
        self.setStyleSheet(telegram_stylesheet)


def main():
    """Точка входа в приложение"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    editor = TestCaseEditor()
    editor.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
