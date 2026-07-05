"""FastAPI backend for the Discovery Lens Ask view.

Exposes the guardrailed RAG (app/rag_core.py) over HTTP so the Next.js UI can answer
ANY user question — not just the 6 preloaded ones — with citations and scope guardrails.

Run locally:
    pip install fastapi uvicorn
    uvicorn api.server:app --reload --port 8000

The Next.js /api/ask route proxies to this (BACKEND_URL, default http://localhost:8000).
"""

from __future__ import annotations

import sys
from pathlib import Path

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from rag_core import ask  # noqa: E402

app = FastAPI(title="Discovery Lens RAG")

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


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/ask")
def ask_endpoint(req: AskRequest) -> dict:
    return ask(req.question, k=req.k, source=req.source, segment=req.segment)
