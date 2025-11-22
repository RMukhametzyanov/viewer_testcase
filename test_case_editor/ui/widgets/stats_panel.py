"""Панель статистики по тест-кейсам."""

from __future__ import annotations

from __future__ import annotations

from collections import Counter
from typing import Iterable, Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget, QFrame, QPushButton, QHBoxLayout, QGroupBox

from ...models import TestCase


class StatsPanel(QWidget):
    """Панель управления раннером и краткая статистика."""

    reset_all_statuses = pyqtSignal()
    mark_current_passed = pyqtSignal()
    reset_current_case = pyqtSignal()
    generate_allure = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Панель управления раннером")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(title)

        global_group = QGroupBox("Управление всеми тест-кейсами")
        global_layout = QHBoxLayout(global_group)
        global_layout.setSpacing(8)
        self.reset_button = QPushButton("Сбросить все статусы")
        self.reset_button.clicked.connect(self.reset_all_statuses.emit)
        global_layout.addWidget(self.reset_button)
        self.generate_button = QPushButton("Generate Allure")
        self.generate_button.clicked.connect(self.generate_allure.emit)
        global_layout.addWidget(self.generate_button)
        global_layout.addStretch(1)
        layout.addWidget(global_group)

        current_group = QGroupBox("Управление текущим тест-кейсом")
        current_layout = QHBoxLayout(current_group)
        current_layout.setSpacing(8)
        self.pass_button = QPushButton("All PASS")
        self.pass_button.clicked.connect(self.mark_current_passed.emit)
        current_layout.addWidget(self.pass_button)
        self.reset_current_button = QPushButton("Сбросить статусы текущего")
        self.reset_current_button.clicked.connect(self.reset_current_case.emit)
        current_layout.addWidget(self.reset_current_button)
        current_layout.addStretch(1)
        layout.addWidget(current_group)

        self.summary_label = QLabel()
        self.summary_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.summary_label.setWordWrap(True)
        self.summary_label.setFont(QFont("Segoe UI", 11))

        container = QFrame()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(self.summary_label)

        layout.addWidget(container, 1)
        layout.addStretch(1)
        self.update_statistics([])
        
        # По умолчанию кнопки заблокированы (режим редактирования)
        self.set_buttons_enabled(False)

    def set_buttons_enabled(self, enabled: bool):
        """Блокировать или разблокировать все кнопки в панели.
        
        Args:
            enabled: True для разблокировки (режим запуска тестов),
                    False для блокировки (режим редактирования)
        """
        self.reset_button.setEnabled(enabled)
        self.generate_button.setEnabled(enabled)
        self.pass_button.setEnabled(enabled)
        self.reset_current_button.setEnabled(enabled)

    def update_statistics(self, test_cases: Iterable[TestCase]) -> None:
        cases = list(test_cases or [])
        total = len(cases)
        if not total:
            self.summary_label.setText("Тест-кейсы не загружены.")
            return

        pending_cases = 0
        passed_cases = 0
        failed_cases = 0
        skipped_cases = 0

        for case in cases:
            steps = case.steps or []
            statuses = [s.status or "" for s in steps]
            if not statuses:
                pending_cases += 1
                continue

            normalized = [status.strip().lower() for status in statuses]
            if all(status in ("", "pending") for status in normalized):
                pending_cases += 1
                continue
            if all(status == "passed" for status in normalized):
                passed_cases += 1
                continue
            if any(status == "failed" for status in normalized):
                failed_cases += 1
            if any(status == "skipped" for status in normalized):
                skipped_cases += 1

        lines = [
            f"<b>Всего тест-кейсов:</b> {total}",
            f"<b>Без статуса прохождения:</b> {pending_cases}",
            f"<b>Все шаги <span style='color:#2ecc71;'>passed</span>:</b> {passed_cases}",
            f"<b>Есть <span style='color:#e74c3c;'>failed</span>:</b> {failed_cases}",
            f"<b>Есть <span style='color:#95a5a6;'>skipped</span>:</b> {skipped_cases}",
        ]

        self.summary_label.setText("<br>".join(lines))

