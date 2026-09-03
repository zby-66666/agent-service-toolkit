import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

for import_path in (PROJECT_ROOT, SRC_PATH):
    import_path_str = str(import_path)
    if import_path_str not in sys.path:
        sys.path.insert(0, import_path_str)

from client import AgentClient  # noqa: E402
from evals.runner import run_case  # noqa: E402

DEFAULT_CASES_PATH = PROJECT_ROOT / "evals" / "cases.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "evals" / "results" / "latest.json"
DEFAULT_TIMEOUT_SECONDS = 600.0


def load_cases(cases_path: Path) -> list[dict[str, Any]]:
    """Load version 1 evaluation cases from JSON."""
    data = json.loads(cases_path.read_text(encoding="utf-8"))

    if data.get("version") != 1:
        raise ValueError("Only evaluation case version 1 is supported")

    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Evaluation file must contain a cases list")

    return cases


def build_summary(results: list[dict[str, Any]]) -> dict[str, int | float | None]:
    """Build aggregate metrics from individual case results."""
    total = len(results)
    passed = sum(result["scores"]["passed"] is True for result in results)
    latencies = [
        result["latency_seconds"]
        for result in results
        if isinstance(result.get("latency_seconds"), int | float)
    ]

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate_percent": round((passed / total) * 100, 1) if total else 0.0,
        "average_latency_seconds": (
            round(sum(latencies) / len(latencies), 3) if latencies else None
        ),
    }


async def run_evaluation(
    base_url: str,
    cases_path: Path,
    output_path: Path,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run all cases sequentially and save a JSON report."""
    cases = load_cases(cases_path)
    client = AgentClient(
        base_url=base_url,
        timeout=timeout_seconds,
    )
    results: list[dict[str, Any]] = []

    for case in cases:
        print(f"Running {case['id']}...")  # noqa: T201
        case_started_at = perf_counter()

        try:
            result = await run_case(client, case)
        except Exception as error:
            latency_seconds = perf_counter() - case_started_at
            result = {
                "id": case["id"],
                "category": case["category"],
                "agent_id": case["agent_id"],
                "question": case["question"],
                "latency_seconds": round(latency_seconds, 3),
                "actual": None,
                "scores": {
                    "tool_pass": False,
                    "arguments_pass": False,
                    "tool_content_pass": False,
                    "answer_pass": False,
                    "passed": False,
                },
                "error": f"{type(error).__name__}: {error}",
            }

        results.append(result)
        status = "PASS" if result["scores"]["passed"] else "FAIL"
        print(f"{case['id']}: {status}")  # noqa: T201

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "timeout_seconds": timeout_seconds,
        "cases_file": str(cases_path),
        "summary": build_summary(results),
        "results": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Agent evaluations")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = asyncio.run(
        run_evaluation(
            base_url=args.base_url,
            cases_path=args.cases,
            output_path=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    )
    summary = report["summary"]
    print(f"Report: {args.output}")  # noqa: T201
    print(  # noqa: T201
        f"Passed: {summary['passed']}/{summary['total']} ({summary['pass_rate_percent']}%)"
    )
    print(f"Average latency: {summary['average_latency_seconds']}s")  # noqa: T201


if __name__ == "__main__":
    main()
