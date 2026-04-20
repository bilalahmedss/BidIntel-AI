import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.deps import get_current_user, get_current_user_from_token
from backend.groq_client import create_streaming_completion
from backend.database import get_db, row, rows
from backend.safety import QuerySafetyLayer

router = APIRouter()

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "data" / "uploads"
BRAIN_DIR = ROOT / "data" / "company_brain"

_safety = QuerySafetyLayer()


def _build_context(project_id: int, question: str) -> str:
    import sys
    sys.path.insert(0, str(ROOT))

    from ingestion.project_indexer import load_project_index, build_project_index
    from rag.retriever import make_retriever

    chunks = []

    # Company brain
    if BRAIN_DIR.exists() and any(BRAIN_DIR.iterdir()):
        try:
            from ingestion.kb_loader import build_kb_index
            idx = build_kb_index(str(BRAIN_DIR))
            ret = make_retriever(idx)
            brain_chunks = ret(question, top_k=3)
            if brain_chunks:
                chunks.append("## Company Knowledge Base\n" + "\n\n---\n\n".join(brain_chunks))
        except Exception:
            pass

    # RFP — semantic search over full indexed text
    rfp_index = load_project_index(project_id, "rfp")
    if rfp_index:
        try:
            ret = make_retriever(rfp_index)
            rfp_chunks = ret(question, top_k=3)
            if rfp_chunks:
                chunks.append("## RFP\n" + "\n\n---\n\n".join(rfp_chunks))
        except Exception:
            pass
    else:
        # Fallback: structured output from the last analysis parse
        db = get_db()
        p = row(db.execute("SELECT parsed_rfp_json FROM projects WHERE id=?", (project_id,)).fetchone())
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

    # Bid response — load persistent index, fall back to building if not ready
    resp_index = load_project_index(project_id, "response")
    if resp_index is None:
        resp_path = UPLOAD_DIR / "response" / f"{project_id}_response.pdf"
        if resp_path.exists():
            try:
                resp_index = build_project_index(project_id, str(resp_path), "response")
            except Exception:
                pass
    if resp_index:
        try:
            ret = make_retriever(resp_index)
            resp_chunks = ret(question, top_k=3)
            if resp_chunks:
                chunks.append("## Bid Response\n" + "\n\n---\n\n".join(resp_chunks))
        except Exception:
            pass

    # Latest analysis results for this project
    db2 = get_db()
    ar = row(db2.execute(
        "SELECT wps_summary_json, criterion_results_json, poison_pills_json "
        "FROM analysis_results WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
        (project_id,),
    ).fetchone())
    db2.close()
    if ar:
        try:
            lines = []
            wps = json.loads(ar["wps_summary_json"] or "{}")
            if wps:
                lines.append(f"WPS: {wps.get('wps', 'N/A')} | Verdict: {wps.get('verdict', 'N/A')}")
            criteria = json.loads(ar["criterion_results_json"] or "[]")
            for c in criteria[:20]:
                lines.append(f"- {c.get('name','')}: {c.get('status','') or c.get('score','')} | gaps: {', '.join(c.get('gap_signals',[]))}")
            pills = json.loads(ar["poison_pills_json"] or "[]")
            for pp in pills[:10]:
                lines.append(f"[RISK {pp.get('severity','')}] {pp.get('clause_text','')[:200]}")
            if lines:
                chunks.append("## Analysis Results\n" + "\n".join(lines))
        except Exception:
            pass

    # Project sections (draft bid response workspace)
    db3 = get_db()
    secs = db3.execute(
        "SELECT title, content FROM sections WHERE project_id=? ORDER BY order_index",
        (project_id,),
    ).fetchall()
    db3.close()
    if secs:
        sec_text = "\n\n".join(
            f"### {s['title']}\n{s['content']}" for s in secs if s["content"].strip()
        )
        if sec_text.strip():
            chunks.append(f"## Draft Response Sections\n{sec_text[:3000]}")

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

    _safety.record_event(
        route="ask",
        context="llm_boundary",
        event_type="confidentiality_notice_enforced",
        action_taken="warn_allow",
        user_id=user_id,
        metadata={"project_id": pid},
    )

    if _safety.detect_prompt_injection(body.question):
        _safety.record_event(
            route="ask",
            context="user_chat_query",
            event_type="prompt_injection_detected",
            action_taken="guarded_prompt_applied",
            user_id=user_id,
            metadata={"project_id": pid},
        )

    safe_question, redacted_types = _safety.redact_pii(body.question)
    if redacted_types:
        _safety.log_intervention(str(user_id), redacted_types, "user_chat_query", route="ask")

    # Persist original user message in our own database.
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

    context = await asyncio.to_thread(_build_context, pid, safe_question)
    system = (
        "You are BidIntel AI, an expert assistant for bid managers and proposal writers. "
        "Answer concisely and professionally using the provided context. "
        "If the context doesn't contain the answer, say so clearly.\n\n"
        f"CONTEXT:\n{context}"
    )
    guarded_system = _safety.build_guarded_system_prompt(system)

    messages = [{"role": "system", "content": guarded_system}]
    for m in history:
        if _safety.detect_prompt_injection(m["content"]):
            _safety.record_event(
                route="ask",
                context="chat_history",
                event_type="prompt_injection_detected",
                action_taken="guarded_prompt_applied",
                user_id=user_id,
                metadata={"project_id": pid},
            )
        safe_history_content, history_redacted_types = _safety.redact_pii(m["content"])
        if history_redacted_types:
            _safety.log_intervention(str(user_id), history_redacted_types, "chat_history", route="ask")
        messages.append({"role": m["role"], "content": safe_history_content})
    messages.append({"role": "user", "content": safe_question})

    async def generate():
        full = ""
        yielded_chunks: list[str] = []
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
                    yielded_chunks.append(delta)
                    yield f"data: {json.dumps({'chunk': delta})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'chunk': f'Error: {e}'})}\n\n"
            full = f"Error: {e}"
        finally:
            safe_full = _safety.check_output(full)
            if safe_full != full:
                _safety.log_intervention(str(user_id), ["UNSAFE_OUTPUT"], "llm_response", route="ask")
                if yielded_chunks:
                    yield f"data: {json.dumps({'replace': safe_full})}\n\n"
                else:
                    yield f"data: {json.dumps({'chunk': safe_full})}\n\n"
            db2 = get_db()
            db2.execute("INSERT INTO chat_messages (project_id, user_id, role, content) VALUES (?,?,?,?)",
                        (pid, user_id, "assistant", safe_full))
            db2.commit()
            db2.close()
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
