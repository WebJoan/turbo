# Агент для работы с WordStat API через MCP сервер
from agno.agent.agent import Agent
from agno.models.openrouter import OpenRouter
from agno.tools.mcp import MCPTools
from ag_ui.core import EventType, StateDeltaEvent, AssistantMessage
import uuid
import asyncio
import json
from typing import Dict, Any
from dotenv import load_dotenv
import os
import subprocess
import sys

# Загружаем переменные окружения
load_dotenv()

class WordStatAgent:
    """
    Агент для анализа поисковых запросов через WordStat API Яндекса.
    Использует MCP сервер для получения данных о поисковых запросах.
    """

    def __init__(self):
        self.mcp_tools = None
        self.agent = None
        self._initialize()
    
    def _initialize(self):
        """Синхронная инициализация с последующим асинхронным подключением MCP"""
        # Инициализация модели OpenRouter
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "sk-or-v1-")
        openrouter_base_url = os.getenv("OPENROUTER_API_BASE_URL", "https://openrouter.ai/api/v1")
        
        print("🔧 Инициализация WordStat агента...", file=sys.stderr)
        print(f"   OpenRouter API Key: {openrouter_api_key[:20]}...", file=sys.stderr)

        # Создаем инструменты MCP для WordStat
        # В Docker контейнере рабочая директория /code
        # Используем абсолютный путь для надежности
        mcp_command = "python /code/run_wordstat_mcp.py" if os.path.exists("/code") else "python run_wordstat_mcp.py"
        print(f"   MCP команда: {mcp_command}", file=sys.stderr)
        
        # Получаем токен WordStat из переменных окружения
        wordstat_token = os.getenv("WORDSTAT_API_TOKEN") or os.getenv("WORDSTAT_TOKEN", "")
        if wordstat_token:
            print(f"   WordStat токен: {wordstat_token[:20]}...", file=sys.stderr)
        else:
            print(f"   ⚠️ WordStat токен не найден!", file=sys.stderr)
        
        print("   Создаем MCP Tools...", file=sys.stderr)
        print(f"   Рабочая директория: {os.getcwd()}", file=sys.stderr)
        print(f"   /code существует: {os.path.exists('/code')}", file=sys.stderr)
        print(f"   run_wordstat_mcp.py существует: {os.path.exists('/code/run_wordstat_mcp.py')}", file=sys.stderr)
        
        # Тестируем запуск MCP скрипта напрямую
        print("   🧪 Тестирую запуск MCP скрипта...", file=sys.stderr)
        try:
            test_result = subprocess.run(
                ["python", "/code/run_wordstat_mcp.py"],
                capture_output=True,
                text=True,
                timeout=2,
                env={**os.environ, "WORDSTAT_TOKEN": wordstat_token}
            )
            print(f"   MCP скрипт stdout: {test_result.stdout[:200]}", file=sys.stderr)
            print(f"   MCP скрипт stderr: {test_result.stderr[:200]}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print("   ⏱️ MCP скрипт запущен (timeout - это нормально, он ждет ввода)", file=sys.stderr)
        except Exception as e:
            print(f"   ⚠️ Ошибка тестового запуска: {e}", file=sys.stderr)
        
        try:
            print("   Создаем MCPTools объект...", file=sys.stderr)
            self.mcp_tools = MCPTools(
                command=mcp_command,
                env={"WORDSTAT_API_TOKEN": wordstat_token, "WORDSTAT_TOKEN": wordstat_token}
            )
            print("   ✅ MCP Tools созданы", file=sys.stderr)
            
            # КРИТИЧНО: Подключаемся к MCP серверу
            print("   🔌 Подключаемся к MCP серверу...", file=sys.stderr)
            try:
                # Создаем новый event loop для синхронного контекста
                import asyncio
                try:
                    # Пробуем получить текущий loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Если loop уже работает, создаем задачу
                        print("   ⚠️ Event loop уже работает, используем create_task", file=sys.stderr)
                        # Подключение произойдет позже
                    else:
                        # Loop не работает, можем использовать run_until_complete
                        loop.run_until_complete(self.mcp_tools.connect())
                        print("   ✅ Подключение к MCP серверу установлено", file=sys.stderr)
                except RuntimeError:
                    # Нет текущего loop, создаем новый
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(self.mcp_tools.connect())
                    new_loop.close()
                    print("   ✅ Подключение к MCP серверу установлено (новый loop)", file=sys.stderr)
            except Exception as connect_error:
                print(f"   ⚠️ Ошибка подключения к MCP: {connect_error}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                # Продолжаем, возможно подключение установится позже
            
            # Проверяем все атрибуты MCPTools
            print(f"   🔍 Атрибуты MCPTools: {[a for a in dir(self.mcp_tools) if not a.startswith('_')]}", file=sys.stderr)
            
            # Проверяем, что инструменты загрузились
            if hasattr(self.mcp_tools, 'tools'):
                tools_list = self.mcp_tools.tools
                print(f"   📋 mcp_tools.tools тип: {type(tools_list)}", file=sys.stderr)
                print(f"   📋 Загружено инструментов: {len(tools_list) if tools_list else 0}", file=sys.stderr)
                if tools_list:
                    for tool in tools_list:
                        tool_name = tool.get('name', 'unknown') if isinstance(tool, dict) else getattr(tool, 'name', 'unknown')
                        print(f"      - {tool_name}", file=sys.stderr)
                else:
                    print("   ⚠️ mcp_tools.tools пустой или None", file=sys.stderr)
            else:
                print("   ⚠️ У MCPTools нет атрибута 'tools'", file=sys.stderr)
                
            # Проверяем другие возможные атрибуты
            for attr in ['get_tools', 'functions', 'list_tools', '_tools']:
                if hasattr(self.mcp_tools, attr):
                    print(f"   🔍 Найден атрибут: {attr}", file=sys.stderr)
                    
        except Exception as e:
            print(f"   ❌ Ошибка создания MCP Tools: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            raise

        # Создаем агента с инструментами WordStat
        print("   Создаем агента Agno...", file=sys.stderr)
        self.agent = Agent(
            model=OpenRouter(
                id="gpt-4o-mini",
                api_key=openrouter_api_key,
                base_url=openrouter_base_url
            ),
            tools=[self.mcp_tools],
            instructions=self._get_system_prompt(),
            markdown=True,
            show_tool_calls=True,
        )
        print("   ✅ Агент создан", file=sys.stderr)
        
        # Проверяем, что агент видит инструменты
        if hasattr(self.agent, 'tools') and self.agent.tools:
            print(f"   🔧 Агент видит {len(self.agent.tools)} инструментов", file=sys.stderr)
        else:
            print(f"   ⚠️ Агент не видит инструменты!", file=sys.stderr)

        self.system_prompt = self._get_system_prompt()
        print("✅ WordStat агент полностью инициализирован", file=sys.stderr)
    
    async def async_connect_mcp(self):
        """
        Асинхронное подключение к MCP серверу.
        Вызывается после создания агента в асинхронном контексте.
        """
        if self.mcp_tools and hasattr(self.mcp_tools, 'connect'):
            try:
                print("🔌 Асинхронное подключение к MCP...", file=sys.stderr)
                await self.mcp_tools.connect()
                print("✅ MCP подключен асинхронно", file=sys.stderr)
                
                # Проверяем инструменты после подключения
                if hasattr(self.mcp_tools, 'tools'):
                    tools_count = len(self.mcp_tools.tools) if self.mcp_tools.tools else 0
                    print(f"📋 После async connect: {tools_count} инструментов", file=sys.stderr)
                    if self.mcp_tools.tools:
                        for tool in self.mcp_tools.tools:
                            tool_name = tool.get('name', 'unknown') if isinstance(tool, dict) else getattr(tool, 'name', 'unknown')
                            print(f"   - {tool_name}", file=sys.stderr)
                return True
            except Exception as e:
                print(f"⚠️ Ошибка async подключения к MCP: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                return False
        return False

    def _get_system_prompt(self) -> str:
        return """
Ты — эксперт по анализу поисковых запросов Яндекса через WordStat API.

**КРИТИЧНО ВАЖНО - РЕЖИМ РАБОТЫ:**
- НИКОГДА не пиши текстовые сообщения типа "Дайте мне минуту", "Начинаю анализ" и т.п. ПЕРЕД вызовом инструментов
- СРАЗУ вызывай инструменты БЕЗ ТЕКСТОВОГО ОТВЕТА, а потом анализируй результаты
- НЕ ОБЪЯСНЯЙ что ты собираешься делать - ПРОСТО ДЕЛАЙ это через инструменты
- Текстовый ответ давай ТОЛЬКО ПОСЛЕ получения результатов от инструментов

**Доступные инструменты WordStat API:**

1. **get_top_requests(phrase, num_phrases, regions, devices)** - топ популярных запросов по фразе
2. **get_dynamics(phrase, period, from_date, to_date, regions, devices)** - динамика запросов во времени  
3. **get_regions_distribution(phrase, region_type, devices)** - распределение по регионам
4. **get_regions_tree()** - дерево регионов для фильтрации
5. **get_user_info()** - лимиты и квота API

**Алгоритм работы:**

1. Пользователь пишет "Проверь запрос купить припой" → ты СРАЗУ (без текста) вызываешь get_top_requests("купить припой")
2. Получаешь результат → анализируешь и даешь подробный ответ
3. Если нужна динамика → вызываешь get_dynamics() и добавляешь анализ

**Примеры ПРАВИЛЬНОГО поведения:**

❌ НЕПРАВИЛЬНО:
Пользователь: "Проверь запрос купить припой"
Ты: "Начинаю анализ популярности запроса 'купить припой'..." ← НЕ ТАК!

✅ ПРАВИЛЬНО:
Пользователь: "Проверь запрос купить припой"  
Ты: [СРАЗУ вызываешь get_top_requests("купить припой", 50)] → получаешь результат → пишешь анализ

**Правила ответов:**
- Используй только русский язык
- После получения данных давай структурированный анализ с цифрами и выводами
- Если запрос не требует уточнений - сразу анализируй с дефолтными параметрами
- Не спрашивай подтверждения - действуй!

**Параметры по умолчанию:**
- num_phrases: 50
- regions: все регионы России
- devices: ["all"]
- period для динамики: "monthly"
"""

    async def process_query(self, step_input):
        """
        Обрабатывает запрос пользователя и возвращает ответ агента.

        Args:
            step_input: Объект с данными запроса

        Returns:
            dict: Обновленные данные с ответом агента
        """
        # Пытаемся подключиться к MCP асинхронно при первом запросе
        if self.mcp_tools and hasattr(self.mcp_tools, 'tools'):
            if not self.mcp_tools.tools or len(self.mcp_tools.tools) == 0:
                print("⚠️ Инструменты не загружены, пытаемся подключиться...", file=sys.stderr)
                await self.async_connect_mcp()
        
        try:
            # Логирование начала обработки
            tool_log_id = str(uuid.uuid4())
            step_input.additional_data['tool_logs'].append({
                "message": "Анализирую запрос с помощью WordStat API...",
                "status": "processing",
                "id": tool_log_id,
            })

            # Обновление UI
            step_input.additional_data["emit_event"](
                StateDeltaEvent(
                    type=EventType.STATE_DELTA,
                    delta=[{
                        "op": "add",
                        "path": "/tool_logs/-",
                        "value": {
                            "message": "Анализирую запрос с помощью WordStat API...",
                            "status": "processing",
                            "id": tool_log_id,
                        },
                    }],
                )
            )
            await asyncio.sleep(0)

            # Извлекаем сообщение пользователя
            user_message = ""
            messages = step_input.additional_data.get('messages', [])
            print(f"DEBUG: Получено {len(messages)} сообщений")

            for msg in reversed(messages):
                print(f"DEBUG: Проверяем сообщение: {type(msg)}, role: {getattr(msg, 'role', 'no role')}, content: {getattr(msg, 'content', 'no content')[:50] if hasattr(msg, 'content') else 'no content attr'}")
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    if msg.role == "user" and msg.content:
                        user_message = msg.content
                        print(f"DEBUG: Найдено пользовательское сообщение: {user_message}")
                        break
                elif isinstance(msg, dict) and msg.get('role') == 'user' and msg.get('content'):
                    user_message = msg['content']
                    print(f"DEBUG: Найдено пользовательское сообщение (dict): {user_message}")
                    break

            # Если сообщение не найдено, используем общее сообщение
            if not user_message:
                user_message = "Проанализируй популярные поисковые запросы"
                print(f"DEBUG: Сообщение не найдено, используем по умолчанию: {user_message}")

            # Вызываем агента Agno с стримингом
            response_content = ""
            tool_calls_started = set()

            # Создаем очередь для передачи событий из синхронного потока
            event_queue = asyncio.Queue()

            def process_stream():
                nonlocal response_content
                print(f"🤖 WordStat агент: обрабатываю запрос: '{user_message}'", file=sys.stderr)
                try:
                    response_stream = self.agent.run(user_message, stream=True)
                    print(f"✅ Поток ответов от агента создан", file=sys.stderr)
                except Exception as e:
                    print(f"❌ Ошибка при создании потока: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc()
                    event_queue.put_nowait({"type": "done"})
                    return

                chunk_count = 0
                for chunk in response_stream:
                    chunk_count += 1
                    if chunk_count % 10 == 0:
                        print(f"📦 Обработано {chunk_count} чанков", file=sys.stderr)
                    if hasattr(chunk, 'event') and chunk.event:
                        # Обрабатываем события от агента (tool calls, etc.)
                        event = chunk.event

                        if hasattr(event, 'type'):
                            if event.type == 'tool_call_start' and hasattr(event, 'tool_call'):
                                tool_call = event.tool_call
                                if hasattr(tool_call, 'id') and tool_call.id not in tool_calls_started:
                                    tool_calls_started.add(tool_call.id)
                                    tool_name = getattr(tool_call, 'name', 'неизвестный инструмент')
                                    
                                    print(f"🔧 Вызываю инструмент: {tool_name}", file=sys.stderr)
                                    if hasattr(tool_call, 'arguments'):
                                        print(f"   Аргументы: {tool_call.arguments}", file=sys.stderr)

                                    # Добавляем лог о вызове инструмента
                                    tool_log_id = str(uuid.uuid4())
                                    step_input.additional_data['tool_logs'].append({
                                        "message": f"Выполняю инструмент: {tool_name}",
                                        "status": "processing",
                                        "id": tool_log_id,
                                    })

                                    # Отправляем событие в очередь
                                    event_queue.put_nowait({
                                        "type": "tool_start",
                                        "tool_log_id": tool_log_id,
                                        "message": f"Выполняю инструмент: {tool_name}"
                                    })

                            elif event.type == 'tool_call_end' and hasattr(event, 'tool_call'):
                                tool_call = event.tool_call
                                if hasattr(tool_call, 'id'):
                                    tool_name = getattr(tool_call, 'name', 'неизвестный инструмент')
                                    print(f"✅ Инструмент {tool_name} завершен", file=sys.stderr)
                                    if hasattr(tool_call, 'result'):
                                        result_preview = str(tool_call.result)[:200] if tool_call.result else 'Нет результата'
                                        print(f"   Результат: {result_preview}", file=sys.stderr)
                                    
                                    # Отправляем событие о завершении
                                    event_queue.put_nowait({
                                        "type": "tool_end",
                                        "tool_id": tool_call.id
                                    })

                    # Собираем текстовый контент
                    if hasattr(chunk, 'content') and chunk.content:
                        response_content += chunk.content

                # Сигнализируем о завершении
                print(f"✅ Обработка завершена. Всего чанков: {chunk_count}, длина ответа: {len(response_content)}", file=sys.stderr)
                event_queue.put_nowait({"type": "done"})

            # Запускаем обработку в фоне
            print(f"🚀 Запускаем фоновую задачу обработки потока", file=sys.stderr)
            stream_task = asyncio.create_task(asyncio.to_thread(process_stream))
            print(f"✅ Фоновая задача создана", file=sys.stderr)

            # Обрабатываем события из очереди
            print(f"🔄 Начинаем обработку событий из очереди", file=sys.stderr)
            event_count = 0
            while not stream_task.done() or not event_queue.empty():
                try:
                    event_data = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    event_count += 1
                    print(f"📨 Получено событие #{event_count}: {event_data.get('type', 'unknown')}", file=sys.stderr)

                    if event_data["type"] == "tool_start":
                        step_input.additional_data["emit_event"](
                            StateDeltaEvent(
                                type=EventType.STATE_DELTA,
                                delta=[{
                                    "op": "add",
                                    "path": "/tool_logs/-",
                                    "value": {
                                        "message": event_data["message"],
                                        "status": "processing",
                                        "id": event_data["tool_log_id"],
                                    },
                                }],
                            )
                        )

                    elif event_data["type"] == "tool_end":
                        # Обновляем статус завершения инструмента
                        for i, log in enumerate(step_input.additional_data['tool_logs']):
                            if log.get('id') == event_data["tool_id"]:
                                step_input.additional_data["emit_event"](
                                    StateDeltaEvent(
                                        type=EventType.STATE_DELTA,
                                        delta=[{
                                            "op": "replace",
                                            "path": f"/tool_logs/{i}/status",
                                            "value": "completed",
                                        }],
                                    )
                                )
                                break

                    elif event_data["type"] == "done":
                        break

                except asyncio.TimeoutError:
                    # Проверяем статус задачи
                    if stream_task.done():
                        try:
                            result = stream_task.result()
                            print(f"✅ Задача завершена успешно", file=sys.stderr)
                        except Exception as e:
                            print(f"❌ Задача завершена с ошибкой: {e}", file=sys.stderr)
                            import traceback
                            traceback.print_exc()
                    continue

            # Обновляем статус основного логирования
            print(f"🏁 Обработка событий завершена. Всего событий: {event_count}", file=sys.stderr)
            index = len(step_input.additional_data['tool_logs']) - 1
            if index >= 0:
                step_input.additional_data["emit_event"](
                    StateDeltaEvent(
                        type=EventType.STATE_DELTA,
                        delta=[{
                            "op": "replace",
                            "path": f"/tool_logs/{index}/status",
                            "value": "completed",
                        }],
                    )
                )
                await asyncio.sleep(0)

            if not response_content:
                response_content = "Извините, произошла ошибка при получении ответа."
                print(f"⚠️ Ответ пустой, используем дефолтное сообщение", file=sys.stderr)
            else:
                print(f"✅ Ответ получен, длина: {len(response_content)} символов", file=sys.stderr)

            assistant_message = AssistantMessage(
                id=str(uuid.uuid4()),
                content=response_content,
                role="assistant",
            )

            step_input.additional_data["messages"].append(assistant_message)
            print(f"✅ Сообщение добавлено в историю, возвращаем результат", file=sys.stderr)
            return step_input.additional_data

        except Exception as e:
            print(f"Ошибка в WordStat агенте: {e}")

            # Обновляем статус на ошибку
            if 'tool_logs' in step_input.additional_data and step_input.additional_data['tool_logs']:
                index = len(step_input.additional_data['tool_logs']) - 1
                step_input.additional_data["emit_event"](
                    StateDeltaEvent(
                        type=EventType.STATE_DELTA,
                        delta=[{
                            "op": "replace",
                            "path": f"/tool_logs/{index}/status",
                            "value": "error",
                        }],
                    )
                )

            # Создаем сообщение об ошибке
            error_message = AssistantMessage(
                id=str(uuid.uuid4()),
                content="Извините, произошла ошибка при работе с WordStat API. Пожалуйста, попробуйте еще раз.",
                role="assistant",
            )

            step_input.additional_data["messages"].append(error_message)
            return step_input.additional_data

# Создаем экземпляр агента
wordstat_agent = WordStatAgent()

# Функция для интеграции с существующей системой
async def wordstat_chat_handler(step_input):
    """
    Обработчик чата для WordStat агента.

    Args:
        step_input: Входные данные с сообщениями пользователя

    Returns:
        Обновленные данные с ответом агента
    """
    return await wordstat_agent.process_query(step_input)

# Пример использования
if __name__ == "__main__":
    print("🔍 WordStat Агент готов к работе!")
    print("Этот агент поможет вам анализировать поисковые запросы Яндекса")
    print("Доступные возможности:")
    print("- Анализ популярности запросов")
    print("- Динамика запросов во времени")
    print("- Географическое распределение")
    print("- Информация о лимитах API")
