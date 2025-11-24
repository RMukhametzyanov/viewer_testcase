"""Дополнительная панель с переключаемыми разделами."""

from __future__ import annotations

import json
from typing import Iterable, List, Optional, Dict
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QMargins, QSize
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QToolButton,
    QButtonGroup,
    QStackedLayout,
    QLabel,
    QSizePolicy,
    QFrame,
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

from .review_panel import ReviewPanel
from .json_preview_widget import JsonPreviewWidget
from .information_panel import InformationPanel
from .files_panel import FilesPanel
from .reports_panel import ReportsPanel
from ...models import TestCase
from ..styles.ui_metrics import UI_METRICS


class AuxiliaryPanel(QWidget):
    """Правая панель с переключателями вкладок."""

    review_prompt_saved = pyqtSignal(str)
    review_enter_clicked = pyqtSignal(str, list)

    creation_prompt_saved = pyqtSignal(str)
    creation_enter_clicked = pyqtSignal(str, list)

    information_data_changed = pyqtSignal()
    generate_report_requested = pyqtSignal()  # Сигнал для запроса генерации отчета

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        methodic_path: Optional[Path] = None,
        default_review_prompt: str = "",
        default_creation_prompt: str = "",
        creation_default_files: Optional[List[Path]] = None,
    ):
        super().__init__(parent)
        self._tabs_order = ["information", "review", "creation", "json", "files", "reports"]
        self._buttons: dict[str, QToolButton] = {}
        self._methodic_path = methodic_path
        self._review_default_prompt = default_review_prompt
        self._creation_default_prompt = default_creation_prompt or "Создай ТТ"
        self._creation_default_files = creation_default_files or []
        self._last_creation_prompt_default = (self._creation_default_prompt or "").strip()
        
        # Загружаем маппинг иконок
        self._icon_mapping = self._load_icon_mapping()

        self._setup_ui()

    def _setup_ui(self):
        # Устанавливаем правильную политику размера для панели
        # Preferred по горизонтали - не расширяется автоматически
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        main_layout = QHBoxLayout(self)  # Горизонтальный layout: минипанель слева, контент справа
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Вертикальная минипанель с кнопками переключения
        self.button_panel = self._create_button_panel()
        main_layout.addWidget(self.button_panel, stretch=0)

        # Контентная область с панелями
        content_widget = QWidget()
        # Устанавливаем правильную политику размера для контентной области
        content_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        content_layout.setSpacing(UI_METRICS.section_spacing)

        self._stack = QStackedLayout()
        self._stack.setStackingMode(QStackedLayout.StackOne)

        # Вкладка информации
        self.information_panel = InformationPanel()
        self.information_panel.data_changed.connect(self.information_data_changed.emit)
        self._stack.addWidget(self.information_panel)

        # Вкладка ревью
        self.review_panel = ReviewPanel(title_text="Панель ревью")
        self.review_panel.prompt_saved.connect(self.review_prompt_saved.emit)
        self.review_panel.enter_clicked.connect(self.review_enter_clicked.emit)
        self._stack.addWidget(self.review_panel)

        # Вкладка создания ТК
        self.creation_panel = ReviewPanel(title_text="Создать ТК")
        self.creation_panel.prompt_saved.connect(self.creation_prompt_saved.emit)
        self.creation_panel.enter_clicked.connect(self.creation_enter_clicked.emit)
        self._stack.addWidget(self.creation_panel)

        # Вкладка JSON превью
        self.json_panel = JsonPreviewWidget()
        self._stack.addWidget(self.json_panel)

        # Вкладка файлов
        self.files_panel = FilesPanel()
        self._stack.addWidget(self.files_panel)
        
        # Вкладка отчетности
        self.reports_panel = ReportsPanel()
        self.reports_panel.generate_report_requested.connect(self.generate_report_requested.emit)
        self._stack.addWidget(self.reports_panel)

        content_layout.addLayout(self._stack, stretch=1)
        main_layout.addWidget(content_widget, stretch=1)

        self.ensure_creation_defaults()
        self.select_tab("information")
        
        # По умолчанию показываем панели Ревью и Создать ТК (режим редактирования по умолчанию)
        # Они будут показаны/скрыты при вызове set_panels_visible из main_window
        self.set_panels_visible(True, True)

    def _load_icon_mapping(self) -> Dict[str, str]:
        """Загрузить маппинг панелей на иконки из JSON файла."""
        # Определяем путь к файлу маппинга относительно корня проекта
        project_root = Path(__file__).parent.parent.parent.parent
        mapping_file = project_root / "icons" / "icon_mapping.json"
        
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Поддерживаем как старый формат (плоский), так и новый (с секциями)
                    if isinstance(data, dict) and 'panels' in data:
                        return data.get('panels', {})
                    else:
                        # Старый формат - возвращаем как есть
                        return data
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка загрузки маппинга иконок: {e}")
        
        # Возвращаем значения по умолчанию, если файл не найден
        return {
            "information": "info.svg",
            "review": "eye.svg",
            "creation": "file-plus.svg",
            "json": "code.svg",
            "files": "file.svg",
            "reports": "book.svg"
        }

    def _load_svg_icon(self, icon_name: str, size: int = 24, color: Optional[str] = None) -> Optional[QIcon]:
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

    def _create_button_panel(self) -> QWidget:
        """Создать вертикальную минипанель с иконками для переключения панелей."""
        panel = QWidget()
        panel.setFixedWidth(50)  # Фиксированная ширина минипанели
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        button_group = QButtonGroup(self)
        button_group.setExclusive(True)

        # Маппинг панелей на подсказки
        tooltips = {
            "information": "Информация",
            "review": "Ревью",
            "creation": "Создать ТК",
            "json": "JSON превью",
            "files": "Файлы",
            "reports": "Отчетность",
        }

        for index, tab_id in enumerate(self._tabs_order):
            button = QToolButton()
            
            # Загружаем иконку из SVG файла
            icon_name = self._icon_mapping.get(tab_id)
            if icon_name:
                # Используем белый цвет для иконок (можно настроить под тему)
                icon = self._load_svg_icon(icon_name, size=20, color="#ffffff")
                if icon:
                    button.setIcon(icon)
                    button.setIconSize(QSize(20, 20))
                else:
                    # Fallback на текст, если иконка не загрузилась
                    button.setText("?")
            else:
                # Fallback на текст, если иконка не найдена в маппинге
                button.setText("?")
            
            button.setToolTip(tooltips.get(tab_id, tab_id))
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setAutoRaise(True)
            button.setFixedSize(40, 40)  # Квадратные кнопки, немного больше чем в шагах
            button.setProperty("tab_id", tab_id)
            
            # Минималистичный стиль кнопки (по умолчанию неактивная)
            button.setStyleSheet(self._get_button_style(False))
            
            button_group.addButton(button, index)
            
            # Подключаем обработчик клика
            button.clicked.connect(
                lambda checked, idx=index: 
                checked and self._stack.setCurrentIndex(idx)
            )
            # При изменении состояния checked обновляем стиль (для визуальной индикации)
            button.toggled.connect(
                lambda checked, btn=button: 
                self._update_button_style(btn, checked)
            )
            
            layout.addWidget(button)
            self._buttons[tab_id] = button

        layout.addStretch()  # Растягиваем пространство, чтобы кнопки были сверху
        
        return panel

    @staticmethod
    def _get_button_style(is_active: bool) -> str:
        """Получить стиль для кнопки переключения панели.
        
        Важно: border-width всегда 1px, чтобы кнопка не "скакала" при активации.
        При активации меняется только цвет границы и фон.
        """
        if is_active:
            # Стиль активной (прожатой) кнопки - только обводка, без фона
            return """
                QToolButton {
                    background-color: transparent;
                    border: 1px solid rgba(255, 255, 255, 0.4);
                    border-radius: 6px;
                    padding: 0px;
                    min-width: 40px;
                    max-width: 40px;
                    min-height: 40px;
                    max-height: 40px;
                    font-size: 16px;
                    font-weight: 500;
                }
                QToolButton:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                    border-color: rgba(255, 255, 255, 0.5);
                }
            """
        else:
            # Стиль неактивной кнопки - прозрачная граница того же размера
            return """
                QToolButton {
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    padding: 0px;
                    min-width: 40px;
                    max-width: 40px;
                    min-height: 40px;
                    max-height: 40px;
                    font-size: 16px;
                    font-weight: 400;
                }
                QToolButton:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                    border-color: rgba(255, 255, 255, 0.15);
                }
            """


    @staticmethod
    def _update_button_style(button: QToolButton, is_active: bool):
        """Обновить стиль кнопки в зависимости от состояния."""
        button.setStyleSheet(AuxiliaryPanel._get_button_style(is_active))

    @staticmethod
    def _build_placeholder(title: str) -> QWidget:
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addStretch()

        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        comment = QLabel("Раздел находится в разработке.")
        comment.setAlignment(Qt.AlignCenter)
        layout.addWidget(comment)

        layout.addStretch()
        return container

    # ------------------------------------------------------------------ review

    def select_tab(self, tab_id: str):
        """Активировать вкладку по идентификатору."""
        if tab_id not in self._tabs_order:
            tab_id = "information"

        index = self._tabs_order.index(tab_id)
        self._stack.setCurrentIndex(index)

        # Обновляем состояние всех кнопок
        for btn_tab_id, button in self._buttons.items():
            if btn_tab_id == tab_id:
                button.setChecked(True)
                self._update_button_style(button, True)
            else:
                button.setChecked(False)
                self._update_button_style(button, False)

        if tab_id == "creation":
            self.ensure_creation_defaults()

    # ------------------------------------------------------------------ information

    def set_information_test_case(self, test_case: Optional[TestCase]):
        """Установить тест-кейс для панели информации"""
        if hasattr(self, "information_panel"):
            self.information_panel.load_test_case(test_case)

    def update_information_test_case(self, test_case: TestCase):
        """Обновить тест-кейс данными из панели информации"""
        if hasattr(self, "information_panel") and test_case:
            self.information_panel.update_test_case(test_case)

    def set_information_edit_mode(self, enabled: bool):
        """Установить режим редактирования для панели информации"""
        if hasattr(self, "information_panel"):
            self.information_panel.set_edit_mode(enabled)

    # ------------------------------------------------------------------ files

    def set_files_test_case(self, test_case: Optional[TestCase]):
        """Установить тест-кейс для панели файлов"""
        if hasattr(self, "files_panel"):
            self.files_panel.load_test_case(test_case)
    
    # ------------------------------------------------------------------ reports

    def update_reports_panel(self):
        """Обновить панель отчетности"""
        if hasattr(self, "reports_panel"):
            self.reports_panel.refresh_reports()

    # ------------------------------------------------------------------ review

    def set_review_attachments(self, attachments: Iterable[Path]):
        self.review_panel.set_attachments(attachments)

    def set_review_prompt_text(self, text: str):
        self.review_panel.set_prompt_text(text)

    def clear_review_response(self):
        self.review_panel.clear_response()

    def set_review_loading_state(self, is_loading: bool):
        self.review_panel.set_loading_state(is_loading)

    def set_review_response_text(self, text: str):
        self.review_panel.set_response_text(text)

    def set_review_error(self, message: str):
        self.review_panel.set_response_text(message)
        self.review_panel.set_loading_state(False)

    def set_review_files(self, files: List[Path]):
        self.review_panel.set_attachments(files)

    # ---------------------------------------------------------------- creation

    def ensure_creation_defaults(self):
        existing = set(self.creation_panel.get_attachments())
        new_files: List[Path] = []

        if self._methodic_path and self._methodic_path.exists() and self._methodic_path not in existing:
            new_files.append(self._methodic_path)

        for extra in self._creation_default_files:
            if extra and extra.exists() and extra not in existing:
                new_files.append(extra)

        if new_files:
            self.creation_panel.add_attachments(new_files)

        current_prompt = (self.creation_panel.get_prompt_text() or "").strip()
        default_clean = (self._creation_default_prompt or "").strip()
        if not current_prompt or current_prompt == self._last_creation_prompt_default:
            self.creation_panel.set_prompt_text(self._creation_default_prompt)
        self.creation_panel.clear_response()
        self._last_creation_prompt_default = default_clean

    def set_creation_loading_state(self, is_loading: bool):
        self.creation_panel.set_loading_state(is_loading)

    def set_creation_response_text(self, text: str):
        self.creation_panel.set_response_text(text)

    def set_creation_default_prompt(self, text: str):
        self._creation_default_prompt = text or "Создай ТТ"
        self._last_creation_prompt_default = (self._creation_default_prompt or "").strip()
        self.creation_panel.set_prompt_text(self._creation_default_prompt)
        self.creation_panel.clear_response()

    # ---------------------------------------------------------------- JSON

    def set_json_test_case(self, test_case: Optional[TestCase]):
        if not hasattr(self, "json_panel"):
            return
        if test_case:
            self.json_panel.show_test_case(test_case)
        else:
            self.json_panel.clear()


    def set_panels_enabled(self, review_enabled: bool, creation_enabled: bool):
        self.review_panel.setEnabled(review_enabled)
        self.creation_panel.setEnabled(creation_enabled)
        if button := self._buttons.get("review"):
            button.setEnabled(review_enabled)
        if button := self._buttons.get("creation"):
            button.setEnabled(creation_enabled)

    def set_panels_visible(self, review_visible: bool, creation_visible: bool):
        """Установить видимость кнопок панелей Ревью и Создать ТК.
        
        Args:
            review_visible: True для показа кнопки Ревью, False для скрытия
            creation_visible: True для показа кнопки Создать ТК, False для скрытия
        """
        if button := self._buttons.get("review"):
            button.setVisible(review_visible)
        if button := self._buttons.get("creation"):
            button.setVisible(creation_visible)
        
        # Если скрываем панели и текущая активная панель - одна из скрываемых, переключаемся на information
        current_index = self._stack.currentIndex()
        if not review_visible and current_index == self._tabs_order.index("review"):
            self.select_tab("information")
        if not creation_visible and current_index == self._tabs_order.index("creation"):
            self.select_tab("information")


