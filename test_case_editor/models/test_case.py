"""Модель тест-кейса"""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class TestCaseStep:
    """Шаг тестирования"""
    step: str = ""
    expected_res: str = ""


@dataclass
class TestCaseLabel:
    """Метка (label) тест-кейса"""
    name: str = ""
    value: str = ""


@dataclass
class TestCase:
    """
    Модель тест-кейса
    
    Соответствует принципу Single Responsibility:
    отвечает только за хранение данных тест-кейса
    """
    id: str = ""
    title: str = "Новый тест-кейс"
    author: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    status: str = "Draft"
    use_case_id: str = ""
    folder_id: str = ""
    level: str = "minor"
    precondition: str = ""
    steps: List[TestCaseStep] = field(default_factory=list)
    labels: List[TestCaseLabel] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    
    # Служебные поля (не сохраняются в JSON)
    _filename: Optional[str] = field(default=None, repr=False)
    _filepath: Optional[Path] = field(default=None, repr=False)
    
    def to_dict(self) -> dict:
        """Преобразование в словарь для сохранения"""
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'description': self.description,
            'tags': self.tags,
            'status': self.status,
            'use_case_id': self.use_case_id,
            'folder_id': self.folder_id,
            'level': self.level,
            'precondition': self.precondition,
            'steps': [{'step': s.step, 'expected_res': s.expected_res} for s in self.steps],
            'labels': [{'name': l.name, 'value': l.value} for l in self.labels],
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: dict, filepath: Optional[Path] = None) -> 'TestCase':
        """Создание из словаря"""
        steps = [TestCaseStep(**s) for s in data.get('steps', [])]
        labels = [TestCaseLabel(**l) for l in data.get('labels', [])]
        
        return cls(
            id=data.get('id', ''),
            title=data.get('title', 'Без названия'),
            author=data.get('author', ''),
            description=data.get('description', ''),
            tags=data.get('tags', []),
            status=data.get('status', 'Draft'),
            use_case_id=data.get('use_case_id', ''),
            folder_id=data.get('folder_id', ''),
            level=data.get('level', 'minor'),
            precondition=data.get('precondition', ''),
            steps=steps,
            labels=labels,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            _filename=filepath.name if filepath else None,
            _filepath=filepath
        )


