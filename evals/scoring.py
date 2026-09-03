from typing import Any


def contains_all(text: str, expected_values: list[str]) -> bool:
    """检查文本是否包含所有预期内容，忽略大小写。"""
    normalized_text = text.casefold()

    return all(expected_value.casefold() in normalized_text for expected_value in expected_values)


def contains_any(text: str, expected_values: list[str]) -> bool:
    """检查文本是否包含任意一个可接受内容，忽略大小写。"""
    if not expected_values:
        return True

    normalized_text = text.casefold()

    return any(expected_value.casefold() in normalized_text for expected_value in expected_values)


def arguments_match(
    actual_arguments: dict[str, object],
    expected_arguments: dict[str, object],
) -> bool:
    """检查所有预期工具参数是否与实际参数一致。"""
    return all(
        argument_name in actual_arguments and actual_arguments[argument_name] == expected_value
        for argument_name, expected_value in expected_arguments.items()
    )


def score_result(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, bool]:
    """分别评估工具选择、参数、工具内容和最终答案。"""
    scores = {
        "tool_pass": actual.get("tool_name") == expected["tool_name"],
        "arguments_pass": arguments_match(
            actual.get("tool_arguments", {}),
            expected["tool_arguments"],
        ),
        "tool_content_pass": contains_all(
            actual.get("tool_content", ""),
            expected["tool_content_contains"],
        ),
        "answer_pass": contains_all(
            actual.get("answer", ""),
            expected["answer_contains_all"],
        )
        and contains_any(
            actual.get("answer", ""),
            expected["answer_contains_any"],
        ),
    }

    scores["passed"] = all(scores.values())
    return scores
