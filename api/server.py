"""FastAPI backend for the Discovery Lens Ask view.

Exposes the guardrailed RAG (app/rag_core.py) over HTTP so the Next.js UI can answer
ANY user question — not just the 6 preloaded ones — with citations and scope guardrails.

Run locally:
    pip install fastapi uvicorn
    uvicorn api.server:app --reload --port 8000

The Next.js /api/ask route proxies to this (BACKEND_URL, default http://localhost:8000).
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from api.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("detour.api")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from rag_core import CHROMA_DIR, COLLECTION, _preview, ask, get_collection  # noqa: E402


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Discovery Lens RAG backend chroma_dir=%s", CHROMA_DIR)
    if not CHROMA_DIR.is_dir():
        logger.error("Chroma directory missing: %s", CHROMA_DIR)
    else:
        try:
            collection = get_collection()
            logger.info(
                "Chroma ready collection=%s doc_count=%d",
                COLLECTION,
                collection.count(),
            )
        except Exception:
            logger.exception("Failed to load Chroma collection")
    yield
    logger.info("Shutting down Discovery Lens RAG backend")


app = FastAPI(title="Discovery Lens RAG", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to your deployed UI origin in production
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    k: int = 5
    source: Optional[str] = None
    segment: Optional[str] = None


@app.get("/")
def root() -> dict:
    return {"status": "Discovery Lens RAG backend is running", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/ask")
def ask_endpoint(req: AskRequest) -> dict:
    logger.info(
        "POST /ask received q=%r k=%d source=%s segment=%s",
        _preview(req.question),
        req.k,
        req.source or "All",
        req.segment or "All",
    )
    t0 = time.perf_counter()
    result = ask(req.question, k=req.k, source=req.source, segment=req.segment)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "POST /ask done refused=%s error=%s cites=%d answer_len=%d takeaway=%s elapsed_ms=%.0f",
        result.get("refused"),
        result.get("error"),
        len(result.get("sources") or []),
        len(result.get("answer") or ""),
        bool(result.get("takeaway")),
        elapsed_ms,
    )
    return result
