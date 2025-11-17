"""
Утилиты для формирования промта ревью.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


ENCODING = "utf-8"


@dataclass
class PromptArtifacts:
    """Содержимое файлов, используемое для формирования промта."""

    methodic: str
    chtz: str
    test_case: str


def _read_text_file(path: Optional[Path]) -> str:
    """Безопасное чтение текста из файла."""
    if not path:
        return ""

    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return ""

    try:
        return file_path.read_text(encoding=ENCODING)
    except UnicodeDecodeError:
        return file_path.read_text(encoding=ENCODING, errors="replace")
    except OSError:
        return ""


def collect_prompt_artifacts(
    methodic_path: Optional[Path],
    *,
    test_case_path: Optional[Path] = None,
    chtz_path: Optional[Path] = None,
) -> PromptArtifacts:
    """
    Собрать текстовое содержимое методики, ЧТЗ и тест-кейса.
    """

    return PromptArtifacts(
        methodic=_read_text_file(methodic_path),
        chtz=_read_text_file(chtz_path),
        test_case=_read_text_file(test_case_path),
    )


def build_review_prompt(
    methodic_path: Optional[Path],
    default_prompt: str,
    *,
    test_case_path: Optional[Path] = None,
    chtz_path: Optional[Path] = None,
) -> str:
    """
    Сформировать текст промта для панели ревью на основе файлов и базового задания.
    """

    artifacts = collect_prompt_artifacts(
        methodic_path,
        test_case_path=test_case_path,
        chtz_path=chtz_path,
    )

    methodic_block = artifacts.methodic.strip() or "[Методика не найдена]"
    chtz_block = artifacts.chtz.strip() or "[ЧТЗ не прикреплено]"
    test_case_block = artifacts.test_case.strip() or "[Тест-кейс не найден]"
    task_block = (default_prompt or "").strip() or "[Не задана задача ревью]"

    return (
        "Твоя роль QA-инженер с многолетним опытом, который совершенствует корпоративные "
        "тест-кейсы, приводит их в соответствие корпоративному стилю — результаты твоей работы "
        "должны быть эталоном для команды.\n\n"
        "Для ревью тест-кейсов используй методику:\n\n"
        f"{methodic_block}\n\n"
        "Также используй ЧТЗ:\n\n"
        f"{chtz_block}\n\n"
        "Тест-кейс для анализа:\n\n"
        f"{test_case_block}\n\n"
        "Твоя задача:\n"
        f"{task_block}\n\n"
        "Ответ предоставь на русском языке."
    )


def build_creation_prompt(
    methodic_path: Optional[Path],
    tech_task_paths: Iterable[Path],
    task_text: str,
) -> str:
    """
    Сформировать промт для генерации тест-кейсов.
    """

    methodic_block = (_read_text_file(methodic_path)).strip() or "[Методика не найдена]"

    unique_paths: list[Path] = []
    seen = set()
    for raw_path in tech_task_paths:
        path = Path(raw_path)
        try:
            key = path.resolve()
        except OSError:
            key = path
        if key in seen:
            continue
        seen.add(key)
        unique_paths.append(path)

    tech_blocks: list[str] = []
    for path in unique_paths:
        content = _read_text_file(path).strip()
        if not content:
            continue
        header = f"{path.name}\n" if len(unique_paths) > 1 else ""
        tech_blocks.append(f"{header}{content}")

    tech_task_block = "\n\n".join(tech_blocks).strip() or "[Постановка задачи не прикреплена]"
    task_block = (task_text or "").strip() or "[Не задана задача создания тест-кейса]"

    return (
        "Твоя роль QA-инженер с многолетним опытом, который совершенствует корпоративные "
        "тест-кейсы, приводит их в соответствие корпоративному стилю — результаты твоей работы "
        "должны быть эталоном для команды.\n\n"
        "Для создания тест-кейсов используй методику:\n\n"
        f"<context>{methodic_block}</context>\n\n"
        "При создании тест-кейсов используй постановку задачи:\n\n"
        f"<context>{tech_task_block}</context>\n\n"
        "Твоя задача:\n\n"
        f"<task>{task_block}</task>\n\n"
        "Верни результат строго в формате JSON без пояснений и лишнего текста. Структура ответа:\n"
        "{\n"
        '  "test_cases": [\n'
        "    {\n"
        '      "id": "uuid",\n'
        '      "name": "string",\n'
        '      "description": "string",\n'
        '      "preconditions": "string",\n'
        '      "expectedResult": "string",\n'
        '      "epic": "string",\n'
        '      "feature": "string",\n'
        '      "story": "string",\n'
        '      "component": "string",\n'
        '      "testLayer": "Unit | API | UI | E2E | Integration",\n'
        '      "severity": "BLOCKER | CRITICAL | MAJOR | NORMAL | MINOR",\n'
        '      "priority": "HIGHEST | HIGH | MEDIUM | LOW | LOWEST",\n'
        '      "environment": "string",\n'
        '      "browser": "string",\n'
        '      "owner": "string",\n'
        '      "author": "string",\n'
        '      "reviewer": "string",\n'
        '      "testCaseId": "string",\n'
        '      "issueLinks": "string",\n'
        '      "testCaseLinks": "string",\n'
        '      "tags": "tag1, tag2",\n'
        '      "status": "Draft | In Progress | Done | Blocked | Deprecated",\n'
        '      "testType": "manual | automated | hybrid",\n'
        '      "steps": [\n'
        "        {\n"
        '          "id": "uuid",\n'
        '          "name": "string",\n'
        '          "description": "string",\n'
        '          "expectedResult": "string",\n'
        '          "status": "pending | passed | failed",\n'
        '          "bugLink": "string",\n'
        '          "skipReason": "string",\n'
        '          "attachments": "comma separated ids"\n'
        "        }\n"
        "      ],\n"
        '      "createdAt": 1700000000000,\n'
        '      "updatedAt": 1700000000000\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Если тест-кейсов несколько, перечисли их в массиве \"test_cases\". "
        "Не добавляй текст вне JSON. Ответ предоставь на русском языке."
    )


