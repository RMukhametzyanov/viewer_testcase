"""Репозиторий для работы с тест-кейсами"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
import uuid

from ..models import TestCase
from ..utils import get_current_datetime


class ITestCaseRepository(ABC):
    """
    Интерфейс репозитория (Interface Segregation Principle)
    Определяет контракт для работы с тест-кейсами
    """
    
    @abstractmethod
    def load_all(self, directory: Path) -> List[TestCase]:
        """Загрузить все тест-кейсы из директории"""
        pass
    
    @abstractmethod
    def save(self, test_case: TestCase, filepath: Path) -> None:
        """Сохранить тест-кейс"""
        pass
    
    @abstractmethod
    def delete(self, filepath: Path) -> None:
        """Удалить тест-кейс"""
        pass
    
    @abstractmethod
    def create_new(self, target_folder: Path) -> TestCase:
        """Создать новый тест-кейс"""
        pass


class TestCaseRepository(ITestCaseRepository):
    """
    Репозиторий для работы с тест-кейсами в файловой системе
    
    Соответствует принципам:
    - Single Responsibility: отвечает только за работу с файлами
    - Open/Closed: можно создать другую реализацию (например, БД) без изменения интерфейса
    - Dependency Inversion: зависит от абстракции (ITestCaseRepository)
    """
    
    def load_all(self, directory: Path) -> List[TestCase]:
        """
        Загрузить все тест-кейсы из директории рекурсивно
        
        Args:
            directory: Путь к директории с тест-кейсами
        
        Returns:
            Список тест-кейсов
        """
        test_cases = []
        
        if not directory.exists():
            return test_cases
        
        # Рекурсивно ищем все JSON файлы
        for json_file in directory.rglob("*.json"):
            try:
                test_case = self._load_from_file(json_file)
                if test_case:
                    test_cases.append(test_case)
            except Exception as e:
                print(f"Ошибка загрузки {json_file}: {e}")
        
        return test_cases
    
    def save(self, test_case: TestCase, filepath: Path) -> None:
        """
        Сохранить тест-кейс в файл
        
        Args:
            test_case: Тест-кейс для сохранения
            filepath: Путь к файлу
        """
        # Обновляем время изменения
        test_case.updated_at = get_current_datetime()
        
        # Создаем директорию если не существует
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(test_case.to_dict(), f, ensure_ascii=False, indent=4)
    
    def delete(self, filepath: Path) -> None:
        """
        Удалить тест-кейс
        
        Args:
            filepath: Путь к файлу
        """
        if filepath.exists():
            filepath.unlink()
    
    def create_new(self, target_folder: Path) -> TestCase:
        """
        Создать новый тест-кейс
        
        Args:
            target_folder: Папка для создания
        
        Returns:
            Новый тест-кейс
        """
        from ..models.test_case import TestCaseStep
        
        new_id = str(uuid.uuid4())
        filename = f'tc_new_{uuid.uuid4().hex[:8]}.json'
        current_time = get_current_datetime()
        
        # Создаем первый пустой шаг
        first_step = TestCaseStep(
            name="Шаг 1",
            description="",
            expected_result="",
            status="pending",
        )
        
        test_case = TestCase(
            id=new_id,
            name='Новый тест-кейс',
            created_at=current_time,
            updated_at=current_time,
            status="Draft",
            test_type="manual",
            steps=[first_step],
            _filename=filename,
            _filepath=target_folder / filename
        )
        
        return test_case
    
    def _load_from_file(self, filepath: Path) -> Optional[TestCase]:
        """
        Загрузить тест-кейс из файла
        
        Args:
            filepath: Путь к файлу
        
        Returns:
            Тест-кейс или None при ошибке
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return TestCase.from_dict(data, filepath)
        except Exception as e:
            print(f"Ошибка загрузки {filepath}: {e}")
            return None


