from collections.abc import AsyncIterable
from typing import Any

from schema import ChatMessage


async def collect_actual_result(
    events: AsyncIterable[ChatMessage | str],
) -> dict[str, Any]:
    """Collect one no-tool or single-tool Agent execution for evaluation."""
    actual: dict[str, Any] = {
        "tool_name": None,
        "tool_arguments": {},
        "tool_content": "",
        "answer": "",
    }

    async for event in events:
        if isinstance(event, str):
            continue

        if event.type == "tool":
            actual["tool_content"] = event.content
            continue

        if event.type != "ai":
            continue

        if event.tool_calls:
            if len(event.tool_calls) != 1 or actual["tool_name"] is not None:
                raise ValueError("Only one tool call is supported in the first evaluator version")

            tool_call = event.tool_calls[0]
            actual["tool_name"] = tool_call["name"]
            actual["tool_arguments"] = tool_call["args"]
            continue

        if event.content:
            actual["answer"] = event.content

    return actual
