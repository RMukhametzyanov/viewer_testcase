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

    # Минимальная ширина контрольных элементов (кнопок и т.п.)
    control_min_width: int = 12
    # Радиус скругления для кнопок/панелей
    control_radius: int = 3
    # Радиус скругления для текстовых полей/списков
    input_radius: int = 4

    # Отступы внутри элементов списков/дерева
    list_item_padding: int = 5
    # Горизонтальные внутренние отступы контролов
    control_padding_horizontal: int = 2
    # Дополнительные отступы внутри панелей вкладок
    tab_padding: int = 9

    @property
    def control_min_height(self) -> int:
        """Минимальная высота интерактивных контролов, вычисляется на основе размера шрифта"""
        # Вычисляем высоту пропорционально размеру шрифта
        # Формула: размер шрифта + 30% от размера + небольшой фиксированный отступ
        # Для 13px -> ~18px, для 16px -> ~22px, для 20px -> ~28px
        return self.base_font_size + int(self.base_font_size * 0.3) + 2

    @property
    def control_padding_vertical(self) -> int:
        """Вертикальные внутренние отступы контролов, вычисляются на основе размера шрифта"""
        # Пропорционально размеру шрифта: для 13px -> 10px, для 16px -> ~12px
        return max(int(self.base_font_size * 0.75), 8)

    @property
    def text_vertical_padding(self) -> int:
        """Дополнительный внутренний отступ для текстовых полей сверху/снизу"""
        # Пропорционально размеру шрифта: для 13px -> 2px, для 16px -> ~3px
        return max(int(self.base_font_size * 0.15), 2)


UI_METRICS = UIMetrics()

