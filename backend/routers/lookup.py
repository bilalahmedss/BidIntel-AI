import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from backend.database import get_db, row, rows
from backend.deps import get_current_user

router = APIRouter()

ROOT = Path(__file__).resolve().parents[3]
BRAIN_DIR = ROOT / "data" / "company_brain"
BRAIN_DIR.mkdir(parents=True, exist_ok=True)


def _rebuild_index():
    import sys
    sys.path.insert(0, str(ROOT))
    if not any(BRAIN_DIR.iterdir()):
        return
    from ingestion.kb_loader import build_kb_index
    build_kb_index(str(BRAIN_DIR))


@router.get("/docs")
def list_docs(user: dict = Depends(get_current_user)):
    db = get_db()
    docs = rows(db.execute("SELECT * FROM lookup_docs ORDER BY uploaded_at DESC").fetchall())
    db.close()
    return docs


@router.post("/upload", status_code=201)
async def upload_doc(bg: BackgroundTasks, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if not file.filename:
        raise HTTPException(400, "No file provided")
    dest = BRAIN_DIR / file.filename
    data = await file.read()
    dest.write_bytes(data)
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO lookup_docs (filename, size_bytes, uploaded_by) VALUES (?,?,?)",
        (file.filename, len(data), user["id"]),
    )
    db.commit()
    db.close()
    bg.add_task(_rebuild_index)
    return {"filename": file.filename, "size_bytes": len(data)}


@router.delete("/doc/{filename}", status_code=204)
def delete_doc(filename: str, bg: BackgroundTasks, user: dict = Depends(get_current_user)):
    fp = BRAIN_DIR / filename
    if fp.exists():
        fp.unlink()
    db = get_db()
    db.execute("DELETE FROM lookup_docs WHERE filename=?", (filename,))
    db.commit()
    db.close()
    bg.add_task(_rebuild_index)


class SearchIn(BaseModel):
    query: str
    top_k: int = 5


@router.post("/search")
async def search(body: SearchIn, user: dict = Depends(get_current_user)):
    import sys
    sys.path.insert(0, str(ROOT))

    docs = list(BRAIN_DIR.iterdir()) if BRAIN_DIR.exists() else []
    if not docs:
        raise HTTPException(400, "No documents in knowledge base. Upload some first.")

    from groq import Groq
    from ingestion.kb_loader import build_kb_index
    from rag.retriever import make_retriever

    idx = await asyncio.to_thread(build_kb_index, str(BRAIN_DIR))
    retriever = make_retriever(idx)
    chunks = await asyncio.to_thread(retriever, body.query, body.top_k)

    if not chunks:
        return {"query": body.query, "summary": "No relevant content found.", "chunks": []}

    context = "\n\n---\n\n".join(chunks)
    co = Groq(api_key=os.getenv("GROQ_API_KEY"))
    resp = await asyncio.to_thread(
        co.chat.completions.create,
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a knowledge-base assistant for a bid management team. "
                    "Summarise the relevant information from the provided excerpts to answer the query. "
                    "Be concise, factual, and cite key details. If context is insufficient, say so."
                ),
            },
            {"role": "user", "content": f"Query: {body.query}\n\nContext:\n{context}"},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    summary = resp.choices[0].message.content or ""
    return {"query": body.query, "summary": summary, "chunks": chunks}
