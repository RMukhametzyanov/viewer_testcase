"""Утилиты для работы с датой и временем."""

from __future__ import annotations

from datetime import datetime
from typing import Union

TimestampInput = Union[str, int, float, None]


def _try_parse_iso_datetime(value: str) -> int:
    """Преобразовать ISO-строку в timestamp (мс)."""
    formats = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    raise ValueError(f"Unsupported datetime format: {value}")


def ensure_timestamp_ms(value: TimestampInput) -> int:
    """
    Привести произвольное значение даты/времени к timestamp в миллисекундах.
    Возвращает 0, если определить значение не удалось.
    """
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if not text:
        return 0

    try:
        return int(float(text))
    except ValueError:
        pass

    try:
        return _try_parse_iso_datetime(text)
    except ValueError:
        return 0


def format_datetime(value: TimestampInput) -> str:
    """
    Форматирование даты и времени в человекочитаемый формат.

    Args:
        value: timestamp (мс) либо строковое представление

    Returns:
        Строка вида YYYY-MM-DD HH:MM либо исходное значение при ошибке.
    """
    if value is None or value == "":
        return ""

    timestamp = ensure_timestamp_ms(value)
    if timestamp == 0:
        return str(value)

    try:
        dt = datetime.fromtimestamp(timestamp / 1000)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return str(value)


def get_current_datetime() -> int:
    """
    Получить текущую дату и время в виде timestamp (мс).
    """
    return ensure_timestamp_ms(datetime.now().timestamp() * 1000)


