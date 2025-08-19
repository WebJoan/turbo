from typing import Annotated, List, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing import Literal


class PlanStep(BaseModel):
    step_number: int
    description: str
    action_type: Literal["think", "use_tool", "respond"]
    tool_name: str = None
    reasoning: str = ""


class UserInfo(BaseModel):
    """Информация о текущем пользователе"""
    user_id: int
    username: Optional[str] = None


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user: Optional[UserInfo]  # Информация о текущем пользователе


class ReasoningState(TypedDict, total=False):  # total=False позволяет опциональные поля
    messages: Annotated[list, add_messages]
    user: Optional[UserInfo]  # Информация о текущем пользователе
    plan: List[PlanStep]
    current_step: int
    goal: str
    reasoning_history: List[str]
    max_steps: int
