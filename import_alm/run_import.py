#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Главный скрипт для последовательного выполнения импорта test cases из ALM.
Объединяет работу build_suite_hierarchy.py и fetch_test_cases.py.
Все выходные файлы сохраняются в папку from_alm.
"""

import os
import sys
import subprocess
from pathlib import Path


def check_and_install_dependencies():
    """Проверяет наличие необходимых библиотек и устанавливает их при необходимости."""
    script_dir = Path(__file__).parent
    requirements_file = script_dir / "requirements.txt"
    
    if not requirements_file.exists():
        print("⚠️  Файл requirements.txt не найден. Пропуск проверки зависимостей.")
        return
    
    # Маппинг имен пакетов к именам модулей для импорта
    # (некоторые пакеты имеют другое имя при импорте)
    package_to_module = {
        'requests': 'requests',
        'urllib3': 'urllib3',
    }
    
    # Читаем список зависимостей
    required_packages = []
    with open(requirements_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Извлекаем имя пакета (до >= или ==)
                package_name = line.split('>=')[0].split('==')[0].split('>')[0].split('<')[0].strip()
                if package_name:
                    required_packages.append(package_name)
    
    # Проверяем наличие пакетов
    missing_packages = []
    for package in required_packages:
        module_name = package_to_module.get(package, package)
        try:
            __import__(module_name)
        except ImportError:
            missing_packages.append(package)
    
    # Устанавливаем недостающие пакеты
    if missing_packages:
        print("=" * 70)
        print("Обнаружены отсутствующие зависимости")
        print("=" * 70)
        print(f"Не найдены пакеты: {', '.join(missing_packages)}")
        print("Начинаю автоматическую установку...")
        print()
        
        try:
            # Устанавливаем через pip
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ])
            print()
            print("✓ Зависимости успешно установлены!")
            print()
        except subprocess.CalledProcessError as e:
            print()
            print("✗ ОШИБКА при установке зависимостей!")
            print()
            print("Попробуйте установить вручную:")
            print(f"  pip install -r {requirements_file}")
            print()
            sys.exit(1)
        except Exception as e:
            print()
            print(f"✗ ОШИБКА при установке зависимостей: {e}")
            print()
            print("Попробуйте установить вручную:")
            print(f"  pip install -r {requirements_file}")
            print()
            sys.exit(1)


# Проверяем и устанавливаем зависимости перед импортом модулей
check_and_install_dependencies()

# Добавляем текущую директорию в путь для импорта
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent))

from import_alm.build_suite_hierarchy import build_and_save_hierarchy
from import_alm.fetch_test_cases import fetch_all_test_cases


def main():
    """Основная функция для последовательного выполнения импорта."""
    print("=" * 70)
    print("Импорт test cases из ALM")
    print("=" * 70)
    print()
    
    # Определяем пути
    script_dir = Path(__file__).parent
    export_dir = script_dir / "from_alm"
    input_file = script_dir / "all_suites.json"
    hierarchy_map_file = "suite_hierarchy_map.json"
    
    # Создаем папку для экспорта
    export_dir.mkdir(exist_ok=True)
    print(f"Выходная директория: {export_dir}")
    print()
    
    # Шаг 1: Построение карты иерархии
    print("=" * 70)
    print("ШАГ 1: Построение карты иерархии suites")
    print("=" * 70)
    print()
    
    try:
        hierarchy_map_path = build_and_save_hierarchy(
            input_file=str(input_file),
            output_file=hierarchy_map_file,
            output_dir=str(export_dir)
        )
        print()
        print(f"✓ Карта иерархии сохранена: {hierarchy_map_path}")
        print()
    except Exception as e:
        print(f"✗ ОШИБКА при построении карты иерархии: {e}")
        print("Завершение работы.")
        return
    
    # Шаг 2: Получение test cases
    print("=" * 70)
    print("ШАГ 2: Получение test cases для всех suites")
    print("=" * 70)
    print()
    
    try:
        stats = fetch_all_test_cases(
            hierarchy_map_file=str(Path(export_dir) / hierarchy_map_file),
            output_dir=str(export_dir)
        )
        print()
        print("✓ Получение test cases завершено")
        print()
    except Exception as e:
        print(f"✗ ОШИБКА при получении test cases: {e}")
        print("Завершение работы.")
        return
    
    # Итоговая статистика
    print("=" * 70)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 70)
    print(f"  Всего suites обработано: {stats.get('total', 0)}")
    print(f"  Успешно получено: {stats.get('success', 0)}")
    print(f"  Пропущено (файл существует): {stats.get('skipped', 0)}")
    print(f"  Ошибок: {stats.get('error', 0)}")
    print()
    print(f"Все файлы сохранены в: {export_dir}")
    print()
    print("=" * 70)
    print("Импорт завершен успешно!")
    print("=" * 70)


if __name__ == '__main__':
    main()

