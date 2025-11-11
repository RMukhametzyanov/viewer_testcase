#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для парсинга тест-кейсов из Azure DevOps и конвертации в Markdown формат
"""

import json
import re
from typing import Dict, List, Any
from datetime import datetime

def clean_html_tags(text: str) -> str:
    """Очищает HTML теги из текста"""
    if not text:
        return ""
    
    # Декодируем HTML entities сначала
    html_entities = {
        '&lt;': '<',
        '&gt;': '>',
        '&amp;': '&',
        '&quot;': '"',
        '&nbsp;': ' ',
        '&BR/&gt;': '\n',
        '&BR/': '\n',
        '&amp;nbsp;': ' '
    }
    
    for entity, replacement in html_entities.items():
        text = text.replace(entity, replacement)
    
    # Удаляем HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    
    # Очищаем лишние пробелы и переносы строк
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Убираем пустые строки
    text = re.sub(r'[ \t]+', ' ', text)      # Убираем лишние пробелы
    text = re.sub(r'\n ', '\n', text)        # Убираем пробелы в начале строк
    
    return text.strip()

def parse_test_steps(steps_xml: str) -> List[Dict[str, str]]:
    """Парсит XML с шагами тест-кейса"""
    steps = []
    
    if not steps_xml:
        return steps
    
    # Простой парсинг XML для извлечения шагов
    step_pattern = r'<step id="(\d+)" type="(\w+)">(.*?)</step>'
    matches = re.findall(step_pattern, steps_xml, re.DOTALL)
    
    for step_id, step_type, step_content in matches:
        # Извлекаем параметры шага
        param_pattern = r'<parameterizedString[^>]*>(.*?)</parameterizedString>'
        params = re.findall(param_pattern, step_content, re.DOTALL)
        
        step_data = {
            'id': step_id,
            'type': step_type,
            'action': clean_html_tags(params[0]) if len(params) > 0 else '',
            'expected_result': clean_html_tags(params[1]) if len(params) > 1 else ''
        }
        
        steps.append(step_data)
    
    return steps

def format_test_case_to_markdown(test_case: Dict[str, Any]) -> str:
    """Форматирует тест-кейс в Markdown"""
    
    # Извлекаем основную информацию
    work_item = test_case.get('workItem', {})
    work_item_fields = work_item.get('workItemFields', [])
    
    # Находим поля
    name = work_item.get('name', 'Без названия')
    steps_field = None
    
    for field in work_item_fields:
        if 'Microsoft.VSTS.TCM.Steps' in field:
            steps_field = field['Microsoft.VSTS.TCM.Steps']
            break
    
    # Парсим шаги
    steps = parse_test_steps(steps_field) if steps_field else []
    
    # Формируем Markdown
    markdown = f"# {name}\n\n"
    
    # Добавляем метаинформацию
    markdown += "## Информация о тест-кейсе\n\n"
    markdown += f"- **ID**: {work_item.get('id', 'N/A')}\n"
    markdown += f"- **Порядок**: {test_case.get('order', 'N/A')}\n"
    
    # Информация о тест-плане
    test_plan = test_case.get('testPlan', {})
    if test_plan:
        markdown += f"- **Тест-план**: {test_plan.get('name', 'N/A')} (ID: {test_plan.get('id', 'N/A')})\n"
    
    # Информация о тест-сьюте
    test_suite = test_case.get('testSuite', {})
    if test_suite:
        markdown += f"- **Тест-сьют**: {test_suite.get('name', 'N/A')} (ID: {test_suite.get('id', 'N/A')})\n"
    
    # Информация о проекте
    project = test_case.get('project', {})
    if project:
        markdown += f"- **Проект**: {project.get('name', 'N/A')}\n"
    
    markdown += "\n"
    
    # Добавляем шаги тест-кейса
    if steps:
        markdown += "## Шаги тест-кейса\n\n"
        
        for i, step in enumerate(steps, 1):
            step_type = step['type']
            action = step['action']
            expected = step['expected_result']
            
            if step_type == 'ActionStep':
                markdown += f"### Шаг {i}: Действие\n\n"
            elif step_type == 'ValidateStep':
                markdown += f"### Шаг {i}: Проверка\n\n"
            else:
                markdown += f"### Шаг {i}: {step_type}\n\n"
            
            if action:
                markdown += f"**Действие:**\n{action}\n\n"
            
            if expected:
                markdown += f"**Ожидаемый результат:**\n{expected}\n\n"
            
            markdown += "---\n\n"
    else:
        markdown += "## Шаги тест-кейса\n\n"
        markdown += "*Шаги не найдены или не удалось их распарсить*\n\n"
    
    return markdown

def main():
    """Основная функция"""
    
    # Читаем JSON файл
    try:
        with open('from_alm.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Ошибка: Файл 'from_alm.json' не найден")
        return
    except json.JSONDecodeError as e:
        print(f"Ошибка при парсинге JSON: {e}")
        return
    
    # Извлекаем тест-кейсы
    test_cases = data.get('value', [])
    
    if not test_cases:
        print("Тест-кейсы не найдены в файле")
        return
    
    print(f"Найдено {len(test_cases)} тест-кейсов")
    
    # Генерируем Markdown для каждого тест-кейса
    all_markdown = []
    
    # Добавляем заголовок документа
    all_markdown.append("# Тест-кейсы из Azure DevOps\n\n")
    all_markdown.append(f"*Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
    all_markdown.append(f"**Всего тест-кейсов:** {len(test_cases)}\n\n")
    all_markdown.append("---\n\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Обрабатываем тест-кейс {i}/{len(test_cases)}")
        markdown = format_test_case_to_markdown(test_case)
        all_markdown.append(markdown)
        
        # Добавляем разделитель между тест-кейсами (кроме последнего)
        if i < len(test_cases):
            all_markdown.append("\n" + "="*80 + "\n\n")
    
    # Сохраняем результат
    output_file = 'test_cases.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(''.join(all_markdown))
    
    print(f"Результат сохранен в файл: {output_file}")

if __name__ == "__main__":
    main()
