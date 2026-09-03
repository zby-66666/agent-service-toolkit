from unittest.mock import MagicMock

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


def test_load_qdrant_db_uses_configured_ollama_base_url(monkeypatch):
    ollama_base_url = "http://host.docker.internal:11434"

    embeddings = object()
    retriever = object()

    embeddings_factory = MagicMock(return_value=embeddings)

    client = MagicMock()
    client.collection_exists.return_value = True

    vector_store = MagicMock()
    vector_store.as_retriever.return_value = retriever

    monkeypatch.setattr(
        tools.settings,
        "OLLAMA_BASE_URL",
        ollama_base_url,
    )
    monkeypatch.setattr(
        tools,
        "OllamaEmbeddings",
        embeddings_factory,
    )
    monkeypatch.setattr(
        tools,
        "QdrantClient",
        MagicMock(return_value=client),
    )
    monkeypatch.setattr(
        tools,
        "QdrantVectorStore",
        MagicMock(return_value=vector_store),
    )

    returned_client, returned_retriever = tools.load_qdrant_db()

    embeddings_factory.assert_called_once_with(
        model=tools.EMBEDDING_MODEL,
        base_url=ollama_base_url,
    )
    assert returned_client is client
    assert returned_retriever is retriever
