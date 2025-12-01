"""Панель ревью для выбора файлов и ввода промта."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional, Dict

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QSizePolicy,
    QScrollArea,
    QTabWidget,
    QFrame,
    QApplication,
)
from PyQt5.QtCore import (
    pyqtSignal,
    Qt,
    QEvent,
    QSize,
)
from PyQt5.QtGui import QTextCursor, QTextOption, QIcon, QPixmap, QPainter, QFont
from PyQt5.QtSvg import QSvgRenderer


class AttachmentItemWidget(QWidget):
    """Виджет элемента списка прикрепленных файлов с кнопкой удаления."""

    def __init__(self, file_path: Path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._setup_ui()

    def _load_svg_icon(self, icon_name: str, size: int = 16, color: Optional[str] = None) -> Optional[QIcon]:
        """Загрузить SVG иконку из файла и вернуть QIcon."""
        # Определяем путь к папке с иконками относительно корня проекта
        project_root = Path(__file__).parent.parent.parent.parent
        icon_path = project_root / "icons" / icon_name
        
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

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        # Отступы для правильного отображения текста
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(5)

        file_label = QLabel(self.file_path.name)
        file_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Сохраняем ссылку на label для использования в sizeHint
        self.file_label = file_label
        # Выравниваем label по центру вертикально
        layout.addWidget(file_label, 0, Qt.AlignVCenter)

        # Проверяем, является ли файл автоматически прикрепляемым guidelines файлом
        # Для него не показываем кнопку удаления
        is_guidelines_file = self.file_path.name.lower() == "test-cases-guidelines.md"
        
        if not is_guidelines_file:
            # Получаем высоту текста для определения размера кнопки
            text_height = file_label.fontMetrics().height()
            icon_size = max(16, min(text_height - 2, 20))  # Размер иконки немного меньше высоты текста
            button_size = text_height  # Размер кнопки равен высоте текста

            # Кнопка удаления с иконкой x.svg
            delete_button = QToolButton()
            delete_icon = self._load_svg_icon("x.svg", size=icon_size, color="#95a5a6")
            if delete_icon:
                delete_button.setIcon(delete_icon)
                delete_button.setIconSize(QSize(icon_size, icon_size))
            else:
                delete_button.setText("×")
            delete_button.setToolTip("Удалить файл")
            delete_button.setCursor(Qt.PointingHandCursor)
            delete_button.setAutoRaise(True)
            delete_button.setFixedSize(button_size, button_size)
            delete_button.setStyleSheet("""
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
            delete_button.clicked.connect(self._on_delete_clicked)
            # Выравниваем кнопку по правому краю и по центру вертикально относительно текста
            layout.addWidget(delete_button, 0, Qt.AlignRight | Qt.AlignVCenter)

    def _on_delete_clicked(self):
        self.delete_requested.emit(self.file_path)

    delete_requested = pyqtSignal(Path)


