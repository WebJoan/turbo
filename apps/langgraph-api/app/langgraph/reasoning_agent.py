from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.errors import NodeInterrupt
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List, Literal
import os
from .tools import tools
from .state import AgentState, ReasoningState, PlanStep

# Загружаем переменные окружения
load_dotenv()

# Настраиваем модель для работы с OpenRouter
model = ChatOpenAI(
    model="google/gemini-2.5-flash",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_API_BASE_URL"),
    temperature=0.7,
)

# PlanStep и ReasoningState теперь импортируются из state.py


def should_continue_reasoning(state: ReasoningState):
    """Определяет следующий шаг в рассуждениях агента"""
    messages = state["messages"]
    current_step = state.get("current_step", 0)
    plan = state.get("plan", [])
    max_steps = state.get("max_steps", 10)
    
    # Если превысили лимит шагов
    if current_step >= max_steps:
        return "respond"
    
    # Если есть план и текущий шаг в рамках плана
    if plan and current_step < len(plan):
        current_action = plan[current_step]
        
        if current_action.action_type == "use_tool":
            return "tools"
        elif current_action.action_type == "think":
            return "think"
        else:
            return "respond"
    
    # Если последнее сообщение содержит tool_calls
    if messages and hasattr(messages[-1], 'tool_calls') and messages[-1].tool_calls:
        return "tools"
    
    # Если нет плана или план завершен
    if not plan or current_step >= len(plan):
        return "respond"
    
    return "think"


async def create_plan(state: ReasoningState, config):
    """Узел планирования - создает план действий для достижения цели"""
    messages = state["messages"]
    system = config["configurable"]["system"]
    
    # Добавляем специальный системный промпт для планирования
    planning_system_prompt = f"""
{system}

ЗАДАЧА ПЛАНИРОВАНИЯ:
Ты должен создать пошаговый план для ответа на вопрос пользователя.
Проанализируй вопрос и определи, какие шаги нужны для полного ответа.

Доступные типы действий:
1. "think" - обдумать, проанализировать информацию
2. "use_tool" - использовать инструмент (поиск, получение данных и т.д.)
3. "respond" - дать окончательный ответ пользователю

ВАЖНО: 
- Создай логическую последовательность шагов
- Не более 5-7 шагов
- Для каждого шага укажи цель и обоснование
- Начинай с анализа задачи ("think"), затем сбор данных ("use_tool"), потом ответ ("respond")

Формат ответа должен быть примерно таким:
"Анализирую задачу:
1. Сначала нужно понять что именно ищет пользователь
2. Затем использовать подходящий инструмент для поиска
3. Проанализировать результаты
4. Дать развернутый ответ

План:
Шаг 1: Анализ запроса (think)
Шаг 2: Поиск данных (use_tool: search_products_smart)
Шаг 3: Анализ результатов (think)
Шаг 4: Формирование ответа (respond)"
"""
    
    planning_messages = [SystemMessage(content=planning_system_prompt)] + messages
    
    response = await model.ainvoke(planning_messages)
    
    # Простой парсинг плана из ответа (можно улучшить с помощью structured output)
    plan_text = response.content
    
        # Создаем базовый план
    plan = []
    lines = plan_text.split('\n')
    step_num = 1
    
    for line in lines:
        line = line.strip()
        if 'шаг' in line.lower() and ':' in line:
            if 'анализ' in line.lower() or 'думать' in line.lower() or 'понять' in line.lower():
                plan.append(PlanStep(
                    step_number=step_num,
                    description=line,
                    action_type="think",
                    tool_name=None,
                    reasoning="Этап анализа и планирования"
                ))
            elif 'поиск' in line.lower() or 'tool' in line.lower() or 'инструмент' in line.lower():
                tool_name = "search_products_smart"  # по умолчанию, можно улучшить
                if 'stock' in line.lower() or 'акци' in line.lower():
                    tool_name = "get_stock_price"
                elif 'металл' in line.lower():
                    tool_name = "get_metal_price"
                elif 'интернет' in line.lower() or 'web' in line.lower():
                    tool_name = "search_duckduckgo"
                    
                plan.append(PlanStep(
                    step_number=step_num,
                    description=line,
                    action_type="use_tool",
                    tool_name=tool_name,
                    reasoning="Сбор необходимых данных"
                ))
            elif 'ответ' in line.lower() or 'respond' in line.lower():
                plan.append(PlanStep(
                    step_number=step_num,
                    description=line,
                    action_type="respond",
                    tool_name=None,
                    reasoning="Формирование финального ответа"
                ))
            step_num += 1
    
    # Если план не был создан, делаем базовый план
    if not plan:
        plan = [
            PlanStep(step_number=1, description="Анализ запроса", action_type="think", tool_name=None, reasoning=""),
            PlanStep(step_number=2, description="Поиск информации", action_type="use_tool", tool_name="search_products_smart", reasoning=""),
            PlanStep(step_number=3, description="Формирование ответа", action_type="respond", tool_name=None, reasoning="")
        ]
    
    # Сохраняем план и ответ планировщика в состояние
    return {
        "messages": [response],
        "plan": plan,
        "current_step": 0,
        "reasoning_history": [f"План создан: {len(plan)} шагов"]
    }


