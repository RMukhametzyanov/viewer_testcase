# 🚀 Test Case Editor - Flet Version

Современная кроссплатформенная версия редактора тест-кейсов на Python + Flet.

## 📦 Две версии приложения

### 1️⃣ PyQt5 версия (test_case_editor.py)
- ✅ Полнофункциональная
- ✅ Drag & Drop
- ✅ Контекстные меню
- ✅ Древовидная структура папок
- ❌ Требует установки PyQt5 (большой размер)
- ❌ Только десктоп

### 2️⃣ Flet версия (test_case_editor_flet.py) ⭐ НОВАЯ
- ✅ Современный Material Design
- ✅ Кроссплатформенность (Web, Desktop, Mobile)
- ✅ Легкий вес
- ✅ Простая установка
- ⏳ В разработке: Drag & Drop, контекстные меню

## 🔧 Установка

### Для PyQt5 версии:
```bash
pip install PyQt5>=5.15.0
python test_case_editor.py
```

### Для Flet версии:
```bash
pip install flet>=0.21.0
python test_case_editor_flet.py
```

## 🎨 Особенности Flet версии

### ✨ Преимущества:
1. **Кроссплатформенность**
   - Запуск как десктоп-приложение
   - Запуск как веб-приложение
   - Возможность портирования на мобильные устройства

2. **Современный UI**
   - Material Design 3
   - Плавные анимации
   - Адаптивный интерфейс

3. **Простота разработки**
   - Декларативный подход
   - Горячая перезагрузка (hot reload)
   - Меньше кода

4. **Легкий вес**
   - Размер установки ~50 МБ (vs ~200 МБ для PyQt5)
   - Быстрый старт

### 🎯 Реализованные функции:

✅ **Базовый функционал:**
- Просмотр дерева тест-кейсов
- Открытие и редактирование
- Создание новых тест-кейсов
- Сохранение изменений
- Работа с папками
- Поиск

✅ **UI компоненты:**
- Двухпанельный интерфейс
- Дерево файлов и папок
- Форма редактирования
- Кнопка "Сохранить" (появляется при изменениях)
- Уведомления (snackbar)
- Telegram Dark Theme

⏳ **В разработке:**
- Drag & Drop для перемещения файлов
- Контекстные меню (ПКМ)
- Дублирование тест-кейсов
- Удаление файлов/папок
- Переименование
- Расширенные шаги тестирования

## 🚀 Запуск

### Десктоп приложение:
```bash
python test_case_editor_flet.py
```

### Веб-приложение:
```bash
flet run test_case_editor_flet.py --web
```

### С горячей перезагрузкой (для разработки):
```bash
flet run test_case_editor_flet.py --web --port 8080
```

## 📱 Режимы запуска

```python
# Десктоп (окно)
ft.app(target=app.main)

# Веб-сервер
ft.app(target=app.main, view=ft.AppView.WEB_BROWSER, port=8080)

# Полноэкранное приложение
ft.app(target=app.main, view=ft.AppView.FLET_APP)
```

## 🎨 Цветовая схема (Telegram Dark)

```python
Backgrounds:
- Primary:   #0E1621
- Surface:   #17212B
- Card:      #1E2732

Accents:
- Blue:      #5288C1
- Green:     #6CC24A
- Red:       #F5555D
- Orange:    #FFA931

Text:
- Primary:   #E1E3E6
- Secondary: #8B9099
- Disabled:  #6B7380
```

## 🔄 Миграция с PyQt5 на Flet

### Основные отличия:

| PyQt5 | Flet |
|-------|------|
| `QWidget` | `ft.Control` |
| `QVBoxLayout` | `ft.Column` |
| `QHBoxLayout` | `ft.Row` |
| `QPushButton` | `ft.ElevatedButton` |
| `QLineEdit` | `ft.TextField` |
| `QTreeWidget` | `ft.ListView` + `ft.ListTile` |
| `QComboBox` | `ft.Dropdown` |
| `QTextEdit` | `ft.TextField(multiline=True)` |

### Пример конвертации:

**PyQt5:**
```python
button = QPushButton("Click")
button.clicked.connect(self.on_click)
layout.addWidget(button)
```

**Flet:**
```python
button = ft.ElevatedButton(
    text="Click",
    on_click=lambda _: self.on_click()
)
column.controls.append(button)
```

## 📚 Документация

- [Flet Official Docs](https://flet.dev)
- [Flet Gallery](https://gallery.flet.dev)
- [Flet GitHub](https://github.com/flet-dev/flet)

## 🐛 Известные ограничения

1. **Drag & Drop** - В разработке (требует custom решения в Flet)
2. **Контекстные меню** - Упрощенная реализация (native контекстные меню ограничены)
3. **Горячие клавиши** - Базовая поддержка

## 🤝 Вклад

Обе версии поддерживаются:
- `test_case_editor.py` - стабильная, полнофункциональная
- `test_case_editor_flet.py` - современная, развивающаяся

## 📄 Лицензия

MIT License

## 🎯 Roadmap

### Версия 1.0 (Flet):
- [ ] Полноценное Drag & Drop
- [ ] Контекстные меню
- [ ] Все операции с файлами/папками
- [ ] Экспорт в различные форматы

### Версия 2.0 (Flet):
- [ ] Веб-интерфейс с аутентификацией
- [ ] Совместная работа (real-time)
- [ ] Интеграция с Jira/TestRail
- [ ] Мобильное приложение

---

**Выбирайте версию под свои нужды:**
- 🖥️ Нужен полный функционал? → PyQt5
- 🌐 Нужна кроссплатформенность? → Flet
- 🚀 Хотите современный UI? → Flet

