#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упрощенная версия скрипта для парсинга тест-кейсов из Azure DevOps
"""

import json
import re
from datetime import datetime

def clean_text(text):
    """Очищает текст от HTML тегов и форматирует"""
    if not text:
        return ""
    
    # Декодируем HTML entities
    entities = {
        '&lt;': '<', '&gt;': '>', '&amp;': '&', '&quot;': '"',
        '&nbsp;': ' ', '&BR/&gt;': '\n', '&BR/': '\n'
    }
    
    for entity, replacement in entities.items():
        text = text.replace(entity, replacement)
    
    # Удаляем HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    
    # Форматируем текст
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n ', '\n', text)
    
    return text.strip()

def extract_steps(steps_xml):
    """Извлекает шаги из XML"""
    if not steps_xml:
        return []
    
    steps = []
    step_pattern = r'<step id="(\d+)" type="(\w+)">(.*?)</step>'
    matches = re.findall(step_pattern, steps_xml, re.DOTALL)
    
    for step_id, step_type, content in matches:
        param_pattern = r'<parameterizedString[^>]*>(.*?)</parameterizedString>'
        params = re.findall(param_pattern, content, re.DOTALL)
        
        action = clean_text(params[0]) if len(params) > 0 else ''
        expected = clean_text(params[1]) if len(params) > 1 else ''
        
        steps.append({
            'id': step_id,
            'type': step_type,
            'action': action,
            'expected': expected
        })
    
    return steps

def main():
    # Читаем JSON
    with open('from_alm.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    test_cases = data.get('value', [])
    
    # Генерируем Markdown
    output = []
    output.append("# Тест-кейсы из Azure DevOps\n")
    output.append(f"*Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    output.append(f"**Всего тест-кейсов:** {len(test_cases)}\n\n")
    output.append("---\n\n")
    
    for i, tc in enumerate(test_cases, 1):
        work_item = tc.get('workItem', {})
        name = work_item.get('name', f'Тест-кейс {i}')
        
        # Находим шаги
        steps_field = None
        for field in work_item.get('workItemFields', []):
            if 'Microsoft.VSTS.TCM.Steps' in field:
                steps_field = field['Microsoft.VSTS.TCM.Steps']
                break
        
        steps = extract_steps(steps_field)
        
        # Заголовок тест-кейса
        output.append(f"## {i}. {name}\n")
        output.append(f"**ID:** {work_item.get('id', 'N/A')} | ")
        output.append(f"**Порядок:** {tc.get('order', 'N/A')}\n\n")
        
        # Шаги
        if steps:
            output.append("### Шаги:\n\n")
            for j, step in enumerate(steps, 1):
                step_type = "Действие" if step['type'] == 'ActionStep' else "Проверка"
                output.append(f"**{j}. {step_type}**\n")
                
                if step['action']:
                    output.append(f"*Действие:* {step['action']}\n")
                
                if step['expected']:
                    output.append(f"*Ожидаемый результат:* {step['expected']}\n")
                
                output.append("\n")
        else:
            output.append("*Шаги не найдены*\n\n")
        
        output.append("---\n\n")
    
    # Сохраняем
    with open('test_cases_simple.md', 'w', encoding='utf-8') as f:
        f.write(''.join(output))
    
    print(f"Создан файл: test_cases_simple.md")
    print(f"Обработано тест-кейсов: {len(test_cases)}")

if __name__ == "__main__":
    main()

