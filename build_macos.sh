#!/bin/bash

# Скрипт для создания дистрибутива приложения Test Case Editor для MacOS
# Этот скрипт создает .app bundle, который можно запускать двойным кликом

set -e  # Остановка при ошибке

echo "🚀 Начало сборки дистрибутива для MacOS..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 не найден. Установите Python3 и повторите попытку.${NC}"
    exit 1
fi

# Проверка наличия PyInstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  PyInstaller не установлен. Устанавливаю...${NC}"
    pip3 install pyinstaller
fi

# Очистка предыдущих сборок
echo -e "${YELLOW}🧹 Очистка предыдущих сборок...${NC}"
rm -rf build dist *.spec __pycache__

# Создание .spec файла если его нет
if [ ! -f "app.spec" ]; then
    echo -e "${YELLOW}📝 Создание файла конфигурации app.spec...${NC}"
    python3 -m PyInstaller --name "Test Case Editor" \
        --windowed \
        --onedir \
        --icon=NONE \
        --add-data "icons:icons" \
        --hidden-import PyQt5.QtSvg \
        --hidden-import PyQt5.QtCore \
        --hidden-import PyQt5.QtGui \
        --hidden-import PyQt5.QtWidgets \
        run_app.py
    # Переименовываем созданный spec файл
    mv "Test Case Editor.spec" app.spec 2>/dev/null || true
fi

# Сборка приложения
echo -e "${GREEN}🔨 Сборка приложения...${NC}"
python3 -m PyInstaller app.spec --clean

# Проверка результата
if [ -d "dist/Test Case Editor.app" ]; then
    echo -e "${GREEN}✅ Сборка успешно завершена!${NC}"
    echo -e "${GREEN}📦 Дистрибутив находится в: $(pwd)/dist/Test Case Editor.app${NC}"
    echo ""
    echo -e "${YELLOW}💡 Для запуска приложения:${NC}"
    echo -e "   open 'dist/Test Case Editor.app'"
    echo ""
    echo -e "${YELLOW}💡 Для создания DMG архива (опционально):${NC}"
    echo -e "   hdiutil create -volname 'Test Case Editor' -srcfolder 'dist/Test Case Editor.app' -ov -format UDZO 'dist/Test Case Editor.dmg'"
else
    echo -e "${RED}❌ Ошибка при сборке. Проверьте логи выше.${NC}"
    exit 1
fi

