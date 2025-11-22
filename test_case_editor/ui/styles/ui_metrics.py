"""Configurable UI metrics for spacing, fonts and sizing."""

from dataclasses import dataclass


@dataclass
class UIMetrics:
    # Базовое семейство шрифтов (в стиле Cursor - Inter/JetBrains Mono)
    font_family: str = "'Inter', 'JetBrains Mono', 'Segoe UI', 'Roboto', system-ui, sans-serif"
    # Размер основного шрифта в пунктах
    base_font_size: int = 13

    # Внешний отступ вокруг главного окна (layout центрального виджета)
    # Настраивается через настройки
    window_margin: int = 8
    # Стандартный промежуток между элементами (layout spacing)
    # Настраивается через настройки
    base_spacing: int = 12
    # Вертикальные интервалы между большими секциями формы/панелей
    # Настраивается через настройки
    section_spacing: int = 8
    # Внутренние отступы контейнеров (панелей, групп)
    # Настраивается через настройки
    container_padding: int = 12
    # Отступы в шапке окна и других хедерах
    # Настраивается через настройки
    header_padding: int = 6

    # Минимальная ширина контрольных элементов (кнопок и т.п.)
    control_min_width: int = 12
    # Радиус скругления для кнопок/панелей (малые скругления как в Cursor)
    control_radius: int = 6
    # Радиус скругления для текстовых полей/списков
    input_radius: int = 6

    # Отступы внутри элементов списков/дерева
    # Настраивается через настройки
    list_item_padding: int = 8
    # Горизонтальные внутренние отступы контролов
    # Настраивается через настройки
    control_padding_horizontal: int = 12
    # Дополнительные отступы внутри панелей вкладок
    tab_padding: int = 12
    # Вертикальные отступы для текстовых полей (сверху и снизу до текста)
    # Настраивается через настройки приложения
    text_input_vertical_padding: int = 2
    # Отступ заголовка QGroupBox до содержимого
    # Настраивается через настройки приложения
    group_title_spacing: int = 1

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


UI_METRICS = UIMetrics()

