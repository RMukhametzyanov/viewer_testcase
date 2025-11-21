#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для получения test cases для каждого suite из карты иерархии.
Выполняет GET запросы к Azure DevOps API и сохраняет результаты в отдельные JSON файлы.
"""

import json
import os
import time
from typing import Dict, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from import_alm.const import PLAN_ID, LOGIN, PASSWORD, BASE_URL
import base64
from collections import namedtuple


# Константы


# MMIME-типы со страницы
# https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types

CONTENT_TYPE_EXTENSIONS = namedtuple(
    "ContentType",
    "aac abw arc avif avi azw bin bmp bz bz2 cda "
    "csh css csv doc docx eot epub gz gif htm html ico ics jar "
    "jpeg jpg js json jsonld mid midi mjs mp3 mp4 mpeg mpkg odp "
    "ods odt oga ogv ogx opus otf png pdf php ppt pptx rar rtf "
    "sh svg tar tif tiff ts ttf txt vsd wav weba webm webp woff "
    "woff2 xhtml xls xlsx xml xul zip video_3gp audio_3gp "
    "video_3g2 audio_3g2 arch_7z xml_text ico_x ",
)
HIERARCHY_MAP_FILE = "suite_hierarchy_map.json"
REQUEST_TIMEOUT = 30  # секунд
RETRY_ATTEMPTS = 3
DELAY_BETWEEN_REQUESTS = 0.5  # секунд между запросами для избежания перегрузки сервера
CONTENT_TYPES = CONTENT_TYPE_EXTENSIONS(
    "audio/aac",
    "application/x-abiword",
    "application/x-freearc",
    "image/avif",
    "video/x-msvideo",
    "application/vnd.amazon.ebook",
    "application/octet-stream",
    "image/bmp",
    "application/x-bzip",
    "application/x-bzip2",
    "application/x-cdf",
    "application/x-csh",
    "text/css",
    "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-fontobject",
    "application/epub+zip",
    "application/gzip",
    "image/gif",
    "text/html",
    "text/html",
    "image/vnd.microsoft.icon",
    "text/calendar",
    "application/java-archive",
    "image/jpeg",
    "image/jpeg",
    "text/javascript",
    "application/json",
    "application/ld+json",
    "audio/midi",
    "audio/midi",
    "text/javascript",
    "audio/mpeg",
    "video/mp4",
    "video/mpeg",
    "application/vnd.apple.installer+xml",
    "application/vnd.oasis.opendocument.presentation",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.text",
    "audio/ogg",
    "video/ogg",
    "application/ogg",
    "audio/opus",
    "font/otf",
    "image/png",
    "application/pdf",
    "application/x-httpd-php",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.rar",
    "application/rtf",
    "application/x-sh",
    "image/svg+xml",
    "application/x-tar",
    "image/tiff",
    "image/tiff",
    "video/mp2t",
    "font/ttf",
    "text/plain",
    "application/vnd.visio",
    "audio/wav",
    "audio/webm",
    "video/webm",
    "image/webp",
    "font/woff",
    "font/woff2",
    "application/xhtml+xml",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/xml",
    "application/vnd.mozilla.xul+xml",
    "application/zip",
    "video/3gpp",
    "audio/3gpp",
    "video/3gpp2",
    "audio/3gpp2",
    "application/x-7z-compressed",
    "text/xml",
    "image/x-icon",
)


def create_session() -> requests.Session:
    """Создает HTTP сессию с настройками для повторных попыток."""
    session = requests.Session()
    credentials = f"{LOGIN}:{PASSWORD}"
    basic_token = base64.b64encode(credentials.encode()).decode()
    session.headers.update({
        "Accept": CONTENT_TYPES.json,
        "Authorization": f"Basic {basic_token}"
    })
    
    # Настройка повторных попыток
    retry_strategy = Retry(
        total=RETRY_ATTEMPTS,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Отключение проверки SSL сертификата (для self-signed сертификатов)
    session.verify = False
    
    # Предупреждение об отключенной проверке SSL
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    return session


def fetch_test_cases(session: requests.Session, suite_id: int) -> Dict:
    """
    Выполняет GET запрос для получения test cases для указанного suite.
    
    Args:
        session: HTTP сессия
        suite_id: ID suite
    
    Returns:
        Словарь с результатом запроса или None в случае ошибки
    """
    url = f"{BASE_URL}/{PLAN_ID}/Suites/{suite_id}/TestCase"
    
    try:
        print(f"Запрос для suite {suite_id}...", end=" ", flush=True)
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        print(f"OK (получено записей: {data.get('count', 0)})")
        return data
        
    except requests.exceptions.Timeout:
        print(f"ОШИБКА: Таймаут запроса")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ОШИБКА: {e}")
        if hasattr(e.response, 'status_code'):
            print(f"  Статус код: {e.response.status_code}")
        return None
    except json.JSONDecodeError as e:
        print(f"ОШИБКА: Не удалось распарсить JSON ответ: {e}")
        return None
    except Exception as e:
        print(f"ОШИБКА: Неожиданная ошибка: {e}")
        return None


def save_test_cases(suite_id: int, data: Dict) -> bool:
    """
    Сохраняет данные test cases в JSON файл.
    
    Args:
        suite_id: ID suite
        data: Данные для сохранения
    
    Returns:
        True если успешно, False в противном случае
    """
    filename = f"{suite_id}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"  ОШИБКА при сохранении файла {filename}: {e}")
        return False


def load_suite_ids(hierarchy_map_file: str) -> List[int]:
    """
    Загружает список suite IDs из файла карты иерархии.
    
    Args:
        hierarchy_map_file: Путь к файлу с картой иерархии
    
    Returns:
        Список suite IDs
    """
    try:
        with open(hierarchy_map_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Извлекаем все ключи (suite IDs) и конвертируем в int
        suite_ids = [int(suite_id) for suite_id in data.keys()]
        return sorted(suite_ids)  # Сортируем для удобства
        
    except FileNotFoundError:
        print(f"ОШИБКА: Файл {hierarchy_map_file} не найден")
        return []
    except json.JSONDecodeError as e:
        print(f"ОШИБКА: Не удалось распарсить JSON файл {hierarchy_map_file}: {e}")
        return []
    except Exception as e:
        print(f"ОШИБКА при загрузке файла {hierarchy_map_file}: {e}")
        return []


def main():
    """Основная функция скрипта."""
    print("=" * 60)
    print("Скрипт получения test cases для suites")
    print("=" * 60)
    print()
    
    # Загружаем список suite IDs
    print(f"Загрузка suite IDs из {HIERARCHY_MAP_FILE}...")
    suite_ids = load_suite_ids(HIERARCHY_MAP_FILE)
    
    if not suite_ids:
        print("Не удалось загрузить suite IDs. Завершение работы.")
        return
    
    print(f"Найдено suites: {len(suite_ids)}")
    print()
    
    # Создаем HTTP сессию
    session = create_session()
    
    # Статистика
    total = len(suite_ids)
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    # Обрабатываем каждый suite
    print("Начало обработки suites:")
    print("-" * 60)
    
    for idx, suite_id in enumerate(suite_ids, 1):
        print(f"[{idx}/{total}] Suite ID: {suite_id}", end=" - ")
        
        # Проверяем, не существует ли уже файл
        filename = f"{suite_id}.json"
        if os.path.exists(filename):
            print(f"Пропущен (файл {filename} уже существует)")
            skipped_count += 1
            continue
        
        # Выполняем запрос
        data = fetch_test_cases(session, suite_id)
        
        if data is None:
            error_count += 1
        else:
            # Сохраняем результат
            if save_test_cases(suite_id, data):
                success_count += 1
            else:
                error_count += 1
        
        # Задержка между запросами
        if idx < total:
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # Выводим статистику
    print()
    print("-" * 60)
    print("Статистика:")
    print(f"  Всего suites: {total}")
    print(f"  Успешно обработано: {success_count}")
    print(f"  Пропущено (файл существует): {skipped_count}")
    print(f"  Ошибок: {error_count}")
    print()
    print("Готово!")


if __name__ == '__main__':
    main()

