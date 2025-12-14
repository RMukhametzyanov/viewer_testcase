"""Утилита для генерации HTML отчетов с статистикой по тест-кейсам."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Set

from ..models.test_case import TestCase
from ..services.test_case_service import TestCaseService
from ..repositories.test_case_repository import TestCaseRepository


def generate_html_report(
    test_cases_dir: Path,
    app_dir: Optional[Path] = None,
    project_name: Optional[str] = None,
) -> Optional[Path]:
    """
    Генерирует HTML отчет с статистикой по тест-кейсам.
    
    Args:
        test_cases_dir: Путь к папке с тест-кейсами
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
        
        # Создаем папку Reports_by_viewer в родительской директории test_cases_dir
        # Если test_cases_dir = "/path/to/test_suites", то reports_dir = "/path/to/Reports_by_viewer"
        reports_dir = test_cases_dir.parent / "Reports_by_viewer"
        reports_dir.mkdir(exist_ok=True, parents=True)
        
        # Создаем подпапку с датой и временем
        dt = datetime.now()
        timestamp = dt.strftime("%Y_%m_%d_%H_%M")
        report_dir = reports_dir / timestamp
        report_dir.mkdir(exist_ok=True)
        
        # Загружаем тест-кейсы
        repository = TestCaseRepository()
        service = TestCaseService(repository)
        test_cases = service.load_all_test_cases(test_cases_dir)
        
        if not test_cases:
            return None
        
        # Собираем статистику
        stats = _calculate_statistics(test_cases)
        
        # Собираем уникальных участников
        owners = _get_unique_owners(test_cases)
        
        # Собираем failed и skipped тест-кейсы с причинами
        failed_cases, skipped_cases, reasons_stats = _collect_failed_and_skipped(test_cases)
        
        # Генерируем HTML
        html_content = _generate_html_content(stats, owners, dt, failed_cases, skipped_cases, reasons_stats, test_cases)
        
        # Формируем имя файла с датой и названием проекта
        date_str = dt.strftime("%Y-%m-%d")
        if project_name and project_name.strip():
            html_filename = f"{project_name.strip()}. Отчет о прохождении тестирования {date_str}.html"
        else:
            html_filename = f"Отчет о прохождении тестирования {date_str}.html"
        
        # Сохраняем HTML файл
        html_file = report_dir / html_filename
        html_file.write_text(html_content, encoding='utf-8')
        
        return report_dir
        
    except Exception as e:
        print(f"Ошибка при генерации HTML отчета: {e}")
        return None


def _calculate_statistics(test_cases: List[TestCase]) -> Dict[str, int]:
    """Вычислить статистику по тест-кейсам"""
    total = len(test_cases)
    passed = 0
    failed = 0
    skipped = 0
    pending = 0
    
    for case in test_cases:
        steps = case.steps or []
        if not steps:
            pending += 1
            continue
        
        statuses = [s.status or "" for s in steps]
        normalized = [status.strip().lower() for status in statuses]
        
        # Проверяем наличие failed (приоритет 1)
        if any(s == "failed" for s in normalized):
            failed += 1
            continue
        
        # Проверяем наличие skipped (приоритет 2)
        if any(s == "skipped" for s in normalized):
            skipped += 1
            continue
        
        # Проверяем, все ли шаги passed
        if all(s for s in normalized) and all(s == "passed" for s in normalized):
            passed += 1
        else:
            pending += 1
    
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pending": pending,
    }


def _get_unique_owners(test_cases: List[TestCase]) -> Set[str]:
    """Получить уникальных участников (Owner)"""
    owners = set()
    for case in test_cases:
        owner = getattr(case, "owner", "") or ""
        if owner.strip():
            owners.add(owner.strip())
    return owners


def _collect_failed_and_skipped(test_cases: List[TestCase]) -> tuple:
    """
    Собрать failed и skipped тест-кейсы с причинами.
    
    Returns:
        tuple: (failed_cases, skipped_cases, reasons_stats)
    """
    failed_cases = []
    skipped_cases = []
    reasons_stats: Dict[str, int] = {}
    
    for case in test_cases:
        if not case.steps:
            continue
        
        steps = case.steps
        statuses = [s.status or "" for s in steps]
        normalized = [status.strip().lower() for status in statuses]
        
        # Проверяем failed
        if any(s == "failed" for s in normalized):
            # Собираем причины ошибок (из bug_link или skip_reason)
            reasons = []
            for step in steps:
                if step.status == "failed":
                    # Для failed приоритет у bug_link, затем skip_reason
                    reason = step.bug_link or step.skip_reason or "Ошибка не указана"
                    reasons.append(reason)
                    reasons_stats[reason] = reasons_stats.get(reason, 0) + 1
            failed_cases.append({
                "case": case,
                "reasons": list(set(reasons))  # Уникальные причины
            })
        
        # Проверяем skipped
        if any(s == "skipped" for s in normalized):
            # Собираем причины пропуска
            reasons = []
            for step in steps:
                if step.status == "skipped":
                    reason = step.skip_reason or "Причина не указана"
                    reasons.append(reason)
                    reasons_stats[reason] = reasons_stats.get(reason, 0) + 1
            skipped_cases.append({
                "case": case,
                "reasons": list(set(reasons))  # Уникальные причины
            })
    
    return failed_cases, skipped_cases, reasons_stats


