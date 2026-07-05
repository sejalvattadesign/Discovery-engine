import { NextRequest, NextResponse } from "next/server";

// Proxies to the Python FastAPI RAG backend (guardrails live there).
// Set BACKEND_URL in the environment for deployment; defaults to local dev.
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch(`${BACKEND_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      // 60s — embeddings + LLM can take a moment
      signal: AbortSignal.timeout(60000),
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: `backend ${res.status}` },
        { status: 502 }
      );
    }
    return NextResponse.json(await res.json());
  } catch (err) {
    return NextResponse.json(
      {
        error: "backend_unreachable",
        detail: String(err),
      },
      { status: 503 }
    );
  }
}
