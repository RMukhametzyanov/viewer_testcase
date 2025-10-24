"""
Редактор тест-кейсов на Flet (вместо PyQt5)
Telegram Dark Theme
"""
import json
import os
import sys
import uuid
import copy
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import flet as ft


class TestCaseEditorApp:
    """Главное приложение редактора тест-кейсов на Flet"""
    
    def __init__(self):
        self.test_cases: List[Dict] = []
        self.current_test_case: Optional[Dict] = None
        self.test_cases_dir = Path("test_cases")
        self.has_unsaved_changes = False
        self.tree_nodes = {}  # Кэш узлов дерева для быстрого доступа
        
        # UI компоненты (будут созданы позже)
        self.page = None
        self.tree_view = None
        self.search_field = None
        self.file_count_label = None
        self.save_button = None
        self.testcase_title_label = None
        
        # Поля формы
        self.id_input = None
        self.title_input = None
        self.author_input = None
        self.status_dropdown = None
        self.level_dropdown = None
        self.use_case_id_input = None
        self.tags_input = None
        self.precondition_input = None
        self.actions_table = None
    
    def main(self, page: ft.Page):
        """Главная функция приложения"""
        self.page = page
        page.title = "✈️ Test Case Editor"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 0
        page.bgcolor = "#0E1621"
        
        # Кастомная тема Telegram Dark
        page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary="#5288C1",
                background="#0E1621",
                surface="#17212B",
                on_surface="#E1E3E6",
            )
        )
        
        # Создаем layout
        self.create_ui()
        
        # Загружаем тест-кейсы
        self.load_test_cases()
    
    def create_ui(self):
        """Создание пользовательского интерфейса"""
        # Левая панель - дерево тест-кейсов
        left_panel = self.create_left_panel()
        
        # Правая панель - форма редактирования
        right_panel = self.create_right_panel()
        
        # Основной layout с разделителем
        content = ft.Row(
            controls=[
                ft.Container(
                    content=left_panel,
                    width=400,
                    bgcolor="#17212B",
                    padding=0,
                ),
                ft.VerticalDivider(width=1, color="#2B3945"),
                ft.Container(
                    content=right_panel,
                    expand=True,
                    bgcolor="#17212B",
                    padding=0,
                ),
            ],
            spacing=0,
            expand=True,
        )
        
        self.page.add(content)
    
    def create_left_panel(self):
        """Создание левой панели с деревом"""
        # Заголовок
        self.file_count_label = ft.Text("(0)", color="#8B9099", size=12)
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text("📁 Файлы тест-кейсов", size=14, weight=ft.FontWeight.BOLD, color="#E1E3E6"),
                    self.file_count_label,
                ],
                spacing=5,
            ),
            padding=ft.padding.all(10),
            bgcolor="#1E2732",
        )
        
        # Поиск
        self.search_field = ft.TextField(
            label="🔍 Поиск...",
            border_color="#2B3945",
            focused_border_color="#5288C1",
            on_change=self.filter_tree,
            height=50,
            text_size=12,
        )
        
        search_container = ft.Container(
            content=self.search_field,
            padding=ft.padding.only(left=10, right=10, bottom=10),
        )
        
        # Дерево тест-кейсов
        self.tree_view = ft.ListView(
            spacing=2,
            padding=10,
            expand=True,
        )
        
        return ft.Column(
            controls=[
                header,
                search_container,
                self.tree_view,
            ],
            spacing=0,
            expand=True,
        )
    
    def create_right_panel(self):
        """Создание правой панели с формой"""
        # Заголовок с кнопкой сохранить
        self.testcase_title_label = ft.Text(
            "Не выбран тест-кейс",
            size=18,
            weight=ft.FontWeight.BOLD,
            color="#5288C1",
        )
        
        self.save_button = ft.ElevatedButton(
            text="💾 Сохранить",
            on_click=lambda _: self.save_current_test_case(),
            bgcolor="#2B5278",
            color="#FFFFFF",
            visible=False,
            height=40,
        )
        
        header = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Редактирование тест-кейса", size=12, color="#8B9099"),
                    ft.Row(
                        controls=[
                            self.testcase_title_label,
                            self.save_button,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=5,
            ),
            padding=15,
            bgcolor="#1E2732",
            border=ft.border.only(bottom=ft.BorderSide(2, "#2B3945")),
        )
        
        # Форма
        form = self.create_form()
        
        return ft.Column(
            controls=[
                header,
                ft.Container(
                    content=form,
                    expand=True,
                    padding=15,
                ),
            ],
            spacing=0,
            expand=True,
        )
    
    def create_form(self):
        """Создание формы редактирования"""
        # ID (только для чтения)
        self.id_input = ft.TextField(
            label="ID",
            read_only=True,
            hint_text="Генерируется автоматически",
            border_color="#2B3945",
            height=50,
            text_size=11,
        )
        
        # Название
        self.title_input = ft.TextField(
            label="Название",
            border_color="#2B3945",
            focused_border_color="#5288C1",
            on_change=lambda _: self.mark_as_changed(),
            height=50,
        )
        
        # Автор
        self.author_input = ft.TextField(
            label="Автор",
            border_color="#2B3945",
            focused_border_color="#5288C1",
            on_change=lambda _: self.mark_as_changed(),
            height=50,
        )
        
        # Статус
        self.status_dropdown = ft.Dropdown(
            label="Статус",
            options=[
                ft.dropdown.Option("Draft"),
                ft.dropdown.Option("In Progress"),
                ft.dropdown.Option("Done"),
                ft.dropdown.Option("Blocked"),
                ft.dropdown.Option("Deprecated"),
            ],
            border_color="#2B3945",
            focused_border_color="#5288C1",
            on_change=lambda _: self.mark_as_changed(),
        )
        
        # Уровень
        self.level_dropdown = ft.Dropdown(
            label="Уровень",
            options=[
                ft.dropdown.Option("smoke"),
                ft.dropdown.Option("critical"),
                ft.dropdown.Option("major"),
                ft.dropdown.Option("minor"),
                ft.dropdown.Option("trivial"),
            ],
            border_color="#2B3945",
            focused_border_color="#5288C1",
            on_change=lambda _: self.mark_as_changed(),
        )
        
        # Use Case ID
        self.use_case_id_input = ft.TextField(
            label="Use Case ID",
            read_only=True,
            border_color="#2B3945",
            height=50,
            text_size=11,
        )
        
        # Теги
        self.tags_input = ft.TextField(
            label="Теги (каждый с новой строки)",
            multiline=True,
            min_lines=3,
            max_lines=5,
            border_color="#2B3945",
            focused_border_color="#5288C1",
            on_change=lambda _: self.mark_as_changed(),
        )
        
        # Предусловия
        self.precondition_input = ft.TextField(
            label="Предусловия",
            multiline=True,
            min_lines=3,
            max_lines=5,
            border_color="#2B3945",
            focused_border_color="#5288C1",
            on_change=lambda _: self.mark_as_changed(),
        )
        
        # Шаги тестирования (упрощенная версия)
        self.actions_table = ft.Column(
            spacing=5,
            scroll=ft.ScrollMode.AUTO,
        )
        
        actions_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Шаги тестирования", size=14, weight=ft.FontWeight.BOLD, color="#5288C1"),
                    self.actions_table,
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                text="➕ Добавить шаг",
                                on_click=lambda _: self.add_action_row(),
                                bgcolor="#2B5278",
                                color="#FFFFFF",
                            ),
                        ],
                    ),
                ],
                spacing=10,
            ),
            border=ft.border.all(1, "#2B3945"),
            border_radius=8,
            padding=10,
        )
        
        # Скроллящаяся форма
        form_content = ft.ListView(
            controls=[
                ft.Text("Основная информация", size=14, weight=ft.FontWeight.BOLD, color="#5288C1"),
                ft.Row(controls=[self.id_input, self.title_input], spacing=10),
                ft.Row(controls=[self.author_input, self.status_dropdown], spacing=10),
                ft.Row(controls=[self.level_dropdown, self.use_case_id_input], spacing=10),
                self.tags_input,
                self.precondition_input,
                actions_container,
            ],
            spacing=15,
            expand=True,
        )
        
        return form_content
    
    def load_test_cases(self):
        """Загрузка всех тест-кейсов"""
        self.test_cases = []
        self.tree_view.controls.clear()
        self.tree_nodes.clear()
        
        if not self.test_cases_dir.exists():
            return
        
        # Загружаем рекурсивно
        self.load_directory_recursive(self.test_cases_dir, self.tree_view.controls)
        
        # Обновляем счетчик
        self.file_count_label.value = f"({len(self.test_cases)})"
        self.page.update()
    
    def load_directory_recursive(self, directory: Path, parent_controls: list):
        """Рекурсивная загрузка директории"""
        # Папки
        subdirs = sorted([d for d in directory.iterdir() if d.is_dir()])
        for subdir in subdirs:
            folder_tile = self.create_folder_tile(subdir)
            parent_controls.append(folder_tile)
            self.tree_nodes[str(subdir)] = folder_tile
        
        # Файлы
        json_files = sorted(list(directory.glob("*.json")))
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    test_case = json.load(f)
                    test_case['_filename'] = json_file.name
                    test_case['_filepath'] = json_file
                    self.test_cases.append(test_case)
                    
                    file_tile = self.create_file_tile(test_case)
                    parent_controls.append(file_tile)
                    self.tree_nodes[str(json_file)] = file_tile
            except Exception as e:
                print(f"Ошибка загрузки {json_file}: {e}")
    
    def create_folder_tile(self, folder_path: Path):
        """Создание элемента папки"""
        folder_name = folder_path.name
        
        tile = ft.ListTile(
            leading=ft.Icon(ft.Icons.FOLDER, color="#FFA931", size=20),
            title=ft.Text(folder_name, size=12, weight=ft.FontWeight.BOLD, color="#E1E3E6"),
            on_click=lambda _: None,
            on_long_press=lambda e: self.show_folder_context_menu(e, folder_path),
            hover_color="#1E2732",
            selected_color="#2B5278",
            data={"type": "folder", "path": folder_path},
        )
        
        return tile
    
    def create_file_tile(self, test_case: Dict):
        """Создание элемента файла"""
        status = test_case.get('status', 'Draft')
        status_icon = self.get_status_icon(status)
        status_color = self.get_status_color(status)
        title = test_case.get('title', 'Без названия')
        
        tile = ft.ListTile(
            leading=ft.Text(status_icon, size=16, color=status_color),
            title=ft.Text(title, size=12, color="#E1E3E6"),
            on_click=lambda _: self.open_test_case(test_case),
            on_long_press=lambda e: self.show_file_context_menu(e, test_case),
            hover_color="#1E2732",
            selected_color="#2B5278",
            data={"type": "file", "test_case": test_case},
        )
        
        return tile
    
    def get_status_icon(self, status: str) -> str:
        """Иконка статуса"""
        icons = {
            'Done': '✓',
            'Blocked': '⚠',
            'In Progress': '⟳',
            'Draft': '○',
            'Deprecated': '×'
        }
        return icons.get(status, '○')
    
    def get_status_color(self, status: str) -> str:
        """Цвет статуса"""
        colors = {
            'Done': '#6CC24A',
            'Blocked': '#F5555D',
            'In Progress': '#FFA931',
            'Draft': '#8B9099',
            'Deprecated': '#6B7380'
        }
        return colors.get(status, '#8B9099')
    
    def open_test_case(self, test_case: Dict):
        """Открыть тест-кейс для редактирования"""
        self.current_test_case = test_case
        self.load_test_case_to_form(test_case)
    
    def load_test_case_to_form(self, test_case: Dict):
        """Загрузка тест-кейса в форму"""
        self.has_unsaved_changes = False
        self.save_button.visible = False
        
        # Заголовок
        title = test_case.get('title', 'Без названия')
        self.testcase_title_label.value = title
        
        # Поля
        self.id_input.value = test_case.get('id', '')
        self.title_input.value = test_case.get('title', '')
        self.author_input.value = test_case.get('author', '')
        self.status_dropdown.value = test_case.get('status', 'Draft')
        self.level_dropdown.value = test_case.get('level', 'minor')
        self.use_case_id_input.value = test_case.get('useCaseId', '')
        
        # Теги
        tags = test_case.get('tags', [])
        self.tags_input.value = '\n'.join(tags)
        
        # Предусловия
        self.precondition_input.value = test_case.get('precondition', '')
        
        # Шаги
        self.actions_table.controls.clear()
        for i, action in enumerate(test_case.get('actions', [])):
            self.add_action_row(action.get('step', ''), action.get('expected_res', ''))
        
        self.page.update()
    
    def add_action_row(self, step_text: str = "", expected_res: str = ""):
        """Добавить строку шага"""
        row_index = len(self.actions_table.controls)
        
        step_field = ft.TextField(
            label=f"Шаг {row_index + 1}",
            value=step_text,
            multiline=True,
            min_lines=2,
            border_color="#2B3945",
            on_change=lambda _: self.mark_as_changed(),
        )
        
        expected_field = ft.TextField(
            label="Ожидаемый результат",
            value=expected_res,
            multiline=True,
            min_lines=2,
            border_color="#2B3945",
            on_change=lambda _: self.mark_as_changed(),
        )
        
        remove_btn = ft.IconButton(
            icon=ft.Icons.DELETE,
            icon_color="#F5555D",
            on_click=lambda _: self.remove_action_row(row_index),
            tooltip="Удалить шаг",
        )
        
        row = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(controls=[step_field, expected_field], expand=True, spacing=5),
                    remove_btn,
                ],
                spacing=10,
            ),
            border=ft.border.all(1, "#2B3945"),
            border_radius=8,
            padding=10,
            data={"step": step_field, "expected": expected_field},
        )
        
        self.actions_table.controls.append(row)
        self.page.update()
    
    def remove_action_row(self, index: int):
        """Удалить строку шага"""
        if 0 <= index < len(self.actions_table.controls):
            self.actions_table.controls.pop(index)
            self.mark_as_changed()
            self.page.update()
    
    def mark_as_changed(self):
        """Отметить форму как измененную"""
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            self.save_button.visible = True
            self.page.update()
    
    def mark_as_saved(self):
        """Отметить форму как сохраненную"""
        self.has_unsaved_changes = False
        self.save_button.visible = False
        self.page.update()
    
    def get_form_data(self) -> Dict:
        """Получить данные из формы"""
        # Шаги
        actions = []
        for row in self.actions_table.controls:
            step_field = row.data["step"]
            expected_field = row.data["expected"]
            actions.append({
                'step': step_field.value or "",
                'expected_res': expected_field.value or ""
            })
        
        # Теги
        tags_text = self.tags_input.value or ""
        tags = [tag.strip() for tag in tags_text.split('\n') if tag.strip()]
        
        return {
            'id': self.id_input.value or "",
            'title': self.title_input.value or "",
            'author': self.author_input.value or "",
            'tags': tags,
            'status': self.status_dropdown.value or "Draft",
            'useCaseId': self.use_case_id_input.value or "",
            'level': self.level_dropdown.value or "minor",
            'precondition': self.precondition_input.value or "",
            'actions': actions
        }
    
    def save_current_test_case(self):
        """Сохранить текущий тест-кейс"""
        if not self.current_test_case:
            self.show_snackbar("Не выбран тест-кейс для сохранения", error=True)
            return
        
        data = self.get_form_data()
        
        if not data['title']:
            self.show_snackbar("Название тест-кейса обязательно", error=True)
            return
        
        # Путь к файлу
        if '_filepath' in self.current_test_case:
            filepath = self.current_test_case['_filepath']
        else:
            filename = self.current_test_case.get('_filename', f"tc_{data['id'][:8]}.json")
            filepath = self.test_cases_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            self.mark_as_saved()
            self.load_test_cases()
            self.show_snackbar(f"Сохранено: {Path(filepath).name}")
        except Exception as e:
            self.show_snackbar(f"Ошибка сохранения: {e}", error=True)
    
    def create_new_test_case(self, target_folder=None):
        """Создать новый тест-кейс"""
        if target_folder is None:
            target_folder = self.test_cases_dir
        
        new_id = str(uuid.uuid4())
        filename = f'tc_new_{uuid.uuid4().hex[:8]}.json'
        
        new_test_case = {
            'id': new_id,
            'title': 'Новый тест-кейс',
            'author': '',
            'tags': [],
            'status': 'Draft',
            'useCaseId': '',
            'level': 'minor',
            'precondition': '',
            'actions': [],
            '_filename': filename,
            '_filepath': target_folder / filename
        }
        
        try:
            filepath = target_folder / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({k: v for k, v in new_test_case.items() if not k.startswith('_')}, 
                         f, ensure_ascii=False, indent=4)
            
            self.load_test_cases()
            self.current_test_case = new_test_case
            self.load_test_case_to_form(new_test_case)
            self.show_snackbar(f"Создан: {filename}")
        except Exception as e:
            self.show_snackbar(f"Ошибка создания: {e}", error=True)
    
    def filter_tree(self, e):
        """Фильтрация дерева по поиску"""
        search_text = self.search_field.value.lower() if self.search_field.value else ""
        
        # Пока просто показываем/скрываем элементы
        # TODO: Реализовать полноценную фильтрацию
        self.page.update()
    
    def show_folder_context_menu(self, e, folder_path: Path):
        """Контекстное меню для папки"""
        # TODO: Реализовать контекстное меню
        pass
    
    def show_file_context_menu(self, e, test_case: Dict):
        """Контекстное меню для файла"""
        # TODO: Реализовать контекстное меню
        pass
    
    def show_snackbar(self, message: str, error: bool = False):
        """Показать уведомление"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color="#FFFFFF"),
            bgcolor="#F5555D" if error else "#2B5278",
        )
        self.page.snack_bar.open = True
        self.page.update()


def main():
    """Точка входа"""
    app = TestCaseEditorApp()
    ft.app(target=app.main)


if __name__ == '__main__':
    main()

