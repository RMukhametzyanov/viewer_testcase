"""Утилита для генерации Allure отчетов из JSON файлов тест-кейсов."""

import json
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..models.test_case import TestCase
from ..services.test_case_service import TestCaseService
from ..repositories.test_case_repository import TestCaseRepository


def generate_allure_report(
    test_cases_dir: Path,
    app_dir: Optional[Path] = None,
) -> Optional[Path]:
    """
    Генерирует папку с JSON файлами для Allure отчета.
    
    Args:
        test_cases_dir: Путь к папке с тест-кейсами
        app_dir: Путь к папке приложения (где находится run_app_v2.py)
                Если None, определяется автоматически
    
    Returns:
        Path к созданной папке с отчетами или None в случае ошибки
    """
    try:
        # Определяем папку приложения
        if app_dir is None:
            # Ищем run_app_v2.py в родительских директориях
            current_file = Path(__file__).resolve()
            # Поднимаемся на 3 уровня вверх от utils/ к корню проекта
            # utils -> test_case_editor -> (корень проекта)
            app_dir = current_file.parent.parent.parent
        
        # Создаем папку Reports
        reports_dir = app_dir / "Reports"
        reports_dir.mkdir(exist_ok=True)
        
        # Создаем подпапку с датой и временем
        dt = datetime.now()
        timestamp = dt.strftime("%Y_%m_%d_%H_%M")
        report_dir = reports_dir / timestamp
        report_dir.mkdir(exist_ok=True)
        
        # Загружаем тест-кейсы и конвертируем в Allure формат
        repository = TestCaseRepository()
        service = TestCaseService(repository)
        test_cases = service.load_all_test_cases(test_cases_dir)
        
        # Генерируем Allure JSON файлы
        generated_count = 0
        for test_case in test_cases:
            try:
                allure_result = _convert_to_allure_format(test_case)
                if allure_result:
                    # Создаем имя файла на основе ID тест-кейса
                    file_name = f"{test_case.id or uuid.uuid4()}-result.json"
                    file_path = report_dir / file_name
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(allure_result, f, ensure_ascii=False, indent=2)
                    generated_count += 1
            except Exception as e:
                print(f"Ошибка при конвертации тест-кейса {test_case.name}: {e}", file=sys.stderr)
        
        # Открываем проводник
        _open_explorer(report_dir)
        
        return report_dir
        
    except Exception as e:
        print(f"Ошибка при генерации Allure отчета: {e}", file=sys.stderr)
        return None


