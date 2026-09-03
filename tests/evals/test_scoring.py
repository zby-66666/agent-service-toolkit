from evals.scoring import (
    arguments_match,
    contains_all,
    contains_any,
    score_result,
)


def test_contains_all_ignores_case():
    assert contains_all(
        "Tickets 1001 and 1002 are RESOLVED.",
        ["1001", "resolved"],
    )
    assert not contains_all(
        "Ticket 1001 is open.",
        ["1001", "resolved"],
    )


def test_contains_any_accepts_empty_expectation():
    assert contains_any(
        "Device was not found.",
        ["not found", "no device"],
    )
    assert not contains_any(
        "Two repair records exist.",
        ["not found", "no device"],
    )
    assert contains_any("Any answer", [])


def test_arguments_match_uses_expected_subset():
    assert arguments_match(
        {"customer_id": 1, "extra": True},
        {"customer_id": 1},
    )
    assert not arguments_match(
        {"customer_id": 2},
        {"customer_id": 1},
    )
    assert arguments_match(
        {"query": "PTO policy"},
        {},
    )


def test_score_result_identifies_answer_failure():
    actual = {
        "tool_name": "Database_Search",
        "tool_arguments": {"query": "PTO policy"},
        "tool_content": "Paid Time Off (PTO): 15 days per year",
        "answer": "Employees receive 10 PTO days per year.",
    }
    expected = {
        "tool_name": "Database_Search",
        "tool_arguments": {},
        "tool_content_contains": ["15 days per year"],
        "answer_contains_all": ["15"],
        "answer_contains_any": [],
    }

    scores = score_result(actual, expected)

    assert scores == {
        "tool_pass": True,
        "arguments_pass": True,
        "tool_content_pass": True,
        "answer_pass": False,
        "passed": False,
    }
