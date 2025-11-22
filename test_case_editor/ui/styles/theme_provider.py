"""Система тем в стиле Cursor с поддержкой light/dark режимов"""

from dataclasses import dataclass
from typing import Dict, Literal

ThemeName = Literal["dark", "light"]


@dataclass
class ThemeColors:
    """Цветовая схема темы"""
    # Основные цвета фона
    background: str  # Основной фон приложения
    background_elevated: str  # Фон панелей/карточек
    background_hover: str  # Фон при наведении
    background_pressed: str  # Фон при нажатии
    
    # Цвета текста
    text_primary: str  # Основной текст
    text_secondary: str  # Вторичный текст
    text_disabled: str  # Неактивный текст
    
    # Границы
    border_primary: str  # Основная граница
    border_secondary: str  # Вторичная граница
    border_hover: str  # Граница при наведении
    
    # Акцентные цвета (Cursor использует синие оттенки)
    accent_primary: str  # Основной акцент (синий)
    accent_hover: str  # Акцент при наведении
    accent_pressed: str  # Акцент при нажатии
    
    # Состояния
    success: str  # Успех (зеленый)
    warning: str  # Предупреждение (желтый)
    error: str  # Ошибка (красный)
    info: str  # Информация (голубой)
    
    # Выделение и выбор
    selection_background: str  # Фон выделенного элемента
    selection_text: str  # Текст выделенного элемента
    
    # Интерактивные элементы
    button_background: str  # Фон кнопки
    button_hover: str  # Кнопка при наведении
    button_pressed: str  # Кнопка при нажатии
    
    # Поля ввода
    input_background: str  # Фон поля ввода
    input_border: str  # Граница поля ввода
    input_focus: str  # Граница при фокусе
    
    # Тени (для разделения слоев)
    shadow_small: str  # Малая тень
    shadow_medium: str  # Средняя тень
    shadow_large: str  # Большая тень


# Темная тема в стиле Cursor
DARK_THEME = ThemeColors(
    background="#0d1117",  # Почти черный фон (как в Cursor)
    background_elevated="#161b22",  # Панели чуть светлее
    background_hover="#1c2128",  # При наведении
    background_pressed="#0d1117",  # При нажатии
    
    text_primary="#e6edf3",  # Основной текст (почти белый)
    text_secondary="#8b949e",  # Вторичный текст (серый)
    text_disabled="#6e7681",  # Неактивный текст
    
    border_primary="#30363d",  # Основная граница
    border_secondary="#21262d",  # Вторичная граница
    border_hover="#3d444d",  # Граница при наведении
    
    accent_primary="#58a6ff",  # Синий акцент Cursor
    accent_hover="#79c0ff",  # Светлее при наведении
    accent_pressed="#3589d4",  # Темнее при нажатии
    
    success="#3fb950",  # Зеленый
    warning="#d29922",  # Желтый
    error="#f85149",  # Красный
    info="#58a6ff",  # Голубой
    
    selection_background="#264f78",  # Синий фон выделения
    selection_text="#ffffff",  # Белый текст
    
    button_background="#21262d",  # Фон кнопки
    button_hover="#30363d",  # Кнопка при наведении
    button_pressed="#161b22",  # Кнопка при нажатии
    
    input_background="#0d1117",  # Фон поля ввода
    input_border="#30363d",  # Граница поля
    input_focus="#58a6ff",  # Граница при фокусе
    
    shadow_small="0 1px 3px rgba(0, 0, 0, 0.3), 0 1px 2px rgba(0, 0, 0, 0.2)",
    shadow_medium="0 4px 6px rgba(0, 0, 0, 0.4), 0 2px 4px rgba(0, 0, 0, 0.3)",
    shadow_large="0 10px 15px rgba(0, 0, 0, 0.5), 0 4px 6px rgba(0, 0, 0, 0.4)",
)

# Светлая тема в стиле Cursor
LIGHT_THEME = ThemeColors(
    background="#ffffff",  # Белый фон
    background_elevated="#f6f8fa",  # Панели чуть темнее
    background_hover="#f3f4f6",  # При наведении
    background_pressed="#e5e7eb",  # При нажатии
    
    text_primary="#24292f",  # Темный текст
    text_secondary="#57606a",  # Вторичный текст
    text_disabled="#8c959f",  # Неактивный текст
    
    border_primary="#d0d7de",  # Основная граница
    border_secondary="#e1e4e8",  # Вторичная граница
    border_hover="#c0c7d1",  # Граница при наведении
    
    accent_primary="#0969da",  # Синий акцент
    accent_hover="#0860ca",  # Темнее при наведении
    accent_pressed="#0757ba",  # Еще темнее при нажатии
    
    success="#1a7f37",  # Зеленый
    warning="#9a6700",  # Желтый
    error="#cf222e",  # Красный
    info="#0969da",  # Голубой
    
    selection_background="#b6e3ff",  # Светло-синий фон выделения
    selection_text="#24292f",  # Темный текст
    
    button_background="#f6f8fa",  # Фон кнопки
    button_hover="#f3f4f6",  # Кнопка при наведении
    button_pressed="#e5e7eb",  # Кнопка при нажатии
    
    input_background="#ffffff",  # Фон поля ввода
    input_border="#d0d7de",  # Граница поля
    input_focus="#0969da",  # Граница при фокусе
    
    shadow_small="0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.08)",
    shadow_medium="0 4px 6px rgba(0, 0, 0, 0.15), 0 2px 4px rgba(0, 0, 0, 0.12)",
    shadow_large="0 10px 15px rgba(0, 0, 0, 0.2), 0 4px 6px rgba(0, 0, 0, 0.15)",
)


class ThemeProvider:
    """Провайдер тем для приложения"""
    
    _themes: Dict[ThemeName, ThemeColors] = {
        "dark": DARK_THEME,
        "light": LIGHT_THEME,
    }
    
    def __init__(self, theme_name: ThemeName = "dark"):
        self._current_theme = theme_name
    
    @property
    def current_theme_name(self) -> ThemeName:
        """Возвращает название текущей темы"""
        return self._current_theme
    
    @property
    def colors(self) -> ThemeColors:
        """Возвращает цвета текущей темы"""
        return self._themes[self._current_theme]
    
    def set_theme(self, theme_name: ThemeName):
        """Установить тему"""
        if theme_name not in self._themes:
            raise ValueError(f"Unknown theme: {theme_name}")
        self._current_theme = theme_name
    
    @classmethod
    def get_available_themes(cls) -> list[ThemeName]:
        """Возвращает список доступных тем"""
        return list(cls._themes.keys())


# Глобальный экземпляр провайдера тем
THEME_PROVIDER = ThemeProvider("dark")

