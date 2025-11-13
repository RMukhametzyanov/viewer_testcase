"""Панель ревью для выбора файлов и ввода промта."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QSizePolicy,
    QScrollArea,
    QTabWidget,
    QFrame,
    QComboBox,
    QLineEdit,
    QCompleter,
)
from PyQt5.QtCore import (
    pyqtSignal,
    Qt,
    QEvent,
    QStringListModel,
)
from PyQt5.QtGui import QTextCursor, QTextOption


class ReviewPanel(QWidget):
    """Панель подготовки промта с возможностью прикрепления файлов."""

    prompt_saved = pyqtSignal(str)
    enter_clicked = pyqtSignal(str, list)
    close_requested = pyqtSignal()

    def __init__(self, parent=None, *, title_text: str = "Панель ревью"):
        super().__init__(parent)
        self._attachments: List[Path] = []
        self._title_text = title_text
        self._all_models: List[str] = []
        self._default_model: str = ""
        self._models_model = QStringListModel(self)
        self._completer: QCompleter | None = None
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
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        self._title_label = QLabel(self._title_text)
        self._title_label.setStyleSheet("color: #E1E3E6; font-size: 16pt; font-weight: 600;")
        content_layout.addWidget(self._title_label)

        model_row = QHBoxLayout()
        model_row.setSpacing(8)

        model_label = QLabel("Модель:")
        model_label.setStyleSheet("color: #8B9099; font-weight: 600;")
        model_row.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.NoInsert)
        self.model_combo.setMaxVisibleItems(10)
        self.model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.model_combo.setMinimumHeight(32)
        self.model_combo.setStyleSheet(
            """
            QComboBox {
                background-color: #1E2732;
                border: 1px solid #2B3945;
                border-radius: 6px;
                color: #E1E3E6;
                padding: 4px 8px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #101820;
                border: 1px solid #2B3945;
                selection-background-color: #2B5278;
                selection-color: #FFFFFF;
            }
            """
        )
        line_edit = self.model_combo.lineEdit()
        line_edit.setPlaceholderText("Поиск и выбор модели…")
        line_edit.setClearButtonEnabled(True)
        line_edit.setStyleSheet(
            """
            QLineEdit {
                background-color: #1E2732;
                border: 1px solid #2B3945;
                border-radius: 6px;
                color: #E1E3E6;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                border: 1px solid #5288C1;
            }
            """
        )
        line_edit.textEdited.connect(self._on_model_text_edited)

        self.model_combo.setModel(self._models_model)
        self.model_combo.setModelColumn(0)
        popup_view = self.model_combo.view()
        popup_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self._completer = QCompleter(self._models_model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.activated[str].connect(self._on_completer_activated)
        completer_popup = self._completer.popup()
        if completer_popup is not None:
            completer_popup.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.model_combo.setCompleter(self._completer)

        model_row.addWidget(self.model_combo)
        model_row.addStretch()
        content_layout.addLayout(model_row)

        # Блок прикрепленных файлов
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.attach_button = QPushButton("📎")
        self.attach_button.setToolTip("Прикрепить файлы")
        self.attach_button.setFixedSize(40, 40)
        self.attach_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2B5278;
                border: 1px solid #3D6A98;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 18pt;
            }
            QPushButton:hover {
                background-color: #3D6A98;
            }
            """
        )
        self.attach_button.clicked.connect(self._choose_files)
        header_row.addWidget(self.attach_button, 0, Qt.AlignLeft)

        attachments_label = QLabel("Прикрепленные файлы:")
        attachments_label.setStyleSheet("color: #8B9099; font-weight: 600;")
        header_row.addWidget(attachments_label, 0, Qt.AlignVCenter)

        header_row.addStretch(1)

        self.close_button = QPushButton("✖")
        self.close_button.setToolTip("Скрыть панель ревью")
        self.close_button.setFixedSize(32, 32)
        self.close_button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: 1px solid #3D6A98;
                border-radius: 6px;
                color: #E1E3E6;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #3D6A98;
            }
            QPushButton:pressed {
                background-color: #1D3F5F;
            }
            """
        )
        self.close_button.clicked.connect(self.close_requested.emit)
        header_row.addWidget(self.close_button, 0, Qt.AlignRight)

        content_layout.addLayout(header_row)

        self.attachments_list = QListWidget()
        self.attachments_list.setStyleSheet(
            """
            QListWidget {
                background-color: #1E2732;
                border: 1px solid #2B3945;
                border-radius: 8px;
                color: #E1E3E6;
            }
            QListWidget::item {
                padding: 6px 8px;
            }
            """
        )
        content_layout.addWidget(self.attachments_list)
        self._update_attachments_height()

        # Поле промта
        prompt_layout = QHBoxLayout()
        prompt_layout.setSpacing(10)

        prompt_label = QLabel("Промт")
        prompt_label.setStyleSheet("color: #8B9099; font-weight: 600;")
        prompt_layout.addWidget(prompt_label)

        self.save_prompt_button = QPushButton("Сохранить")
        self.save_prompt_button.setFixedHeight(32)
        self.save_prompt_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2B5278;
                border: 1px solid #3D6A98;
                border-radius: 6px;
                color: #FFFFFF;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #3D6A98;
            }
            """
        )
        self.save_prompt_button.clicked.connect(self._save_prompt_clicked)
        prompt_layout.addWidget(self.save_prompt_button, 0, Qt.AlignRight)
        prompt_layout.addStretch(1)
        content_layout.addLayout(prompt_layout)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(110)
        self.prompt_edit.setMaximumHeight(150)
        prompt_policy = self.prompt_edit.sizePolicy()
        prompt_policy.setVerticalPolicy(QSizePolicy.Fixed)
        self.prompt_edit.setSizePolicy(prompt_policy)
        self.prompt_edit.setStyleSheet(
            """
            QTextEdit {
                background-color: #1E2732;
                border: 1px solid #2B3945;
                border-radius: 8px;
                color: #E1E3E6;
                padding: 10px;
                font-size: 11pt;
            }
            """
        )
        self.prompt_edit.installEventFilter(self)
        content_layout.addWidget(self.prompt_edit)

        # Кнопка Enter
        self.enter_button = QPushButton("Enter")
        self.enter_button.setMinimumHeight(45)
        self.enter_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2B5278;
                border: 1px solid #3D6A98;
                border-radius: 8px;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #3D6A98;
            }
            QPushButton:pressed {
                background-color: #1D3F5F;
            }
            """
        )
        self.enter_button.clicked.connect(self._enter_clicked)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        buttons_row.addWidget(self.enter_button)
        content_layout.addLayout(buttons_row)

        # Ответ LLM
        response_label = QLabel("Ответ LLM")
        response_label.setStyleSheet("color: #8B9099; font-weight: 600;")
        content_layout.addWidget(response_label)

        self.response_tabs = QTabWidget()
        self.response_tabs.setDocumentMode(True)
        self.response_tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid #2B3945;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #1E2732;
                color: #8B9099;
                padding: 8px 16px;
                border: 1px solid #2B3945;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #2B3945;
                color: #E1E3E6;
            }
            """
        )

        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response_text.setWordWrapMode(QTextOption.NoWrap)
        text_policy = self.response_text.sizePolicy()
        text_policy.setVerticalPolicy(QSizePolicy.Expanding)
        self.response_text.setSizePolicy(text_policy)
        self.response_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #101820;
                border: none;
                color: #E1E3E6;
                padding: 10px;
                font-size: 11pt;
            }
            """
        )

        self.response_markdown = QTextEdit()
        self.response_markdown.setReadOnly(True)
        self.response_markdown.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response_markdown.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.response_markdown.setWordWrapMode(QTextOption.WordWrap)
        md_policy = self.response_markdown.sizePolicy()
        md_policy.setVerticalPolicy(QSizePolicy.Expanding)
        self.response_markdown.setSizePolicy(md_policy)
        self.response_markdown.setMarkdown("")
        self.response_markdown.setStyleSheet(
            """
            QTextEdit {
                background-color: #101820;
                border: none;
                color: #E1E3E6;
                padding: 10px;
                font-size: 11pt;
            }
            """
        )

        tabs_container = QFrame()
        tabs_container.setStyleSheet("QFrame { border: 1px solid #2B3945; border-radius: 6px; }")
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

    def set_model_options(self, models: Iterable[str], default_model: str | None = None):
        """Установить список доступных моделей."""
        unique: List[str] = []
        seen = set()
        for model in models or []:
            model_str = str(model or "").strip()
            if not model_str or model_str in seen:
                continue
            seen.add(model_str)
            unique.append(model_str)

        self._all_models = unique
        self._default_model = (default_model or "").strip()

        self._models_model.setStringList(unique)
        if self._completer is not None:
            self._completer.setCompletionPrefix("")

        line_edit = self.model_combo.lineEdit()
        line_edit.blockSignals(True)
        if self._default_model and self._default_model in unique:
            line_edit.setText(self._default_model)
        elif unique:
            line_edit.setText(unique[0])
        else:
            line_edit.clear()
        line_edit.blockSignals(False)

        self.model_combo.blockSignals(True)
        if unique:
            target = self._default_model if self._default_model in unique else unique[0]
            self.model_combo.setCurrentText(target)
        else:
            self.model_combo.setCurrentIndex(-1)
        self.model_combo.blockSignals(False)

    def get_selected_model(self) -> str:
        """Вернуть выбранную модель."""
        value = self.model_combo.lineEdit().text().strip()
        return value if value in self._all_models else ""

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
        if is_loading:
            self.enter_button.setText("Отправка…")
        else:
            self.enter_button.setText("Enter")

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


    def _update_attachments_height(self):
        """Адаптировать высоту списка прикрепленных файлов."""
        count = max(self.attachments_list.count(), 1)
        frame = self.attachments_list.frameWidth() * 2
        if self.attachments_list.count() > 0:
            metrics_height = self.attachments_list.sizeHintForRow(0)
        else:
            metrics_height = self.attachments_list.fontMetrics().height() + 12
        new_height = frame + metrics_height * count
        self.attachments_list.setFixedHeight(new_height)
        if self.attachments_list.count() == 0:
            QListWidgetItem("Файлы не прикреплены", self.attachments_list)
            self.attachments_list.item(0).setFlags(Qt.ItemIsEnabled)

    def _refresh_attachments(self):
        self.attachments_list.clear()
        if not self._attachments:
            self._update_attachments_height()
            return
        for path in self._attachments:
            QListWidgetItem(str(path), self.attachments_list)
        self._update_attachments_height()

    def _on_model_text_edited(self, text: str):
        if self._completer is None:
            return
        self._completer.setCompletionPrefix(text)
        self._completer.complete()
        line_edit = self.model_combo.lineEdit()
        if line_edit is not None:
            line_edit.setFocus(Qt.OtherFocusReason)
            line_edit.setCursorPosition(len(text))

    def _on_completer_activated(self, text: str):
        if not text:
            return
        self.model_combo.setCurrentText(text)
        line_edit = self.model_combo.lineEdit()
        if line_edit is not None:
            line_edit.setText(text)
            line_edit.setFocus(Qt.OtherFocusReason)
            line_edit.setCursorPosition(len(text))

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


