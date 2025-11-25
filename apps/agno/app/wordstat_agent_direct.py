# Агент для работы с WordStat API через прямые вызовы (без MCP)
from agno.agent.agent import Agent
from agno.models.openrouter import OpenRouter
from ag_ui.core import EventType, StateDeltaEvent, AssistantMessage
import uuid
import asyncio
import sys
from typing import Dict, Any
from dotenv import load_dotenv
import os
import requests

# Загружаем переменные окружения
load_dotenv()

# Базовый URL API
WORDSTAT_BASE_URL = "https://api.wordstat.yandex.net/v1"
WORDSTAT_TOKEN = os.getenv("WORDSTAT_API_TOKEN") or os.getenv("WORDSTAT_TOKEN")

def get_top_requests_direct(phrase: str, num_phrases: int = 50) -> str:
    """
    Получить топ популярных запросов, содержащих указанную фразу в Яндекс WordStat.
    
    Args:
        phrase: Фраза для поиска популярных запросов, например 'купить припой'
        num_phrases: Количество фраз в ответе (максимум 2000, по умолчанию 50)
    
    Returns:
        JSON строка с результатами анализа популярности запроса
    """
    print(f"🔧 Прямой вызов get_top_requests_direct: phrase={phrase}, num_phrases={num_phrases}", file=sys.stderr)
    
    if not WORDSTAT_TOKEN:
        import json
        return json.dumps({
            "success": False,
            "error": "WORDSTAT_TOKEN не найден",
            "message": "Токен API не настроен"
        }, ensure_ascii=False)
    
    url = f"{WORDSTAT_BASE_URL}/topRequests"
    headers = {
        "Content-Type": "application/json;charset=utf-8",
        "Authorization": f"Bearer {WORDSTAT_TOKEN}"
    }
    
    payload = {"phrase": phrase.strip()}
    if num_phrases and num_phrases != 50:
        payload["numPhrases"] = num_phrases
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ Получен ответ от API: {len(result.get('topRequests', []))} запросов", file=sys.stderr)
        
        # Форматируем результат для агента
        top_requests = result.get("topRequests", [])
        analysis = f"Анализ запроса '{phrase}':\n\n"
        analysis += f"Всего найдено запросов: {result.get('totalCount', 0)}\n\n"
        analysis += "Топ-10 популярных запросов:\n"
        
        for i, req in enumerate(top_requests[:10], 1):
            req_text = req.get("phrase", "")
            req_count = req.get("count", 0)
            analysis += f"{i}. {req_text} (показов: {req_count})\n"
        
        # Возвращаем как JSON строку для агента
        import json
        return json.dumps({
            "success": True,
            "phrase": phrase,
            "total_count": result.get("totalCount", 0),
            "top_requests_count": len(top_requests),
            "top_10": top_requests[:10],
            "analysis": analysis
        }, ensure_ascii=False)
        
    except Exception as e:
        print(f"❌ Ошибка вызова API: {e}", file=sys.stderr)
        import json
        return json.dumps({
            "success": False,
            "error": str(e),
            "phrase": phrase,
            "message": "Не удалось получить топ запросов"
        }, ensure_ascii=False)

class WordStatAgentDirect:
    """
    Агент с прямыми вызовами API (без MCP).
    """
    
    def __init__(self):
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "sk-or-v1-")
        openrouter_base_url = os.getenv("OPENROUTER_API_BASE_URL", "https://openrouter.ai/api/v1")
        
        print("🔧 Инициализация WordStat агента (Direct Mode)...", file=sys.stderr)
        
        # Создаем агента с функцией напрямую (не как dict, а как callable)
        self.agent = Agent(
            model=OpenRouter(
                id="gpt-4o-mini",
                api_key=openrouter_api_key,
                base_url=openrouter_base_url
            ),
            tools=[get_top_requests_direct],  # Передаем саму функцию!
            instructions="""
Ты — эксперт по анализу поисковых запросов Яндекса через WordStat API.

ВАЖНО: Когда пользователь просит проверить или проанализировать запрос, СРАЗУ используй функцию get_top_requests_direct.

Не пиши текстовые сообщения перед вызовом функции - СРАЗУ вызывай get_top_requests_direct.

После получения результатов от функции, дай подробный анализ с цифрами.
""",
            markdown=True,
            show_tool_calls=True,
        )
        
        print("✅ WordStat агент (Direct Mode) инициализирован", file=sys.stderr)
    
    async def process_query(self, step_input):
        """
        Обрабатывает запрос пользователя.
        """
        try:
            # Извлекаем сообщение пользователя
            user_message = ""
            messages = step_input.additional_data.get('messages', [])
            
            for msg in reversed(messages):
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    if msg.role == "user" and msg.content:
                        user_message = msg.content
                        break
                elif isinstance(msg, dict) and msg.get('role') == 'user' and msg.get('content'):
                    user_message = msg['content']
                    break
            
            if not user_message:
                user_message = "Проанализируй популярные поисковые запросы"
            
            print(f"🤖 WordStat агент (Direct): обрабатываю запрос: '{user_message}'", file=sys.stderr)
            
            # Вызываем агента - он сам вызовет функцию get_top_requests_direct
            response_content = ""
            response_stream = self.agent.run(user_message, stream=True)
            
            for chunk in response_stream:
                # Собираем текстовый контент
                if hasattr(chunk, 'content') and chunk.content:
                    response_content += chunk.content
            
            print(f"✅ Ответ получен, длина: {len(response_content)} символов", file=sys.stderr)
            
            if not response_content:
                response_content = "Извините, произошла ошибка при получении ответа."
            
            assistant_message = AssistantMessage(
                id=str(uuid.uuid4()),
                content=response_content,
                role="assistant",
            )
            
            step_input.additional_data["messages"].append(assistant_message)
            return step_input.additional_data
            
        except Exception as e:
            print(f"❌ Ошибка в WordStat агенте (Direct): {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            
            error_message = AssistantMessage(
                id=str(uuid.uuid4()),
                content="Извините, произошла ошибка при работе с WordStat API.",
                role="assistant",
            )
            
            step_input.additional_data["messages"].append(error_message)
            return step_input.additional_data

# Создаем экземпляр агента
wordstat_agent_direct = WordStatAgentDirect()

