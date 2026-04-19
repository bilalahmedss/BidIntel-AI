from fastapi import Header, HTTPException, Query
from backend.auth_utils import decode_token
from backend.database import get_db, row


def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(authorization.split(" ", 1)[1])
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    db = get_db()
    u = row(db.execute("SELECT * FROM users WHERE id=?", (int(payload["sub"]),)).fetchone())
    db.close()
    if not u:
        raise HTTPException(401, "User not found")
    return u


def get_current_user_ws(token: str = Query(...)) -> dict:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "Invalid token")
    db = get_db()
    u = row(db.execute("SELECT * FROM users WHERE id=?", (int(payload["sub"]),)).fetchone())
    db.close()
    if not u:
        raise HTTPException(401, "User not found")
    return u
