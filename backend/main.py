import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))
logging.getLogger("bidintel").addHandler(_handler)
logging.getLogger("bidintel").setLevel(logging.INFO)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import auth, projects, sections, analysis, ask, lookup, safety_dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="BidIntel AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/api/auth",     tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(sections.router, prefix="/api",          tags=["sections"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(ask.router,      prefix="/api/ask",      tags=["ask"])
app.include_router(lookup.router,   prefix="/api/lookup",   tags=["lookup"])
app.include_router(safety_dashboard.router, prefix="/api/safety", tags=["safety"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
