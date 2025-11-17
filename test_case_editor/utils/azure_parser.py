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
    "&amp;nbsp;": " ",
    "&#160;": " ",
}

_BLOCK_BREAK_TAGS = (
    "p",
    "div",
    "section",
    "article",
    "header",
    "footer",
    "blockquote",
    "pre",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
)


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

    # Переводим HTML-переносы и блочные элементы в явные переносы строк
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)

    for tag in _BLOCK_BREAK_TAGS:
        # Закрывающий тег → перенос строки
        text = re.sub(fr"(?i)</\s*{tag}\s*>", "\n", text)
        # Маркируем элементы списка
        if tag == "li":
            text = re.sub(r"(?i)<\s*li[^>]*>", "- ", text)
        else:
            text = re.sub(fr"(?i)<\s*{tag}[^>]*>", "", text)
    # Очищаем оставшиеся теги
    text = re.sub(r"<[^>]+>", "", text)

    # Нормализуем переводы строк
    text = text.replace("\r\n", "\n").replace("\r", "\n")

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
    if not payload:
        return []

    value = payload.get("value")
    if isinstance(value, list):
        results: List[Dict[str, Any]] = []
        for entry in value:
            parsed = _parse_collection_entry(entry)
            if parsed:
                results.append(parsed)
        return results

    single_case = _parse_single_work_item(payload)
    return [single_case] if single_case else []


def _parse_collection_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    work_item = entry.get("workItem", {}) or {}
    work_item_fields = work_item.get("workItemFields", []) or []

    steps_xml = None
    additional_fields: Dict[str, Any] = {}

    for field in work_item_fields:
        if not isinstance(field, dict):
            continue
        if "Microsoft.VSTS.TCM.Steps" in field:
            steps_xml = field.get("Microsoft.VSTS.TCM.Steps")
        else:
            additional_fields.update(field)

    return {
        "id": work_item.get("id"),
        "title": work_item.get("name")
        or additional_fields.get("System.Title")
        or "Без названия",
        "steps": extract_azure_steps(steps_xml),
        "plan": entry.get("testPlan", {}) or {},
        "suite": entry.get("testSuite", {}) or {},
        "project": entry.get("project", {}) or {},
        "additional_fields": additional_fields,
    }


def _parse_single_work_item(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = payload.get("fields") or {}
    if not isinstance(fields, dict):
        return None

    steps_xml = fields.get("Microsoft.VSTS.TCM.Steps")
    additional_fields = {
        key: value for key, value in fields.items() if key != "Microsoft.VSTS.TCM.Steps"
    }

    return {
        "id": payload.get("id") or additional_fields.get("System.Id"),
        "title": additional_fields.get("System.Title") or "Без названия",
        "steps": extract_azure_steps(steps_xml),
        "plan": payload.get("testPlan", {}) or {},
        "suite": payload.get("testSuite", {}) or {},
        "project": payload.get("project", {}) or {},
        "additional_fields": additional_fields,
    }


__all__ = ["clean_azure_text", "extract_azure_steps", "parse_azure_test_cases"]


