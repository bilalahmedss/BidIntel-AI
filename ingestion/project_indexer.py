"""
Persistent per-project vector indices.

Each project gets its own ChromaDB directory at:
  data/chroma_projects/{project_id}/

Two collections per project:
  project_{id}_rfp      — full raw text of the RFP PDF
  project_{id}_response — full raw text of the bid response PDF

Built once at upload time. Loaded at query time (analysis, Ask).
Re-built automatically when a PDF is re-uploaded.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, List, Optional

import chromadb
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from pydantic import PrivateAttr
from sentence_transformers import SentenceTransformer

from ingestion.pdf_utils import extract_pdf_pages
from rag.retriever import HybridIndex

PROJECTS_DIR = Path(__file__).resolve().parents[1] / "data" / "chroma_projects"
_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100


class _Embedding(BaseEmbedding):
    model_name: str = "all-MiniLM-L6-v2"
    _st: Any = PrivateAttr(default=None)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embed(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._embed(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embed(text)

    def _embed(self, text: str) -> List[float]:
        if self._st is None:
            self._st = SentenceTransformer(self.model_name)
        return [float(v) for v in self._st.encode(text, normalize_embeddings=True).tolist()]


def _chunk_text(text: str) -> List[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i : i + _CHUNK_SIZE])
        if chunk.strip():
            chunks.append(chunk)
        i += _CHUNK_SIZE - _CHUNK_OVERLAP
    return chunks


def _collection_name(project_id: int, kind: str) -> str:
    return f"project_{project_id}_{kind}"


def build_project_index(project_id: int, pdf_path: str, kind: str) -> HybridIndex:
    """
    Index a project PDF into a persistent per-project ChromaDB collection.

    kind: 'rfp' or 'response'
    Rebuilds the collection from scratch if it already exists (re-upload case).

    Returns a HybridIndex that bundles the VectorStoreIndex with the chunk
    corpus so make_retriever() can activate BM25 keyword search alongside
    vector search.
    """
    persist_path = PROJECTS_DIR / str(project_id)
    persist_path.mkdir(parents=True, exist_ok=True)

    corpus: List[str] = []
    documents: List[Document] = []
    for p in extract_pdf_pages(pdf_path):
        text = p["text"].strip()
        if not text:
            continue
        for chunk in _chunk_text(text):
            corpus.append(chunk)
            documents.append(Document(
                text=chunk,
                metadata={"page": p["page_number"], "source": kind, "project_id": project_id},
            ))

    if not documents:
        raise ValueError(f"No extractable text found in {kind} PDF for project {project_id}.")

    embed = _Embedding()
    Settings.embed_model = embed

    client = chromadb.PersistentClient(path=str(persist_path))
    # Delete existing collection so re-uploads produce a clean rebuild
    try:
        client.delete_collection(_collection_name(project_id, kind))
    except Exception:
        pass
    collection = client.get_or_create_collection(_collection_name(project_id, kind))
    store = ChromaVectorStore(chroma_collection=collection)
    ctx = StorageContext.from_defaults(vector_store=store)
    index = VectorStoreIndex.from_documents(documents, storage_context=ctx, embed_model=embed)
    return HybridIndex(vector_index=index, corpus=corpus)


def load_project_index(project_id: int, kind: str) -> Optional[HybridIndex]:
    """
    Load a previously built persistent index.
    Returns None if the index does not exist or is empty.

    Recovers the BM25 corpus by querying ChromaDB for all stored documents —
    this is necessary because the corpus list is not persisted to disk.
    """
    persist_path = PROJECTS_DIR / str(project_id)
    if not persist_path.exists():
        return None
    try:
        embed = _Embedding()
        Settings.embed_model = embed
        client = chromadb.PersistentClient(path=str(persist_path))
        collection = client.get_or_create_collection(_collection_name(project_id, kind))
        if collection.count() == 0:
            return None
        store = ChromaVectorStore(chroma_collection=collection)
        vector_index = VectorStoreIndex.from_vector_store(vector_store=store, embed_model=embed)
        # Recover corpus for BM25 by pulling all stored documents from ChromaDB
        all_docs = collection.get(include=["documents"])
        corpus: List[str] = [d for d in (all_docs.get("documents") or []) if d and d.strip()]
        return HybridIndex(vector_index=vector_index, corpus=corpus)
    except Exception:
        return None


def delete_project_indices(project_id: int) -> None:
    """Remove all persisted vector data for a project (called on project delete)."""
    persist_path = PROJECTS_DIR / str(project_id)
    if persist_path.exists():
        shutil.rmtree(persist_path, ignore_errors=True)
