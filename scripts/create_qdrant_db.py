from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

DATA_DIR = Path("./data")
QDRANT_PATH = Path("./qdrant_data")
COLLECTION_NAME = "employee_handbook"
EMBEDDING_MODEL = "bge-m3"
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 500


def load_documents(folder_path: Path) -> list[Document]:
    """Load supported documents from a folder."""
    if not folder_path.is_dir():
        raise FileNotFoundError(f"Document folder does not exist: {folder_path}")

    documents: list[Document] = []

    for file_path in sorted(folder_path.iterdir()):
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            loader = PyPDFLoader(str(file_path))
        elif suffix == ".docx":
            loader = Docx2txtLoader(str(file_path))
        else:
            continue

        loaded_documents = loader.load()
        documents.extend(loaded_documents)
        print(f"Loaded {file_path.name}: {len(loaded_documents)} document(s)")

    if not documents:
        raise ValueError(f"No supported PDF or DOCX files found in: {folder_path}")

    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    """Split documents into chunks while preserving their metadata."""
    if not 0 <= CHUNK_OVERLAP < CHUNK_SIZE:
        raise ValueError("CHUNK_OVERLAP must be non-negative and smaller than CHUNK_SIZE")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = text_splitter.split_documents(documents)

    if not chunks:
        raise ValueError("Document splitting produced no chunks")

    return chunks


def create_qdrant_db() -> int:
    """Create a new local Qdrant collection from the documents in DATA_DIR."""
    documents = load_documents(DATA_DIR)
    chunks = split_documents(documents)

    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    probe_vector = embeddings.embed_query("vector dimension probe")
    vector_size = len(probe_vector)
    if vector_size == 0:
        raise ValueError("The embedding model returned an empty vector")

    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(QDRANT_PATH))
    collection_created = False

    try:
        if client.collection_exists(COLLECTION_NAME):
            raise RuntimeError(
                f"Collection '{COLLECTION_NAME}' already exists in {QDRANT_PATH}. "
                "Refusing to overwrite it."
            )

        created = client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        if not created:
            raise RuntimeError(f"Failed to create collection: {COLLECTION_NAME}")
        collection_created = True

        vector_store = QdrantVectorStore(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding=embeddings,
        )
        chunk_ids = vector_store.add_documents(chunks)

        if len(chunk_ids) != len(chunks):
            raise RuntimeError(
                f"Expected {len(chunks)} stored chunks, but received {len(chunk_ids)} IDs"
            )

        print(f"Embedding model: {EMBEDDING_MODEL}")
        print(f"Vector size: {vector_size}")
        print(f"Source documents: {len(documents)}")
        print(f"Stored chunks: {len(chunk_ids)}")
        print(f"Qdrant path: {QDRANT_PATH.resolve()}")
        print(f"Collection: {COLLECTION_NAME}")
        return len(chunk_ids)
    except Exception:
        if collection_created:
            client.delete_collection(COLLECTION_NAME)
            print(f"Rolled back incomplete collection: {COLLECTION_NAME}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    create_qdrant_db()
