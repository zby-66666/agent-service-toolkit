from collections.abc import AsyncGenerator

import pytest

from evals.collector import collect_actual_result
from schema import ChatMessage


@pytest.mark.asyncio
async def test_collect_actual_result_from_single_tool_stream():
    async def events() -> AsyncGenerator[ChatMessage | str, None]:
        yield "ignored token"
        yield ChatMessage(
            type="ai",
            content="",
            tool_calls=[
                {
                    "name": "get_customer_tickets",
                    "args": {"customer_id": 1},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        )
        yield ChatMessage(
            type="tool",
            content='{"ticket_count": 3}',
            tool_call_id="call-1",
        )
        yield ChatMessage(
            type="ai",
            content="Customer 1 has three tickets.",
        )

    actual = await collect_actual_result(events())

    assert actual == {
        "tool_name": "get_customer_tickets",
        "tool_arguments": {"customer_id": 1},
        "tool_content": '{"ticket_count": 3}',
        "answer": "Customer 1 has three tickets.",
    }


@pytest.mark.asyncio
async def test_collect_actual_result_without_tool_call():
    async def events() -> AsyncGenerator[ChatMessage | str, None]:
        yield ChatMessage(type="ai", content="Hello!")

    actual = await collect_actual_result(events())

    assert actual == {
        "tool_name": None,
        "tool_arguments": {},
        "tool_content": "",
        "answer": "Hello!",
    }


@pytest.mark.asyncio
async def test_collect_actual_result_rejects_multiple_tool_calls():
    async def events() -> AsyncGenerator[ChatMessage | str, None]:
        yield ChatMessage(
            type="ai",
            content="",
            tool_calls=[
                {
                    "name": "first_tool",
                    "args": {},
                    "id": "call-1",
                    "type": "tool_call",
                },
                {
                    "name": "second_tool",
                    "args": {},
                    "id": "call-2",
                    "type": "tool_call",
                },
            ],
        )

    with pytest.raises(ValueError, match="Only one tool call"):
        await collect_actual_result(events())
