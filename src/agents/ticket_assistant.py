from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import (
    RunnableConfig,
    RunnableLambda,
    RunnableSerializable,
)
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.managed import RemainingSteps
from langgraph.prebuilt import ToolNode

from agents.safeguard import (
    Safeguard,
    SafeguardOutput,
    SafetyAssessment,
)
from agents.ticket_tools import (
    customer_tickets,
    device_repair_history,
)
from core import get_model, settings


class AgentState(MessagesState, total=False):
    """Ticket Agent 使用的 LangGraph State。"""

    safety: SafeguardOutput
    remaining_steps: RemainingSteps


tools = [
    customer_tickets,
    device_repair_history,
]


instructions = """
You are AcmeTech's support ticket assistant.

Your job is to answer questions about customer tickets, devices, and repair
history by using the available tools.

Important rules:
- Use Customer_Tickets for questions about a customer's devices or tickets.
- Use Device_Repair_History for questions about a device's previous problems,
  diagnoses, repair actions, technicians, or repair count.
- Do not invent customer IDs, serial numbers, ticket data, or repair data.
- If a required customer ID or serial number is missing, ask the user for it.
- Base business-specific answers only on tool results.
- The user cannot see raw tool responses, so explain the result clearly.
"""


def wrap_model(
    model: BaseChatModel,
) -> RunnableSerializable[AgentState, AIMessage]:
    """把系统提示词和 Ticket Tools 绑定到模型。"""
    bound_model = model.bind_tools(tools)

    preprocessor = RunnableLambda(
        lambda state: [
            SystemMessage(content=instructions),
            *state["messages"],
        ],
        name="StateModifier",
    )

    return preprocessor | bound_model  # type: ignore[return-value]


def format_safety_message(
    safety: SafeguardOutput,
) -> AIMessage:
    """把安全检查结果转换成 AIMessage。"""
    categories = ", ".join(safety.unsafe_categories)

    return AIMessage(content=(f"This conversation was flagged for unsafe content: {categories}"))


async def acall_model(
    state: AgentState,
    config: RunnableConfig,
) -> AgentState:
    """调用模型，并把模型响应追加到 messages。"""
    model_name = config["configurable"].get(
        "model",
        settings.DEFAULT_MODEL,
    )
    model = get_model(model_name)
    model_runnable = wrap_model(model)

    response = await model_runnable.ainvoke(state, config)

    if state["remaining_steps"] < 2 and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content=(
                        "Sorry, there are not enough remaining steps to execute another tool."
                    ),
                )
            ]
        }

    return {"messages": [response]}


async def safeguard_input(
    state: AgentState,
    config: RunnableConfig,
) -> AgentState:
    """检查用户输入是否安全。"""
    safeguard = Safeguard()
    safety_output = await safeguard.ainvoke(state["messages"])

    return {
        "safety": safety_output,
        "messages": [],
    }


async def block_unsafe_content(
    state: AgentState,
    config: RunnableConfig,
) -> AgentState:
    """阻止不安全输入继续进入模型节点。"""
    safety = state["safety"]

    return {
        "messages": [
            format_safety_message(safety),
        ]
    }


def check_safety(
    state: AgentState,
) -> Literal["unsafe", "safe"]:
    """根据安全检查结果选择下一节点。"""
    safety = state["safety"]

    if safety.safety_assessment is SafetyAssessment.UNSAFE:
        return "unsafe"

    return "safe"


def pending_tool_calls(
    state: AgentState,
) -> Literal["tools", "done"]:
    """检查最后一条 AIMessage 是否包含工具调用。"""
    last_message = state["messages"][-1]

    if not isinstance(last_message, AIMessage):
        raise TypeError(f"Expected AIMessage, got {type(last_message)}")

    if last_message.tool_calls:
        return "tools"

    return "done"


builder = StateGraph(AgentState)

builder.add_node("guard_input", safeguard_input)
builder.add_node("block_unsafe_content", block_unsafe_content)
builder.add_node("model", acall_model)
builder.add_node("tools", ToolNode(tools))

builder.set_entry_point("guard_input")

builder.add_conditional_edges(
    "guard_input",
    check_safety,
    {
        "unsafe": "block_unsafe_content",
        "safe": "model",
    },
)

builder.add_edge("block_unsafe_content", END)
builder.add_edge("tools", "model")

builder.add_conditional_edges(
    "model",
    pending_tool_calls,
    {
        "tools": "tools",
        "done": END,
    },
)

ticket_assistant = builder.compile()
