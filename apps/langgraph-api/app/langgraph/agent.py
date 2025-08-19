from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langgraph.errors import NodeInterrupt
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from .tools import tools
from .state import AgentState

# Загружаем переменные окружения
load_dotenv()

# Настраиваем модель для работы с OpenRouter
model = ChatOpenAI(
    #model="google/gemini-2.5-flash",  # openai/gpt-oss-120b Можете выбрать любую доступную модель
    model="google/gemini-2.5-pro",
    #model="openai/gpt-4o-mini",
    #model="deepseek/deepseek-chat-v3-0324",
    #№model="qwen/qwen3-235b-a22b-thinking-2507",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_API_BASE_URL"),
    temperature=0.5,
)


def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        return END
    else:
        return "tools"


class AnyArgsSchema(BaseModel):
    # By not defining any fields and allowing extras,
    # this schema will accept any input passed in.
    class Config:
        extra = "allow"


class FrontendTool(BaseTool):
    def __init__(self, name: str):
        super().__init__(name=name, description="", args_schema=AnyArgsSchema)

    def _run(self, *args, **kwargs):
        # Since this is a frontend-only tool, it might not actually execute anything.
        # Raise an interrupt or handle accordingly.
        raise NodeInterrupt("This is a frontend tool call")

    async def _arun(self, *args, **kwargs) -> str:
        # Similarly handle async calls
        raise NodeInterrupt("This is a frontend tool call")


def get_tool_defs(config):
    frontend_tools = [
        {"type": "function", "function": tool}
        for tool in config["configurable"]["frontend_tools"]
    ]
    return tools + frontend_tools


def get_tools(config):
    frontend_tools = [
        FrontendTool(tool.name) for tool in config["configurable"]["frontend_tools"]
    ]
    return tools + frontend_tools


async def call_model(state, config):
    system_prompt = config["configurable"]["system"]
    
    # Если есть информация о пользователе, добавляем её в системный промпт
    user_info = state.get("user")
    if user_info:
        user_context = f"\n\nВАЖНО: Сейчас ты общаешься с пользователем ID={user_info.user_id}"
        if user_info.username:
            user_context += f" (username: {user_info.username})"
        user_context += ". Запомни это для всего разговора. Можешь обращаться к пользователю персонально если это уместно."
        system_prompt += user_context
        
        print(f"🤖 ИИ получил информацию о пользователе: ID={user_info.user_id}")

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    model_with_tools = model.bind_tools(get_tool_defs(config))
    response = await model_with_tools.ainvoke(messages)
    # We return a list, because this will get added to the existing list
    return {"messages": response}


async def run_tools(input, config, **kwargs):
    tool_node = ToolNode(get_tools(config))
    return await tool_node.ainvoke(input, config, **kwargs)


# Define a new graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", run_tools)

workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    ["tools", END],
)

workflow.add_edge("tools", "agent")

assistant_ui_graph = workflow.compile()
