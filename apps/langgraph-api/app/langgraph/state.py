from typing import Annotated, List
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


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


class ReasoningState(TypedDict, total=False):  # total=False позволяет опциональные поля
    messages: Annotated[list, add_messages]
    plan: List[PlanStep]
    current_step: int
    goal: str
    reasoning_history: List[str]
    max_steps: int
