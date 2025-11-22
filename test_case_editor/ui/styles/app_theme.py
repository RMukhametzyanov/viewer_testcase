"""Qt style sheet assembled from configurable UI metrics."""

from .ui_metrics import UI_METRICS, UIMetrics
from .cursor_theme import build_cursor_style_sheet
from .theme_provider import ThemeProvider, THEME_PROVIDER


def build_app_style_sheet(metrics: UIMetrics, theme_provider: ThemeProvider = None) -> str:
    """Создать стиль приложения в стиле Cursor"""
    return build_cursor_style_sheet(metrics, theme_provider or THEME_PROVIDER)


# Глобальная переменная для хранения текущего стиля (deprecated, используйте build_app_style_sheet)
APP_STYLE_SHEET = build_app_style_sheet(UI_METRICS)

