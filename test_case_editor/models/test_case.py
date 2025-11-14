"""Модель тест-кейса нового формата."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..utils.datetime_utils import ensure_timestamp_ms


def _to_list(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


@dataclass
class TestCaseStep:
    """Шаг тестирования в новой схеме."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    expected_result: str = ""
    status: str = "pending"
    bug_link: str = ""
    skip_reason: str = ""
    attachments: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        attachments = ", ".join(self.attachments) if self.attachments else ""
        return {
            "id": self.id or str(uuid.uuid4()),
            "name": self.name or (self.description.splitlines()[0] if self.description else ""),
            "description": self.description or "",
            "expectedResult": self.expected_result or "",
            "status": self.status or "",
            "bugLink": self.bug_link or "",
            "skipReason": self.skip_reason or "",
            "attachments": attachments,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TestCaseStep":
        if not isinstance(data, dict):
            return cls()

        attachments = data.get("attachments")
        attachments_list = _to_list(attachments)

        return cls(
            id=str(data.get("id") or uuid.uuid4()),
            name=str(data.get("name") or "").strip(),
            description=str(data.get("description") or "").strip(),
            expected_result=str(data.get("expectedResult") or "").strip(),
            status=str(data.get("status") or "pending").strip(),
            bug_link=str(data.get("bugLink") or "").strip(),
            skip_reason=str(data.get("skipReason") or "").strip(),
            attachments=attachments_list,
        )


@dataclass
class TestCase:
    """
    Модель тест-кейса в новой схеме.

    Отвечает только за хранение данных тест-кейса.
    """

    id: str = ""
    name: str = "Новый тест-кейс"
    description: str = ""
    preconditions: str = ""
    expected_result: str = ""
    epic: str = ""
    feature: str = ""
    story: str = ""
    component: str = ""
    test_layer: str = "E2E"
    severity: str = "NORMAL"
    priority: str = "MEDIUM"
    environment: str = ""
    browser: str = ""
    owner: str = ""
    author: str = ""
    reviewer: str = ""
    test_case_id: str = ""
    issue_links: str = ""
    test_case_links: str = ""
    tags: List[str] = field(default_factory=list)
    status: str = "Draft"
    test_type: str = "manual"
    steps: List[TestCaseStep] = field(default_factory=list)
    created_at: int = 0
    updated_at: int = 0

    # Служебные поля (не сохраняются в JSON)
    _filename: Optional[str] = field(default=None, repr=False)
    _filepath: Optional[Path] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        """Преобразование в словарь новой схемы для сохранения."""
        tags_value = ", ".join(self.tags).strip()

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "preconditions": self.preconditions,
            "expectedResult": self.expected_result,
            "epic": self.epic,
            "feature": self.feature,
            "story": self.story,
            "component": self.component,
            "testLayer": self.test_layer,
            "severity": self.severity,
            "priority": self.priority,
            "environment": self.environment,
            "browser": self.browser,
            "owner": self.owner,
            "author": self.author,
            "reviewer": self.reviewer,
            "testCaseId": self.test_case_id,
            "issueLinks": self.issue_links,
            "testCaseLinks": self.test_case_links,
            "tags": tags_value,
            "testType": self.test_type,
            "steps": [step.to_dict() for step in self.steps],
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict, filepath: Optional[Path] = None) -> "TestCase":
        """Создание модели тест-кейса из словаря новой схемы."""
        data = data or {}

        steps_payload = data.get("steps") or []
        steps = [TestCaseStep.from_dict(step) for step in steps_payload if isinstance(step, dict)]

        tags = _to_list(data.get("tags"))

        created_at = ensure_timestamp_ms(data.get("createdAt"))
        updated_at = ensure_timestamp_ms(data.get("updatedAt"))

        return cls(
            id=str(data.get("id") or ""),
            name=str(data.get("name") or "Без названия").strip(),
            description=str(data.get("description") or "").strip(),
            preconditions=str(data.get("preconditions") or "").strip(),
            expected_result=str(data.get("expectedResult") or "").strip(),
            epic=str(data.get("epic") or "").strip(),
            feature=str(data.get("feature") or "").strip(),
            story=str(data.get("story") or "").strip(),
            component=str(data.get("component") or "").strip(),
            test_layer=str(data.get("testLayer") or "E2E").strip(),
            severity=str(data.get("severity") or "NORMAL").strip(),
            priority=str(data.get("priority") or "MEDIUM").strip(),
            environment=str(data.get("environment") or "").strip(),
            browser=str(data.get("browser") or "").strip(),
            owner=str(data.get("owner") or "").strip(),
            author=str(data.get("author") or "").strip(),
            reviewer=str(data.get("reviewer") or "").strip(),
            test_case_id=str(data.get("testCaseId") or "").strip(),
            issue_links=str(data.get("issueLinks") or "").strip(),
            test_case_links=str(data.get("testCaseLinks") or "").strip(),
            tags=tags,
            status=str(data.get("status") or "Draft").strip(),
            test_type=str(data.get("testType") or "manual").strip(),
            steps=steps,
            created_at=created_at,
            updated_at=updated_at,
            _filename=filepath.name if filepath else None,
            _filepath=filepath,
        )

