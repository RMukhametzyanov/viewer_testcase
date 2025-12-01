"""Панель управления файлами для тест-кейса с drag & drop."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QSizePolicy,
    QScrollArea,
    QMessageBox,
    QInputDialog,
    QComboBox,
)

from ...models import TestCase, TestCaseStep
from ..styles.ui_metrics import UI_METRICS


class FileItemWidget(QWidget):
    """Виджет элемента списка прикрепленных файлов с информацией о привязке к шагам и кнопкой удаления."""

    delete_requested = pyqtSignal(Path)

    def __init__(self, file_path: Path, attached_to_steps: List[int] = None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.attached_to_steps = attached_to_steps or []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # Увеличиваем вертикальные отступы, чтобы текст не обрезался
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(8)

        # Первая строка: имя файла и кнопка удаления в одной строке
        file_row = QHBoxLayout()
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.setSpacing(5)

        file_label = QLabel(self.file_path.name)
        file_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        file_label.setWordWrap(False)  # Не переносим текст на новую строку
        file_label.setToolTip(str(self.file_path))  # Полный путь в подсказке
        # Обрезаем текст вручную, если он слишком длинный
        file_label.setTextFormat(Qt.PlainText)
        # Устанавливаем минимальную высоту для label, чтобы текст не обрезался
        font_metrics = file_label.fontMetrics()
        # Увеличиваем отступы для текста - используем lineSpacing для лучшего отображения
        file_label.setMinimumHeight(font_metrics.lineSpacing() + 10)  # Добавляем больше отступов
        file_row.addWidget(file_label, 1)  # Растягивается, но оставляет место для кнопки

        # Минималистичная кнопка удаления, как в шагах
        delete_button = QToolButton()
        delete_button.setText("×")
        delete_button.setToolTip("Удалить файл")
        delete_button.setCursor(Qt.PointingHandCursor)
        delete_button.setAutoRaise(True)
        delete_button.setFixedSize(24, 24)
        delete_button.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                font-size: 12px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.2);
            }
        """)
        delete_button.clicked.connect(self._on_delete_clicked)
        file_row.addWidget(delete_button, 0)  # Фиксированный размер, не растягивается

        layout.addLayout(file_row)

        # Вторая строка: информация о привязке к шагам
        if self.attached_to_steps:
            steps_text = ", ".join([f"Шаг {idx + 1}" for idx in self.attached_to_steps])
            steps_label = QLabel(f"Прикреплен к: {steps_text}")
            steps_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
            steps_label.setWordWrap(True)  # Разрешаем перенос текста на новую строку
            # Устанавливаем минимальную высоту для label, чтобы текст не обрезался
            font_metrics = steps_label.fontMetrics()
            # Увеличиваем отступы для текста - используем lineSpacing для лучшего отображения
            steps_label.setMinimumHeight(font_metrics.lineSpacing() + 10)  # Добавляем больше отступов
            layout.addWidget(steps_label)
        else:
            no_attachment_label = QLabel("Не прикреплен к шагам")
            no_attachment_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px; font-style: italic;")
            # Устанавливаем минимальную высоту для label, чтобы текст не обрезался
            font_metrics = no_attachment_label.fontMetrics()
            # Увеличиваем отступы для текста - используем lineSpacing для лучшего отображения
            no_attachment_label.setMinimumHeight(font_metrics.lineSpacing() + 10)  # Добавляем больше отступов
            layout.addWidget(no_attachment_label)
    
    def sizeHint(self) -> QSize:
        """Возвращает предпочтительный размер виджета с учетом увеличенных отступов."""
        hint = super().sizeHint()
        # Убеждаемся, что высота достаточна для отображения текста без обрезания
        # Высота = отступы сверху/снизу (10+10=20) + высота первой строки + spacing (8) + высота второй строки
        font_metrics = self.fontMetrics()
        first_line_height = font_metrics.lineSpacing() + 10  # Имя файла с отступами
        second_line_height = font_metrics.lineSpacing() + 10  # Информация о шагах с отступами
        min_height = 20 + first_line_height + 8 + second_line_height  # Отступы + строки + spacing
        return QSize(hint.width(), max(hint.height(), min_height))

    def _on_delete_clicked(self):
        self.delete_requested.emit(self.file_path)


