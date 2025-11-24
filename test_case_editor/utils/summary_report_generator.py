"""Утилита для генерации суммарного отчета на основе всех HTML отчетов."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Tuple


def generate_summary_report(
    reports_dir: Path,
    app_dir: Optional[Path] = None,
) -> Optional[Path]:
    """
    Генерирует суммарный HTML отчет на основе всех HTML отчетов в папке Reports.
    
    Args:
        reports_dir: Путь к папке Reports
        app_dir: Путь к папке приложения (где находится run_app.py)
                Если None, определяется автоматически
    
    Returns:
        Path к созданному HTML файлу или None в случае ошибки
    """
    try:
        # Определяем папку приложения
        if app_dir is None:
            current_file = Path(__file__).resolve()
            app_dir = current_file.parent.parent.parent
        
        # Собираем данные из всех отчетов
        report_data = _collect_all_reports_data(reports_dir)
        
        if not report_data:
            return None
        
        # Генерируем HTML с графиком
        html_content = _generate_summary_html_content(report_data)
        
        # Сохраняем HTML файл
        summary_file = reports_dir / "Суммарный отчет.html"
        summary_file.write_text(html_content, encoding='utf-8')
        
        return summary_file
        
    except Exception as e:
        print(f"Ошибка при генерации суммарного отчета: {e}")
        import traceback
        traceback.print_exc()
        return None


def _collect_all_reports_data(reports_dir: Path) -> List[Dict]:
    """
    Собрать данные из всех HTML отчетов в папке Reports.
    
    Returns:
        Список словарей с данными каждого отчета:
        {
            'date': datetime,
            'total': int,
            'passed': int,
            'failed': int,
            'skipped': int,
            'pending': int
        }
    """
    report_data = []
    
    if not reports_dir.exists():
        return report_data
    
    # Ищем все HTML файлы в подпапках Reports
    html_files = []
    for item in reports_dir.iterdir():
        if item.is_dir():
            # Ищем HTML файлы в подпапке
            for html_file in item.glob("*.html"):
                html_files.append(html_file)
        elif item.is_file() and item.suffix == ".html":
            html_files.append(item)
    
    # Парсим каждый HTML файл
    for html_file in html_files:
        try:
            data = _parse_html_report(html_file)
            if data:
                report_data.append(data)
        except Exception as e:
            print(f"Ошибка парсинга {html_file}: {e}")
            continue
    
    # Сортируем по дате
    report_data.sort(key=lambda x: x['date'])
    
    return report_data


def _parse_html_report(html_file: Path) -> Optional[Dict]:
    """
    Распарсить HTML отчет и извлечь статистику используя регулярные выражения.
    
    Returns:
        Словарь с данными отчета или None в случае ошибки
    """
    try:
        content = html_file.read_text(encoding='utf-8')
        
        # Извлекаем дату из subtitle используя регулярные выражения
        date_match = re.search(r'Дата формирования:\s*(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})', content)
        if date_match:
            date_str = date_match.group(1)
            try:
                report_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
            except:
                # Пробуем извлечь дату из имени папки (формат YYYY_MM_DD_HH_MM)
                folder_name = html_file.parent.name
                try:
                    report_date = datetime.strptime(folder_name, "%Y_%m_%d_%H_%M")
                except:
                    # Используем дату модификации файла
                    report_date = datetime.fromtimestamp(html_file.stat().st_mtime)
        else:
            # Пробуем извлечь дату из имени папки
            folder_name = html_file.parent.name
            try:
                report_date = datetime.strptime(folder_name, "%Y_%m_%d_%H_%M")
            except:
                # Используем дату модификации файла
                report_date = datetime.fromtimestamp(html_file.stat().st_mtime)
        
        # Извлекаем статистику из stat-value элементов используя регулярные выражения
        total = 0
        passed = 0
        failed = 0
        skipped = 0
        pending = 0
        
        # Ищем все stat-card блоки
        stat_card_pattern = r'<div class="stat-card[^"]*">.*?<div class="stat-value[^"]*">(\d+)</div>.*?<div class="stat-label[^"]*">([^<]+)</div>'
        stat_cards = re.findall(stat_card_pattern, content, re.DOTALL)
        
        for value_text, label_text in stat_cards:
            try:
                value = int(value_text)
                label = label_text.strip()
                
                if 'Всего' in label and 'тест-кейсов' in label:
                    total = value
                elif 'Не пройдено' in label:
                    failed = value
                elif 'Успешно' in label or ('пройдено' in label and 'Не' not in label):
                    passed = value
                elif 'Пропущено' in label:
                    skipped = value
                elif 'Осталось' in label:
                    pending = value
            except ValueError:
                continue
        
        # Если не нашли через stat-card, пробуем через info-section
        if total == 0:
            # Ищем паттерны типа "Всего тест-кейсов: 491"
            total_match = re.search(r'Всего тест-кейсов:\s*(\d+)', content)
            if total_match:
                total = int(total_match.group(1))
            
            passed_match = re.search(r'Успешно:\s*(\d+)', content)
            if passed_match:
                passed = int(passed_match.group(1))
            
            failed_match = re.search(r'Не пройдено:\s*(\d+)', content)
            if failed_match:
                failed = int(failed_match.group(1))
            
            skipped_match = re.search(r'Пропущено:\s*(\d+)', content)
            if skipped_match:
                skipped = int(skipped_match.group(1))
            
            pending_match = re.search(r'Осталось:\s*(\d+)', content)
            if pending_match:
                pending = int(pending_match.group(1))
        
        if total == 0:
            return None
        
        return {
            'date': report_date,
            'total': total,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'pending': pending,
        }
        
    except Exception as e:
        print(f"Ошибка парсинга HTML отчета {html_file}: {e}")
        import traceback
        traceback.print_exc()
        return None


def _generate_summary_html_content(report_data: List[Dict]) -> str:
    """Сгенерировать HTML содержимое суммарного отчета с графиком."""
    
    # Формируем данные для графика
    dates = [data['date'].strftime("%Y-%m-%d") for data in report_data]
    passed_data = [data['passed'] for data in report_data]
    failed_data = [data['failed'] for data in report_data]
    skipped_data = [data['skipped'] for data in report_data]
    pending_data = [data['pending'] for data in report_data]
    
    # Форматируем даты для отображения
    date_labels = [data['date'].strftime("%d.%m.%Y") for data in report_data]
    
    # Сериализуем данные для JavaScript
    dates_json = json.dumps(dates, ensure_ascii=False)
    date_labels_json = json.dumps(date_labels, ensure_ascii=False)
    passed_data_json = json.dumps(passed_data, ensure_ascii=False)
    failed_data_json = json.dumps(failed_data, ensure_ascii=False)
    skipped_data_json = json.dumps(skipped_data, ensure_ascii=False)
    pending_data_json = json.dumps(pending_data, ensure_ascii=False)
    
    # Вычисляем общую статистику
    total_reports = len(report_data)
    latest_report = report_data[-1] if report_data else None
    
    generation_date = datetime.now()
    date_str = generation_date.strftime("%d.%m.%Y %H:%M")
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Суммарный отчет по тест-кейсам</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
            color: #e0e0e0;
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: #2a2a2a;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        
        h1 {{
            color: #ffffff;
            margin-bottom: 10px;
            font-size: 32px;
            text-align: center;
        }}
        
        .subtitle {{
            text-align: center;
            color: #a0a0a0;
            margin-bottom: 30px;
            font-size: 14px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .stat-card {{
            background: #333;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            border: 1px solid #444;
        }}
        
        .stat-value {{
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            color: #b0b0b0;
            font-size: 14px;
        }}
        
        .chart-container {{
            background: #333;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 40px;
            border: 1px solid #444;
        }}
        
        .chart-title {{
            color: #ffffff;
            font-size: 20px;
            margin-bottom: 20px;
            text-align: center;
        }}
        
        .chart-wrapper {{
            position: relative;
            height: 400px;
            margin: 0 auto;
        }}
        
        .info-section {{
            background: #333;
            border-radius: 8px;
            padding: 20px;
            border: 1px solid #444;
            text-align: center;
        }}
        
        .info-item {{
            color: #b0b0b0;
            margin: 5px 0;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Суммарный отчет по тест-кейсам</h1>
        <div class="subtitle">Дата формирования: {date_str}</div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{total_reports}</div>
                <div class="stat-label">Всего отчетов</div>
            </div>
"""
    
    if latest_report:
        html += f"""
            <div class="stat-card">
                <div class="stat-value" style="color: #6CC24A;">{latest_report['total']}</div>
                <div class="stat-label">Всего тест-кейсов (последний отчет)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #6CC24A;">{latest_report['passed']}</div>
                <div class="stat-label">Успешно пройдено</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #F5555D;">{latest_report['failed']}</div>
                <div class="stat-label">Не пройдено</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #95a5a6;">{latest_report['skipped']}</div>
                <div class="stat-label">Пропущено</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #FFA931;">{latest_report['pending']}</div>
                <div class="stat-label">Осталось</div>
            </div>
"""
    
    html += f"""
        </div>
        
        <div class="chart-container">
            <div class="chart-title">Динамика прохождения тестов по периодам</div>
            <div class="chart-wrapper">
                <canvas id="summaryChart"></canvas>
            </div>
        </div>
        
        <div class="info-section">
            <div class="info-item">📅 Период: {date_labels[0] if date_labels else 'N/A'} - {date_labels[-1] if date_labels else 'N/A'}</div>
            <div class="info-item">📈 Всего отчетов: {total_reports}</div>
        </div>
    </div>
    
    <script>
        const ctx = document.getElementById('summaryChart');
        const dates = {dates_json};
        const dateLabels = {date_labels_json};
        
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: dateLabels,
                datasets: [
                    {{
                        label: 'Passed',
                        data: {passed_data_json},
                        borderColor: '#6CC24A',
                        backgroundColor: 'rgba(108, 194, 74, 0.6)',
                        fill: true,
                        tension: 0.4,
                        stack: 'stack1'
                    }},
                    {{
                        label: 'Failed',
                        data: {failed_data_json},
                        borderColor: '#F5555D',
                        backgroundColor: 'rgba(245, 85, 93, 0.6)',
                        fill: true,
                        tension: 0.4,
                        stack: 'stack1'
                    }},
                    {{
                        label: 'Skipped',
                        data: {skipped_data_json},
                        borderColor: '#95a5a6',
                        backgroundColor: 'rgba(149, 165, 166, 0.6)',
                        fill: true,
                        tension: 0.4,
                        stack: 'stack1'
                    }},
                    {{
                        label: 'Not run',
                        data: {pending_data_json},
                        borderColor: '#808080',
                        backgroundColor: 'rgba(128, 128, 128, 0.6)',
                        fill: true,
                        tension: 0.4,
                        stack: 'stack1'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    mode: 'index',
                    intersect: false,
                }},
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{
                            color: '#e0e0e0',
                            font: {{
                                size: 14
                            }},
                            padding: 15
                        }}
                    }},
                    tooltip: {{
                        mode: 'index',
                        intersect: false,
                        callbacks: {{
                            label: function(context) {{
                                return context.dataset.label + ': ' + context.parsed.y;
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        title: {{
                            display: true,
                            text: 'Дата',
                            color: '#e0e0e0'
                        }},
                        ticks: {{
                            color: '#e0e0e0',
                            maxRotation: 45,
                            minRotation: 45
                        }},
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.1)'
                        }}
                    }},
                    y: {{
                        title: {{
                            display: true,
                            text: 'Tests',
                            color: '#e0e0e0'
                        }},
                        ticks: {{
                            color: '#e0e0e0'
                        }},
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.1)'
                        }},
                        beginAtZero: true
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    return html