class ReviewPanel(QWidget):
    """Панель подготовки промта с возможностью прикрепления файлов."""

    prompt_saved = pyqtSignal(str)
    enter_clicked = pyqtSignal(str, list)

    def __init__(self, parent=None, *, title_text: str = "Панель ревью"):
        super().__init__(parent)
        self._attachments: List[Path] = []
        self._title_text = title_text
        
        # Загружаем маппинг иконок
        self._icon_mapping = self._load_icon_mapping()
        
        self._setup_ui()

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
                    if isinstance(data, dict) and any(key in data for key in ['panels', 'context_menu', 'panel_buttons']):
                        return data
                    else:
                        # Старый формат - возвращаем с секциями
                        return {
                            'panels': data if isinstance(data, dict) else {},
                            'context_menu': {},
                            'panel_buttons': {}
                        }
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка загрузки маппинга иконок: {e}")
        
        # Возвращаем значения по умолчанию, если файл не найден
        return {
            'panels': {},
            'context_menu': {},
            'panel_buttons': {
                "attach_files": "file-plus.svg"
            }
        }

    def _get_panel_button_icon(self, icon_key: str) -> Optional[str]:
        """Получить имя файла иконки для кнопки панели по ключу."""
        panel_buttons_mapping = self._icon_mapping.get('panel_buttons', {})
        return panel_buttons_mapping.get(icon_key)

    def _load_svg_icon(self, icon_name: str, size: int = 20, color: Optional[str] = None) -> Optional[QIcon]:
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
        # Используем те же отступы, что и в панели "Отчетность" (эталон)
        from ..styles.ui_metrics import UI_METRICS
        content_layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        content_layout.setSpacing(UI_METRICS.section_spacing)

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Заголовок панели с кнопкой прикрепления файла в одной строке
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        
        self._title_label = QLabel(self._title_text)
        # Используем тот же стиль заголовка, что и в панели "Отчетность"
        self._title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        title_row.addWidget(self._title_label)
        
        title_row.addStretch()  # Растягиваем пространство между заголовком и кнопкой
        
        # Стиль для кнопок с иконками (аналогично шагам тестирования)
        action_button_style = """
            QToolButton {
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.2);
            }
        """
        
        # Кнопка прикрепления файла справа от заголовка
        self.attach_button = QToolButton()
        # Загружаем иконку из маппинга
        icon_name = self._get_panel_button_icon("attach_files")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            if icon:
                self.attach_button.setIcon(icon)
                self.attach_button.setIconSize(QSize(16, 16))
            else:
                self.attach_button.setText("📎")
        else:
            self.attach_button.setText("📎")
        
        self.attach_button.setToolTip("Прикрепить файлы")
        self.attach_button.setCursor(Qt.PointingHandCursor)
        self.attach_button.setAutoRaise(True)
        self.attach_button.setFixedSize(24, 24)
        self.attach_button.setStyleSheet(action_button_style)
        self.attach_button.clicked.connect(self._choose_files)
        title_row.addWidget(self.attach_button, 0, Qt.AlignRight)
        
        content_layout.addLayout(title_row)

        # Блок прикрепленных файлов
        self.attachments_list = QListWidget()
        # Увеличиваем высоту выбранного элемента
        self.attachments_list.setStyleSheet("""
            QListWidget::item:selected {
                padding: 4px 0px;
                min-height: 28px;
            }
            QListWidget::item {
                padding: 2px 0px;
            }
        """)
        content_layout.addWidget(self.attachments_list)
        self._update_attachments_height()

        # Поле промта
        prompt_layout = QHBoxLayout()
        prompt_layout.setSpacing(10)

        prompt_label = QLabel("Промт")
        prompt_layout.addWidget(prompt_label)
        
        prompt_layout.addStretch(1)  # Растягиваем пространство между заголовком и кнопками
        
        # Стиль для кнопок с иконками (аналогично шагам тестирования)
        action_button_style = """
            QToolButton {
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.2);
            }
        """
        
        # Кнопка сохранения промта
        self.save_prompt_button = QToolButton()
        save_icon_name = self._icon_mapping.get('panel_buttons', {}).get('save', 'save.svg')
        save_icon = self._load_svg_icon(save_icon_name, size=16, color="#ffffff")
        if save_icon:
            self.save_prompt_button.setIcon(save_icon)
            self.save_prompt_button.setIconSize(QSize(16, 16))
        self.save_prompt_button.setToolTip("Сохранить")
        self.save_prompt_button.setCursor(Qt.PointingHandCursor)
        self.save_prompt_button.setAutoRaise(True)
        self.save_prompt_button.setFixedSize(24, 24)
        self.save_prompt_button.setStyleSheet(action_button_style)
        self.save_prompt_button.clicked.connect(self._save_prompt_clicked)
        prompt_layout.addWidget(self.save_prompt_button, 0, Qt.AlignRight)
        
        # Кнопка отправки (Enter)
        self.enter_button = QToolButton()
        send_icon_name = self._icon_mapping.get('panel_buttons', {}).get('send', 'send.svg')
        send_icon = self._load_svg_icon(send_icon_name, size=16, color="#ffffff")
        if send_icon:
            self.enter_button.setIcon(send_icon)
            self.enter_button.setIconSize(QSize(16, 16))
        self.enter_button.setToolTip("Отправить")
        self.enter_button.setCursor(Qt.PointingHandCursor)
        self.enter_button.setAutoRaise(True)
        self.enter_button.setFixedSize(24, 24)
        self.enter_button.setStyleSheet(action_button_style)
        self.enter_button.clicked.connect(self._enter_clicked)
        prompt_layout.addWidget(self.enter_button, 0, Qt.AlignRight)
        
        content_layout.addLayout(prompt_layout)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(110)
        self.prompt_edit.setMaximumHeight(150)
        prompt_policy = self.prompt_edit.sizePolicy()
        prompt_policy.setVerticalPolicy(QSizePolicy.Fixed)
        self.prompt_edit.setSizePolicy(prompt_policy)
        self.prompt_edit.installEventFilter(self)
        content_layout.addWidget(self.prompt_edit)

        # Ответ LLM с кнопкой копирования
        response_row = QHBoxLayout()
        response_label = QLabel("Ответ LLM")
        response_row.addWidget(response_label)
        response_row.addStretch(1)
        
        # Кнопка копирования markdown
        self.copy_response_button = QToolButton()
        copy_icon_name = self._icon_mapping.get('panel_buttons', {}).get('copy', 'copy.svg')
        copy_icon = self._load_svg_icon(copy_icon_name, size=16, color="#ffffff")
        if copy_icon:
            self.copy_response_button.setIcon(copy_icon)
            self.copy_response_button.setIconSize(QSize(16, 16))
        self.copy_response_button.setToolTip("Копировать Markdown")
        self.copy_response_button.setCursor(Qt.PointingHandCursor)
        self.copy_response_button.setAutoRaise(True)
        self.copy_response_button.setFixedSize(24, 24)
        self.copy_response_button.setStyleSheet("""
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
        self.copy_response_button.clicked.connect(self._copy_markdown)
        response_row.addWidget(self.copy_response_button, 0, Qt.AlignRight)
        
        content_layout.addLayout(response_row)

        self.response_tabs = QTabWidget()
        self.response_tabs.setDocumentMode(True)
        # Уменьшаем отступы вкладок, чтобы текст не обрезался
        self.response_tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 4px 4px;
                min-width: 70px;
            }
            QTabBar::tab:selected {
                padding: 4px 4px;
            }
        """)

        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response_text.setWordWrapMode(QTextOption.NoWrap)
        # Устанавливаем минимальные отступы для предотвращения обрезания текста
        text_document = self.response_text.document()
        text_document.setDocumentMargin(2)  # Минимальные отступы (2px)
        text_policy = self.response_text.sizePolicy()
        text_policy.setVerticalPolicy(QSizePolicy.Expanding)
        self.response_text.setSizePolicy(text_policy)

        self.response_markdown = QTextEdit()
        self.response_markdown.setReadOnly(True)
        self.response_markdown.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response_markdown.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response_markdown.setWordWrapMode(QTextOption.WordWrap)
        # Устанавливаем минимальные отступы для предотвращения обрезания текста
        md_document = self.response_markdown.document()
        md_document.setDocumentMargin(2)  # Минимальные отступы (2px)
        md_policy = self.response_markdown.sizePolicy()
        md_policy.setVerticalPolicy(QSizePolicy.Expanding)
        self.response_markdown.setSizePolicy(md_policy)
        self.response_markdown.setMarkdown("")

        tabs_container = QFrame()
        tabs_layout = QVBoxLayout(tabs_container)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(0)
        tabs_layout.addWidget(self.response_tabs)

        self.response_tabs.addTab(self.response_text, "Текст")
        self.response_tabs.addTab(self.response_markdown, "Markdown")
        content_layout.addWidget(tabs_container, 1)
        content_layout.addStretch(1)

        self._response_min_height = 160
        self._adjust_response_height()

    # --- Публичные методы -------------------------------------------------

    def set_prompt_text(self, text: str):
        """Установить текст промта."""
        self.prompt_edit.setPlainText(text or "")

    def get_prompt_text(self) -> str:
        """Получить текущий текст промта."""
        return self.prompt_edit.toPlainText().strip()

    def set_response_text(self, text: str):
        """Показать текст ответа LLM."""
        displayed = text or ""
        self.response_text.setPlainText(displayed)
        self.response_text.moveCursor(QTextCursor.Start)
        self.response_markdown.setMarkdown(displayed)
        self.response_tabs.setCurrentIndex(0)
        self._adjust_response_height()

    def clear_response(self):
        """Очистить поле ответа."""
        self.response_text.clear()
        self.response_markdown.clear()
        self._adjust_response_height()

    def set_loading_state(self, is_loading: bool):
        """Заблокировать элементы управления на время запроса."""
        self.enter_button.setEnabled(not is_loading)
        self.prompt_edit.setEnabled(not is_loading)
        # Обновляем tooltip в зависимости от состояния
        if is_loading:
            self.enter_button.setToolTip("Отправка…")
        else:
            self.enter_button.setToolTip("Отправить")

    def clear_attachments(self):
        """Очистить список прикрепленных файлов."""
        self._attachments.clear()
        self.attachments_list.clear()
        self._update_attachments_height()

    def set_attachments(self, paths: Iterable[Path]):
        """Заменить список прикрепленных файлов."""
        self._attachments.clear()
        self.attachments_list.clear()
        self._update_attachments_height()
        self.add_attachments(paths)

    def add_attachments(self, paths: Iterable[Path]):
        """Добавить новые файлы к списку прикрепленных."""
        changed = False
        for path in paths:
            path_obj = Path(path)
            if path_obj not in self._attachments:
                self._attachments.append(path_obj)
                changed = True
        if changed:
            self._refresh_attachments()

    def get_attachments(self) -> List[Path]:
        """Получить текущие прикрепленные файлы."""
        return list(self._attachments)

    # --- Внутренние обработчики -------------------------------------------

    def _choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для ревью",
            "",
            "Все файлы (*.*)",
        )

        if not files:
            return

        self.add_attachments(Path(path) for path in files)

    def _save_prompt_clicked(self):
        text = self.get_prompt_text()
        self.prompt_saved.emit(text)

    def _enter_clicked(self):
        self.enter_clicked.emit(self.get_prompt_text(), [str(p) for p in self._attachments])
    
    def _copy_markdown(self):
        """Копировать содержимое markdown в буфер обмена."""
        # Используем response_text, так как там хранится исходный текст,
        # который был передан в setMarkdown
        markdown_text = self.response_text.toPlainText()
        if not markdown_text.strip():
            return
        
        clipboard = QApplication.clipboard()
        clipboard.setText(markdown_text)


    def _get_row_height(self) -> int:
        """Получить высоту одной строки в списке прикрепленных файлов."""
        # Если есть элементы, используем реальную высоту строки
        if self.attachments_list.count() > 0:
            row_height = self.attachments_list.sizeHintForRow(0)
            if row_height > 0:
                return row_height
        
        # Если элементов нет, создаем временный виджет для получения его sizeHint
        # Это даст нам точную высоту с учетом всех отступов
        temp_widget = AttachmentItemWidget(Path("temp_file.txt"))
        temp_size_hint = temp_widget.sizeHint()
        if temp_size_hint.isValid() and temp_size_hint.height() > 0:
            return temp_size_hint.height()
        
        # Fallback: рассчитываем высоту на основе шрифта и отступов виджета
        font_metrics = self.attachments_list.fontMetrics()
        line_spacing = font_metrics.lineSpacing()
        # Отступы виджета: 6px сверху + 6px снизу = 12px
        # Добавляем небольшой запас для правильного отображения
        return line_spacing + 14  # lineSpacing + отступы виджета (12px) + запас (2px)

    def _update_attachments_height(self):
        """Адаптировать высоту списка прикрепленных файлов."""
        # Получаем высоту одной строки
        row_height = self._get_row_height()
        
        # Количество элементов для отображения (минимум 1 для пустого состояния)
        item_count = max(self.attachments_list.count(), 1)
        
        # Высота рамки списка
        frame_height = self.attachments_list.frameWidth() * 2
        
        # Рассчитываем общую высоту: количество строк * высота строки + рамка
        # Добавляем небольшой запас для правильного отображения
        total_height = frame_height + (row_height * item_count) + 2
        
        # Устанавливаем фиксированную высоту
        self.attachments_list.setFixedHeight(total_height)
        
        # Если файлов нет, показываем сообщение
        if self.attachments_list.count() == 0:
            placeholder_item = QListWidgetItem("Файлы не прикреплены", self.attachments_list)
            placeholder_item.setFlags(Qt.ItemIsEnabled)
            # Устанавливаем размер hint для placeholder элемента
            placeholder_item.setSizeHint(QSize(0, row_height))

    def _refresh_attachments(self):
        self.attachments_list.clear()
        if not self._attachments:
            self._update_attachments_height()
            return
        
        # Используем ту же формулу расчета высоты, что и для пустого состояния
        font_metrics = self.attachments_list.fontMetrics()
        line_spacing = font_metrics.lineSpacing()
        row_height = line_spacing + 14  # Та же формула, что и в _get_row_height()
        
        for path in self._attachments:
            item_widget = AttachmentItemWidget(path)
            item_widget.delete_requested.connect(self._remove_attachment)
            item = QListWidgetItem()
            # Используем ту же высоту, что и для placeholder
            item.setSizeHint(QSize(0, row_height))
            self.attachments_list.addItem(item)
            self.attachments_list.setItemWidget(item, item_widget)
        
        self._update_attachments_height()

    def _remove_attachment(self, path: Path):
        """Удалить файл из списка прикрепленных."""
        if path in self._attachments:
            self._attachments.remove(path)
            self._refresh_attachments()

    # --- Qt события -------------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self.prompt_edit and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
                event.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
            ):
                self._enter_clicked()
                return True
        return super().eventFilter(obj, event)

    # --- Вспомогательные методы -------------------------------------------

    def _adjust_response_height(self):
        """Подстроить высоту области ответа под содержимое."""
        documents = [self.response_text.document(), self.response_markdown.document()]
        max_height = 0
        for edit, doc in (
            (self.response_text, self.response_text.document()),
            (self.response_markdown, self.response_markdown.document()),
        ):
            viewport_width = edit.viewport().width()
            if viewport_width > 0:
                doc.setTextWidth(viewport_width)
            height = doc.size().height()
            if height > max_height:
                max_height = height

        tab_bar_height = self.response_tabs.tabBar().sizeHint().height()
        padding = 48  # запас под отступы
        total_height = int(max_height + tab_bar_height + padding)
        total_height = max(total_height, self._response_min_height)
        self.response_tabs.setMinimumHeight(total_height)


