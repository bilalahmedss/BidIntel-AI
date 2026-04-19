import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.database import get_db, row, rows
from backend.deps import get_current_user

router = APIRouter()


class SectionCreate(BaseModel):
    title: str
    content: str = ""
    order_index: Optional[int] = None
    source: str = "manual"


class SectionUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    order_index: Optional[int] = None


class ReorderItem(BaseModel):
    section_id: int
    order_index: int


@router.get("/projects/{pid}/sections")
def list_sections(pid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    secs = rows(db.execute("SELECT * FROM sections WHERE project_id=? ORDER BY order_index", (pid,)).fetchall())
    db.close()
    return secs


@router.post("/projects/{pid}/sections", status_code=201)
def create_section(pid: int, body: SectionCreate, user: dict = Depends(get_current_user)):
    db = get_db()
    if body.order_index is None:
        max_idx = db.execute("SELECT MAX(order_index) FROM sections WHERE project_id=?", (pid,)).fetchone()[0]
        order = (max_idx or 0) + 10
    else:
        order = body.order_index
    cur = db.execute(
        "INSERT INTO sections (project_id, title, content, order_index, source) VALUES (?,?,?,?,?)",
        (pid, body.title.strip(), body.content, order, body.source),
    )
    db.commit()
    sec = row(db.execute("SELECT * FROM sections WHERE id=?", (cur.lastrowid,)).fetchone())
    db.close()
    return sec


@router.patch("/sections/{sid}")
def update_section(sid: int, body: SectionUpdate, user: dict = Depends(get_current_user)):
    db = get_db()
    sec = row(db.execute("SELECT * FROM sections WHERE id=?", (sid,)).fetchone())
    if not sec:
        raise HTTPException(404, "Section not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        sets = ", ".join(f"{k}=?" for k in updates)
        db.execute(f"UPDATE sections SET {sets}, updated_at=datetime('now') WHERE id=?",
                   list(updates.values()) + [sid])
        db.commit()
    sec = row(db.execute("SELECT * FROM sections WHERE id=?", (sid,)).fetchone())
    db.close()
    return sec


@router.delete("/sections/{sid}", status_code=204)
def delete_section(sid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("DELETE FROM sections WHERE id=?", (sid,))
    db.commit()
    db.close()


@router.post("/projects/{pid}/sections/generate")
def generate_sections(pid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    p = row(db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
    if not p:
        raise HTTPException(404, "Project not found")
    if not p.get("parsed_rfp_json"):
        raise HTTPException(400, "No parsed RFP data. Run analysis first.")

    parsed = json.loads(p["parsed_rfp_json"])
    existing_titles = {
        r[0].lower()
        for r in db.execute("SELECT title FROM sections WHERE project_id=?", (pid,)).fetchall()
    }
    max_idx = db.execute("SELECT MAX(order_index) FROM sections WHERE project_id=?", (pid,)).fetchone()[0] or 0

    created = []
    order = max_idx + 10
    for gate in parsed.get("gates", []):
        gate_title = gate.get("name", "Unnamed Gate")
        if gate_title.lower() not in existing_titles:
            cur = db.execute(
                "INSERT INTO sections (project_id, title, content, order_index, source) VALUES (?,?,?,?,?)",
                (pid, gate_title, "", order, "auto"),
            )
            created.append(row(db.execute("SELECT * FROM sections WHERE id=?", (cur.lastrowid,)).fetchone()))
            existing_titles.add(gate_title.lower())
            order += 10
        for criterion in gate.get("criteria", []):
            cname = f"{gate_title} — {criterion.get('name', '')}"
            if cname.lower() not in existing_titles:
                signals = criterion.get("checklist_signals", [])
                evidence = criterion.get("evidence_required", [])
                content = ""
                if signals:
                    content += "**Required signals:**\n" + "\n".join(f"- {s}" for s in signals)
                if evidence:
                    content += "\n\n**Evidence needed:**\n" + "\n".join(f"- {e}" for e in evidence)
                cur = db.execute(
                    "INSERT INTO sections (project_id, title, content, order_index, source) VALUES (?,?,?,?,?)",
                    (pid, cname, content.strip(), order, "auto"),
                )
                created.append(row(db.execute("SELECT * FROM sections WHERE id=?", (cur.lastrowid,)).fetchone()))
                existing_titles.add(cname.lower())
                order += 10

    db.commit()
    db.close()
    return {"sections": created, "count": len(created)}


@router.patch("/projects/{pid}/sections/reorder")
def reorder_sections(pid: int, order: list[ReorderItem], user: dict = Depends(get_current_user)):
    db = get_db()
    for item in order:
        db.execute("UPDATE sections SET order_index=? WHERE id=? AND project_id=?",
                   (item.order_index, item.section_id, pid))
    db.commit()
    secs = rows(db.execute("SELECT * FROM sections WHERE project_id=? ORDER BY order_index", (pid,)).fetchall())
    db.close()
    return secs
