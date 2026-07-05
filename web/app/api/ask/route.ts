import { NextRequest, NextResponse } from "next/server";

// Proxies to the Python FastAPI RAG backend (guardrails live there).
// Set BACKEND_URL in the environment for deployment; defaults to local dev.
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export const maxDuration = 60;

function preview(text: unknown, max = 80): string {
  const s = String(text ?? "").replace(/\s+/g, " ").trim();
  return s.length <= max ? s : `${s.slice(0, max - 1)}…`;
}

function backendHost(): string {
  try {
    return new URL(BACKEND_URL).host;
  } catch {
    return "(invalid BACKEND_URL)";
  }
}

export async function POST(req: NextRequest) {
  const t0 = Date.now();

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch (err) {
    console.error("[ask] invalid json", {
      totalMs: Date.now() - t0,
      err: String(err),
    });
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  console.info("[ask] proxy start", {
    q: preview(body.question),
    k: body.k ?? 5,
    source: body.source ?? "All",
    segment: body.segment ?? "All",
    backend: backendHost(),
  });

  try {
    const fetchStart = Date.now();
    const res = await fetch(`${BACKEND_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      // 60s — embeddings + LLM can take a moment
      signal: AbortSignal.timeout(60000),
    });
    const fetchMs = Date.now() - fetchStart;

    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      console.warn("[ask] backend error", {
        status: res.status,
        fetchMs,
        totalMs: Date.now() - t0,
        backend: backendHost(),
        detail: preview(detail, 200),
      });
      return NextResponse.json(
        { error: `backend ${res.status}` },
        { status: 502 }
      );
    }

    const data = await res.json();
    console.info("[ask] proxy ok", {
      fetchMs,
      totalMs: Date.now() - t0,
      refused: Boolean(data.refused),
      error: data.error ?? null,
      cites: Array.isArray(data.sources) ? data.sources.length : 0,
      answerLen: typeof data.answer === "string" ? data.answer.length : 0,
    });
    return NextResponse.json(data);
  } catch (err) {
    const errStr = String(err);
    const timedOut =
      errStr.includes("TimeoutError") || errStr.includes("timed out");
    console.error("[ask] proxy failed", {
      totalMs: Date.now() - t0,
      backend: backendHost(),
      timedOut,
      err: errStr,
    });
    return NextResponse.json(
      {
        error: "backend_unreachable",
        detail: errStr,
      },
      { status: 503 }
    );
  }
}
