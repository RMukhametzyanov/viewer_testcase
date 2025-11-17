# Инструкция по использованию uv

## Быстрый старт

### 1. Установка uv

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Linux / macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Или через pip:**
```bash
pip install uv
```

### 2. Установка зависимостей проекта

```bash
uv sync
```

Эта команда:
- Создаст виртуальное окружение `.venv` (если его нет)
- Установит все зависимости из `pyproject.toml`
- Создаст файл `uv.lock` с зафиксированными версиями

### 3. Запуск приложения

```bash
uv run python run_app.py
```

## Основные команды

### Управление зависимостями

```bash
# Добавить новую зависимость
uv add package-name

# Добавить зависимость с версией
uv add "package-name>=1.0.0"

# Удалить зависимость
uv remove package-name

# Обновить все зависимости
uv sync --upgrade

# Обновить конкретную зависимость
uv sync --upgrade-package package-name
```

### Работа с виртуальным окружением

```bash
# Создать виртуальное окружение
uv venv

# Активировать (Windows)
.venv\Scripts\activate

# Активировать (Linux/macOS)
source .venv/bin/activate

# Деактивировать
deactivate
```

### Полезные команды

```bash
# Показать список установленных пакетов
uv pip list

# Показать дерево зависимостей
uv tree

# Экспортировать в requirements.txt
uv pip compile pyproject.toml -o requirements.txt
```

## Структура проекта

- `pyproject.toml` - основной файл с зависимостями проекта
- `uv.lock` - файл блокировки версий (создается автоматически)
- `.python-version` - версия Python для проекта
- `.venv/` - виртуальное окружение (создается автоматически)

## Преимущества uv

1. **Скорость** - в 10-100 раз быстрее pip
2. **Надежность** - детерминированные установки
3. **Удобство** - один инструмент для всех задач
4. **Совместимость** - работает с существующими проектами

## Устранение проблем

**Команда `uv` не найдена:**
- Перезапустите терминал
- Проверьте, что uv установлен: `uv --version`
- Добавьте uv в PATH вручную

**Конфликты зависимостей:**
```bash
uv sync --upgrade
```

**Использование конкретной версии Python:**
```bash
uv venv --python 3.11
```

## Дополнительная информация

Полная документация: https://docs.astral.sh/uv/
Репозиторий: https://github.com/astral-sh/uv

