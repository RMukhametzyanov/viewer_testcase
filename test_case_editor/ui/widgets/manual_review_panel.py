"""Панель ручного ревью с чат-интерфейсом."""

from __future__ import annotations

import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QScrollArea,
    QFrame,
    QToolButton,
    QMessageBox,
    QApplication,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

from ...models import TestCase
from ...utils.resource_path import get_icon_path
from ..styles.ui_metrics import UI_METRICS


def get_git_user_name() -> str:
    """Получить имя пользователя из git config."""
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        return result.stdout.strip() or "Unknown User"
    except Exception:
        return "Unknown User"


class ChatMessageWidget(QWidget):
    """Виджет сообщения в чате."""

    edit_requested = pyqtSignal(str)  # timestamp
    delete_requested = pyqtSignal(str)  # timestamp
    resolved_changed = pyqtSignal(str, str)  # timestamp, resolved

    def __init__(self, timestamp: str, author: str, message: str, resolved: str = "new", edited: bool = False, parent=None):
        super().__init__(parent)
        self.timestamp = timestamp
        self.author = author
        self.message = message
        self.resolved = resolved
        self.edited = edited
        self._setup_ui()
    
    @staticmethod
    def _load_svg_icon(icon_name: str, size: int = 16, color: Optional[str] = None) -> Optional[QIcon]:
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

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Заголовок с автором, датой и кнопками в одну строку
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        # Автор
        author_label = QLabel(self.author)
        author_font = QFont()
        author_font.setBold(True)
        author_label.setFont(author_font)
        author_label.setStyleSheet("color: #6CC24A;")
        header_layout.addWidget(author_label)
        
        # Дата и время
        try:
            timestamp_ms = int(self.timestamp)
            dt = datetime.fromtimestamp(timestamp_ms / 1000.0)
            date_str = dt.strftime("%d.%m.%Y %H:%M")
            if self.edited:
                date_str += " (изменено)"
        except Exception:
            date_str = self.timestamp
            if self.edited:
                date_str += " (изменено)"
        
        date_label = QLabel(date_str)
        date_label.setStyleSheet("color: #95a5a6; font-size: 11px;")
        header_layout.addWidget(date_label)
        
        header_layout.addStretch()
        
        # Кнопка статуса resolved
        self.resolved_btn = QToolButton()
        self._update_resolved_icon()
        self.resolved_btn.setToolTip(self._get_resolved_tooltip())
        self.resolved_btn.setCursor(Qt.PointingHandCursor)
        self.resolved_btn.setFixedSize(20, 20)
        self.resolved_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: transparent;
                padding: 2px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
            }
        """)
        self.resolved_btn.clicked.connect(self._on_resolved_clicked)
        header_layout.addWidget(self.resolved_btn)
        
        # Кнопка редактирования
        edit_btn = QToolButton()
        edit_icon = self._load_svg_icon("edit-2.svg", size=16, color="#95a5a6")
        if edit_icon:
            edit_btn.setIcon(edit_icon)
            edit_btn.setIconSize(QSize(16, 16))
        else:
            edit_btn.setText("✎")
        edit_btn.setToolTip("Редактировать")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setFixedSize(20, 20)
        edit_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: transparent;
                padding: 2px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
            }
        """)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.timestamp))
        header_layout.addWidget(edit_btn)
        
        # Кнопка удаления
        delete_btn = QToolButton()
        delete_icon = self._load_svg_icon("x.svg", size=16, color="#95a5a6")
        if delete_icon:
            delete_btn.setIcon(delete_icon)
            delete_btn.setIconSize(QSize(16, 16))
        else:
            delete_btn.setText("×")
        delete_btn.setToolTip("Удалить")
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setFixedSize(20, 20)
        delete_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: transparent;
                padding: 2px;
            }
            QToolButton:hover {
                background-color: rgba(245, 85, 93, 0.2);
                border-radius: 3px;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.timestamp))
        header_layout.addWidget(delete_btn)
        
        layout.addLayout(header_layout)

        # Текст сообщения
        message_label = QLabel(self.message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #ffffff; padding: 4px 0px;")
        message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(message_label)

        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: rgba(255, 255, 255, 0.1);")
        layout.addWidget(separator)
    
    def _update_resolved_icon(self):
        """Обновить иконку и цвет кнопки resolved в зависимости от статуса."""
        if self.resolved == "new":
            icon_name = "help-circle.svg"
            color = "#FFA931"  # Желтый
        elif self.resolved == "fixed":
            icon_name = "arrow-right-circle.svg"
            color = "#6CC24A"  # Зеленый
        elif self.resolved == "closed":
            icon_name = "check-circle.svg"
            color = "#95a5a6"  # Серый
        else:
            # По умолчанию "new"
            icon_name = "help-circle.svg"
            color = "#FFA931"
            self.resolved = "new"
        
        icon = self._load_svg_icon(icon_name, size=16, color=color)
        if icon:
            self.resolved_btn.setIcon(icon)
            self.resolved_btn.setIconSize(QSize(16, 16))
    
    def _get_resolved_tooltip(self) -> str:
        """Получить подсказку для кнопки resolved."""
        tooltips = {
            "new": "Новое (клик для отметки как исправлено)",
            "fixed": "Исправлено (клик для отметки как закрыто)",
            "closed": "Закрыто (клик для сброса в новое)",
        }
        return tooltips.get(self.resolved, "Новое")
    
    def _on_resolved_clicked(self):
        """Обработчик клика на кнопку resolved - переключение состояний."""
        # Переключаем состояние по циклу: new -> fixed -> closed -> new
        if self.resolved == "new":
            self.resolved = "fixed"
        elif self.resolved == "fixed":
            self.resolved = "closed"
        elif self.resolved == "closed":
            self.resolved = "new"
        else:
            self.resolved = "new"
        
        # Обновляем иконку
        self._update_resolved_icon()
        self.resolved_btn.setToolTip(self._get_resolved_tooltip())
        
        # Отправляем сигнал об изменении
        self.resolved_changed.emit(self.timestamp, self.resolved)


class ManualReviewPanel(QWidget):
    """Панель ручного ревью в стиле чата."""

    notes_changed = pyqtSignal()  # Сигнал об изменении notes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_test_case: Optional[TestCase] = None
        self._editing_timestamp: Optional[str] = None  # Timestamp сообщения, которое редактируется
        
        # Загружаем маппинг иконок
        self._icon_mapping = self._load_icon_mapping()
        
        self._setup_ui()
    
    def _load_icon_mapping(self) -> Dict[str, Dict[str, str]]:
        """Загрузить маппинг иконок из JSON файла."""
        project_root = Path(__file__).parent.parent.parent.parent
        mapping_file = project_root / "icons" / "icon_mapping.json"
        
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and any(key in data for key in ['panels', 'context_menu', 'panel_buttons']):
                        return data
                    else:
                        return {
                            'panels': data if isinstance(data, dict) else {},
                            'context_menu': {},
                            'panel_buttons': {}
                        }
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка загрузки маппинга иконок: {e}")
        
        return {
            'panels': {},
            'context_menu': {},
            'panel_buttons': {
                "send": "arrow-right-circle.svg"
            }
        }
    
    def _get_panel_button_icon(self, icon_key: str) -> Optional[str]:
        """Получить имя файла иконки для кнопки панели по ключу."""
        panel_buttons_mapping = self._icon_mapping.get('panel_buttons', {})
        return panel_buttons_mapping.get(icon_key)
    
    def _load_svg_icon(self, icon_name: str, size: int = 20, color: Optional[str] = None) -> Optional[QIcon]:
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

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        layout.setSpacing(UI_METRICS.section_spacing)

        # Заголовок (как в панели "Отчетность")
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)
        
        title = QLabel("Ручное ревью")
        # Используем тот же стиль заголовка, что и в панели "Отчетность"
        title.setStyleSheet("font-weight: 600; font-size: 14px;")
        title_layout.addWidget(title)
        
        title_layout.addStretch()
        
        layout.addLayout(title_layout)

        # Область прокрутки для сообщений
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)

        # Контейнер для сообщений
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(8, 8, 8, 8)
        self.messages_layout.setSpacing(0)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area, stretch=1)

        # Область ввода
        input_container = QFrame()
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(0)

        # Контейнер для поля ввода с кнопкой внутри (используем QWidget для абсолютного позиционирования)
        input_wrapper = QWidget()
        input_wrapper.setFixedHeight(100)  # Фиксированная высота для контейнера
        
        # Поле ввода сообщения
        self.message_input = QTextEdit(input_wrapper)
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.message_input.setAcceptRichText(False)
        # Добавляем отступ справа для кнопки
        self.message_input.setStyleSheet("""
            QTextEdit {
                padding-right: 50px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        
        # Кнопка отправки - размещаем поверх поля ввода в правом нижнем углу
        self.send_button = QToolButton(input_wrapper)
        icon_name = self._get_panel_button_icon("send")
        if icon_name:
            icon = self._load_svg_icon(icon_name, size=16, color="#ffffff")
            if icon:
                self.send_button.setIcon(icon)
                self.send_button.setIconSize(QSize(16, 16))
            else:
                self.send_button.setText("→")
        else:
            self.send_button.setText("→")
        
        self.send_button.setToolTip("Отправить (Ctrl+Enter)")
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.setAutoRaise(True)
        self.send_button.setFixedSize(24, 24)
        self.send_button.setStyleSheet("""
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
        self.send_button.clicked.connect(self._on_send_clicked)
        
        # Обработка Enter для отправки
        self.message_input.keyPressEvent = self._handle_key_press
        
        # Переопределяем resizeEvent для контейнера
        def input_wrapper_resize_event(event):
            QWidget.resizeEvent(input_wrapper, event)
            # Обновляем размеры поля ввода
            self.message_input.setGeometry(0, 0, input_wrapper.width(), input_wrapper.height())
            # Обновляем позицию кнопки
            button_size = 24
            margin = 8
            x = input_wrapper.width() - button_size - margin
            y = input_wrapper.height() - button_size - margin
            self.send_button.move(x, y)
        
        input_wrapper.resizeEvent = input_wrapper_resize_event
        
        input_layout.addWidget(input_wrapper)
        
        # Инициализируем позицию кнопки после отрисовки
        def init_button_position():
            button_size = 24
            margin = 8
            x = input_wrapper.width() - button_size - margin
            y = input_wrapper.height() - button_size - margin
            self.send_button.move(x, y)
        
        QTimer.singleShot(0, init_button_position)

        layout.addWidget(input_container)

    def _handle_key_press(self, event):
        """Обработка нажатия клавиш в поле ввода."""
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            # Ctrl+Enter - отправка
            self._on_send_clicked()
        elif event.key() == Qt.Key_Return and event.modifiers() == Qt.NoModifier:
            # Enter - новая строка (обычное поведение)
            QTextEdit.keyPressEvent(self.message_input, event)
        else:
            QTextEdit.keyPressEvent(self.message_input, event)

    def load_test_case(self, test_case: Optional[TestCase]):
        """Загрузить тест-кейс и отобразить его notes."""
        self.current_test_case = test_case
        self._refresh_messages()

    def _refresh_messages(self):
        """Обновить отображение сообщений."""
        # Очищаем существующие сообщения
        while self.messages_layout.count() > 1:  # Оставляем только stretch
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.current_test_case or not self.current_test_case.notes:
            return

        # Сортируем notes по timestamp (от старых к новым)
        sorted_timestamps = sorted(self.current_test_case.notes.keys(), key=lambda x: int(x) if x.isdigit() else 0)

        # Добавляем сообщения
        for timestamp in sorted_timestamps:
            note_data = self.current_test_case.notes.get(timestamp, {})
            author = note_data.get("author", "Unknown")
            message = note_data.get("message", "")
            resolved = note_data.get("resolved", "new")
            edited = bool(note_data.get("edited", False))
            
            if message:  # Показываем только непустые сообщения
                message_widget = ChatMessageWidget(timestamp, author, message, resolved, edited, self)
                message_widget.edit_requested.connect(self._on_edit_requested)
                message_widget.delete_requested.connect(self._on_delete_requested)
                message_widget.resolved_changed.connect(self._on_resolved_changed)
                self.messages_layout.insertWidget(self.messages_layout.count() - 1, message_widget)

        # Прокручиваем вниз после обновления layout
        # Обновляем layout контейнера
        self.messages_container.update()
        
        # Прокручиваем вниз после небольшой задержки для обновления layout
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def _on_send_clicked(self):
        """Обработчик нажатия кнопки отправки."""
        message = self.message_input.toPlainText().strip()
        
        if not message:
            return
        
        if not self.current_test_case:
            # Не показываем модальное окно - просто не делаем ничего
            # QMessageBox.warning(self, "Ошибка", "Тест-кейс не выбран")
            return

        # Добавляем note в тест-кейс
        if not self.current_test_case.notes:
            self.current_test_case.notes = {}
        
        # Проверяем, редактируем ли мы существующее сообщение
        if self._editing_timestamp and self._editing_timestamp in self.current_test_case.notes:
            # Обновляем существующее сообщение с тем же timestamp
            # Текст сообщения обновляется, timestamp остается прежним
            self.current_test_case.notes[self._editing_timestamp]["message"] = message
            self.current_test_case.notes[self._editing_timestamp]["edited"] = True
            self._editing_timestamp = None  # Сбрасываем флаг редактирования
        else:
            # Создаем новое сообщение - только здесь создаем новый timestamp
            timestamp_ms = int(datetime.now().timestamp() * 1000)
            timestamp_str = str(timestamp_ms)
            author = get_git_user_name()
            
            self.current_test_case.notes[timestamp_str] = {
                "author": author,
                "message": message,
                "resolved": "new",
                "edited": False,
            }

        # Очищаем поле ввода
        self.message_input.clear()
        
        # Сбрасываем флаг редактирования
        self._editing_timestamp = None

        # Обновляем отображение
        self._refresh_messages()

        # Отправляем сигнал об изменении
        self.notes_changed.emit()

        # Фокус обратно на поле ввода
        self.message_input.setFocus()

    def _on_edit_requested(self, timestamp: str):
        """Обработчик запроса на редактирование сообщения."""
        if not self.current_test_case or timestamp not in self.current_test_case.notes:
            return

        note_data = self.current_test_case.notes[timestamp]
        current_message = note_data.get("message", "")

        # Сохраняем timestamp редактируемого сообщения
        self._editing_timestamp = timestamp

        # Загружаем сообщение в поле ввода
        self.message_input.setPlainText(current_message)
        self.message_input.setFocus()
        
        # Устанавливаем курсор в конец
        cursor = self.message_input.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.message_input.setTextCursor(cursor)

    def _on_delete_requested(self, timestamp: str):
        """Обработчик запроса на удаление сообщения."""
        if not self.current_test_case or timestamp not in self.current_test_case.notes:
            return

        # Подтверждение удаления
        reply = QMessageBox.question(
            self,
            "Удаление сообщения",
            "Вы уверены, что хотите удалить это сообщение?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            del self.current_test_case.notes[timestamp]
            self._refresh_messages()

            # Отправляем сигнал об изменении
            self.notes_changed.emit()
    
    def _on_resolved_changed(self, timestamp: str, resolved: str):
        """Обработчик изменения статуса resolved сообщения."""
        if not self.current_test_case or timestamp not in self.current_test_case.notes:
            return
        
        # Обновляем статус resolved
        self.current_test_case.notes[timestamp]["resolved"] = resolved
        
        # Отправляем сигнал об изменении
        self.notes_changed.emit()

