import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", "86400"))
ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS)
    return f"pbkdf2:sha256:{ITERATIONS}${salt}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rest = stored.split(":", 1)
        algo_iters, salt, expected = rest.split("$")
        iters = int(algo_iters.split(":")[1])
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iters)
        return secrets.compare_digest(h.hex(), expected)
    except Exception:
        return False


def create_token(user_id: int, email: str, token_version: int = 0) -> str:
    exp = datetime.now(timezone.utc) + timedelta(seconds=EXPIRE_SECONDS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "ver": int(token_version), "exp": exp},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
