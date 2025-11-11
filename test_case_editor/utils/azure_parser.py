"""Утилиты для конвертации тест-кейсов из Azure DevOps."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


_HTML_ENTITIES = {
    "&lt;": "<",
    "&gt;": ">",
    "&amp;": "&",
    "&quot;": '"',
    "&nbsp;": " ",
    "&BR/&gt;": "\n",
    "&BR/": "\n",
    "&amp;nbsp;": " ",
}


def clean_azure_text(text: Optional[str]) -> str:
    """
    Очистка HTML-содержимого шага Azure DevOps.

    Args:
        text: исходная строка

    Returns:
        Очищенная строка.
    """
    if not text:
        return ""

    # Унифицируем переносы строк
    text = text.replace("\r\n", "\n")

    for entity, replacement in _HTML_ENTITIES.items():
        text = text.replace(entity, replacement)

    # Удаляем HTML-теги
    text = re.sub(r"<[^>]+>", "", text)

    # Схлопываем множественные пробелы и пустые строки
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n ", "\n", text)

    return text.strip()


def extract_azure_steps(steps_xml: Optional[str]) -> List[Dict[str, str]]:
    """
    Извлечение шагов тест-кейса из XML-представления Azure DevOps.

    Args:
        steps_xml: XML со списком шагов.

    Returns:
        Список шагов с типом, действием и ожидаемым результатом.
    """
    if not steps_xml:
        return []

    steps: List[Dict[str, str]] = []
    step_pattern = r'<step id="(\d+)" type="(\w+)">(.*?)</step>'
    matches = re.findall(step_pattern, steps_xml, re.DOTALL)

    for step_id, step_type, content in matches:
        param_pattern = r"<parameterizedString[^>]*>(.*?)</parameterizedString>"
        params = re.findall(param_pattern, content, re.DOTALL)

        action = clean_azure_text(params[0]) if len(params) > 0 else ""
        expected = clean_azure_text(params[1]) if len(params) > 1 else ""

        steps.append(
            {
                "id": step_id,
                "type": step_type,
                "action": action,
                "expected": expected,
            }
        )

    return steps


def parse_azure_test_cases(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Разбор JSON-ответа Azure DevOps в структуру для конвертации.

    Args:
        payload: исходный JSON.

    Returns:
        Список словарей с данными тест-кейсов.
    """
    results: List[Dict[str, Any]] = []

    for entry in payload.get("value", []):
        work_item = entry.get("workItem", {}) or {}
        work_item_fields = work_item.get("workItemFields", []) or []

        # Извлекаем XML со шагами
        steps_xml = None
        additional_fields: Dict[str, Any] = {}

        for field in work_item_fields:
            if "Microsoft.VSTS.TCM.Steps" in field:
                steps_xml = field.get("Microsoft.VSTS.TCM.Steps")
            else:
                additional_fields.update(field)

        steps = extract_azure_steps(steps_xml)

        results.append(
            {
                "id": work_item.get("id"),
                "title": work_item.get("name") or "Без названия",
                "steps": steps,
                "plan": entry.get("testPlan", {}) or {},
                "suite": entry.get("testSuite", {}) or {},
                "project": entry.get("project", {}) or {},
                "additional_fields": additional_fields,
            }
        )

    return results


__all__ = ["clean_azure_text", "extract_azure_steps", "parse_azure_test_cases"]


