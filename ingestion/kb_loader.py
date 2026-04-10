import argparse
import os
from pathlib import Path
from typing import Any, List

import chromadb
from dotenv import load_dotenv
from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from pydantic import PrivateAttr
from sentence_transformers import SentenceTransformer

load_dotenv()

DEFAULT_COLLECTION_NAME = "company_brain"
DEFAULT_PERSIST_DIR = str((Path(__file__).resolve().parents[1] / "data" / "chroma_kb").resolve())


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


def _build_embedding_model() -> BaseEmbedding:
    return LocalSentenceTransformerEmbedding()


def build_kb_index(
    source_dir: str,
    persist_dir: str = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> VectorStoreIndex:
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    reader = SimpleDirectoryReader(input_dir=source_dir, required_exts=[".pdf", ".txt"], recursive=True)
    documents = reader.load_data()
    if not documents:
        raise ValueError(f"No .pdf or .txt documents found in: {source_dir}")

    embedding_model = _build_embedding_model()
    Settings.embed_model = embedding_model

    persist_path = Path(persist_dir)
    persist_path.mkdir(parents=True, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(persist_path))
    chroma_collection = chroma_client.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context, embed_model=embedding_model)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Load company documents and build a Chroma-backed VectorStoreIndex.")
    parser.add_argument("source_dir", help="Directory containing .pdf/.txt knowledge base files")
    parser.add_argument("--persist-dir", default=DEFAULT_PERSIST_DIR, help="Directory for Chroma persisted index")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME, help="Chroma collection name")
    args = parser.parse_args()

    build_kb_index(args.source_dir, persist_dir=args.persist_dir, collection_name=args.collection)
    print(f"Index built successfully at {args.persist_dir} (collection={args.collection})")


if __name__ == "__main__":
    main()
