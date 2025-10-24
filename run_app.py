"""
Скрипт для выбора и запуска версии приложения
"""
import sys
import subprocess


def main():
    print("=" * 60)
    print("✈️  Test Case Editor - Выбор версии")
    print("=" * 60)
    print()
    print("Выберите версию для запуска:")
    print()
    print("1. PyQt5 версия (полнофункциональная, десктоп)")
    print("2. Flet версия (современная, кроссплатформенная)")
    print("3. Flet веб-версия (запуск в браузере)")
    print()
    print("0. Выход")
    print()
    
    choice = input("Введите номер (1-3): ").strip()
    
    if choice == "1":
        print("\n🚀 Запуск PyQt5 версии...")
        print("-" * 60)
        try:
            subprocess.run([sys.executable, "test_case_editor.py"])
        except FileNotFoundError:
            print("❌ Файл test_case_editor.py не найден!")
        except Exception as e:
            print(f"❌ Ошибка запуска: {e}")
    
    elif choice == "2":
        print("\n🚀 Запуск Flet десктоп версии...")
        print("-" * 60)
        try:
            subprocess.run([sys.executable, "test_case_editor_flet.py"])
        except FileNotFoundError:
            print("❌ Файл test_case_editor_flet.py не найден!")
        except Exception as e:
            print(f"❌ Ошибка запуска: {e}")
    
    elif choice == "3":
        print("\n🌐 Запуск Flet веб-версии...")
        print("-" * 60)
        print("📱 Приложение откроется в браузере на http://localhost:8080")
        print()
        try:
            subprocess.run([
                "flet", "run", "test_case_editor_flet.py", 
                "--web", "--port", "8080"
            ])
        except FileNotFoundError:
            print("❌ Команда 'flet' не найдена! Установите: pip install flet")
        except Exception as e:
            print(f"❌ Ошибка запуска: {e}")
    
    elif choice == "0":
        print("\n👋 До свидания!")
        return
    
    else:
        print("\n❌ Неверный выбор!")
        return
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()

