from time import perf_counter
from typing import Any
from uuid import uuid4

from client import AgentClient
from evals.collector import collect_actual_result
from evals.scoring import score_result

EVALUATION_USER_ID = "phase15-evaluation"


async def run_case(
    client: AgentClient,
    case: dict[str, Any],
) -> dict[str, Any]:
    """Run and score one isolated evaluation case."""
    client.update_agent(case["agent_id"])
    thread_id = f"eval-{case['id']}-{uuid4()}"

    started_at = perf_counter()
    events = client.astream(
        message=case["question"],
        thread_id=thread_id,
        user_id=EVALUATION_USER_ID,
        stream_tokens=False,
    )
    actual = await collect_actual_result(events)
    latency_seconds = perf_counter() - started_at

    scores = score_result(actual, case["expected"])

    return {
        "id": case["id"],
        "category": case["category"],
        "agent_id": case["agent_id"],
        "question": case["question"],
        "thread_id": thread_id,
        "latency_seconds": round(latency_seconds, 3),
        "actual": actual,
        "scores": scores,
    }
