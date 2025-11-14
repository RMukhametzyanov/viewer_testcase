"""
Скрипт и вспомогательные функции для получения списка доступных моделей от LLM-хоста.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "settings.json"


def load_settings(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Файл настроек не найден: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _parse_models_payload(payload: Any) -> List[str]:
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return [
                str(item.get("id") or item.get("name"))
                for item in payload["data"]
                if isinstance(item, dict) and (item.get("id") or item.get("name"))
            ]
        if isinstance(payload.get("models"), list):
            return [str(item) for item in payload["models"] if item]
    if isinstance(payload, list):
        return [
            str(item.get("id") or item.get("name"))
            for item in payload
            if isinstance(item, dict) and (item.get("id") or item.get("name"))
        ]
    return []


MODEL_ENDPOINTS = (
    "/models",
    "/v1/models",
    "/api/models",
    "/api/tags",
)


def fetch_models(host: str, timeout: float = 10.0) -> List[str]:
    """
    Получить список моделей от LLM-хоста.
    """
    if not host:
        raise ValueError("Не указан LLM-хост.")

    base = host.rstrip("/")
    last_error: Exception | None = None
    parsed_models: List[str] = []

    for endpoint in MODEL_ENDPOINTS:
        url = base + endpoint
        request = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    text = response.read().decode("utf-8", errors="replace")
                    last_error = RuntimeError(f"Хост {url} вернул статус {response.status}: {text}")
                    continue
                raw_payload = response.read()
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"HTTP ошибка {exc.code} при обращении к {url}: {message}")
            continue
        except URLError as exc:
            last_error = RuntimeError(f"Не удалось выполнить запрос к {url}: {exc}")
            continue

        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            last_error = RuntimeError(f"Не удалось распарсить JSON от {url}: {exc}")
            continue

        models = _parse_models_payload(payload)
        if models:
            parsed_models = [model for model in models if model]
            break
        last_error = RuntimeError(f"Эндпойнт {url} вернул неожиданный формат: {payload}")

    if parsed_models:
        return parsed_models

    if last_error:
        raise last_error

    raise RuntimeError("Не удалось получить список моделей: попытки всех эндпойнтов завершились без результата.")


def main():
    try:
        settings = load_settings(SETTINGS_PATH)
    except Exception as exc:  # noqa: BLE001
        print(f"[Ошибка] {exc}", file=sys.stderr)
        sys.exit(1)

    host = settings.get("LLM_HOST")
    if not host:
        print("[Ошибка] В settings.json отсутствует ключ LLM_HOST", file=sys.stderr)
        sys.exit(1)

    try:
        models = fetch_models(str(host))
    except Exception as exc:  # noqa: BLE001
        print(f"[Ошибка] {exc}", file=sys.stderr)
        sys.exit(1)

    if not models:
        print("Модели не найдены.")
        return

    print("Доступные модели:")
    for model in models:
        print(f"- {model}")


if __name__ == "__main__":
    main()

