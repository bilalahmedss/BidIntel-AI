"""
Retrieval layer for BidIntel-AI.

Exposes two public helpers:

  retrieve(query, top_k)          — one-shot KB query (standalone use)
  make_retriever(index)           — factory that returns a retriever closure

Both return List[str] of ranked document chunks.

Hybrid Search
-------------
When make_retriever receives a HybridIndex (produced by the index builders in
ingestion/), it runs *both* vector search and BM25 keyword search and fuses
the results with Reciprocal Rank Fusion (RRF).

Why hybrid?  all-MiniLM-L6-v2 semantic search finds thematically similar text
well, but misses exact-string requirements like "ISO-27001" — it may return
paragraphs about "data security" instead.  BM25 catches the exact token.
RRF merges the two ranked lists without requiring compatible score scales.

RRF formula:  score(d) = Σ  1 / (k + rank_of_d_in_list_i)   (k=60, standard)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List

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
_MODEL = None  # loaded lazily on first use

_RRF_K = 60  # standard constant; higher → less aggressive rank boosting


# ---------------------------------------------------------------------------
# HybridIndex — bundles a vector index with the plain-text corpus for BM25
# ---------------------------------------------------------------------------

@dataclass
class HybridIndex:
    """
    Wraps a LlamaIndex VectorStoreIndex together with the raw chunk corpus so
    that make_retriever() can build a BM25 index alongside the vector index.

    All index builders (kb_loader, response_loader, project_indexer) return
    this type.  make_retriever() also accepts a plain VectorStoreIndex for
    backward compatibility (falls back to vector-only search).
    """
    vector_index: VectorStoreIndex
    corpus: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Embedding model (shared across retriever variants)
# ---------------------------------------------------------------------------

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
            global _MODEL
            if _MODEL is None:
                _MODEL = SentenceTransformer(self.model_name)
            self._st_model = _MODEL
        vector = self._st_model.encode(text, normalize_embeddings=True)
        return [float(v) for v in vector.tolist()]


def _build_embedding_model() -> BaseEmbedding:
    return LocalSentenceTransformerEmbedding()


# ---------------------------------------------------------------------------
# Internal RRF helper
# ---------------------------------------------------------------------------

def _rrf_fuse(ranked_lists: list[list[str]], k: int = _RRF_K) -> list[str]:
    """
    Reciprocal Rank Fusion across multiple ranked lists.

    Each document accumulates score  1/(k + rank)  for every list it appears
    in.  Documents are returned highest-score-first.  RRF is rank-based so it
    handles incompatible score scales (cosine similarity vs BM25) with zero
    tuning.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, text in enumerate(ranked):
            scores[text] = scores.get(text, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=scores.__getitem__, reverse=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve(query: str, top_k: int = 3) -> List[str]:
    """One-shot vector retrieval from the persisted KB index."""
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


def make_retriever(
    index: HybridIndex | VectorStoreIndex,
) -> Callable[[str, int], List[str]]:
    """
    Return a retriever closure bound to *index*.

    If *index* is a HybridIndex with a non-empty corpus:
      → runs vector search AND BM25 keyword search, fuses with RRF.

    If *index* is a plain VectorStoreIndex (or HybridIndex with empty corpus):
      → falls back to vector-only search (original behaviour).

    The returned callable has signature:
        retriever(query: str, top_k: int = 3) -> List[str]
    """
    embedding_model = _build_embedding_model()
    Settings.embed_model = embedding_model

    # Unwrap HybridIndex
    if isinstance(index, HybridIndex):
        vi: VectorStoreIndex = index.vector_index
        corpus: list[str] = index.corpus
    else:
        vi = index
        corpus = []

    # Build BM25 index once, at retriever-creation time (cheap)
    bm25 = None
    if corpus:
        try:
            from rank_bm25 import BM25Okapi  # keyword search — exact-match complement to vector
            tokenized = [doc.lower().split() for doc in corpus]
            bm25 = BM25Okapi(tokenized)
        except ImportError:
            pass  # rank-bm25 not installed — degrade gracefully to vector-only

    def _retrieve(query: str, top_k: int = 3) -> List[str]:
        if not query or not query.strip():
            return []

        # --- Vector search (semantic) ---
        r = vi.as_retriever(similarity_top_k=top_k * 2)  # fetch extra for RRF headroom
        nodes = r.retrieve(query)
        vector_ranked = [n.get_content().strip() for n in nodes if n.get_content().strip()]

        if bm25 is None or not corpus:
            return vector_ranked[:top_k]

        # --- BM25 keyword search (exact-match for certification codes, etc.) ---
        scores = bm25.get_scores(query.lower().split())
        bm25_ranked = [
            corpus[i]
            for i in scores.argsort()[::-1][: top_k * 2]
            if corpus[i].strip()
        ]

        # --- Reciprocal Rank Fusion ---
        fused = _rrf_fuse([vector_ranked, bm25_ranked], k=_RRF_K)
        return fused[:top_k]

    return _retrieve