def _generate_results_section(
    failed_cases: List[Dict],
    skipped_cases: List[Dict],
    reasons_stats: Dict[str, int],
    test_cases: List[TestCase]
) -> str:
    """Сгенерировать секцию с результатами прогона в виде таблицы"""
    
    # Объединяем все тест-кейсы с их статусами
    all_results = []
    
    for case in test_cases:
        if not case.steps:
            continue
        
        steps = case.steps
        statuses = [s.status or "" for s in steps]
        normalized = [status.strip().lower() for status in statuses]
        
        # Определяем статус тест-кейса
        status = "pending"
        skip_reason = ""
        error_reason = ""
        
        if any(s == "failed" for s in normalized):
            status = "failed"
            # Собираем причины ошибок
            error_reasons = []
            for step in steps:
                if step.status == "failed":
                    reason = step.bug_link or step.skip_reason or ""
                    if reason:
                        error_reasons.append(reason)
            error_reason = ", ".join(set(error_reasons)) if error_reasons else ""
        elif any(s == "skipped" for s in normalized):
            status = "skipped"
            # Собираем причины пропуска
            skip_reasons = []
            for step in steps:
                if step.status == "skipped":
                    reason = step.skip_reason or ""
                    if reason:
                        skip_reasons.append(reason)
            skip_reason = ", ".join(set(skip_reasons)) if skip_reasons else ""
        elif all(s for s in normalized) and all(s == "passed" for s in normalized):
            status = "passed"
        
        # Добавляем только тест-кейсы со статусами failed, skipped или passed
        if status in ("failed", "skipped", "passed"):
            all_results.append({
                "case": case,
                "status": status,
                "skip_reason": skip_reason,
                "error_reason": error_reason
            })
    
    # Сортируем: сначала failed, потом skipped, потом passed
    status_order = {"failed": 0, "skipped": 1, "passed": 2}
    all_results.sort(key=lambda x: (status_order.get(x["status"], 3), x["case"].name))
    
    # Формируем строки таблицы
    table_rows = ""
    for item in all_results:
        case = item["case"]
        status = item["status"]
        skip_reason = item["skip_reason"]
        error_reason = item["error_reason"]
        
        case_id = case.test_case_id or ""
        owner = case.owner or ""
        
        # Определяем класс для статуса
        status_class = f"status-{status}"
        status_text = {
            "failed": "Не пройдено",
            "skipped": "Пропущено",
            "passed": "Успешно"
        }.get(status, status)
        
        table_rows += f"""
            <tr>
                <td>{_escape_html(case_id)}</td>
                <td>{_escape_html(case.name)}</td>
                <td>{_escape_html(owner)}</td>
                <td><span class="status-badge {status_class}">{status_text}</span></td>
                <td>{_escape_html(skip_reason) if skip_reason else "-"}</td>
                <td>{_escape_html(error_reason) if error_reason else "-"}</td>
            </tr>
        """
    
    if not table_rows:
        table_rows = """
            <tr>
                <td colspan="6" style="text-align: center; color: #888; padding: 40px;">
                    Нет тест-кейсов с результатами прогона
                </td>
            </tr>
        """
    
    html = f"""
        <div class="results-section">
            <div class="results-title">📋 Результаты прогона тест-кейсов</div>
            
            <table class="results-table">
                <thead>
                    <tr>
                        <th>Идентификатор тест-кейса</th>
                        <th>Название</th>
                        <th>Владелец</th>
                        <th>Статус</th>
                        <th>Причина пропуска</th>
                        <th>Причина ошибки</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
    """
    
    return html