async def think_step(state: ReasoningState, config):
    """Узел размышлений - анализирует текущую ситуацию"""
    messages = state["messages"]
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    reasoning_history = state.get("reasoning_history", [])
    system = config["configurable"]["system"]
    
    if plan and current_step < len(plan):
        current_action = plan[current_step]
        
        thinking_prompt = f"""
{system}

ЗАДАЧА РАЗМЫШЛЕНИЯ:
Сейчас выполняется шаг {current_step + 1}: {current_action.description}

Предыдущие размышления:
{chr(10).join(reasoning_history)}

Проанализируй текущую ситуацию и подумай о следующих действиях.
Что мы уже знаем? Что нужно выяснить? Какой следующий шаг?

Формат размышлений:
"🤔 АНАЛИЗ СИТУАЦИИ:
- Что мне известно: ...
- Что нужно выяснить: ...
- Мой план действий: ...
- Ожидаемый результат: ..."
"""
    else:
        thinking_prompt = f"""
{system}

Проанализируй текущую ситуацию и подумай о том, как лучше ответить пользователю.
"""
    
    thinking_messages = [SystemMessage(content=thinking_prompt)] + messages
    
    response = await model.ainvoke(thinking_messages)
    
    # Обновляем историю размышлений
    new_reasoning = f"Шаг {current_step + 1}: {response.content[:200]}..."
    updated_reasoning_history = reasoning_history + [new_reasoning]
    
    return {
        "messages": [response],
        "current_step": current_step + 1,
        "reasoning_history": updated_reasoning_history
    }


async def call_model_with_reasoning(state: ReasoningState, config):
    """Вызов модели с учетом контекста рассуждений"""
    messages = state["messages"]
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    reasoning_history = state.get("reasoning_history", [])
    system = config["configurable"]["system"]
    
    # Создаем обогащенный контекст
    enhanced_system_prompt = f"""
{system}

КОНТЕКСТ РАССУЖДЕНИЙ:
План выполнения: {len(plan)} шагов
Текущий шаг: {current_step}
История размышлений:
{chr(10).join(reasoning_history[-3:])}  # Последние 3 размышления

Используй этот контекст для формирования более продуманного ответа.
"""
    
    enhanced_messages = [SystemMessage(content=enhanced_system_prompt)] + messages
    
    from .agent import get_tool_defs
    model_with_tools = model.bind_tools(get_tool_defs(config))
    response = await model_with_tools.ainvoke(enhanced_messages)
    
    return {
        "messages": [response],
        "current_step": current_step + 1
    }


async def run_tools_with_context(state: ReasoningState, config, **kwargs):
    """Выполнение инструментов с контекстом рассуждений"""
    from .agent import get_tools
    tool_node = ToolNode(get_tools(config))
    result = await tool_node.ainvoke(state, config, **kwargs)
    
    # Обновляем шаг после выполнения инструмента
    current_step = state.get("current_step", 0)
    reasoning_history = state.get("reasoning_history", [])
    
    # Добавляем информацию об использовании инструмента
    if result.get("messages"):
        tool_used = "инструмент использован"
        for msg in result["messages"]:
            if hasattr(msg, 'name'):
                tool_used = f"использован {msg.name}"
                break
        
        reasoning_entry = f"Шаг {current_step + 1}: {tool_used}"
        reasoning_history.append(reasoning_entry)
    
    return {
        **result,
        "current_step": current_step + 1,
        "reasoning_history": reasoning_history
    }


# Создаем граф рассуждающего агента
def create_reasoning_graph():
    workflow = StateGraph(ReasoningState)
    
    # Добавляем узлы
    workflow.add_node("planning", create_plan)           # Планирование
    workflow.add_node("think", think_step)           # Размышления
    workflow.add_node("agent", call_model_with_reasoning)  # Основной агент
    workflow.add_node("tools", run_tools_with_context)     # Инструменты
    
    # Настраиваем маршруты
    workflow.set_entry_point("planning")  # Начинаем с планирования
    
    # От планирования к размышлениям
    workflow.add_edge("planning", "think")
    
    # От размышлений к агенту
    workflow.add_edge("think", "agent")
    
    # От агента - условная логика
    workflow.add_conditional_edges(
        "agent",
        should_continue_reasoning,
        {
            "tools": "tools",
            "think": "think", 
            "respond": END
        }
    )
    
    # От инструментов обратно к размышлениям
    workflow.add_edge("tools", "think")
    
    return workflow.compile()


# Создаем рассуждающий граф
reasoning_agent_graph = create_reasoning_graph()
