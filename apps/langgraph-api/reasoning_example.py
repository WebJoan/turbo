"""
Пример использования рассуждающего агента
"""
import asyncio
import json
from app.langgraph.reasoning_agent import reasoning_agent_graph

async def test_reasoning_agent():
    """Тестируем рассуждающий агент"""
    
    # Пример сложной задачи
    test_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": "Мне нужно найти микросхему STM32 от ST Microelectronics для проекта умного дома. Также хочу узнать текущую цену акций ST и сравнить с конкурентами."
                }
            ]
        }
    ]
    
    # Конвертируем в LangChain формат
    from app.add_langgraph_route import convert_to_langchain_messages
    langchain_messages = convert_to_langchain_messages(test_messages)
    
    # Конфигурация
    config = {
        "configurable": {
            "system": """
Ты эксперт по электронным компонентам и финансовым рынкам.
Помогаешь пользователям находить подходящие компоненты и анализировать рынок.
Всегда рассуждай пошагово и объясняй свои действия.
""",
            "frontend_tools": []
        }
    }
    
    print("🚀 Запуск рассуждающего агента...")
    print("=" * 60)
    
    step_count = 0
    async for chunk, metadata in reasoning_agent_graph.astream(
        {
            "messages": langchain_messages,
            "plan": [],
            "current_step": 0,
            "goal": "",
            "reasoning_history": [],
            "max_steps": 8
        },
        config,
        stream_mode="values"
    ):
        step_count += 1
        print(f"\n📍 ШАГ {step_count}")
        print("-" * 30)
        
        # Показываем план если он есть
        if chunk.get("plan"):
            print("🎯 ПЛАН:")
            for i, step in enumerate(chunk["plan"]):
                status = "✅" if i < chunk.get("current_step", 0) else "⏳"
                print(f"  {status} {step.step_number}. {step.description} ({step.action_type})")
        
        # Показываем последнее сообщение
        if chunk.get("messages"):
            last_message = chunk["messages"][-1]
            if hasattr(last_message, 'content'):
                content = last_message.content
                if content.strip():
                    print(f"\n💬 ОТВЕТ: {content[:300]}{'...' if len(content) > 300 else ''}")
        
        # Показываем историю рассуждений
        if chunk.get("reasoning_history"):
            print(f"\n🧠 ИСТОРИЯ РАССУЖДЕНИЙ ({len(chunk['reasoning_history'])} записей):")
            for reasoning in chunk["reasoning_history"][-2:]:  # Последние 2
                print(f"  • {reasoning}")
        
        print("-" * 30)
    
    print(f"\n🏁 Завершено за {step_count} шагов")


if __name__ == "__main__":
    # Запускаем тест
    asyncio.run(test_reasoning_agent())
