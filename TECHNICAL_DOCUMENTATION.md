# Техническая документация Test Case Editor

## Содержание

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Структура проекта](#структура-проекта)
3. [Архитектурные принципы](#архитектурные-принципы)
4. [Модели данных](#модели-данных)
5. [Слои приложения](#слои-приложения)
6. [Компоненты UI](#компоненты-ui)
7. [Утилиты и вспомогательные модули](#утилиты-и-вспомогательные-модули)
8. [Формат данных](#формат-данных)
9. [Настройки и конфигурация](#настройки-и-конфигурация)
10. [Интеграции](#интеграции)
11. [Расширение функционала](#расширение-функционала)

---

## Обзор архитектуры

Test Case Editor построен на принципах SOLID и использует многослойную архитектуру:

```
┌─────────────────────────────────────┐
│         UI Layer (PyQt5)            │
│  (MainWindow, Widgets, Panels)       │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Service Layer                  │
│  (TestCaseService)                  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    Repository Layer                 │
│  (ITestCaseRepository)              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Model Layer                    │
│  (TestCase, TestCaseStep)           │
└─────────────────────────────────────┘
```

### Основные компоненты

- **Models** - модели данных (TestCase, TestCaseStep)
- **Repositories** - работа с хранилищем данных (файловая система)
- **Services** - бизнес-логика приложения
- **UI** - пользовательский интерфейс (PyQt5)
- **Utils** - вспомогательные утилиты

---

## Структура проекта

```
test_case_editor/
├── models/                          # Модели данных
│   ├── __init__.py
│   └── test_case.py                 # TestCase, TestCaseStep
│
├── repositories/                     # Работа с хранилищем
│   ├── __init__.py
│   └── test_case_repository.py      # ITestCaseRepository, TestCaseRepository
│
├── services/                         # Бизнес-логика
│   ├── __init__.py
│   └── test_case_service.py         # TestCaseService
│
├── ui/                               # Пользовательский интерфейс
│   ├── __init__.py
│   ├── main_window.py               # Главное окно приложения
│   │
│   ├── widgets/                      # Виджеты UI
│   │   ├── tree_widget.py           # Дерево тест-кейсов
│   │   ├── form_widget.py           # Форма редактирования
│   │   ├── information_panel.py     # Панель основной информации
│   │   ├── auxiliary_panel.py       # Боковая панель (Ревью, Создать ТК, JSON, Статистика)
│   │   ├── review_panel.py          # Панель ревью с LLM
│   │   ├── manual_review_panel.py   # Панель ручного ревью
│   │   ├── stats_panel.py           # Панель статистики
│   │   ├── json_preview_widget.py   # Просмотр JSON
│   │   ├── files_panel.py           # Панель управления файлами
│   │   ├── reports_panel.py          # Панель отчетности
│   │   ├── filter_panel.py          # Панель фильтрации
│   │   ├── toggle_switch.py         # Переключатель режимов
│   │   ├── checkbox_combo.py        # Комбобокс с чекбоксами
│   │   └── draggable_content_widget.py # Виджет с drag & drop
│   │
│   └── styles/                       # Стили интерфейса
│       ├── app_theme.py              # Тема приложения
│       ├── cursor_theme.py            # Тема курсора
│       ├── theme_provider.py         # Провайдер тем
│       └── ui_metrics.py             # Метрики UI (шрифты, отступы)
│
└── utils/                            # Утилиты
    ├── allure_generator.py           # Генерация Allure отчетов
    ├── html_report_generator.py      # Генерация HTML отчетов
    ├── summary_report_generator.py    # Генерация суммарных отчетов
    ├── llm.py                        # Работа с LLM
    ├── prompt_builder.py             # Построение промптов
    ├── azure_parser.py               # Парсинг Azure DevOps
    ├── datetime_utils.py              # Утилиты для работы с датами
    ├── list_models.py                 # Модели для списков
    ├── resource_path.py              # Пути к ресурсам
    └── settings_path.py              # Пути к настройкам
```

---

## Архитектурные принципы

### SOLID принципы

#### 1. Single Responsibility Principle (SRP)

Каждый класс отвечает за одну задачу:

- **TestCase** - хранение данных тест-кейса
- **TestCaseStep** - хранение данных шага
- **TestCaseRepository** - работа с файлами
- **TestCaseService** - бизнес-логика
- **MainWindow** - координация UI
- **Widgets** - отображение отдельных компонентов

#### 2. Open/Closed Principle (OCP)

- Можно добавлять новые виджеты без изменения существующих
- Можно создать новый репозиторий (например, для БД) без изменения сервиса
- Новые панели добавляются через `AuxiliaryPanel` без изменения `MainWindow`

#### 3. Liskov Substitution Principle (LSP)

- Любая реализация `ITestCaseRepository` может заменить `TestCaseRepository`
- Все виджеты наследуются от стандартных PyQt5 виджетов

#### 4. Interface Segregation Principle (ISP)

- `ITestCaseRepository` определяет только необходимые методы
- Клиенты зависят только от нужных им интерфейсов

#### 5. Dependency Inversion Principle (DIP)

- `MainWindow` зависит от `TestCaseService` (абстракция)
- `TestCaseService` зависит от `ITestCaseRepository` (абстракция)
- Конкретные реализации создаются на верхнем уровне (`run_app.py`)

---

## Модели данных

### TestCase

Основная модель тест-кейса.

**Расположение:** `test_case_editor/models/test_case.py`

**Основные поля:**

```python
@dataclass
class TestCase:
    id: str                          # UUID тест-кейса
    name: str                        # Название
    description: str                 # Описание
    preconditions: str               # Предусловия
    expected_result: str             # Общий ожидаемый результат
    epic: str                        # Epic
    feature: str                     # Feature
    story: str                       # Story
    component: str                  # Component
    test_layer: str                 # Test Layer (Unit, API, UI, E2E, Integration)
    severity: str                   # Severity (BLOCKER, CRITICAL, MAJOR, NORMAL, MINOR)
    priority: str                   # Priority (HIGHEST, HIGH, MEDIUM, LOW, LOWEST)
    environment: str                # Environment
    browser: str                    # Browser
    owner: str                      # Owner
    author: str                     # Author
    reviewer: str                   # Reviewer
    test_case_id: str              # Test Case ID
    issue_links: str                # Issue Links
    test_case_links: str           # Test Case Links
    tags: List[str]                # Tags
    test_type: str                 # Test Type (manual, automated)
    status: str                    # Status (Draft, In Progress, Done, Blocked, Deprecated)
    steps: List[TestCaseStep]      # Шаги тестирования
    created_at: int                # Timestamp создания
    updated_at: int                # Timestamp обновления
    _filepath: Optional[Path]     # Путь к файлу (внутреннее поле)
    _filename: str                 # Имя файла (внутреннее поле)
```

**Методы:**

- `to_dict()` - преобразование в словарь для JSON
- `from_dict(data: dict)` - создание из словаря
- `to_json()` - преобразование в JSON строку

### TestCaseStep

Модель шага тест-кейса.

**Расположение:** `test_case_editor/models/test_case.py`

**Основные поля:**

```python
@dataclass
class TestCaseStep:
    id: str                         # UUID шага
    name: str                       # Название шага
    description: str                # Действие (описание шага)
    expected_result: str           # Ожидаемый результат
    status: str                    # Статус (pending, passed, failed, skipped)
    bug_link: str                  # Ссылка на баг
    skip_reason: str               # Причина пропуска
    attachments: List[str]         # Прикрепленные файлы
```

**Методы:**

- `to_dict()` - преобразование в словарь
- `from_dict(data: dict)` - создание из словаря

---

## Слои приложения

### Repository Layer

**Интерфейс:** `ITestCaseRepository`

**Реализация:** `TestCaseRepository`

**Ответственность:**
- Загрузка тест-кейсов из файловой системы
- Сохранение тест-кейсов в JSON файлы
- Удаление тест-кейсов
- Создание новых тест-кейсов

**Основные методы:**

```python
class ITestCaseRepository(ABC):
    def load_all(directory: Path) -> List[TestCase]
    def save(test_case: TestCase, filepath: Path) -> None
    def delete(filepath: Path) -> None
    def create_new(target_folder: Path) -> TestCase
```

**Особенности:**
- Рекурсивный поиск JSON файлов
- Валидация данных при загрузке
- Автоматическая генерация UUID для новых тест-кейсов
- Обработка ошибок чтения/записи

### Service Layer

**Класс:** `TestCaseService`

**Ответственность:**
- Бизнес-логика работы с тест-кейсами
- Валидация данных
- Координация операций
- Дублирование тест-кейсов
- Перемещение тест-кейсов
- Импорт из Azure DevOps

**Основные методы:**

```python
class TestCaseService:
    def load_all_test_cases(directory: Path) -> List[TestCase]
    def save_test_case(test_case: TestCase) -> bool
    def delete_test_case(test_case: TestCase) -> bool
    def create_new_test_case(target_folder: Path) -> Optional[TestCase]
    def duplicate_test_case(test_case: TestCase) -> Optional[TestCase]
    def move_item(source_path: Path, target_folder: Path) -> bool
    def import_from_azure(json_file: Path) -> List[TestCase]
```

**Зависимости:**
- `ITestCaseRepository` - для работы с данными

### UI Layer

**Главное окно:** `MainWindow`

**Ответственность:**
- Координация всех компонентов UI
- Управление состоянием приложения
- Обработка событий
- Управление панелями

**Основные компоненты:**

1. **TreeWidget** - дерево тест-кейсов
2. **FormWidget** - форма редактирования
3. **AuxiliaryPanel** - боковая панель с вкладками
4. **FilterPanel** - панель фильтрации
5. **Header** - заголовок с переключателем режимов

---

## Компоненты UI

### MainWindow

**Расположение:** `test_case_editor/ui/main_window.py`

**Основные компоненты:**

- **Левая панель:**
  - `FilterPanel` - поиск и фильтрация
  - `TestCaseTreeWidget` - дерево тест-кейсов

- **Центральная панель:**
  - `TestCaseFormWidget` - форма редактирования

- **Правая панель:**
  - `AuxiliaryPanel` - боковая панель с вкладками:
    - Ревью
    - Создать ТК
    - JSON Preview
    - Статистика
    - Файлы
    - Отчетность

**Режимы работы:**

1. **Режим редактирования** (по умолчанию)
   - Все поля редактируемые
   - Доступны контекстные меню
   - Доступны все панели

2. **Режим запуска тестов**
   - Поля read-only
   - Кнопки статусов шагов (passed, failed, skipped)
   - Автоматически открывается панель статистики

### TestCaseTreeWidget

**Расположение:** `test_case_editor/ui/widgets/tree_widget.py`

**Функционал:**

- Отображение дерева тест-кейсов и папок
- Drag & Drop для перемещения
- Контекстные меню для операций
- Фильтрация элементов
- Отображение статусов (цветные кружки)
- Создание/переименование/удаление папок и файлов
- Валидация имен файлов и папок

**Сигналы:**

- `test_case_selected` - выбор тест-кейса
- `tree_updated` - обновление дерева
- `review_requested` - запрос ревью
- `test_cases_updated` - обновление тест-кейсов
- `add_to_review_requested` - добавление в ревью

**Особенности:**

- Сохранение состояния развернутых папок
- Восстановление выбранного элемента после обновления
- Поддержка режимов редактирования и запуска тестов

### TestCaseFormWidget

**Расположение:** `test_case_editor/ui/widgets/form_widget.py`

**Компоненты:**

1. **InformationPanel** - основная информация:
   - Название, ID, статус
   - Автор, владелец, ревьювер
   - Epic, Feature, Story, Component
   - Test Layer, Test Type, Severity, Priority
   - Environment, Browser
   - Теги, описание, предусловия, ожидаемый результат

2. **Таблица шагов:**
   - Редактирование шагов
   - Контекстные меню для управления
   - Кнопки статусов в режиме запуска тестов
   - Прикрепление файлов к шагам

**Сигналы:**

- `test_case_changed` - изменение тест-кейса
- `save_requested` - запрос сохранения

### AuxiliaryPanel

**Расположение:** `test_case_editor/ui/widgets/auxiliary_panel.py`

**Вкладки:**

1. **ReviewPanel** - ревью с LLM
2. **CreationPanel** - создание тест-кейсов с LLM
3. **JSONPreviewWidget** - просмотр JSON
4. **StatsPanel** - статистика
5. **FilesPanel** - управление файлами
6. **ReportsPanel** - отчетность

### ReviewPanel

**Расположение:** `test_case_editor/ui/widgets/review_panel.py`

**Функционал:**

- Отправка запросов к LLM для ревью
- Прикрепление методики и тест-кейса
- Сохранение промптов
- Отображение истории сообщений

### StatsPanel

**Расположение:** `test_case_editor/ui/widgets/stats_panel.py`

**Функционал:**

- Отображение статистики по тест-кейсам
- Управление статусами (сброс, пометка как passed)
- Генерация Allure отчетов

### FilesPanel

**Расположение:** `test_case_editor/ui/widgets/files_panel.py`

**Функционал:**

- Отображение прикрепленных файлов
- Drag & Drop для добавления файлов
- Привязка файлов к шагам
- Удаление файлов
- Открытие файлов в проводнике (двойной клик)

### ReportsPanel

**Расположение:** `test_case_editor/ui/widgets/reports_panel.py`

**Функционал:**

- Отображение структуры папки Reports
- Генерация отчетов
- Генерация суммарных отчетов
- Открытие файлов в проводнике (двойной клик)

---

## Утилиты и вспомогательные модули

### allure_generator.py

**Функционал:**

- Конвертация тест-кейсов в формат Allure Test Result JSON
- Создание структуры папок для отчетов
- Генерация метаданных

**Основные функции:**

- `generate_allure_report(test_cases_dir: Path, output_dir: Path) -> Path`
- `convert_test_case_to_allure(test_case: TestCase) -> dict`

### llm.py

**Функционал:**

- Работа с LLM API
- Отправка запросов
- Обработка ответов
- Обработка ошибок

**Основные классы:**

- `LLMClient` - клиент для работы с LLM

### prompt_builder.py

**Функционал:**

- Построение промптов для LLM
- Прикрепление файлов
- Форматирование контекста

### azure_parser.py

**Функционал:**

- Парсинг JSON файлов из Azure DevOps
- Конвертация в формат TestCase
- Обработка различных форматов

### datetime_utils.py

**Функционал:**

- Работа с датами и временем
- Конвертация в timestamp
- Форматирование дат

---

## Формат данных

### JSON структура тест-кейса

```json
{
  "id": "uuid",
  "name": "Название тест-кейса",
  "description": "Описание",
  "preconditions": "Предусловия",
  "expectedResult": "Общий ожидаемый результат",
  "epic": "Epic",
  "feature": "Feature",
  "story": "Story",
  "component": "Component",
  "testLayer": "E2E",
  "severity": "NORMAL",
  "priority": "MEDIUM",
  "environment": "dev",
  "browser": "chrome",
  "owner": "Owner",
  "author": "Author",
  "reviewer": "Reviewer",
  "testCaseId": "TC-001",
  "issueLinks": "ISSUE-1, ISSUE-2",
  "testCaseLinks": "TC-002, TC-003",
  "tags": ["tag1", "tag2"],
  "testType": "manual",
  "status": "Draft",
  "steps": [
    {
      "id": "uuid",
      "name": "Название шага",
      "description": "Действие",
      "expectedResult": "Ожидаемый результат",
      "status": "pending",
      "bugLink": "",
      "skipReason": "",
      "attachments": "file1.pdf, file2.png"
    }
  ],
  "createdAt": 1234567890000,
  "updatedAt": 1234567890000
}
```

### Особенности формата

- **ID** - UUID v4
- **Timestamps** - миллисекунды с эпохи Unix
- **Tags** - массив строк или строка с разделителями
- **Attachments** - строка с разделителями (запятая)
- **Status** - строковые значения (pending, passed, failed, skipped)

---

## Настройки и конфигурация

### settings.json

**Расположение:** определяется через `settings_path.py`

**Структура:**

```json
{
  "test_cases_dir": "путь/к/папке/с/тест-кейсами",
  "DEFAULT_PROMT": "Промт для ревью",
  "DEFAULT_PROMT_CREATE_TC": "Промт для создания ТК",
  "LLM_MODEL": "модель",
  "LLM_HOST": "http://host:port",
  "LLM_METHODIC_PATH": "путь/к/методике.md",
  "skip_reasons": ["Автотесты", "Нагрузочное тестирование", "Другое"],
  "panel_sizes": {
    "left": 350,
    "form_area": 900,
    "review": 360
  },
  "window_geometry": {
    "x": 100,
    "y": 100,
    "width": 1600,
    "height": 900,
    "is_fullscreen": false
  }
}
```

### Пути к ресурсам

- **Иконки:** `icons/` в корне проекта
- **Методика:** путь из настроек или по умолчанию
- **Reports:** `Reports/` в корне проекта
- **Attachments:** `_attachment/` в папке тест-кейса

---

## Интеграции

### LLM интеграция

**Модуль:** `test_case_editor/utils/llm.py`

**Настройка:**

- `LLM_HOST` - адрес API
- `LLM_MODEL` - модель для использования

**Использование:**

1. Ревью тест-кейсов
2. Создание тест-кейсов из ТЗ

### Git интеграция

**Функционал:**

- Commit и push изменений
- Работает в папке с тест-кейсами (должна быть git репозиторием)

### Azure DevOps импорт

**Модуль:** `test_case_editor/utils/azure_parser.py`

**Функционал:**

- Парсинг JSON файлов из Azure DevOps
- Конвертация в формат TestCase
- Создание тест-кейсов в папке "from alm"

### Allure интеграция

**Модуль:** `test_case_editor/utils/allure_generator.py`

**Функционал:**

- Генерация Allure Test Result JSON
- Создание структуры для `allure serve`

---

## Расширение функционала

### Добавление нового виджета

1. Создайте класс виджета в `test_case_editor/ui/widgets/`
2. Наследуйтесь от `QWidget` или соответствующего базового класса
3. Добавьте виджет в `AuxiliaryPanel` или `MainWindow`

**Пример:**

```python
class MyCustomWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # ... настройка UI
```

### Добавление нового репозитория

1. Создайте класс, реализующий `ITestCaseRepository`
2. Реализуйте все абстрактные методы
3. Используйте в `TestCaseService`

**Пример:**

```python
class DatabaseRepository(ITestCaseRepository):
    def load_all(self, directory: Path) -> List[TestCase]:
        # Реализация загрузки из БД
        pass
    
    def save(self, test_case: TestCase, filepath: Path) -> None:
        # Реализация сохранения в БД
        pass
    
    # ... остальные методы
```

### Добавление новой панели

1. Создайте виджет панели
2. Добавьте вкладку в `AuxiliaryPanel`
3. Подключите сигналы и слоты

**Пример:**

```python
# В auxiliary_panel.py
self.tabs.addTab(MyNewPanel(), "Новая панель")
```

### Добавление нового фильтра

1. Добавьте поле фильтра в `FilterPanel`
2. Обновите метод `_apply_filter` в `TestCaseTreeWidget`
3. Добавьте логику фильтрации

### Добавление новой утилиты

1. Создайте модуль в `test_case_editor/utils/`
2. Реализуйте необходимые функции
3. Импортируйте в нужных местах

---

## Работа с файловой системой

### Структура папок

```
test_cases_dir/
├── folder1/
│   ├── test_case_1.json
│   ├── test_case_2.json
│   └── _attachment/
│       ├── {id}_file1.pdf
│       └── {id}_file2.png
├── folder2/
│   └── ...
└── from LLM/
    └── ...
```

### Именование файлов

- Тест-кейсы: `{name}.json`
- Вложения: `{test_case_id}_{original_name}.{ext}`
- Папки: произвольные имена (без запрещенных символов)

### Запрещенные символы в именах

`\ / : * ? " < > |`

Валидация выполняется в:
- `TestCaseTreeWidget._validate_folder_name()`
- `TestCaseTreeWidget.FolderNameDialog`
- `TestCaseTreeWidget.FileNameDialog`

---

## Обработка ошибок

### Принципы

1. **Валидация на уровне UI** - проверка данных перед отправкой
2. **Обработка исключений** - try/except блоки в критических местах
3. **Логирование** - print для отладки (можно заменить на logging)
4. **Сообщения пользователю** - QMessageBox для ошибок

### Типичные ошибки

- **Файл не найден** - проверка существования перед операциями
- **Ошибка чтения JSON** - обработка в `TestCaseRepository.load_all()`
- **Ошибка сохранения** - обработка в `TestCaseService.save_test_case()`
- **Ошибка LLM** - обработка в `LLMClient`

---

## Тестирование

### Рекомендации

1. **Unit тесты** - для моделей и утилит
2. **Integration тесты** - для сервисов и репозиториев
3. **UI тесты** - для виджетов (можно использовать pytest-qt)

### Пример структуры тестов

```
tests/
├── unit/
│   ├── test_models.py
│   └── test_utils.py
├── integration/
│   ├── test_repository.py
│   └── test_service.py
└── ui/
    └── test_widgets.py
```

---

## Производительность

### Оптимизации

1. **Ленивая загрузка** - загрузка тест-кейсов только при необходимости
2. **Кэширование** - кэш иконок в `TestCaseTreeWidget`
3. **Виртуализация** - использование стандартных виджетов PyQt5
4. **Асинхронность** - для LLM запросов (можно добавить)

### Рекомендации

- Избегайте загрузки всех тест-кейсов сразу при большом количестве
- Используйте пагинацию для больших списков
- Кэшируйте часто используемые данные

---

## Безопасность

### Рекомендации

1. **Валидация входных данных** - проверка всех пользовательских данных
2. **Санитизация путей** - проверка путей к файлам
3. **Обработка исключений** - не показывать внутренние ошибки пользователю
4. **Безопасность LLM** - валидация промптов

---

## Миграция и совместимость

### Версионирование

- Формат данных обратно совместим
- Новые поля добавляются с значениями по умолчанию
- Старые форматы автоматически конвертируются

### Миграция данных

- Автоматическая конвертация при загрузке
- Сохранение в новом формате при сохранении

---

## Дополнительные ресурсы

- **README.md** - общая информация о проекте
- **BUILD_INSTRUCTIONS.md** - инструкции по сборке
- **test_case_editor/docs/** - дополнительная документация

---

## Контакты и поддержка

Для вопросов по разработке обращайтесь к команде разработки.

---

*Последнее обновление: 2024*