def _convert_to_allure_format(test_case: TestCase) -> Optional[Dict[str, Any]]:
    """
    Конвертирует тест-кейс в формат Allure Test Result JSON.
    
    Args:
        test_case: Тест-кейс для конвертации
    
    Returns:
        Словарь в формате Allure Test Result или None в случае ошибки
    """
    try:
        # Определяем общий статус теста на основе статусов шагов
        overall_status = _determine_overall_status(test_case)
        
        # Формируем labels для Allure
        labels = []
        
        # Epic, Feature, Story
        if test_case.epic:
            labels.append({"name": "epic", "value": test_case.epic})
        if test_case.feature:
            labels.append({"name": "feature", "value": test_case.feature})
        if test_case.story:
            labels.append({"name": "story", "value": test_case.story})
        
        # Severity
        if test_case.severity:
            labels.append({"name": "severity", "value": test_case.severity.upper()})
        
        # Test Layer
        if test_case.test_layer:
            labels.append({"name": "testLayer", "value": test_case.test_layer})
        
        # Tags
        for tag in test_case.tags:
            if tag:
                labels.append({"name": "tag", "value": tag})
        
        # Test Type
        if test_case.test_type:
            labels.append({"name": "testType", "value": test_case.test_type})
        
        # Environment, Browser
        if test_case.environment:
            labels.append({"name": "environment", "value": test_case.environment})
        if test_case.browser:
            labels.append({"name": "browser", "value": test_case.browser})
        
        # Owner, Author
        if test_case.owner:
            labels.append({"name": "owner", "value": test_case.owner})
        if test_case.author:
            labels.append({"name": "author", "value": test_case.author})
        
        # Формируем links
        links = []
        if test_case.test_case_id:
            links.append({
                "name": "test_case",
                "url": test_case.test_case_id,
                "type": "tms"
            })
        if test_case.issue_links:
            for issue in test_case.issue_links.split(","):
                issue = issue.strip()
                if issue:
                    links.append({
                        "name": issue,
                        "url": issue,
                        "type": "issue"
                    })
        
        # Конвертируем шаги в Allure steps
        allure_steps = []
        for idx, step in enumerate((test_case.steps or []), start=1):
            step_status = _map_step_status(step.status)
            
            # В форме: action_edit -> description, expected_edit -> expected_result
            # Формируем название шага из description (действие) - это основной текст
            action_text = step.description.strip() if step.description else ""
            step_name = action_text if action_text else (step.name.strip() if step.name else f"Шаг {idx}")
            
            # Если название шага слишком длинное, обрезаем его
            if len(step_name) > 200:
                step_name = step_name[:197] + "..."
            
            allure_step = {
                "name": step_name,
                "status": step_status,
                "start": 0,
                "stop": 0,
            }
            
            # Формируем описание шага с дополнительной информацией
            description_parts = []
            
            # Если есть name и он отличается от description, добавляем его
            if step.name and step.name.strip() and step.name.strip() != action_text:
                description_parts.append(f"Название шага: {step.name}")
            
            # Добавляем полный текст действия, если он был обрезан
            if action_text and len(action_text) > 200:
                description_parts.append(f"Полное действие: {action_text}")
            
            # Добавляем expected result
            if step.expected_result:
                description_parts.append(f"Ожидаемый результат: {step.expected_result}")
            
            if description_parts:
                allure_step["description"] = "\n".join(description_parts)
            
            # Добавляем attachments если есть
            if step.attachments:
                allure_step["attachments"] = [
                    {"name": att, "source": att, "type": "text/plain"}
                    for att in step.attachments if att
                ]
            
            # Добавляем bug link если есть
            if step.bug_link:
                links.append({
                    "name": step.bug_link,
                    "url": step.bug_link,
                    "type": "issue"
                })
            
            # Добавляем skip reason если шаг пропущен
            if step.status == "skipped" and step.skip_reason:
                allure_step["statusDetails"] = {
                    "message": step.skip_reason,
                    "trace": ""
                }
            
            allure_steps.append(allure_step)
        
        # Формируем полный результат Allure
        allure_result = {
            "uuid": test_case.id or str(uuid.uuid4()),
            "historyId": test_case.id or str(uuid.uuid4()),
            "fullName": test_case.name,
            "labels": labels,
            "links": links,
            "name": test_case.name,
            "status": overall_status,
            "statusDetails": {},
            "steps": allure_steps,
            "attachments": [],
            "parameters": [],
            "start": test_case.created_at or int(datetime.now().timestamp() * 1000),
            "stop": test_case.updated_at or int(datetime.now().timestamp() * 1000),
        }
        
        # Добавляем описание тест-кейса
        if test_case.description:
            allure_result["description"] = test_case.description
        
        # Добавляем preconditions
        if test_case.preconditions:
            if "description" in allure_result:
                allure_result["description"] = f"{test_case.preconditions}\n\n{allure_result['description']}"
            else:
                allure_result["description"] = test_case.preconditions
        
        # Добавляем expected result
        if test_case.expected_result:
            if "description" in allure_result:
                allure_result["description"] += f"\n\nОбщий ожидаемый результат: {test_case.expected_result}"
            else:
                allure_result["description"] = f"Общий ожидаемый результат: {test_case.expected_result}"
        
        return allure_result
        
    except Exception as e:
        print(f"Ошибка при конвертации тест-кейса в Allure формат: {e}", file=sys.stderr)
        return None


def _determine_overall_status(test_case: TestCase) -> str:
    """
    Определяет общий статус тест-кейса на основе статусов шагов.
    
    Args:
        test_case: Тест-кейс
    
    Returns:
        Статус в формате Allure: passed, failed, broken, skipped, unknown
    """
    if not test_case.steps:
        return "unknown"
    
    statuses = [step.status or "" for step in test_case.steps]
    
    # Если есть failed - тест failed
    if any(s.lower() == "failed" for s in statuses):
        return "failed"
    
    # Если все passed - тест passed
    if all(s.lower() == "passed" for s in statuses if s):
        return "passed"
    
    # Если есть skipped - тест skipped
    if any(s.lower() == "skipped" for s in statuses):
        return "skipped"
    
    # Если все пустые или pending - unknown
    if all(not s or s.lower() in ("", "pending") for s in statuses):
        return "unknown"
    
    # По умолчанию broken
    return "broken"


def _map_step_status(status: str) -> str:
    """
    Маппит статус шага в формат Allure.
    
    Args:
        status: Статус шага (passed, failed, skipped, pending, "")
    
    Returns:
        Статус в формате Allure: passed, failed, skipped, broken, unknown
    """
    if not status:
        return "unknown"
    
    status_lower = status.lower()
    
    if status_lower == "passed":
        return "passed"
    elif status_lower == "failed":
        return "failed"
    elif status_lower == "skipped":
        return "skipped"
    elif status_lower in ("", "pending"):
        return "unknown"
    else:
        return "broken"


def _open_explorer(path: Path):
    """
    Открывает проводник Windows в указанной папке.
    
    Args:
        path: Путь к папке для открытия
    """
    try:
        if sys.platform == "win32":
            import subprocess
            subprocess.Popen(f'explorer "{path}"')
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", str(path)])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        print(f"Ошибка при открытии проводника: {e}", file=sys.stderr)