class FilesPanel(QWidget):
    """Панель управления файлами тест-кейса с drag & drop и привязкой к шагам."""

    # Сигнал для обновления attachments в шагах
    attachment_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_test_case: Optional[TestCase] = None
        self._attached_files: List[Path] = []  # Все файлы из _attachment
        self._file_to_steps: dict[Path, List[int]] = {}  # Маппинг: файл -> индексы шагов
        self._setup_ui()
        self.setAcceptDrops(True)

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
        content_layout.setContentsMargins(
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
            UI_METRICS.container_padding,
        )
        content_layout.setSpacing(UI_METRICS.section_spacing)

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Заголовок с кнопкой (как в панели "Отчетность")
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)
        
        title_label = QLabel("Файлы")
        # Используем тот же стиль заголовка, что и в панели "Отчетность"
        title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        content_layout.addLayout(title_layout)

        # Список прикрепленных файлов (перемещен наверх)
        self.files_list = QListWidget()
        content_layout.addWidget(self.files_list)
        self._update_files_height()

        # Инструкция (перемещена вниз)
        instruction_label = QLabel("Отображение прикрепленных файлов. Для прикрепления файлов используйте таблицу шагов.")
        instruction_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        instruction_label.setWordWrap(True)
        content_layout.addWidget(instruction_label)
        
        # Добавляем растягивающийся элемент в конец, чтобы заголовок всегда был сверху
        content_layout.addStretch()

    # --- Публичные методы ---

    def load_test_case(self, test_case: Optional[TestCase]):
        """Загрузить тест-кейс и показать его прикрепленные файлы с информацией о привязке к шагам."""
        self.current_test_case = test_case
        self._attached_files.clear()
        self._file_to_steps.clear()
        self.files_list.clear()

        if not test_case or not test_case._filepath:
            self._update_files_height()
            return

        # Получаем идентификатор тест-кейса для фильтрации файлов
        test_case_id = test_case.id or ""
        if not test_case_id:
            self._update_files_height()
            return

        # Собираем все файлы из папки _attachment, которые содержат идентификатор тест-кейса в названии
        attachment_dir = self._get_attachment_directory()
        if attachment_dir and attachment_dir.exists() and attachment_dir.is_dir():
            try:
                # Ищем все файлы в папке _attachment
                for file_path in attachment_dir.iterdir():
                    if not file_path.is_file():
                        continue
                    
                    # Проверяем, содержит ли имя файла идентификатор тест-кейса
                    file_name = file_path.name
                    if test_case_id in file_name:
                        if file_path not in self._attached_files:
                            self._attached_files.append(file_path)
            except (OSError, PermissionError):
                # Если не удалось прочитать папку, просто пропускаем
                pass

        # Сортируем список файлов
        self._attached_files = sorted(set(self._attached_files))

        # Строим маппинг файлов к шагам из attachments шагов
        self._build_file_to_steps_mapping()

        self._refresh_files_list()
        self._update_files_height()

    def _build_file_to_steps_mapping(self):
        """Построить маппинг файлов к шагам на основе attachments в шагах."""
        if not self.current_test_case:
            return

        self._file_to_steps.clear()
        attachment_dir = self._get_attachment_directory()
        test_case_id = self.current_test_case.id or ""

        if not test_case_id or not attachment_dir:
            return

        # Проходим по всем шагам и собираем информацию о прикрепленных файлах
        for step_idx, step in enumerate(self.current_test_case.steps):
            if not step.attachments:
                continue

            for attachment_path_str in step.attachments:
                try:
                    attachment_path = Path(attachment_path_str)
                    
                    # Если путь относительный, делаем абсолютный относительно папки _attachment
                    if not attachment_path.is_absolute():
                        attachment_path = attachment_dir / attachment_path.name
                    else:
                        # Проверяем, что файл находится в папке _attachment
                        try:
                            if attachment_dir in attachment_path.parents or attachment_path.parent == attachment_dir:
                                pass  # Файл в правильной папке
                            else:
                                # Файл не в _attachment, пропускаем
                                continue
                        except (ValueError, AttributeError):
                            # Если не удалось сравнить пути, пропускаем
                            continue

                    # Проверяем, что файл существует
                    if not attachment_path.exists():
                        continue
                    
                    # Проверяем, содержит ли имя файла идентификатор тест-кейса
                    file_name = attachment_path.name
                    if test_case_id not in file_name:
                        continue

                    # Добавляем в маппинг только если файл уже в списке _attached_files
                    if attachment_path in self._attached_files:
                        if attachment_path not in self._file_to_steps:
                            self._file_to_steps[attachment_path] = []
                        
                        if step_idx not in self._file_to_steps[attachment_path]:
                            self._file_to_steps[attachment_path].append(step_idx)

                except (ValueError, OSError, AttributeError, TypeError):
                    # Если не удалось разобрать путь, пропускаем
                    continue

    def _get_attachment_directory(self) -> Optional[Path]:
        """Получить путь к папке _attachment для текущего тест-кейса."""
        if not self.current_test_case or not hasattr(self.current_test_case, '_filepath') or not self.current_test_case._filepath:
            return None

        try:
            # Папка тест-кейса - это родительская папка файла
            test_case_dir = self.current_test_case._filepath.parent
            attachment_dir = test_case_dir / "_attachment"
            return attachment_dir
        except (AttributeError, TypeError):
            return None

    def _process_files(self, file_paths: List[Path]):
        """Обработать список файлов для прикрепления."""
        if not self.current_test_case:
            return

        attachment_dir = self._get_attachment_directory()
        test_case_id = self.current_test_case.id or ""

        if not test_case_id:
            QMessageBox.warning(
                self,
                "Нет ID тест-кейса",
                "Не удалось определить ID тест-кейса. Файлы не могут быть прикреплены."
            )
            return

        # Проверяем, есть ли шаги в тест-кейсе
        if not self.current_test_case.steps:
            reply = QMessageBox.question(
                self,
                "Нет шагов в тест-кейсе",
                "В тест-кейсе нет шагов. Файлы можно прикрепить только к шагам.\n\nСоздать новый шаг?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            # TODO: Можно добавить логику создания шага, но пока просто сообщаем об ошибке
            QMessageBox.warning(
                self,
                "Невозможно прикрепить файл",
                "Пожалуйста, сначала создайте хотя бы один шаг в тест-кейсе."
            )
            return

        # Создаем папку _attachment если её нет
        attachment_dir.mkdir(exist_ok=True)

        copied_files = []

        for source_file in file_paths:
            if not source_file.exists() or not source_file.is_file():
                continue

            # Формируем новое имя: {id тест-кейса}_{оригинальное имя}.{расширение}
            original_name = source_file.stem  # Имя без расширения
            extension = source_file.suffix  # Расширение с точкой
            new_name = f"{test_case_id}_{original_name}{extension}"
            target_file = attachment_dir / new_name

            # Проверяем, существует ли уже такой файл
            if target_file.exists():
                # Предлагаем переименовать
                new_name_custom, ok = QInputDialog.getText(
                    self,
                    "Файл уже существует",
                    f"Файл '{new_name}' уже существует.\nВведите новое имя (без расширения):",
                    text=original_name
                )

                if not ok or not new_name_custom.strip():
                    continue  # Пропускаем этот файл

                new_name = f"{test_case_id}_{new_name_custom.strip()}{extension}"
                target_file = attachment_dir / new_name

                # Проверяем еще раз на случай, если пользователь ввел имя, которое тоже существует
                if target_file.exists():
                    QMessageBox.warning(
                        self,
                        "Файл уже существует",
                        f"Файл '{new_name}' также уже существует. Файл пропущен."
                    )
                    continue

            try:
                # Копируем файл
                shutil.copy2(source_file, target_file)
                copied_files.append(target_file)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Ошибка копирования",
                    f"Не удалось скопировать файл '{source_file.name}':\n{str(e)}"
                )

        # Для каждого скопированного файла выбираем шаг для прикрепления
        for target_file in copied_files:
            step_idx = self._select_step_for_attachment()
            if step_idx is not None:
                self._attach_file_to_step(target_file, step_idx)
            else:
                # Если шаг не выбран, просто добавляем файл в список, но не прикрепляем к шагам
                pass

        # Обновляем список
        if copied_files:
            self._attached_files.extend(copied_files)
            self._attached_files = sorted(set(self._attached_files))  # Убираем дубликаты
            self._refresh_files_list()
            # Эмитируем сигнал об изменении attachments
            self.attachment_changed.emit()

    def _select_step_for_attachment(self) -> Optional[int]:
        """Выбрать шаг для прикрепления файла. Возвращает индекс шага или None."""
        if not self.current_test_case or not self.current_test_case.steps:
            return None

        # Создаем список вариантов для выбора
        step_options = []
        for idx, step in enumerate(self.current_test_case.steps):
            step_description = step.description or step.name or f"Шаг {idx + 1}"
            # Берем первую строку описания для отображения
            first_line = step_description.splitlines()[0] if step_description else ""
            if len(first_line) > 50:
                first_line = first_line[:47] + "..."
            step_options.append(f"Шаг {idx + 1}: {first_line}")

        # Диалог выбора шага
        step_text, ok = QInputDialog.getItem(
            self,
            "Выберите шаг",
            "К какому шагу прикрепить файл?",
            step_options,
            0,  # Индекс по умолчанию (первый шаг)
            False  # Не editable
        )

        if not ok:
            return None

        # Находим индекс выбранного шага
        try:
            selected_idx = step_options.index(step_text)
            return selected_idx
        except ValueError:
            return None

    def _attach_file_to_step(self, file_path: Path, step_idx: int):
        """Прикрепить файл к указанному шагу."""
        if not self.current_test_case:
            return

        if step_idx < 0 or step_idx >= len(self.current_test_case.steps):
            return

        step = self.current_test_case.steps[step_idx]
        
        # Используем относительный путь от папки тест-кейса
        attachment_dir = self._get_attachment_directory()
        if not attachment_dir:
            # Если нет папки, используем имя файла
            file_path_str = file_path.name
        else:
            try:
                # Делаем относительный путь для хранения в attachments
                relative_path = file_path.relative_to(attachment_dir)
                file_path_str = str(relative_path)
            except (ValueError, TypeError):
                # Если не получается сделать относительный, используем имя файла
                file_path_str = file_path.name

        # Добавляем в attachments шага, если ещё не добавлен
        if file_path_str not in step.attachments:
            step.attachments.append(file_path_str)

        # Обновляем маппинг
        if file_path not in self._file_to_steps:
            self._file_to_steps[file_path] = []
        if step_idx not in self._file_to_steps[file_path]:
            self._file_to_steps[file_path].append(step_idx)
            self._file_to_steps[file_path].sort()  # Сортируем для красоты

    def _choose_files(self):
        """Выбрать файлы через проводник."""
        if not self.current_test_case:
            QMessageBox.warning(
                self,
                "Нет выбранного тест-кейса",
                "Пожалуйста, сначала выберите тест-кейс для прикрепления файлов."
            )
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для прикрепления",
            "",
            "Все файлы (*.*)",
        )

        if not files:
            return

        file_paths = [Path(path) for path in files]
        self._process_files(file_paths)

    def _refresh_files_list(self):
        """Обновить список отображаемых файлов."""
        self.files_list.clear()
        if not self._attached_files:
            self._update_files_height()
            return

        for file_path in self._attached_files:
            # Получаем список шагов, к которым прикреплен файл
            attached_to_steps = self._file_to_steps.get(file_path, [])
            item_widget = FileItemWidget(file_path, attached_to_steps)
            item_widget.delete_requested.connect(self._remove_file)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            self.files_list.addItem(item)
            self.files_list.setItemWidget(item, item_widget)

        self._update_files_height()

    def _remove_file(self, file_path: Path):
        """Удалить файл из списка, из attachments шагов и с диска."""
        # Проверяем, к каким шагам прикреплен файл
        attached_to_steps = self._file_to_steps.get(file_path, [])
        
        if attached_to_steps:
            steps_text = ", ".join([f"Шаг {idx + 1}" for idx in attached_to_steps])
            message = (
                f"Вы уверены, что хотите удалить файл '{file_path.name}'?\n\n"
                f"Файл прикреплен к: {steps_text}\n"
                f"Файл будет удален с диска и убран из всех шагов."
            )
        else:
            message = (
                f"Вы уверены, что хотите удалить файл '{file_path.name}'?\n\n"
                f"Файл будет удален с диска."
            )

        reply = QMessageBox.question(
            self,
            "Удалить файл",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            # Удаляем файл из attachments всех шагов
            if self.current_test_case:
                attachment_dir = self._get_attachment_directory()
                if not attachment_dir:
                    # Если нет папки, просто удаляем из списка
                    pass
                else:
                    for step in self.current_test_case.steps:
                        if not step.attachments:
                            continue
                        
                        # Удаляем все упоминания этого файла из attachments
                        updated_attachments = []
                        for attachment_path_str in step.attachments:
                            try:
                                attachment_path = Path(attachment_path_str)
                                if not attachment_path.is_absolute():
                                    attachment_path = attachment_dir / attachment_path.name
                                
                                # Если путь указывает на удаляемый файл, пропускаем
                                if attachment_path.resolve() == file_path.resolve():
                                    continue
                                
                                updated_attachments.append(attachment_path_str)
                            except Exception:
                                # Если не удалось разобрать путь, оставляем как есть
                                updated_attachments.append(attachment_path_str)
                        
                        step.attachments = updated_attachments

            # Удаляем файл с диска
            if file_path.exists():
                file_path.unlink()

            # Удаляем из списка и маппинга
            if file_path in self._attached_files:
                self._attached_files.remove(file_path)
            if file_path in self._file_to_steps:
                del self._file_to_steps[file_path]

            self._refresh_files_list()
            # Эмитируем сигнал об изменении attachments
            self.attachment_changed.emit()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка удаления",
                f"Не удалось удалить файл '{file_path.name}':\n{str(e)}"
            )

    def _update_files_height(self):
        """Адаптировать высоту списка файлов."""
        count = max(self.files_list.count(), 1)
        frame = self.files_list.frameWidth() * 2
        if self.files_list.count() > 0:
            metrics_height = self.files_list.sizeHintForRow(0)
        else:
            metrics_height = self.files_list.fontMetrics().height() + 12
        new_height = frame + metrics_height * count
        self.files_list.setFixedHeight(min(new_height, 300))  # Максимум 300px
