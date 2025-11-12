"""
Утилиты для формирования промта ревью.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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
        f"{task_block}"
    )


