"use client";

import { useEffect } from "react";
import { THEME_DETAILS, ThemeDetail } from "@/lib/theme_details";

const SOURCE_COLOR: Record<string, string> = {
  "Play Store": "#1DB954",
  "App Store": "#4A90D9",
  "Community Forum": "#9B59B6",
  Reddit: "#FF4500",
};

function Stars({ n }: { n: number | null }) {
  const r = Math.max(0, Math.min(5, Math.round(Number(n) || 0))); // clamp 0–5 (guards -1 sentinel)
  if (r < 1) return null;
  return (
    <span style={{ color: "#F59E0B", fontSize: "0.8rem", letterSpacing: 1 }}>
      {"★".repeat(r)}{"☆".repeat(5 - r)}
    </span>
  );
}

export default function ThemeDrawer({
  theme,
  onClose,
}: {
  theme: string | null;
  onClose: () => void;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!theme) return null;
  const d: ThemeDetail | undefined = THEME_DETAILS[theme];
  if (!d) return null;

  return (
    <>
      {/* backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.6)",
          zIndex: 100,
        }}
      />
      {/* drawer */}
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(560px, 92vw)",
          background: "#181818",
          borderLeft: "1px solid #282828",
          zIndex: 101,
          overflowY: "auto",
          padding: "24px 26px 40px",
          boxShadow: "-8px 0 24px rgba(0,0,0,0.4)",
        }}
      >
        {/* header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ color: "#1DB954", fontSize: "0.68rem", fontWeight: 700, letterSpacing: ".09em" }}>
              THEME
            </div>
            <h2 style={{ margin: "2px 0 0", fontSize: "1.4rem", fontWeight: 700 }}>{d.label}</h2>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "#282828",
              border: "none",
              color: "#B3B3B3",
              borderRadius: 8,
              width: 32,
              height: 32,
              cursor: "pointer",
              fontSize: "1.1rem",
            }}
          >
            ✕
          </button>
        </div>

        <p style={{ color: "#B3B3B3", fontSize: "0.9rem", lineHeight: 1.55, marginTop: 10 }}>
          {d.definition}
        </p>

        {/* stat chips */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "14px 0 8px" }}>
          <span style={chip}>
            <b style={{ color: "#1DB954" }}>{d.count}</b> reviews
          </span>
          <span style={chip}>
            <b style={{ color: d.negPct >= 80 ? "#1DB954" : "#F59E0B" }}>{d.negPct}%</b> negative
          </span>
          {d.sources.map((s) => (
            <span key={s.source} style={chip}>
              <b style={{ color: SOURCE_COLOR[s.source] || "#fff" }}>{s.n}</b> {s.source}
            </span>
          ))}
        </div>

        {/* sub-problem synthesis */}
        {d.summary && (
          <div style={{ marginTop: 18 }}>
            <div style={sectionTitle}>The sub-problems inside this theme</div>
            <div
              style={{
                background: "#121212",
                border: "1px solid #282828",
                borderRadius: 10,
                padding: "14px 16px",
                color: "#D8D8D8",
                fontSize: "0.88rem",
                lineHeight: 1.6,
                whiteSpace: "pre-wrap",
              }}
            >
              {d.summary}
            </div>
            <div style={{ color: "#555", fontSize: "0.72rem", marginTop: 6 }}>
              AI-synthesized from the reviews below — [n] refers to the quotes.
            </div>
          </div>
        )}

        {/* representative quotes */}
        <div style={{ marginTop: 20 }}>
          <div style={sectionTitle}>Representative quotes (real reviews)</div>
          {d.quotes.map((q) => (
            <div
              key={q.n}
              style={{
                display: "flex",
                gap: 12,
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
                  minWidth: 22,
                  height: 22,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 700,
                  fontSize: "0.72rem",
                  marginTop: 2,
                }}
              >
                {q.n}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: "#fff", fontStyle: "italic", fontSize: "0.86rem", lineHeight: 1.45, marginBottom: 6 }}>
                  &quot;{q.snippet}&quot;
                </div>
                <div style={{ display: "flex", gap: 7, alignItems: "center", flexWrap: "wrap" }}>
                  <span
                    style={{
                      background: (SOURCE_COLOR[q.source] || "#888") + "33",
                      color: SOURCE_COLOR[q.source] || "#aaa",
                      borderRadius: 4,
                      padding: "2px 8px",
                      fontSize: "0.66rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                    }}
                  >
                    {q.source}
                  </span>
                  {q.date && <span style={{ color: "#666", fontSize: "0.76rem" }}>{q.date.slice(0, 4)}</span>}
                  <Stars n={q.rating} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

const chip: React.CSSProperties = {
  background: "#282828",
  borderRadius: 6,
  padding: "4px 10px",
  fontSize: "0.76rem",
  color: "#B3B3B3",
};
const sectionTitle: React.CSSProperties = {
  fontSize: "0.8rem",
  fontWeight: 700,
  color: "#fff",
  marginBottom: 10,
  textTransform: "uppercase",
  letterSpacing: ".05em",
};
