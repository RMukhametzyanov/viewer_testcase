#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Главный скрипт для последовательного выполнения импорта test cases из ALM.
Объединяет работу build_suite_hierarchy.py и fetch_test_cases.py.
Все выходные файлы сохраняются в папку from_alm.
"""

import os
import sys
from pathlib import Path

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

