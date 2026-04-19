import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.deps import get_current_user, get_current_user_from_token
from backend.groq_client import create_streaming_completion
from backend.database import get_db, row, rows

router = APIRouter()

ROOT = Path(__file__).resolve().parents[3]
UPLOAD_DIR = ROOT / "data" / "uploads"
BRAIN_DIR = ROOT / "data" / "company_brain"

_response_index_cache: dict = {}


def _build_context(project_id: int, question: str) -> str:
    import sys
    sys.path.insert(0, str(ROOT))

    chunks = []

    # Company brain
    if BRAIN_DIR.exists() and any(BRAIN_DIR.iterdir()):
        try:
            from ingestion.kb_loader import build_kb_index
            from rag.retriever import make_retriever
            idx = build_kb_index(str(BRAIN_DIR))
            ret = make_retriever(idx)
            brain_chunks = ret(question, top_k=3)
            if brain_chunks:
                chunks.append("## Company Knowledge Base\n" + "\n\n---\n\n".join(brain_chunks))
        except Exception:
            pass

    # Project RFP (from cached parsed JSON)
    db = get_db()
    p = row(db.execute("SELECT parsed_rfp_json, rfp_filename FROM projects WHERE id=?", (project_id,)).fetchone())
    db.close()

    if p and p.get("parsed_rfp_json"):
        try:
            parsed = json.loads(p["parsed_rfp_json"])
            rfp_text = " ".join(
                c.get("description", "") + " ".join(c.get("checklist_signals", []))
                for g in parsed.get("gates", [])
                for c in g.get("criteria", [])
            )
            if rfp_text.strip():
                chunks.append(f"## RFP Requirements\n{rfp_text[:3000]}")
        except Exception:
            pass

    # Project response PDF
    resp_path = UPLOAD_DIR / "response" / f"{project_id}_response.pdf"
    if resp_path.exists():
        cache_key = str(resp_path)
        try:
            from rag.retriever import make_retriever
            from ingestion.response_loader import build_response_index
            if cache_key not in _response_index_cache:
                _response_index_cache[cache_key] = build_response_index(str(resp_path))
            idx = _response_index_cache[cache_key]
            ret = make_retriever(idx)
            resp_chunks = ret(question, top_k=3)
            if resp_chunks:
                chunks.append("## Bid Response\n" + "\n\n---\n\n".join(resp_chunks))
        except Exception:
            pass

    return "\n\n====\n\n".join(chunks) if chunks else "No relevant documents found."


@router.get("/{pid}/history")
def history(pid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    msgs = rows(db.execute(
        "SELECT id, role, content, created_at FROM chat_messages WHERE project_id=? ORDER BY created_at",
        (pid,),
    ).fetchall())
    db.close()
    return msgs


@router.delete("/{pid}/history", status_code=204)
def clear_history(pid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("DELETE FROM chat_messages WHERE project_id=?", (pid,))
    db.commit()
    db.close()


class AskIn(BaseModel):
    question: str


@router.post("/{pid}/send")
async def send_message(pid: int, body: AskIn, token: str = Query(...)):
    user = get_current_user_from_token(token)
    user_id = int(user["id"])

    import asyncio
    import sys
    sys.path.insert(0, str(ROOT))

    # Persist user message
    db = get_db()
    db.execute("INSERT INTO chat_messages (project_id, user_id, role, content) VALUES (?,?,?,?)",
               (pid, user_id, "user", body.question))
    db.commit()

    # Get last 8 messages for context
    history = rows(db.execute(
        "SELECT role, content FROM chat_messages WHERE project_id=? ORDER BY created_at DESC LIMIT 9",
        (pid,),
    ).fetchall())
    db.close()
    history = list(reversed(history[1:]))  # exclude the one we just added

    context = await asyncio.to_thread(_build_context, pid, body.question)
    system = (
        "You are BidIntel AI, an expert assistant for bid managers and proposal writers. "
        "Answer concisely and professionally using the provided context. "
        "If the context doesn't contain the answer, say so clearly.\n\n"
        f"CONTEXT:\n{context}"
    )

    messages = [{"role": "system", "content": system}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": body.question})

    async def generate():
        full = ""
        try:
            stream = await create_streaming_completion(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full += delta
                    yield f"data: {json.dumps({'chunk': delta})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'chunk': f'Error: {e}'})}\n\n"
            full = f"Error: {e}"
        finally:
            db2 = get_db()
            db2.execute("INSERT INTO chat_messages (project_id, user_id, role, content) VALUES (?,?,?,?)",
                        (pid, user_id, "assistant", full))
            db2.commit()
            db2.close()
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
