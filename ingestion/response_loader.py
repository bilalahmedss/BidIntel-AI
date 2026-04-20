import os
from pathlib import Path
from typing import Any, List

import chromadb
from dotenv import load_dotenv
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from pydantic import PrivateAttr
from sentence_transformers import SentenceTransformer

from ingestion.pdf_utils import extract_pdf_as_markdown
from rag.retriever import HybridIndex

load_dotenv()

COLLECTION_NAME = "bid_response"
_CHUNK_SIZE = 800   # words per chunk
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


def build_response_index(pdf_path: str) -> HybridIndex:
    """
    Index a bid response PDF into an ephemeral ChromaDB for this session.

    Uses layout-aware Markdown extraction (via extract_pdf_as_markdown) so
    that tables in the response — e.g. pricing grids, compliance sign-off
    tables — are preserved as pipe-table rows rather than garbled columns.

    Returns a HybridIndex that bundles the VectorStoreIndex together with the
    plain-text chunk corpus for BM25 keyword search in make_retriever().
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Response PDF not found: {pdf_path}")

    # Layout-aware extraction: tables arrive as Markdown pipe-table rows
    md = extract_pdf_as_markdown(pdf_path)

    corpus: List[str] = []
    documents: List[Document] = []
    page_num = 1
    for chunk in _chunk_text(md):
        corpus.append(chunk)
        documents.append(Document(
            text=chunk,
            metadata={"page": page_num, "source": "bid_response"},
        ))
        page_num += 1  # approximate — word chunks don't have exact page numbers

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
    # Return HybridIndex so make_retriever can enable BM25 alongside vector search
    return HybridIndex(vector_index=index, corpus=corpus)
