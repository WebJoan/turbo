# Агент поддержки электронных компонентов для компании Ruelectronics
from agno.agent.agent import Agent  # Core agent functionality
from agno.models.openrouter import OpenRouter  # OpenRouter model integration
from ag_ui.core import EventType, StateDeltaEvent  # Event handling for UI updates
from ag_ui.core import AssistantMessage, ToolMessage  # Message types for chat interface
import uuid  # For generating unique identifiers
import asyncio  # For asynchronous operations
import requests  # For HTTP requests to OpenRouter API
from dotenv import load_dotenv  # For loading environment variables
import os  # Operating system interface
import json  # JSON data handling
from .prompts import support_prompt  # Промпт для агента поддержки Ruelectronics

# Загружаем переменные окружения
load_dotenv()


# ПРОСТОЙ АГЕНТ ДЛЯ ПОДДЕРЖКИ ЭЛЕКТРОННЫХ КОМПОНЕНТОВ
# Заменяет сложный stock анализатор на простого чат-агента для поддержки Ruelectronics
class ElectronicsSupportAgent:
    """
    Простой агент поддержки для компании Ruelectronics.
    Помогает пользователям с вопросами по заказам, доставке, оплате, 
    гарантии, возвратам, наличию и характеристикам товаров.
    """
    
    def __init__(self):
        # Инициализация модели OpenRouter
        # Используем ваш API ключ из переменных окружения
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "sk-or-v1-")
        openrouter_base_url = os.getenv("OPENROUTER_API_BASE_URL", "https://openrouter.ai/api/v1")
        
        # Создаем агента с OpenRouter моделью
        self.agent = Agent(
            model=OpenRouter(
                id="gpt-4o-mini",  # Эффективная и доступная модель
                api_key=openrouter_api_key,
                base_url=openrouter_base_url
            ),
            instructions=support_prompt,
            markdown=True,
            show_tool_calls=True,
        )
        
        self.system_prompt = support_prompt
    
    async def process_query(self, step_input):
        """
        Обрабатывает запрос пользователя и возвращает ответ агента поддержки.
        
        Args:
            step_input: Объект с данными запроса, включая сообщения пользователя
            
        Returns:
            dict: Обновленные данные с ответом агента
        """
        try:
            # Шаг 1: Логирование начала обработки запроса
            tool_log_id = str(uuid.uuid4())
            step_input.additional_data['tool_logs'].append({
                "message": "Анализирую ваш запрос с помощью OpenRouter...",
                "status": "processing",
                "id": tool_log_id,
            })
            
            # Шаг 2: Обновление UI о начале обработки
            step_input.additional_data["emit_event"](
                StateDeltaEvent(
                    type=EventType.STATE_DELTA,
                    delta=[
                        {
                            "op": "add",
                            "path": "/tool_logs/-",
                            "value": {
                                "message": "Анализирую ваш запрос с помощью OpenRouter...",
                                "status": "processing",
                                "id": tool_log_id,
                            },
                        }
                    ],
                )
            )
            await asyncio.sleep(0)
            
            # Шаг 3: Извлекаем последнее сообщение пользователя
            user_message = "Привет! Как дела?"  # Дефолтное сообщение
            
            for msg in reversed(step_input.additional_data.get('messages', [])):
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    if msg.role == "user" and msg.content:
                        user_message = msg.content
                        break
                elif isinstance(msg, dict) and msg.get('role') == 'user' and msg.get('content'):
                    user_message = msg['content']
                    break
            
            # Спец-логика: если пользователь спрашивает "кто я" — отвечаем его именем
            normalized = (user_message or "").strip().lower()
            whoami_triggers = [
                "кто я",
                "как меня зовут",
                "мое имя",
                "моё имя",
                "кто со мной разговаривает",
                "ты знаешь кто я",
            ]
            if any(trigger in normalized for trigger in whoami_triggers):
                user = step_input.additional_data.get('user') if isinstance(step_input.additional_data, dict) else None
                if user and (user.get('username') or user.get('first_name') or user.get('last_name')):
                    full_name = None
                    first_name = user.get('first_name')
                    last_name = user.get('last_name')
                    if first_name or last_name:
                        full_name = f"{first_name or ''} {last_name or ''}".strip()
                    answer_name = full_name or user.get('username')
                    response_content = f"Вы — {answer_name}. Рад помочь!"
                    assistant_message = AssistantMessage(
                        id=str(uuid.uuid4()),
                        content=response_content,
                        role="assistant",
                    )
                    step_input.additional_data["messages"].append(assistant_message)
                    # Завершаем ранний ответ без вызова LLM
                    return step_input.additional_data

            # Шаг 4: Вызов агента Agno с OpenRouter
            response = self.agent.run(user_message, stream=False)
            
            # Шаг 5: Обновление статуса логирования
            index = len(step_input.additional_data['tool_logs']) - 1
            step_input.additional_data["emit_event"](
                StateDeltaEvent(
                    type=EventType.STATE_DELTA,
                    delta=[
                        {
                            "op": "replace",
                            "path": f"/tool_logs/{index}/status",
                            "value": "completed",
                        }
                    ],
                )
            )
            await asyncio.sleep(0)
            
            # Шаг 6: Создание ответного сообщения из ответа Agno
            response_content = ""
            
            # Извлекаем контент из ответа агента
            if hasattr(response, 'content') and response.content:
                response_content = response.content
            elif hasattr(response, 'messages') and response.messages:
                # Ищем последнее сообщение ассистента
                for msg in reversed(response.messages):
                    if hasattr(msg, 'role') and msg.role == 'assistant' and hasattr(msg, 'content'):
                        response_content = msg.content
                        break
            
            # Если контент все еще пустой, используем строковое представление
            if not response_content:
                response_content = str(response) if response else "Извините, произошла ошибка при получении ответа."
            
            assistant_message = AssistantMessage(
                id=str(uuid.uuid4()),
                content=response_content,
                role="assistant",
            )
            
            step_input.additional_data["messages"].append(assistant_message)
            
            # Шаг 7: Возврат обновленных данных
            return step_input.additional_data
            
        except Exception as e:
            # Обработка ошибок
            print(f"Ошибка в агенте поддержки: {e}")
            
            # Обновляем статус логирования на ошибку
            if 'tool_logs' in step_input.additional_data and step_input.additional_data['tool_logs']:
                index = len(step_input.additional_data['tool_logs']) - 1
                step_input.additional_data["emit_event"](
                    StateDeltaEvent(
                        type=EventType.STATE_DELTA,
                        delta=[
                            {
                                "op": "replace",
                                "path": f"/tool_logs/{index}/status",
                                "value": "error",
                            }
                        ],
                    )
                )
            
            # Создаем сообщение об ошибке
            error_message = AssistantMessage(
                id=str(uuid.uuid4()),
                content="Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз или обратитесь к оператору.",
                role="assistant",
            )
            
            step_input.additional_data["messages"].append(error_message)
            return step_input.additional_data


# Создаем экземпляр агента поддержки
electronics_support_agent = ElectronicsSupportAgent()


# ФУНКЦИЯ ДЛЯ ИНТЕГРАЦИИ С СУЩЕСТВУЮЩЕЙ СИСТЕМОЙ
async def support_chat_handler(step_input):
    """
    Обработчик чата для агента поддержки электронных компонентов.
    Эта функция заменяет сложный stock анализатор.
    
    Args:
        step_input: Входные данные с сообщениями пользователя
        
    Returns:
        Обновленные данные с ответом агента
    """
    return await electronics_support_agent.process_query(step_input)


# ПРИМЕР ИСПОЛЬЗОВАНИЯ
if __name__ == "__main__":
    print("🤖 Агент поддержки электронных компонентов Ruelectronics готов к работе!")
    print("Этот агент поможет вам с:")
    print("- Вопросами по заказам")
    print("- Доставкой и оплатой") 
    print("- Гарантией и возвратами")
    print("- Наличием и характеристиками товаров")
    print("- Общей поддержкой клиентов")
