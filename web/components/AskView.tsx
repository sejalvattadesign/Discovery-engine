"use client";

import { useState } from "react";
import { BRIEF_QUESTIONS, PRELOADED_QA, QAEntry } from "@/lib/data";

function Stars({ n }: { n: number }) {
  const r = Math.max(0, Math.min(5, Math.round(n || 0))); // clamp to 0–5 (guards -1 sentinel)
  if (r < 1) return null;
  return (
    <span style={{ color: "#F59E0B", fontSize: "0.82rem", letterSpacing: 1 }}>
      {"★".repeat(r)}{"☆".repeat(5 - r)}
    </span>
  );
}

function SourceCard({ card }: { card: QAEntry["sources"][0] }) {
  return (
    <div
      style={{
        display: "flex",
        gap: 14,
        padding: "11px 0",
        borderBottom: "1px solid #282828",
        alignItems: "flex-start",
      }}
    >
      <div
        style={{
          background: "#1DB954",
          color: "#000",
          borderRadius: "50%",
          minWidth: 24,
          height: 24,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 700,
          fontSize: "0.78rem",
          marginTop: 2,
          flexShrink: 0,
        }}
      >
        {card.n}
      </div>
      <div style={{ flex: 1 }}>
        <div
          style={{
            color: "#fff",
            fontStyle: "italic",
            fontSize: "0.87rem",
            lineHeight: 1.45,
            marginBottom: 7,
          }}
        >
          &quot;{card.snippet}&quot;
        </div>
        <div style={{ display: "flex", gap: 7, flexWrap: "wrap", alignItems: "center" }}>
          <span
            style={{
              background: card.sourceColor + "33",
              color: card.sourceColor,
              borderRadius: 4,
              padding: "2px 8px",
              fontSize: "0.68rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            {card.source}
          </span>
          {card.year && (
            <span style={{ color: "#666", fontSize: "0.78rem" }}>{card.year}</span>
          )}
          <Stars n={card.stars} />
          {card.segment && (
            <span
              style={{
                background: "#282828",
                color: "#B3B3B3",
                borderRadius: 4,
                padding: "2px 8px",
                fontSize: "0.68rem",
              }}
            >
              {card.segment}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function AnswerBlock({ entry }: { entry: QAEntry }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 14 }}>
      {/* question label */}
      <div
        style={{
          background: "#181818",
          border: "1px solid #282828",
          borderRadius: 12,
          padding: "12px 18px",
        }}
      >
        <div
          style={{
            color: "#1DB954",
            fontSize: "0.68rem",
            fontWeight: 700,
            letterSpacing: "0.09em",
            marginBottom: 4,
          }}
        >
          QUESTION
        </div>
        <div style={{ color: "#fff", fontSize: "0.98rem", fontWeight: 600 }}>
          {entry.question}
        </div>
      </div>

      {/* answer */}
      <div
        style={{
          background: "#181818",
          border: "1px solid #282828",
          borderRadius: 12,
          padding: "18px 22px",
        }}
      >
        <p style={{ color: "#fff", fontSize: "0.9rem", lineHeight: 1.65, margin: "0 0 12px" }}>
          {entry.answer}
        </p>
        <div
          style={{
            background: "#0d2016",
            border: "1px solid #1DB954",
            borderRadius: 8,
            padding: "12px 16px",
          }}
        >
          <div
            style={{
              color: "#1DB954",
              fontSize: "0.68rem",
              fontWeight: 700,
              letterSpacing: "0.09em",
              marginBottom: 4,
            }}
          >
            TAKEAWAY
          </div>
          <div style={{ color: "#fff", fontWeight: 600, fontSize: "0.93rem" }}>
            {entry.takeaway}
          </div>
        </div>
      </div>

      {/* source cards */}
      <div
        style={{
          background: "#181818",
          border: "1px solid #282828",
          borderRadius: 12,
          padding: "16px 20px",
        }}
      >
        <div style={{ fontWeight: 700, color: "#fff", marginBottom: 4 }}>Sources</div>
        <div style={{ color: "#B3B3B3", fontSize: "0.8rem", marginBottom: 12 }}>
          {entry.sources.length} cited reviews
        </div>
        {entry.sources.map((src) => (
          <SourceCard key={src.n} card={src} />
        ))}
      </div>
    </div>
  );
}

const SOURCE_META: Record<string, { label: string; color: string }> = {
  play_store: { label: "Play Store", color: "#1DB954" },
  app_store: { label: "App Store", color: "#4A90D9" },
  forum: { label: "Community Forum", color: "#9B59B6" },
  reddit: { label: "Reddit", color: "#FF4500" },
};

interface RawSource {
  n: number;
  snippet: string;
  source: string;
  segment: string;
  date: string;
  rating: number | null;
}

function mapSources(raw: RawSource[]): QAEntry["sources"] {
  return (raw || []).map((s) => {
    const meta = SOURCE_META[s.source] || { label: s.source || "Source", color: "#888" };
    const date = String(s.date || "");
    // ratings are 1–5; reddit/forum have none (Chroma stores -1) → no stars
    const rn = Number(s.rating);
    const stars = Number.isFinite(rn) && rn >= 1 && rn <= 5 ? Math.round(rn) : 0;
    return {
      n: s.n,
      snippet: s.snippet || "",
      source: meta.label,
      sourceColor: meta.color,
      year: date.length >= 4 ? date.slice(0, 4) : "",
      stars,
      segment: s.segment || "",
    };
  });
}

export default function AskView() {
  const [history, setHistory] = useState<QAEntry[]>([]);
  const [inputVal, setInputVal] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleQuestion(q: string) {
    // The 6 chips have vetted, instant answers (work even if backend is down).
    const preloaded = PRELOADED_QA.find((p) => p.question === q);
    if (preloaded) {
      setHistory((h) => (h[0]?.question === q ? h : [preloaded, ...h]));
      setInputVal("");
      return;
    }

    // Everything else → live guardrailed RAG backend.
    setInputVal("");
    setLoading(true);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, k: 5 }),
      });
      const data = await res.json();
      const entry: QAEntry = res.ok && !data.error
        ? {
            question: q,
            answer: data.answer || "",
            takeaway: data.takeaway || "",
            sources: mapSources(data.sources),
          }
        : {
            question: q,
            answer:
              "The answer engine isn't reachable right now. Start the backend (uvicorn api.server:app --port 8000) or try a suggested question above.",
            takeaway: "",
            sources: [],
          };
      setHistory((h) => [entry, ...h]);
    } catch {
      setHistory((h) => [
        {
          question: q,
          answer: "Couldn't reach the answer engine. Please try again.",
          takeaway: "",
          sources: [],
        },
        ...h,
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* header + chips + filters */}
      <div
        style={{
          background: "#181818",
          border: "1px solid #282828",
          borderRadius: 16,
          padding: "20px 24px 18px",
        }}
      >
        {/* header */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <div
            style={{
              background: "#1DB954",
              borderRadius: 8,
              minWidth: 34,
              height: 34,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "1.1rem",
            }}
          >
            💬
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: "1.05rem", color: "#fff" }}>
              Ask the reviews
            </div>
            <div style={{ fontSize: "0.81rem", color: "#B3B3B3" }}>
              Every answer is grounded in real user reviews, with citations.
            </div>
          </div>
        </div>

        <div style={{ fontSize: "0.79rem", color: "#B3B3B3", marginBottom: 10 }}>
          Try a suggested question:
        </div>

        {/* chips grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 8,
            marginBottom: 16,
          }}
        >
          {BRIEF_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => handleQuestion(q)}
              style={{
                background: "transparent",
                border: "1px solid #1DB954",
                color: "#1DB954",
                borderRadius: 20,
                padding: "8px 14px",
                fontSize: "0.82rem",
                cursor: "pointer",
                textAlign: "left",
                lineHeight: 1.35,
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "#1DB954";
                (e.currentTarget as HTMLButtonElement).style.color = "#000";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                (e.currentTarget as HTMLButtonElement).style.color = "#1DB954";
              }}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* chat input */}
      <div
        style={{
          display: "flex",
          gap: 8,
          marginTop: 12,
          background: "#181818",
          border: "1px solid #282828",
          borderRadius: 28,
          padding: "8px 8px 8px 20px",
          alignItems: "center",
        }}
      >
        <input
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && inputVal.trim()) handleQuestion(inputVal.trim());
          }}
          placeholder="Ask anything about discovery feedback…"
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "#fff",
            fontSize: "0.9rem",
          }}
        />
        <button
          onClick={() => inputVal.trim() && handleQuestion(inputVal.trim())}
          style={{
            background: "#1DB954",
            border: "none",
            borderRadius: "50%",
            width: 36,
            height: 36,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            color: "#000",
            fontSize: "1rem",
            flexShrink: 0,
          }}
        >
          ➤
        </button>
      </div>

      {/* loading indicator */}
      {loading && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "#181818",
            border: "1px solid #282828",
            borderRadius: 12,
            padding: "16px 20px",
            marginTop: 14,
            color: "#B3B3B3",
            fontSize: "0.9rem",
          }}
        >
          <span
            style={{
              width: 14,
              height: 14,
              border: "2px solid #1DB954",
              borderTopColor: "transparent",
              borderRadius: "50%",
              display: "inline-block",
              animation: "spin 0.7s linear infinite",
            }}
          />
          Retrieving reviews and composing a cited answer…
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* conversation */}
      {history.map((entry, i) => (
        <AnswerBlock key={i} entry={entry} />
      ))}

      {/* empty state */}
      {history.length === 0 && !loading && (
        <div
          style={{
            textAlign: "center",
            padding: "56px 20px",
            color: "#444",
          }}
        >
          <div style={{ fontSize: "2.5rem", marginBottom: 10 }}>🎵</div>
          <div style={{ fontSize: "0.95rem" }}>
            Click a question chip above or type your own.
          </div>
        </div>
      )}

      {/* clear */}
      {history.length > 0 && (
        <button
          onClick={() => setHistory([])}
          style={{
            marginTop: 16,
            background: "transparent",
            border: "1px solid #282828",
            color: "#B3B3B3",
            borderRadius: 8,
            padding: "8px 20px",
            cursor: "pointer",
            fontSize: "0.83rem",
            alignSelf: "flex-start",
          }}
        >
          Clear chat
        </button>
      )}
    </div>
  );
}
