from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from backend.database import get_db, row
from backend.auth_utils import hash_password, verify_password, create_token
from backend.deps import get_current_user
from fastapi import Depends

router = APIRouter()


class RegisterIn(BaseModel):
    email: str
    password: str
    full_name: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/register", status_code=201)
def register(body: RegisterIn):
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email=?", (body.email.lower(),)).fetchone()
    if existing:
        raise HTTPException(409, "Email already registered")
    db.execute(
        "INSERT INTO users (email, full_name, password_hash) VALUES (?,?,?)",
        (body.email.lower(), body.full_name.strip(), hash_password(body.password)),
    )
    db.commit()
    u = row(db.execute("SELECT id, email, full_name, created_at FROM users WHERE email=?", (body.email.lower(),)).fetchone())
    db.close()
    return u


@router.post("/login")
def login(body: LoginIn):
    db = get_db()
    u = row(db.execute("SELECT * FROM users WHERE email=?", (body.email.lower(),)).fetchone())
    db.close()
    if not u or not verify_password(body.password, u["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(u["id"], u["email"], u.get("token_version", 0))
    return {"access_token": token, "token_type": "bearer", "expires_in": 86400,
            "user": {"id": u["id"], "email": u["email"], "full_name": u["full_name"]}}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "full_name": user["full_name"]}


@router.post("/logout", status_code=204)
def logout(user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute(
        "UPDATE users SET token_version=token_version+1, updated_at=datetime('now') WHERE id=?",
        (user["id"],),
    )
    db.commit()
    db.close()
