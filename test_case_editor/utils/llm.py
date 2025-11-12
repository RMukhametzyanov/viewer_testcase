#!/usr/bin/env python3
"""
Простой клиент для удалённого сервера Ollama.

Скрипт отправляет одно сообщение выбранной модели и печатает ответ.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

try:
    from ollama import Client, ResponseError
    _OLLAMA_IMPORT_ERROR: Optional[ModuleNotFoundError] = None
except ModuleNotFoundError as exc:  # pragma: no cover - информативно при отсутствии зависимости
    Client = None  # type: ignore[assignment]

    class ResponseError(Exception):  # type: ignore[override]
        """Заглушка, используемая при отсутствии библиотеки ollama."""

    _OLLAMA_IMPORT_ERROR = exc


DEFAULT_MODEL = "qwen3:latest"
DEFAULT_HOST = os.getenv("OLLAMA_HOST", "http://spb99-vkc-dhwgpu06.devzone.local:11434")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Отправить сообщение на удалённый Ollama-сервер и получить ответ модели."
    )
    parser.add_argument(
        "-m",
        "--model",
        default=DEFAULT_MODEL,
        help="Имя модели на удалённом сервере Ollama.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="URL Ollama-сервера. По умолчанию — значение переменной окружения OLLAMA_HOST "
        "или http://localhost:11434.",
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="Сообщение для модели. Если не передано, будет прочитано из STDIN.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    message = args.message
    if message is None:
        if sys.stdin.isatty():
            print("Введите сообщение для модели и завершите ввод комбинацией Ctrl+D (Unix) или Ctrl+Z (Windows).")
        message = sys.stdin.read().strip()

    if not message:
        print("Пустое сообщение. Нечего отправлять модели.", file=sys.stderr)
        return 1

    try:
        output = send_prompt(message=message, model=args.model, host=args.host)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    except ResponseError as exc:  # pragma: no cover - для пользовательской диагностики
        print(f"Ошибка при обращении к серверу Ollama: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    print(output)
    return 0


if __name__ == "__llm__":
    raise SystemExit(main())


def send_prompt(
    message: str,
    *,
    model: Optional[str] = None,
    host: Optional[str] = None,
) -> str:
    """
    Отправка промта на Ollama и возврат текстового ответа.

    :param message: текст запроса пользователя
    :param model: имя модели (если None — используется значение по умолчанию)
    :param host: URL сервера Ollama (если None — используется значение по умолчанию)
    :raises ValueError: если сообщение пустое
    :raises RuntimeError: если ответ не содержит текстового сообщения
    :raises ResponseError: если ollama.Client выбрасывает ResponseError
    :return: текст ответа модели
    """
    if not message or not message.strip():
        raise ValueError("Пустое сообщение. Нечего отправлять модели.")

    if Client is None or _OLLAMA_IMPORT_ERROR is not None:
        raise RuntimeError(
            "Библиотека 'ollama' не установлена. Установите её командой:\n    pip install ollama"
        ) from _OLLAMA_IMPORT_ERROR

    client = Client(host=host or DEFAULT_HOST)
    response = client.chat(
        model=model or DEFAULT_MODEL,
        messages=[
            {"role": "user", "content": message.strip()},
        ],
    )

    output = response.get("message", {}).get("content")
    if output is None:
        raise RuntimeError("Ответ от сервера не содержит текстового сообщения.")

    return output