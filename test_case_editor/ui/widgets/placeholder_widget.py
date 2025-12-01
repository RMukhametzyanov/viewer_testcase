"""Виджет заглушки"""

from typing import List, Optional
from collections import Counter
from pathlib import Path
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QTableWidget, QTableWidgetItem, QToolButton, QApplication, QAbstractItemView
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

from ...models.test_case import TestCase
from ...utils.resource_path import get_icon_path


class PlaceholderWidget(QWidget):
    """
    Виджет заглушки для отображения когда не выбран тест-кейс
    
    Соответствует принципу Single Responsibility:
    отвечает только за отображение заглушки и статистики
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Настройка интерфейса"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)
        
        # Заголовок с кнопкой копирования
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        
        title_label = QLabel("Статистика тест-кейсов")
        title_font = QFont("Segoe UI", 18, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #ffffff; padding-bottom: 10px;")
        title_row.addWidget(title_label)
        
        title_row.addStretch()
        
        # Кнопка копирования
        self.copy_button = QToolButton()
        copy_icon = self._load_svg_icon("copy.svg", size=16, color="#ffffff")
        if copy_icon:
            self.copy_button.setIcon(copy_icon)
        self.copy_button.setIconSize(QSize(16, 16))
        self.copy_button.setToolTip("Копировать статистику")
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.setAutoRaise(True)
        self.copy_button.setFixedSize(24, 24)
        self.copy_button.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.2);
            }
        """)
        self.copy_button.clicked.connect(self._copy_statistics)
        title_row.addWidget(self.copy_button)
        
        main_layout.addLayout(title_row)
        
        # Область прокрутки для статистики
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        # Контейнер для статистики
        self.stats_container = QWidget()
        self.stats_layout = QVBoxLayout(self.stats_container)
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        self.stats_layout.setSpacing(8)
        
        scroll_area.setWidget(self.stats_container)
        main_layout.addWidget(scroll_area)
        
        # Инициализируем виджеты статистики
        self._init_statistics_widgets()
    
    def _init_statistics_widgets(self):
        """Инициализация виджета статистики"""
        # Таблица для статистики
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.horizontalHeader().setVisible(False)  # Скрываем заголовки
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.setShowGrid(False)
        self.stats_table.setAlternatingRowColors(False)
        self.stats_table.setSelectionMode(QAbstractItemView.NoSelection)  # Отключаем выделение
        self.stats_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stats_table.setFocusPolicy(Qt.NoFocus)  # Отключаем фокус
        self.stats_table.setStyleSheet("""
            QTableWidget {
                border: none;
                background-color: transparent;
                color: #b0b0b0;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.stats_layout.addWidget(self.stats_table)
    
    def update_count(self, count: int):
        """Обновить счетчик тест-кейсов (для обратной совместимости)"""
        # Оставляем для обратной совместимости, но не используем
        pass
    
    def update_statistics(self, test_cases: List[TestCase]):
        """Обновить статистику на основе списка тест-кейсов"""
        rows = []
        
        if not test_cases:
            rows.append(("Всего тест-кейсов", "0"))
            self._populate_table(rows)
            return
        
        total_count = len(test_cases)
        
        # Всего тест-кейсов
        rows.append(("Всего тест-кейсов", str(total_count)))
        
        # Ручных тест-кейсов
        manual_count = sum(1 for tc in test_cases 
                          if tc.test_type and tc.test_type.lower() == "manual")
        rows.append(("Ручных тест-кейсов", str(manual_count)))
        
        # Автоматизировано
        automated_count = sum(1 for tc in test_cases 
                             if tc.test_type and tc.test_type.lower() in ["automated", "auto"])
        rows.append(("Автоматизировано", str(automated_count)))
        
        # Гибридных
        hybrid_count = sum(1 for tc in test_cases 
                          if tc.test_type and tc.test_type.lower() == "hybrid")
        rows.append(("Гибридных", str(hybrid_count)))
        
        # Разделитель
        rows.append(("", ""))
        
        # Количество тест-кейсов по исполнителям
        rows.append(("Количество тест-кейсов по исполнителям", ""))
        owners_counter = Counter()
        for tc in test_cases:
            owner = tc.owner.strip() if tc.owner else "Не указан"
            owners_counter[owner] += 1
        
        # Сортируем по количеству тест-кейсов (по убыванию)
        sorted_owners = sorted(owners_counter.items(), key=lambda x: x[1], reverse=True)
        for owner, count in sorted_owners:
            rows.append((f"    {owner}", str(count)))
        
        # Разделитель
        rows.append(("", ""))
        
        # Количество по статусам
        rows.append(("Количество по статусам", ""))
        statuses_counter = Counter()
        for tc in test_cases:
            status = tc.status.strip() if tc.status else "Не указан"
            statuses_counter[status] += 1
        
        # Сортируем по количеству тест-кейсов (по убыванию)
        sorted_statuses = sorted(statuses_counter.items(), key=lambda x: x[1], reverse=True)
        for status, count in sorted_statuses:
            rows.append((f"    {status}", str(count)))
        
        # Разделитель
        rows.append(("", ""))
        
        # Количество ТК по статусу ручного ревью (resolved из notes)
        rows.append(("Количество ТК по статусу ручного ревью", ""))
        resolved_new_count = 0
        resolved_fixed_count = 0
        
        for tc in test_cases:
            has_new = False
            has_fixed = False
            if tc.notes:
                for note_data in tc.notes.values():
                    if isinstance(note_data, dict):
                        resolved = note_data.get("resolved", "").strip().lower()
                        if resolved == "new":
                            has_new = True
                        elif resolved == "fixed":
                            has_fixed = True
            # Считаем тест-кейс, если у него есть хотя бы одна note с соответствующим статусом
            if has_new:
                resolved_new_count += 1
            if has_fixed:
                resolved_fixed_count += 1
        
        rows.append(("    new", str(resolved_new_count)))
        rows.append(("    fixed", str(resolved_fixed_count)))
        
        # Разделитель
        rows.append(("", ""))
        
        # Количество по тегам
        rows.append(("Количество по тегам", ""))
        tags_counter = Counter()
        for tc in test_cases:
            if tc.tags:
                for tag in tc.tags:
                    if tag and tag.strip():
                        tags_counter[tag.strip()] += 1
        
        if tags_counter:
            # Сортируем по количеству тест-кейсов (по убыванию)
            sorted_tags = sorted(tags_counter.items(), key=lambda x: x[1], reverse=True)
            for tag, count in sorted_tags:
                rows.append((f"    {tag}", str(count)))
        else:
            rows.append(("    (нет тегов)", "0"))
        
        self._populate_table(rows)
    
    def _populate_table(self, rows: List[tuple]):
        """Заполнить таблицу данными"""
        self.stats_table.setRowCount(len(rows))
        
        for row_idx, (param, value) in enumerate(rows):
            # Параметр (левая колонка)
            param_item = QTableWidgetItem(param)
            param_item.setFlags(param_item.flags() & ~Qt.ItemIsEditable)
            self.stats_table.setItem(row_idx, 0, param_item)
            
            # Значение (правая колонка)
            value_item = QTableWidgetItem(value)
            value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
            self.stats_table.setItem(row_idx, 1, value_item)
        
        # Автоматически подгоняем ширину колонок
        self.stats_table.resizeColumnsToContents()
        # Устанавливаем минимальную ширину для первой колонки
        if self.stats_table.columnWidth(0) < 200:
            self.stats_table.setColumnWidth(0, 200)
    
    def _load_svg_icon(self, icon_name: str, size: int = 16, color: Optional[str] = None) -> Optional[QIcon]:
        """Загрузить SVG иконку из файла и вернуть QIcon."""
        icon_path = get_icon_path(icon_name)
        
        if not icon_path.exists():
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
                return None
            
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            renderer.render(painter)
            painter.end()
            
            return QIcon(pixmap)
        except Exception:
            return None
    
    def _copy_statistics(self):
        """Копировать содержимое статистики в буфер обмена"""
        clipboard = QApplication.clipboard()
        text_lines = []
        
        for row in range(self.stats_table.rowCount()):
            param_item = self.stats_table.item(row, 0)
            value_item = self.stats_table.item(row, 1)
            
            if param_item and value_item:
                param = param_item.text()
                value = value_item.text()
                
                if param and value:
                    text_lines.append(f"{param}: {value}")
                elif param:
                    text_lines.append(param)
                elif value:
                    text_lines.append(value)
        
        clipboard.setText("\n".join(text_lines))


