import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.database import get_db, row, rows
from backend.deps import get_current_user

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def _save_file(project_id: int, kind: str, f: UploadFile) -> str:
    dest = UPLOAD_DIR / kind / f"{project_id}_{kind}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(await f.read())
    return str(dest)


def _project_out(p: dict, db) -> dict:
    member_count = db.execute("SELECT COUNT(*) FROM project_members WHERE project_id=?", (p["id"],)).fetchone()[0]
    section_count = db.execute("SELECT COUNT(*) FROM sections WHERE project_id=?", (p["id"],)).fetchone()[0]
    latest = db.execute(
        "SELECT id FROM analysis_results WHERE project_id=? ORDER BY created_at DESC LIMIT 1", (p["id"],)
    ).fetchone()
    members = rows(db.execute(
        "SELECT u.id, u.email, u.full_name, pm.role FROM project_members pm JOIN users u ON u.id=pm.user_id WHERE pm.project_id=?",
        (p["id"],),
    ).fetchall())
    return {**p, "member_count": member_count, "section_count": section_count,
            "latest_analysis_id": latest[0] if latest else None, "members": members,
            "parsed_rfp_json": None}


@router.get("")
def list_projects(user: dict = Depends(get_current_user)):
    db = get_db()
    ps = rows(db.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall())
    out = [_project_out(p, db) for p in ps]
    db.close()
    return out


@router.post("", status_code=201)
async def create_project(
    title: str = Form(...),
    issuer: str = Form(""),
    rfp_id: str = Form(""),
    deadline: str = Form(""),
    status: str = Form("draft"),
    rfp_pdf: Optional[UploadFile] = File(None),
    response_pdf: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    cur = db.execute(
        "INSERT INTO projects (owner_id, title, rfp_id, issuer, status, deadline) VALUES (?,?,?,?,?,?)",
        (user["id"], title.strip(), rfp_id.strip(), issuer.strip(), status, deadline),
    )
    pid = cur.lastrowid
    db.execute("INSERT INTO project_members (project_id, user_id, role) VALUES (?,?,?)", (pid, user["id"], "admin"))

    rfp_fn, resp_fn = "", ""
    if rfp_pdf and rfp_pdf.filename:
        await _save_file(pid, "rfp", rfp_pdf)
        rfp_fn = rfp_pdf.filename
    if response_pdf and response_pdf.filename:
        await _save_file(pid, "response", response_pdf)
        resp_fn = response_pdf.filename

    db.execute("UPDATE projects SET rfp_filename=?, response_filename=? WHERE id=?", (rfp_fn, resp_fn, pid))
    db.commit()
    p = row(db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
    out = _project_out(p, db)
    db.close()
    return out


@router.get("/{pid}")
def get_project(pid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    p = row(db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
    if not p:
        raise HTTPException(404, "Project not found")
    secs = rows(db.execute("SELECT * FROM sections WHERE project_id=? ORDER BY order_index", (pid,)).fetchall())
    out = {**_project_out(p, db), "sections": secs}
    db.close()
    return out


@router.patch("/{pid}")
async def update_project(
    pid: int,
    title: Optional[str] = Form(None),
    issuer: Optional[str] = Form(None),
    rfp_id: Optional[str] = Form(None),
    deadline: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    rfp_pdf: Optional[UploadFile] = File(None),
    response_pdf: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    p = row(db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
    if not p:
        raise HTTPException(404, "Project not found")

    updates = {k: v for k, v in {"title": title, "issuer": issuer, "rfp_id": rfp_id,
                                   "deadline": deadline, "status": status}.items() if v is not None}
    if rfp_pdf and rfp_pdf.filename:
        await _save_file(pid, "rfp", rfp_pdf)
        updates["rfp_filename"] = rfp_pdf.filename
    if response_pdf and response_pdf.filename:
        await _save_file(pid, "response", response_pdf)
        updates["response_filename"] = response_pdf.filename

    if updates:
        sets = ", ".join(f"{k}=?" for k in updates)
        db.execute(f"UPDATE projects SET {sets}, updated_at=datetime('now') WHERE id=?",
                   list(updates.values()) + [pid])
        db.commit()

    p = row(db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
    out = _project_out(p, db)
    db.close()
    return out


@router.delete("/{pid}", status_code=204)
def delete_project(pid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    p = row(db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
    if not p:
        raise HTTPException(404, "Project not found")
    for kind in ("rfp", "response"):
        fp = UPLOAD_DIR / kind / f"{pid}_{kind}.pdf"
        if fp.exists():
            fp.unlink()
    db.execute("DELETE FROM projects WHERE id=?", (pid,))
    db.commit()
    db.close()


class MemberAdd(BaseModel):
    email: str
    role: str = "editor"


@router.post("/{pid}/members", status_code=201)
def add_member(pid: int, body: MemberAdd, user: dict = Depends(get_current_user)):
    db = get_db()
    target = row(db.execute("SELECT id FROM users WHERE email=?", (body.email.lower(),)).fetchone())
    if not target:
        raise HTTPException(404, "User not found")
    try:
        db.execute("INSERT INTO project_members (project_id, user_id, role) VALUES (?,?,?)",
                   (pid, target["id"], body.role))
        db.commit()
    except Exception:
        raise HTTPException(409, "Already a member")
    db.close()
    return {"project_id": pid, "user_id": target["id"], "role": body.role}


@router.delete("/{pid}/members/{uid}", status_code=204)
def remove_member(pid: int, uid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("DELETE FROM project_members WHERE project_id=? AND user_id=?", (pid, uid))
    db.commit()
    db.close()
