from pathlib import Path
from typing import Any, List

import chromadb
from dotenv import load_dotenv
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from pydantic import PrivateAttr
from sentence_transformers import SentenceTransformer

load_dotenv()

DEFAULT_COLLECTION_NAME = "company_brain"
DEFAULT_PERSIST_DIR = str((Path(__file__).resolve().parents[1] / "data" / "chroma_kb").resolve())
_MODEL = SentenceTransformer("all-MiniLM-L6-v2")


class LocalSentenceTransformerEmbedding(BaseEmbedding):
    model_name: str = "all-MiniLM-L6-v2"
    _st_model: Any = PrivateAttr(default=None)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embed_text(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._embed_text(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embed_text(text)

    def _embed_text(self, text: str) -> List[float]:
        if self._st_model is None:
            self._st_model = _MODEL
        vector = self._st_model.encode(text, normalize_embeddings=True)
        return [float(v) for v in vector.tolist()]


def _build_embedding_model() -> BaseEmbedding:
    return LocalSentenceTransformerEmbedding()


def retrieve(query: str, top_k: int = 3) -> List[str]:
    if not query or not query.strip():
        return []

    embedding_model = _build_embedding_model()
    Settings.embed_model = embedding_model

    persist_path = Path(DEFAULT_PERSIST_DIR)
    if not persist_path.exists():
        raise FileNotFoundError(f"Persisted index directory not found: {persist_path}")

    chroma_client = chromadb.PersistentClient(path=str(persist_path))
    chroma_collection = chroma_client.get_or_create_collection(DEFAULT_COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store, embed_model=embedding_model)

    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query)
    return [node.get_content().strip() for node in nodes if node.get_content().strip()]
