"""Configurable UI metrics for spacing, fonts and sizing."""

from dataclasses import dataclass


@dataclass
class UIMetrics:
    # Базовое семейство шрифтов, которое применяем к приложению
    font_family: str = "'Inter', 'Roboto', 'Segoe UI', sans-serif"
    # Размер основного шрифта в пунктах
    base_font_size: int = 13

    # Внешний отступ вокруг главного окна (layout центрального виджета)
    window_margin: int = 6
    # Стандартный промежуток между элементами (layout spacing)
    base_spacing: int = 10
    # Вертикальные интервалы между большими секциями формы/панелей
    section_spacing: int = 5
    # Внутренние отступы контейнеров (панелей, групп)
    container_padding: int = 6
    # Отступы в шапке окна и других хедерах
    header_padding: int = 6

    # Минимальная высота интерактивных контролов (кнопок, инпутов)
    control_min_height: int = 14
    # Минимальная ширина контрольных элементов (кнопок и т.п.)
    control_min_width: int = 12
    # Радиус скругления для кнопок/панелей
    control_radius: int = 3
    # Радиус скругления для текстовых полей/списков
    input_radius: int = 4

    # Отступы внутри элементов списков/дерева
    list_item_padding: int = 5
    # Вертикальные внутренние отступы контролов (например, кнопок)
    control_padding_vertical: int = 10
    # Горизонтальные внутренние отступы контролов
    control_padding_horizontal: int = 2
    # Дополнительный внутренний отступ для текстовых полей сверху/снизу
    text_vertical_padding: int = 2
    # Дополнительные отступы внутри панелей вкладок
    tab_padding: int = 9


UI_METRICS = UIMetrics()

