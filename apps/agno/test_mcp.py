#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы MCP сервера WordStat.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_mcp_server():
    """Тестирует работу MCP сервера WordStat."""
    print("🧪 Запуск тестирования MCP сервера WordStat...")
    print()
    
    # Проверяем наличие токена
    wordstat_token = os.getenv("WORDSTAT_API_TOKEN") or os.getenv("WORDSTAT_TOKEN")
    if not wordstat_token:
        print("❌ ОШИБКА: Токен WordStat не найден в переменных окружения!")
        print("   Проверьте наличие WORDSTAT_API_TOKEN или WORDSTAT_TOKEN в .env файле")
        return False
    
    print(f"✅ Токен WordStat найден: {wordstat_token[:10]}...")
    print()
    
    # Тестируем импорт модулей
    try:
        from app.wordstat_mcp import get_top_requests
        print("✅ Модуль wordstat_mcp успешно импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта wordstat_mcp: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Тестируем вызов функции get_top_requests
    print()
    print("🔍 Тестируем вызов get_top_requests('купить припой', 10)...")
    try:
        result = await get_top_requests("купить припой", num_phrases=10)
        print("✅ Вызов успешен!")
        print(f"   Результат: {result.get('message', 'N/A')}")
        print(f"   Успех: {result.get('success', False)}")
        if result.get('success'):
            print(f"   Всего запросов: {result.get('total_count', 0)}")
            print(f"   Топ запросов: {result.get('top_requests_count', 0)}")
        else:
            print(f"   Ошибка: {result.get('error', 'N/A')}")
        return result.get('success', False)
    except Exception as e:
        print(f"❌ Ошибка при вызове get_top_requests: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mcp_server())
    print()
    if success:
        print("✅ Все тесты пройдены!")
        sys.exit(0)
    else:
        print("❌ Тесты не пройдены!")
        sys.exit(1)


