"""Утилиты для работы с датой и временем"""

from datetime import datetime


def format_datetime(datetime_str: str) -> str:
    """
    Форматирование даты и времени в человекочитаемый формат
    
    Args:
        datetime_str: Строка с датой в ISO формате (YYYY-MM-DDTHH:MM:SS)
    
    Returns:
        Отформатированная строка (YYYY-MM-DD HH:MM) или исходная строка при ошибке
    """
    if not datetime_str:
        return ""
    
    try:
        dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return datetime_str


def get_current_datetime() -> str:
    """
    Получить текущую дату и время в ISO формате
    
    Returns:
        Строка с текущей датой и временем (YYYY-MM-DDTHH:MM:SS)
    """
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


