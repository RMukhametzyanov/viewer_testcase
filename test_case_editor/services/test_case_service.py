"""Сервис для работы с тест-кейсами"""

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, List, Optional, Tuple

from ..models import TestCase, TestCaseLabel, TestCaseStep
from ..repositories import ITestCaseRepository
from ..utils import get_current_datetime
from ..utils.azure_parser import parse_azure_test_cases


class TestCaseService:
    """
    Сервис для работы с тест-кейсами
    
    Соответствует принципам:
    - Single Responsibility: отвечает только за бизнес-логику тест-кейсов
    - Dependency Inversion: зависит от абстракции (ITestCaseRepository), а не от конкретной реализации
    """
    
    def __init__(self, repository: ITestCaseRepository):
        """
        Args:
            repository: Репозиторий для работы с данными (внедрение зависимости)
        """
        self._repository = repository
    
    def load_all_test_cases(self, directory: Path) -> List[TestCase]:
        """
        Загрузить все тест-кейсы из директории
        
        Args:
            directory: Путь к директории
        
        Returns:
            Список тест-кейсов
        """
        return self._repository.load_all(directory)
    
    def save_test_case(self, test_case: TestCase) -> bool:
        """
        Сохранить тест-кейс
        
        Args:
            test_case: Тест-кейс для сохранения
        
        Returns:
            True при успехе, False при ошибке
        """
        if not test_case.title:
            return False
        
        filepath = test_case._filepath
        if not filepath:
            return False
        
        try:
            self._repository.save(test_case, filepath)
            return True
        except Exception as e:
            print(f"Ошибка сохранения: {e}")
            return False
    
    def delete_test_case(self, test_case: TestCase) -> bool:
        """
        Удалить тест-кейс
        
        Args:
            test_case: Тест-кейс для удаления
        
        Returns:
            True при успехе, False при ошибке
        """
        filepath = test_case._filepath
        if not filepath:
            return False
        
        try:
            self._repository.delete(filepath)
            return True
        except Exception as e:
            print(f"Ошибка удаления: {e}")
            return False
    
    def create_new_test_case(self, target_folder: Path) -> Optional[TestCase]:
        """
        Создать новый тест-кейс
        
        Args:
            target_folder: Папка для создания
        
        Returns:
            Новый тест-кейс или None при ошибке
        """
        try:
            test_case = self._repository.create_new(target_folder)
            self._repository.save(test_case, test_case._filepath)
            return test_case
        except Exception as e:
            print(f"Ошибка создания: {e}")
            return None
    
    def duplicate_test_case(self, test_case: TestCase) -> Optional[TestCase]:
        """
        Дублировать тест-кейс
        
        Args:
            test_case: Тест-кейс для дублирования
        
        Returns:
            Копия тест-кейса или None при ошибке
        """
        import uuid
        import copy
        
        if not test_case._filepath:
            return None
        
        try:
            # Создаем глубокую копию
            new_test_case = copy.deepcopy(test_case)
            new_test_case.id = str(uuid.uuid4())
            new_test_case.title = f"(копия) {new_test_case.title}"
            
            # Генерируем новое имя файла
            original_path = test_case._filepath
            base_name = original_path.stem
            new_filename = f"{base_name}_copy_{uuid.uuid4().hex[:8]}.json"
            new_filepath = original_path.parent / new_filename
            
            new_test_case._filename = new_filename
            new_test_case._filepath = new_filepath
            
            self._repository.save(new_test_case, new_filepath)
            return new_test_case
        except Exception as e:
            print(f"Ошибка дублирования: {e}")
            return None
    
    def move_item(self, source_path: Path, target_folder: Path) -> bool:
        """
        Переместить файл или папку
        
        Args:
            source_path: Исходный путь
            target_folder: Целевая папка
        
        Returns:
            True при успехе, False при ошибке
        """
        try:
            new_path = target_folder / source_path.name
            
            # Проверки
            if source_path.parent == target_folder:
                return False  # Уже в этой папке
            
            if new_path.exists():
                return False  # Уже существует
            
            if source_path.is_dir():
                # Проверка на перемещение в саму себя
                if str(target_folder).startswith(str(source_path)):
                    return False
            
            shutil.move(str(source_path), str(new_path))
            return True
        except Exception as e:
            print(f"Ошибка перемещения: {e}")
            return False
    
    def bulk_move_items(self, items: List[dict], target_folder: Path) -> tuple[int, List[str]]:
        """
        Массовое перемещение элементов
        
        Args:
            items: Список элементов для перемещения
            target_folder: Целевая папка
        
        Returns:
            Кортеж (количество перемещенных, список ошибок)
        """
        moved_count = 0
        errors = []
        
        for item_data in items:
            try:
                item_type = item_data.get('type')
                
                if item_type == 'file':
                    test_case = item_data.get('test_case')
                    if test_case and test_case._filepath:
                        if self.move_item(test_case._filepath, target_folder):
                            moved_count += 1
                        else:
                            errors.append(f"Не удалось переместить {test_case._filepath.name}")
                
                elif item_type == 'folder':
                    folder_path = item_data.get('path')
                    if folder_path:
                        if self.move_item(folder_path, target_folder):
                            moved_count += 1
                        else:
                            errors.append(f"Не удалось переместить {folder_path.name}")
            except Exception as e:
                errors.append(str(e))
        
        return moved_count, errors
    
    def bulk_delete_items(self, items: List[dict]) -> tuple[int, List[str]]:
        """
        Массовое удаление элементов
        
        Args:
            items: Список элементов для удаления
        
        Returns:
            Кортеж (количество удаленных, список ошибок)
        """
        deleted_count = 0
        errors = []
        
        for item_data in items:
            try:
                item_type = item_data.get('type')
                
                if item_type == 'file':
                    test_case = item_data.get('test_case')
                    if test_case:
                        if self.delete_test_case(test_case):
                            deleted_count += 1
                        else:
                            errors.append(f"Не удалось удалить файл")
                
                elif item_type == 'folder':
                    folder_path = item_data.get('path')
                    if folder_path and folder_path.exists():
                        shutil.rmtree(folder_path)
                        deleted_count += 1
            except Exception as e:
                errors.append(str(e))
        
        return deleted_count, errors

    # --- Импорт из Azure DevOps -------------------------------------------------

    def import_from_azure(self, json_path: Path, target_root: Path) -> Tuple[int, List[str]]:
        """
        Импорт тест-кейсов из JSON-файла Azure DevOps.

        Args:
            json_path: путь к JSON-файлу Azure DevOps
            target_root: корневая папка тест-кейсов в приложении

        Returns:
            Кортеж (количество созданных тест-кейсов, список ошибок)
        """
        created_count = 0
        errors: List[str] = []

        try:
            payload = self._load_azure_payload(json_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{json_path.name}: {exc}")
            return created_count, errors

        parsed_cases = parse_azure_test_cases(payload)
        if not parsed_cases:
            errors.append(f"{json_path.name}: тест-кейсы не найдены")
            return created_count, errors

        target_folder = target_root / "from alm" / json_path.stem
        target_folder.mkdir(parents=True, exist_ok=True)

        for case_data in parsed_cases:
            try:
                test_case = self._build_test_case_from_azure(case_data, target_folder)
                if not test_case._filepath:
                    raise ValueError("Не удалось определить путь для сохранения")
                self._repository.save(test_case, test_case._filepath)
                created_count += 1
            except Exception as exc:  # noqa: BLE001 - хотим собрать все ошибки импорта
                title = case_data.get("title") or case_data.get("id") or "без названия"
                errors.append(f"{json_path.name} → {title}: {exc}")

        return created_count, errors

    # --- Внутренние методы ------------------------------------------------------

    def _build_test_case_from_azure(self, case_data: dict, target_folder: Path) -> TestCase:
        """
        Создать модель тест-кейса приложения на основе данных Azure DevOps.

        Args:
            case_data: данные тест-кейса из Azure DevOps
            target_folder: папка, куда будет сохранен файл тест-кейса

        Returns:
            Экземпляр TestCase.
        """
        case_id = str(case_data.get("id") or uuid.uuid4())
        title = str(case_data.get("title") or f"Тест-кейс {case_id}")

        description = self._compose_description(case_data)

        now = get_current_datetime()
        steps = self._build_steps(case_data.get("steps", []))

        status = case_data.get("additional_fields", {}).get("System.State", "Draft")
        author = case_data.get("additional_fields", {}).get("System.AssignedTo", "")

        test_case = TestCase(
            id=case_id,
            title=title,
            author=author,
            description=description,
            status=status or "Draft",
            tags=[],
            use_case_id="",
            folder_id="",
            level="minor",
            precondition="",
            steps=steps,
            labels=[],
            created_at=now,
            updated_at=now,
        )

        filename = self._generate_unique_filename(title, case_id, target_folder)
        test_case._filename = filename
        test_case._filepath = target_folder / filename

        return test_case

    def _build_steps(self, steps_data: List[dict]) -> List[TestCaseStep]:
        """Построить список шагов тест-кейса на основе данных Azure DevOps."""
        steps: List[TestCaseStep] = []

        for step in steps_data:
            step_type = step.get("type", "")
            action = step.get("action", "").strip()
            expected = step.get("expected", "").strip()

            if not action and not expected:
                continue

            prefix = ""
            if step_type == "ActionStep":
                prefix = "Действие: "
            elif step_type == "ValidateStep":
                prefix = "Проверка: "
            elif step_type:
                prefix = f"{step_type}: "

            step_text = action or expected
            if prefix and not step_text.startswith(prefix):
                step_text = f"{prefix}{step_text}"

            steps.append(
                TestCaseStep(
                    step=step_text.strip(),
                    expected_res=expected,
                )
            )

        return steps

    def _compose_description(self, case_data: dict) -> str:
        """Сформировать описание тест-кейса на основе планов и дополнительных данных."""
        parts: List[str] = []

        project = case_data.get("project") or {}
        plan = case_data.get("plan") or {}
        suite = case_data.get("suite") or {}
        additional = case_data.get("additional_fields") or {}

        if project.get("name"):
            parts.append(f"Проект: {project.get('name')} (ID: {project.get('id')})")
        if plan.get("name"):
            parts.append(f"Тест-план: {plan.get('name')} (ID: {plan.get('id')})")
        if suite.get("name"):
            parts.append(f"Тест-сьют: {suite.get('name')} (ID: {suite.get('id')})")

        priority = additional.get("Microsoft.VSTS.Common.Priority")
        if priority is not None:
            parts.append(f"Приоритет: {priority}")

        automation_status = additional.get("Microsoft.VSTS.TCM.AutomationStatus")
        if automation_status:
            parts.append(f"Статус автоматизации: {automation_status}")

        state_change = additional.get("Microsoft.VSTS.Common.StateChangeDate")
        if state_change:
            parts.append(f"Дата изменения статуса: {state_change}")

        description = "\n".join(parts).strip()
        return description

    def _generate_unique_filename(self, title: str, case_id: str, target_folder: Path) -> str:
        """Сгенерировать уникальное имя файла для тест-кейса."""
        sanitized_title = re.sub(r"[^A-Za-zА-Яа-я0-9_-]+", "_", title).strip("_")
        base = sanitized_title or f"test_case_{case_id}"
        base = base[:80]  # ограничим длину имени файла

        candidate = f"{base}.json"
        index = 1
        while (target_folder / candidate).exists():
            candidate = f"{base}_{index}.json"
            index += 1

        return candidate

    def _load_azure_payload(self, json_path: Path) -> dict:
        """
        Загрузить JSON Azure DevOps с попыткой исправить распространенные ошибки формата.

        Args:
            json_path: путь к файлу

        Returns:
            Распакованный JSON-объект.
        """
        with open(json_path, "r", encoding="utf-8") as source:
            raw_content = source.read()

        try:
            return json.loads(raw_content)
        except json.JSONDecodeError:
            sanitized = self._remove_trailing_commas(raw_content)
            return json.loads(sanitized)

    @staticmethod
    def _remove_trailing_commas(raw_json: str) -> str:
        """
        Удалить «висячие» запятые перед закрывающими скобками.

        Args:
            raw_json: исходный JSON как строка

        Returns:
            Строка без лишних запятых.
        """
        pattern = re.compile(r",(\s*[\]}])")

        previous = None
        current = raw_json
        while previous != current:
            previous = current
            current = pattern.sub(r"\1", current)

        return current


