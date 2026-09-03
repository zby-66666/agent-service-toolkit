from collections.abc import AsyncGenerator

import pytest

from evals.runner import EVALUATION_USER_ID, run_case
from schema import ChatMessage


class FakeAgentClient:
    def __init__(self) -> None:
        self.selected_agent: str | None = None
        self.stream_requests: list[dict[str, object]] = []

    def update_agent(self, agent: str) -> None:
        self.selected_agent = agent

    async def astream(
        self,
        message: str,
        thread_id: str,
        user_id: str,
        stream_tokens: bool,
    ) -> AsyncGenerator[ChatMessage | str, None]:
        self.stream_requests.append(
            {
                "message": message,
                "thread_id": thread_id,
                "user_id": user_id,
                "stream_tokens": stream_tokens,
            }
        )
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
            content="Tickets 1001, 1002 and 1003 are resolved or open.",
        )


def make_case() -> dict[str, object]:
    return {
        "id": "ticket-customer-001",
        "category": "ticket",
        "agent_id": "ticket-mcp-agent",
        "question": "List tickets for customer ID 1.",
        "expected": {
            "tool_name": "get_customer_tickets",
            "tool_arguments": {"customer_id": 1},
            "tool_content_contains": ['"ticket_count": 3'],
            "answer_contains_all": ["1001", "1002", "1003", "resolved", "open"],
            "answer_contains_any": [],
        },
    }


@pytest.mark.asyncio
async def test_run_case_collects_and_scores_agent_stream():
    client = FakeAgentClient()

    result = await run_case(client, make_case())  # type: ignore[arg-type]

    assert client.selected_agent == "ticket-mcp-agent"
    assert client.stream_requests[0] == {
        "message": "List tickets for customer ID 1.",
        "thread_id": result["thread_id"],
        "user_id": EVALUATION_USER_ID,
        "stream_tokens": False,
    }
    assert result["thread_id"].startswith("eval-ticket-customer-001-")
    assert result["latency_seconds"] >= 0
    assert result["scores"]["passed"] is True


@pytest.mark.asyncio
async def test_run_case_uses_a_new_thread_for_each_execution():
    client = FakeAgentClient()
    case = make_case()

    first_result = await run_case(client, case)  # type: ignore[arg-type]
    second_result = await run_case(client, case)  # type: ignore[arg-type]

    assert first_result["thread_id"] != second_result["thread_id"]
