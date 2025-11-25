#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для построения карты иерархии test suites.
Для каждого suite строит цепочку родителей до корневого suite (id=442605).
"""

import json
from typing import Dict, List, Optional
from import_alm.const import ROOT_TEST_PLAN_ID


def build_suite_map(suites: List[Dict]) -> Dict[int, Dict]:
    """Создает словарь для быстрого поиска suite по id."""
    suite_map = {}
    for suite in suites:
        suite_id = suite.get('id')
        if suite_id:
            suite_map[suite_id] = suite
    return suite_map


def get_parent_chain(suite_id: int, suite_map: Dict[int, Dict], root_id: int = ROOT_TEST_PLAN_ID) -> List[Dict]:
    """
    Строит цепочку родителей для заданного suite.
    
    Args:
        suite_id: ID suite для которого строится цепочка
        suite_map: Словарь всех suites по id
        root_id: ID корневого suite (останавливаемся на нем)
    
    Returns:
        Список родителей от ближайшего к корневому (включая корневой)
    """
    chain = []
    current_id = suite_id
    visited = set()  # Защита от циклических ссылок
    
    while current_id and current_id != root_id and current_id not in visited:
        visited.add(current_id)
        current_suite = suite_map.get(current_id)
        
        if not current_suite:
            break
        
        # Проверяем наличие parentSuite
        parent_suite = current_suite.get('parentSuite')
        if not parent_suite:
            break
        
        parent_id = parent_suite.get('id')
        if not parent_id:
            break
        
        # Добавляем родителя в цепочку
        chain.append({
            'id': parent_id,
            'name': parent_suite.get('name', '')
        })
        
        current_id = parent_id
    
    # Если дошли до корневого, но он еще не добавлен в цепочку, добавляем его
    if current_id == root_id and (not chain or chain[-1].get('id') != root_id):
        root_suite = suite_map.get(root_id)
        if root_suite:
            chain.append({
                'id': root_id,
                'name': root_suite.get('name', '')
            })
    
    return chain


def build_hierarchy_map(suites: List[Dict], root_id: int = ROOT_TEST_PLAN_ID) -> Dict[int, List[Dict]]:
    """
    Строит карту иерархии для всех suites.
    
    Args:
        suites: Список всех suites
        root_id: ID корневого suite
    
    Returns:
        Словарь: suite_id -> список родителей (от ближайшего к корневому)
    """
    suite_map = build_suite_map(suites)
    hierarchy_map = {}
    
    for suite in suites:
        suite_id = suite.get('id')
        if not suite_id:
            continue
        
        # Для корневого suite цепочка пустая
        if suite_id == root_id:
            hierarchy_map[suite_id] = []
        else:
            # Строим цепочку родителей
            parent_chain = get_parent_chain(suite_id, suite_map, root_id)
            hierarchy_map[suite_id] = parent_chain
    
    return hierarchy_map


def main():
    # Загружаем данные
    input_file = 'all_suites.json'
    output_file = 'suite_hierarchy_map.json'
    
    print(f"Загрузка данных из {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    suites = data.get('value', [])
    print(f"Найдено suites: {len(suites)}")
    
    # Строим карту иерархии
    print("Построение карты иерархии...")
    hierarchy_map = build_hierarchy_map(suites)
    
    # Сохраняем результат
    print(f"Сохранение результата в {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(hierarchy_map, f, ensure_ascii=False, indent=2)
    
    print(f"Готово! Обработано suites: {len(hierarchy_map)}")
    
    # Выводим статистику
    chains_with_parents = sum(1 for chain in hierarchy_map.values() if len(chain) > 0)
    print(f"Suites с родителями: {chains_with_parents}")
    print(f"Корневой suite (без родителей): {len([s for s in suites if s.get('id') == ROOT_TEST_PLAN_ID])}")


if __name__ == '__main__':
    main()

