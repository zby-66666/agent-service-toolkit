import math
import re

import numexpr
from langchain_core.tools import BaseTool, tool
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

QDRANT_PATH = "./qdrant_data"
COLLECTION_NAME = "employee_handbook"
EMBEDDING_MODEL = "bge-m3"


def calculator_func(expression: str) -> str:
    """Calculates a math expression using numexpr.

    Useful for when you need to answer questions about math using numexpr.
    This tool is only for math questions and nothing else. Only input
    math expressions.

    Args:
        expression (str): A valid numexpr formatted math expression.

    Returns:
        str: The result of the math expression.
    """

    try:
        local_dict = {"pi": math.pi, "e": math.e}
        output = str(
            numexpr.evaluate(
                expression.strip(),
                global_dict={},  # restrict access to globals
                local_dict=local_dict,  # add common mathematical functions
            )
        )
        return re.sub(r"^\[|\]$", "", output)
    except Exception as e:
        raise ValueError(
            f'calculator("{expression}") raised error: {e}.'
            " Please try again with a valid numerical expression"
        )


calculator: BaseTool = tool(calculator_func)
calculator.name = "Calculator"


# Format retrieved documents
def format_contexts(docs):
    return "\n\n".join(doc.page_content for doc in docs)


def load_qdrant_db():
    """Open the local Qdrant collection and create its retriever."""
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    client = QdrantClient(path=QDRANT_PATH)

    try:
        if not client.collection_exists(COLLECTION_NAME):
            raise RuntimeError(
                f"Qdrant collection '{COLLECTION_NAME}' does not exist. "
                "Run scripts/create_qdrant_db.py first."
            )

        vector_store = QdrantVectorStore(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding=embeddings,
        )
        retriever = vector_store.as_retriever(search_kwargs={"k": 5})
        return client, retriever
    except Exception:
        client.close()
        raise


def database_search_func(query: str) -> str:
    """Searches Qdrant for information in the company's handbook."""
    client, retriever = load_qdrant_db()

    try:
        documents = retriever.invoke(query)
        context_str = format_contexts(documents)
        return context_str
    finally:
        client.close()


database_search: BaseTool = tool(database_search_func)
database_search.name = "Database_Search"  # Update name with the purpose of your database
