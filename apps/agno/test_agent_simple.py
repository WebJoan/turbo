#!/usr/bin/env python3
"""
Простой тест агента с MCP инструментами.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Устанавливаем переменные окружения, если их нет
if not os.getenv("WORDSTAT_TOKEN") and not os.getenv("WORDSTAT_API_TOKEN"):
    print("❌ Токен WordStat не найден!")
    sys.exit(1)

print("🧪 Тест 1: Проверка импорта модулей")
try:
    from agno.agent.agent import Agent
    from agno.models.openrouter import OpenRouter
    from agno.tools.mcp import MCPTools
    print("✅ Модули импортированы успешно")
except Exception as e:
    print(f"❌ Ошибка импорта: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🧪 Тест 2: Создание MCP Tools")
try:
    mcp_command = "python /code/run_wordstat_mcp.py" if os.path.exists("/code") else "python run_wordstat_mcp.py"
    print(f"   Команда: {mcp_command}")
    
    wordstat_token = os.getenv("WORDSTAT_API_TOKEN") or os.getenv("WORDSTAT_TOKEN", "")
    print(f"   Токен: {wordstat_token[:20]}...")
    
    mcp_tools = MCPTools(
        command=mcp_command,
        env={"WORDSTAT_API_TOKEN": wordstat_token, "WORDSTAT_TOKEN": wordstat_token}
    )
    print("✅ MCP Tools созданы")
    
    # Проверяем атрибуты
    print(f"   Атрибуты MCP Tools: {dir(mcp_tools)}")
    
    if hasattr(mcp_tools, 'tools'):
        print(f"   📋 Инструменты: {mcp_tools.tools}")
    
except Exception as e:
    print(f"❌ Ошибка создания MCP Tools: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🧪 Тест 3: Создание агента")
try:
    agent = Agent(
        model=OpenRouter(
            id="gpt-4o-mini",
            api_key=os.getenv("OPENROUTER_API_KEY", "sk-or-v1-"),
            base_url=os.getenv("OPENROUTER_API_BASE_URL", "https://openrouter.ai/api/v1")
        ),
        tools=[mcp_tools],
        instructions="Ты помощник для анализа поисковых запросов.",
        markdown=True,
        show_tool_calls=True,
    )
    print("✅ Агент создан")
    
    # Проверяем инструменты агента
    if hasattr(agent, 'tools'):
        print(f"   🔧 Инструментов в агенте: {len(agent.tools) if agent.tools else 0}")
        if agent.tools:
            print(f"   📋 Инструменты агента: {agent.tools}")
    
except Exception as e:
    print(f"❌ Ошибка создания агента: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🧪 Тест 4: Простой запрос (без инструментов)")
try:
    response = agent.run("Привет!")
    print(f"✅ Ответ получен: {response.content[:100] if hasattr(response, 'content') else str(response)[:100]}")
except Exception as e:
    print(f"❌ Ошибка запроса: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🧪 Тест 5: Запрос с использованием инструмента")
try:
    response = agent.run("Проверь запрос 'купить припой'")
    print(f"✅ Ответ получен")
    if hasattr(response, 'content'):
        print(f"   Содержимое: {response.content[:200]}")
    else:
        print(f"   Ответ: {str(response)[:200]}")
except Exception as e:
    print(f"❌ Ошибка запроса с инструментом: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ Все тесты завершены!")