def _escape_html(text: str) -> str:
    """Экранировать HTML символы"""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _generate_html_content(
    stats: Dict[str, int], 
    owners: Set[str], 
    generation_date: datetime,
    failed_cases: List[Dict],
    skipped_cases: List[Dict],
    reasons_stats: Dict[str, int],
    test_cases: List[TestCase]
) -> str:
    """Сгенерировать HTML содержимое отчета"""
    
    total = stats["total"]
    passed = stats["passed"]
    failed = stats["failed"]
    skipped = stats["skipped"]
    pending = stats["pending"]
    
    # Вычисляем проценты для диаграммы
    passed_percent = (passed / total * 100) if total > 0 else 0
    failed_percent = (failed / total * 100) if total > 0 else 0
    skipped_percent = (skipped / total * 100) if total > 0 else 0
    pending_percent = (pending / total * 100) if total > 0 else 0
    
    # Формируем данные для круговой диаграммы
    chart_data = [
        {"label": "Успешно", "value": passed, "percent": passed_percent, "color": "#6CC24A"},
        {"label": "Не пройдено", "value": failed, "percent": failed_percent, "color": "#F5555D"},
        {"label": "Пропущено", "value": skipped, "percent": skipped_percent, "color": "#95a5a6"},
        {"label": "Осталось", "value": pending, "percent": pending_percent, "color": "#FFA931"},
    ]
    
    # Формируем список участников
    owners_list = sorted(list(owners)) if owners else ["Не указано"]
    
    # Форматируем дату
    date_str = generation_date.strftime("%d.%m.%Y %H:%M")
    
    # Генерируем секцию с результатами
    results_section = _generate_results_section(failed_cases, skipped_cases, reasons_stats, test_cases)
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчет по тест-кейсам</title>
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
            max-width: 1200px;
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
        
        .stat-card.passed {{
            border-color: #6CC24A;
        }}
        
        .stat-card.failed {{
            border-color: #F5555D;
        }}
        
        .stat-card.skipped {{
            border-color: #95a5a6;
        }}
        
        .stat-card.pending {{
            border-color: #FFA931;
        }}
        
        .stat-value {{
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-value.passed {{
            color: #6CC24A;
        }}
        
        .stat-value.failed {{
            color: #F5555D;
        }}
        
        .stat-value.skipped {{
            color: #95a5a6;
        }}
        
        .stat-value.pending {{
            color: #FFA931;
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
            max-width: 400px;
            margin: 0 auto;
        }}
        
        .owners-section {{
            background: #333;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 40px;
            border: 1px solid #444;
        }}
        
        .owners-title {{
            color: #ffffff;
            font-size: 20px;
            margin-bottom: 20px;
        }}
        
        .owners-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        .owner-badge {{
            background: #444;
            color: #e0e0e0;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            border: 1px solid #555;
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
        
        .results-section {{
            background: #333;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 40px;
            border: 1px solid #444;
        }}
        
        .results-title {{
            color: #ffffff;
            font-size: 20px;
            margin-bottom: 20px;
        }}
        
        .filter-section {{
            margin-bottom: 20px;
        }}
        
        .filter-label {{
            color: #b0b0b0;
            margin-right: 10px;
            font-size: 14px;
        }}
        
        .filter-select {{
            background: #444;
            color: #e0e0e0;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 8px 12px;
            font-size: 14px;
            min-width: 200px;
        }}
        
        .filter-select:focus {{
            outline: none;
            border-color: #6CC24A;
        }}
        
        .test-case-item {{
            background: #2a2a2a;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 4px solid;
        }}
        
        .test-case-item.failed {{
            border-left-color: #F5555D;
        }}
        
        .test-case-item.skipped {{
            border-left-color: #95a5a6;
        }}
        
        .test-case-name {{
            color: #ffffff;
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        
        .test-case-id {{
            color: #888;
            font-size: 12px;
            margin-bottom: 8px;
        }}
        
        .test-case-reasons {{
            color: #b0b0b0;
            font-size: 14px;
            margin-top: 8px;
        }}
        
        .reason-tag {{
            display: inline-block;
            background: #444;
            color: #e0e0e0;
            padding: 4px 8px;
            border-radius: 4px;
            margin: 4px 4px 4px 0;
            font-size: 12px;
        }}
        
        .reasons-stats {{
            background: #2a2a2a;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 20px;
        }}
        
        .reasons-stats-title {{
            color: #ffffff;
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 10px;
        }}
        
        .reason-stat-item {{
            color: #b0b0b0;
            font-size: 14px;
            margin: 5px 0;
            padding: 5px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .reason-stat-count {{
            color: #FFA931;
            font-weight: 600;
        }}
        
        .hidden {{
            display: none;
        }}
        
        .tabs {{
            display: flex;
            border-bottom: 2px solid #444;
            margin-bottom: 30px;
        }}
        
        .tab-button {{
            background: #2a2a2a;
            color: #b0b0b0;
            border: none;
            padding: 12px 24px;
            font-size: 16px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
            transition: all 0.3s;
        }}
        
        .tab-button:hover {{
            color: #e0e0e0;
            background: #333;
        }}
        
        .tab-button.active {{
            color: #ffffff;
            border-bottom-color: #6CC24A;
            background: #333;
        }}
        
        .tab-content {{
            display: none;
        }}
        
        .tab-content.active {{
            display: block;
        }}
        
        .results-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        
        .results-table th {{
            background: #2a2a2a;
            color: #ffffff;
            padding: 12px;
            text-align: left;
            border-bottom: 2px solid #444;
            font-weight: 600;
        }}
        
        .results-table td {{
            padding: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            color: #e0e0e0;
        }}
        
        .results-table tr:hover {{
            background: rgba(255, 255, 255, 0.05);
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .status-failed {{
            background: #F5555D;
            color: #ffffff;
        }}
        
        .status-skipped {{
            background: #95a5a6;
            color: #ffffff;
        }}
        
        .status-passed {{
            background: #6CC24A;
            color: #ffffff;
        }}
        
        .status-pending {{
            background: #FFA931;
            color: #ffffff;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Отчет по тест-кейсам</h1>
        <div class="subtitle">Дата формирования: {date_str}</div>
        
        <div class="tabs">
            <button class="tab-button active" onclick="showTab('general')">Общая информация</button>
            <button class="tab-button" onclick="showTab('results')">Результаты прогона тест-кейсов</button>
        </div>
        
        <div id="generalTab" class="tab-content active">
            <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{total}</div>
                <div class="stat-label">Всего тест-кейсов</div>
            </div>
            <div class="stat-card passed">
                <div class="stat-value passed">{passed}</div>
                <div class="stat-label">Успешно пройдено</div>
            </div>
            <div class="stat-card failed">
                <div class="stat-value failed">{failed}</div>
                <div class="stat-label">Не пройдено</div>
            </div>
            <div class="stat-card skipped">
                <div class="stat-value skipped">{skipped}</div>
                <div class="stat-label">Пропущено</div>
            </div>
            <div class="stat-card pending">
                <div class="stat-value pending">{pending}</div>
                <div class="stat-label">Осталось</div>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">Распределение по статусам</div>
            <div class="chart-wrapper">
                <canvas id="statusChart"></canvas>
            </div>
        </div>
        
        <div class="owners-section">
            <div class="owners-title">👥 Участники ({len(owners_list)})</div>
            <div class="owners-list">
"""
    
    for owner in owners_list:
        html += f'                <div class="owner-badge">{owner}</div>\n'
    
    html += f"""            </div>
        </div>
        
            <div class="info-section">
                <div class="info-item">📅 Дата формирования отчета: {date_str}</div>
                <div class="info-item">📈 Всего тест-кейсов: {total}</div>
                <div class="info-item">✅ Успешно: {passed} ({passed_percent:.1f}%)</div>
                <div class="info-item">❌ Не пройдено: {failed} ({failed_percent:.1f}%)</div>
                <div class="info-item">⏭️ Пропущено: {skipped} ({skipped_percent:.1f}%)</div>
                <div class="info-item">⏳ Осталось: {pending} ({pending_percent:.1f}%)</div>
            </div>
        </div>
        
        <div id="resultsTab" class="tab-content">
            {results_section}
        </div>
    </div>
    
    <script>
        const ctx = document.getElementById('statusChart');
        const chartData = {json.dumps(chart_data, ensure_ascii=False)};
        
        new Chart(ctx, {{
            type: 'doughnut',
            data: {{
                labels: chartData.map(item => item.label),
                datasets: [{{
                    data: chartData.map(item => item.value),
                    backgroundColor: chartData.map(item => item.color),
                    borderWidth: 2,
                    borderColor: '#2a2a2a'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
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
                        callbacks: {{
                            label: function(context) {{
                                const item = chartData[context.dataIndex];
                                return item.label + ': ' + item.value + ' (' + item.percent.toFixed(1) + '%)';
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        function showTab(tabName) {{
            // Скрываем все вкладки
            document.querySelectorAll('.tab-content').forEach(tab => {{
                tab.classList.remove('active');
            }});
            
            // Убираем активный класс со всех кнопок
            document.querySelectorAll('.tab-button').forEach(btn => {{
                btn.classList.remove('active');
            }});
            
            // Показываем выбранную вкладку
            document.getElementById(tabName + 'Tab').classList.add('active');
            
            // Активируем кнопку
            const buttons = document.querySelectorAll('.tab-button');
            buttons.forEach(btn => {{
                if (btn.textContent.includes(tabName === 'general' ? 'Общая информация' : 'Результаты прогона')) {{
                    btn.classList.add('active');
                }}
            }});
        }}
    </script>
</body>
</html>"""
    
    return html

