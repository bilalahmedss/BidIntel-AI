import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import auth, projects, sections, analysis, ask, lookup


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


@app.get("/api/health")
def health():
    return {"status": "ok"}
