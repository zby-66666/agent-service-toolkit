import json
from pathlib import Path
from typing import Any

import pytest

import evals.run_evaluation as evaluation_module
from evals.run_evaluation import build_summary, load_cases, run_evaluation


def test_load_cases_reads_version_one_file(tmp_path: Path):
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps({"version": 1, "cases": [{"id": "case-1"}]}),
        encoding="utf-8",
    )

    assert load_cases(cases_path) == [{"id": "case-1"}]


def test_build_summary_counts_passes_and_average_latency():
    results = [
        {"scores": {"passed": True}, "latency_seconds": 2.0},
        {"scores": {"passed": False}, "latency_seconds": 4.0},
        {"scores": {"passed": False}, "latency_seconds": None},
    ]

    assert build_summary(results) == {
        "total": 3,
        "passed": 1,
        "failed": 2,
        "pass_rate_percent": 33.3,
        "average_latency_seconds": 3.0,
    }


@pytest.mark.asyncio
async def test_run_evaluation_continues_after_case_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    cases = [
        {
            "id": "passing-case",
            "category": "ticket",
            "agent_id": "ticket-mcp-agent",
            "question": "passing question",
            "expected": {},
        },
        {
            "id": "error-case",
            "category": "ticket",
            "agent_id": "ticket-mcp-agent",
            "question": "error question",
            "expected": {},
        },
    ]
    cases_path = tmp_path / "cases.json"
    output_path = tmp_path / "latest.json"
    cases_path.write_text(
        json.dumps({"version": 1, "cases": cases}),
        encoding="utf-8",
    )

    fake_client = object()

    fake_times = iter([10.0, 20.0, 24.0])
    monkeypatch.setattr(
        evaluation_module,
        "perf_counter",
        lambda: next(fake_times),
    )
    monkeypatch.setattr(
        evaluation_module,
        "AgentClient",
        lambda **kwargs: fake_client,
    )

    async def fake_run_case(client: object, case: dict[str, Any]) -> dict[str, Any]:
        assert client is fake_client
        if case["id"] == "error-case":
            raise RuntimeError("simulated failure")
        return {
            "id": case["id"],
            "scores": {"passed": True},
            "latency_seconds": 1.5,
        }

    monkeypatch.setattr(evaluation_module, "run_case", fake_run_case)

    report = await run_evaluation(
        base_url="http://test-service",
        cases_path=cases_path,
        output_path=output_path,
        timeout_seconds=321.0,
    )

    assert report["summary"] == {
        "total": 2,
        "passed": 1,
        "failed": 1,
        "pass_rate_percent": 50.0,
        "average_latency_seconds": 2.75,
    }
    assert report["results"][1]["latency_seconds"] == 4.0
    assert report["results"][1]["error"] == "RuntimeError: simulated failure"
    assert report["timeout_seconds"] == 321.0
    assert json.loads(output_path.read_text(encoding="utf-8"))["summary"] == report["summary"]
