import os
from pathlib import Path
from typing import Any, List

import chromadb
import fitz  # pymupdf
from dotenv import load_dotenv
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from pydantic import PrivateAttr
from sentence_transformers import SentenceTransformer

load_dotenv()

COLLECTION_NAME = "bid_response"
_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100


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
            self._st_model = SentenceTransformer(self.model_name)
        vector = self._st_model.encode(text, normalize_embeddings=True)
        return [float(v) for v in vector.tolist()]


def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def build_response_index(pdf_path: str) -> VectorStoreIndex:
    """Index a bid response PDF into an ephemeral ChromaDB for this session."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Response PDF not found: {pdf_path}")

    documents: List[Document] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            text = (page.get_text() or "").strip()
            if not text:
                continue
            for chunk in _chunk_text(text):
                documents.append(Document(text=chunk, metadata={"page": i, "source": "bid_response"}))

    if not documents:
        raise ValueError("No extractable text found in bid response PDF.")

    embedding_model = LocalSentenceTransformerEmbedding()
    Settings.embed_model = embedding_model

    chroma_client = chromadb.EphemeralClient()
    chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context, embed_model=embedding_model
    )
    return index
