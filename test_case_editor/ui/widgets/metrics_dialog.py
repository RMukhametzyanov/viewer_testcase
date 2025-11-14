"""Диалог настройки отступов и размеров интерфейса."""

from __future__ import annotations

from typing import Dict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QSpinBox,
    QLabel,
    QPushButton,
    QHBoxLayout,
)

from ..styles.ui_metrics import UI_METRICS


class MetricsDialog(QDialog):
    """Позволяет интерактивно изменять значения метрик UI."""

    metrics_changed = pyqtSignal(dict)

    FIELD_CONFIG = {
        "base_font_size": ("Размер шрифта", (8, 32)),
        "window_margin": ("Отступ окна", (0, 40)),
        "base_spacing": ("Базовый spacing", (0, 40)),
        "section_spacing": ("Отступ секций", (0, 60)),
        "container_padding": ("Padding контейнеров", (0, 40)),
        "header_padding": ("Padding заголовка", (0, 60)),
        "control_min_height": ("Мин. высота контролов", (12, 120)),
        "control_min_width": ("Мин. ширина контролов", (12, 120)),
        "control_radius": ("Скругление контролов", (0, 30)),
        "input_radius": ("Скругление инпутов", (0, 30)),
        "list_item_padding": ("Padding элементов списка", (0, 40)),
        "control_padding_vertical": ("Вертикальный padding", (0, 40)),
        "control_padding_horizontal": ("Горизонтальный padding", (0, 60)),
        "text_vertical_padding": ("Vertical padding текста", (0, 20)),
        "tab_padding": ("Padding вкладок", (0, 60)),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки отступов")
        self.setModal(False)
        self._spin_boxes: Dict[str, QSpinBox] = {}

        layout = QFormLayout(self)
        layout.setSpacing(10)

        for field, (label, limits) in self.FIELD_CONFIG.items():
            spin = QSpinBox(self)
            spin.setRange(*limits)
            spin.setSingleStep(1)
            spin.setValue(getattr(UI_METRICS, field))
            spin.valueChanged.connect(lambda value, key=field: self._on_value_changed(key, value))
            layout.addRow(QLabel(label), spin)
            self._spin_boxes[field] = spin

        buttons_row = QHBoxLayout()
        close_btn = QPushButton("Закрыть", self)
        close_btn.clicked.connect(self.close)
        buttons_row.addStretch(1)
        buttons_row.addWidget(close_btn)
        layout.addRow(buttons_row)

    def refresh_values(self):
        """Синхронизировать спинбоксы с актуальными метриками."""
        for key, spin in self._spin_boxes.items():
            current = getattr(UI_METRICS, key)
            if spin.value() != current:
                spin.blockSignals(True)
                spin.setValue(current)
                spin.blockSignals(False)

    def _on_value_changed(self, field: str, value: int):
        self.metrics_changed.emit({field: value})

