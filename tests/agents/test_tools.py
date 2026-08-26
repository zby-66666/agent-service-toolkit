import pytest
from langchain_core.documents import Document

from agents import tools


class FakeReranker:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.received_query: str | None = None
        self.received_documents: list[str] | None = None

    def rerank(
        self,
        query: str,
        documents: list[str],
    ) -> list[float]:
        self.received_query = query
        self.received_documents = documents
        return self.scores


def test_rerank_documents_orders_and_limits(monkeypatch):
    documents = [
        Document(
            page_content="Unrelated company introduction.",
            metadata={"label": "introduction"},
        ),
        Document(
            page_content="Paid Time Off: 15 days per year.",
            metadata={"label": "pto"},
        ),
        Document(
            page_content="Leave requests use the HR portal.",
            metadata={"label": "leave_request"},
        ),
    ]
    fake_reranker = FakeReranker(scores=[-5.0, 8.0, 1.0])
    monkeypatch.setattr(
        tools,
        "get_reranker",
        lambda: fake_reranker,
    )

    results = tools.rerank_documents(
        "How many PTO days do employees receive?",
        documents,
    )

    assert [document.metadata["label"] for document in results] == ["pto", "leave_request"]
    assert fake_reranker.received_query == ("How many PTO days do employees receive?")
    assert fake_reranker.received_documents == [document.page_content for document in documents]


def test_rerank_documents_returns_empty_without_loading_model(
    monkeypatch,
):
    def fail_if_called():
        raise AssertionError("The reranker should not load for empty documents")

    monkeypatch.setattr(
        tools,
        "get_reranker",
        fail_if_called,
    )

    assert tools.rerank_documents("question", []) == []


def test_rerank_documents_rejects_mismatched_score_count(
    monkeypatch,
):
    documents = [
        Document(page_content="First document"),
        Document(page_content="Second document"),
    ]
    fake_reranker = FakeReranker(scores=[1.0])
    monkeypatch.setattr(
        tools,
        "get_reranker",
        lambda: fake_reranker,
    )

    with pytest.raises(
        RuntimeError,
        match="different number of scores",
    ):
        tools.rerank_documents("question", documents)
